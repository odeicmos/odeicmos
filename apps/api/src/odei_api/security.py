"""OIDC JWT verification and facility-scoped authorization primitives."""
from dataclasses import dataclass
from typing import Any, Iterable
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import httpx
import jwt
from jwt.algorithms import RSAAlgorithm
from odei_api.config import get_settings

_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class Principal:
    subject: str
    issuer: str
    claims: dict[str, Any]


class OidcVerifier:
    def __init__(self) -> None:
        self._jwks: dict[str, Any] | None = None

    async def _load_jwks(self, url: str) -> dict[str, Any]:
        if self._jwks is None:
            try:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    response = await client.get(url)
                    response.raise_for_status()
                    payload = response.json()
                if not isinstance(payload, dict) or not isinstance(payload.get("keys"), list):
                    raise ValueError("Invalid JWKS document")
                self._jwks = payload
            except (httpx.HTTPError, ValueError) as exc:
                raise HTTPException(status_code=503, detail="Identity verification service unavailable") from exc
        return self._jwks

    async def verify(self, token: str) -> Principal:
        settings = get_settings()
        if not all((settings.oidc_issuer, settings.oidc_audience, settings.oidc_jwks_url)):
            raise HTTPException(status_code=503, detail="Identity provider is not configured")
        try:
            header = jwt.get_unverified_header(token)
            algorithm = header.get("alg")
            if algorithm not in settings.oidc_allowed_algorithms or algorithm != "RS256":
                raise ValueError("Disallowed signing algorithm")
            kid = header.get("kid")
            if not isinstance(kid, str) or not kid:
                raise ValueError("Missing signing key identifier")
            jwks = await self._load_jwks(settings.oidc_jwks_url or "")
            key_data = next((key for key in jwks["keys"] if key.get("kid") == kid and key.get("kty") == "RSA"), None)
            if not key_data:
                self._jwks = None
                jwks = await self._load_jwks(settings.oidc_jwks_url or "")
                key_data = next((key for key in jwks["keys"] if key.get("kid") == kid and key.get("kty") == "RSA"), None)
            if not key_data:
                raise ValueError("Signing key not found")
            public_key = RSAAlgorithm.from_jwk(key_data)
            claims = jwt.decode(
                token, public_key, algorithms=["RS256"],
                audience=settings.oidc_audience, issuer=settings.oidc_issuer,
                options={"require": ["exp", "iat", "iss", "aud", "sub"]}, leeway=30,
            )
            if not isinstance(claims.get("sub"), str) or not claims["sub"]:
                raise ValueError("Invalid subject")
            return Principal(subject=claims["sub"], issuer=claims["iss"], claims=claims)
        except HTTPException:
            raise
        except (jwt.PyJWTError, ValueError, TypeError, KeyError) as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token") from exc


_verifier = OidcVerifier()


async def require_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> Principal:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Bearer authentication required")
    return await _verifier.verify(credentials.credentials)


def require_platform_admin(principal: Principal = Depends(require_principal)) -> Principal:
    roles = principal.claims.get("odei_platform_roles", [])
    if not isinstance(roles, list) or not all(isinstance(role, str) for role in roles):
        raise HTTPException(status_code=403, detail="Platform administrator permission required")
    if "platform_admin" not in roles:
        raise HTTPException(status_code=403, detail="Platform administrator permission required")
    return principal


async def authorize_facility_access(
    request: Request,
    principal: Principal,
    tenant_id: str,
    facility_id: str,
    allowed_roles: Iterable[str],
) -> str:
    """Return the matched role or fail closed for the requested facility scope."""
    db = getattr(request.app.state, "mongo_database", None)
    if db is None:
        raise HTTPException(status_code=503, detail="Authorization store unavailable")
    assignment = await db.role_assignments.find_one({
        "tenant_id": tenant_id,
        "facility_id": facility_id,
        "user_issuer": principal.issuer,
        "user_id": principal.subject,
        "status": "active",
        "role": {"$in": list(allowed_roles)},
    })
    if assignment is None:
        raise HTTPException(status_code=403, detail="No permitted role for this facility")
    return str(assignment["role"])
