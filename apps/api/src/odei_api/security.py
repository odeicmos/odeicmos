"""OIDC JWT verification and fail-closed authorization primitives."""
from dataclasses import dataclass
from typing import Any
from fastapi import Depends, HTTPException, status
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
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(url)
                response.raise_for_status()
                self._jwks = response.json()
        return self._jwks

    async def verify(self, token: str) -> Principal:
        settings = get_settings()
        if not all((settings.oidc_issuer, settings.oidc_audience, settings.oidc_jwks_url)):
            raise HTTPException(status_code=503, detail="Identity provider is not configured")
        try:
            header = jwt.get_unverified_header(token)
            if header.get("alg") not in settings.oidc_allowed_algorithms:
                raise ValueError("Disallowed signing algorithm")
            kid = header.get("kid")
            jwks = await self._load_jwks(settings.oidc_jwks_url or "")
            key_data = next((key for key in jwks.get("keys", []) if key.get("kid") == kid), None)
            if not key_data:
                self._jwks = None
                jwks = await self._load_jwks(settings.oidc_jwks_url or "")
                key_data = next((key for key in jwks.get("keys", []) if key.get("kid") == kid), None)
            if not key_data:
                raise ValueError("Signing key not found")
            public_key = RSAAlgorithm.from_jwk(key_data)
            claims = jwt.decode(
                token,
                public_key,
                algorithms=list(settings.oidc_allowed_algorithms),
                audience=settings.oidc_audience,
                issuer=settings.oidc_issuer,
                options={"require": ["exp", "iat", "iss", "aud", "sub"]},
                leeway=30,
            )
            return Principal(subject=str(claims["sub"]), issuer=str(claims["iss"]), claims=claims)
        except HTTPException:
            raise
        except Exception as exc:
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
    if "platform_admin" not in roles:
        raise HTTPException(status_code=403, detail="Platform administrator permission required")
    return principal
