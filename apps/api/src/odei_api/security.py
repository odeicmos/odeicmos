"""OIDC JWT verification and facility-scoped authorization primitives."""
import asyncio
import time
from dataclasses import dataclass
from datetime import datetime, timezone
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
    """RS256 verifier with bounded JWKS cache lifetime and serialized refresh."""

    def __init__(self) -> None:
        self._jwks: dict[str, Any] | None = None
        self._jwks_loaded_at = 0.0
        self._refresh_lock = asyncio.Lock()

    async def _load_jwks(self, url: str, *, force_refresh: bool = False) -> dict[str, Any]:
        settings = get_settings()
        ttl = max(30, min(settings.oidc_jwks_cache_seconds, 3600))
        fresh = self._jwks is not None and (time.monotonic() - self._jwks_loaded_at) < ttl
        if force_refresh or not fresh:
            async with self._refresh_lock:
                fresh = self._jwks is not None and (time.monotonic() - self._jwks_loaded_at) < ttl
                if force_refresh or not fresh:
                    try:
                        async with httpx.AsyncClient(timeout=5.0) as client:
                            response = await client.get(url)
                            response.raise_for_status()
                            payload = response.json()
                        if not isinstance(payload, dict) or not isinstance(payload.get("keys"), list):
                            raise ValueError("Invalid JWKS document")
                        valid_keys = [
                            key for key in payload["keys"]
                            if isinstance(key, dict)
                            and key.get("kty") == "RSA"
                            and isinstance(key.get("kid"), str)
                            and key.get("kid")
                            and key.get("use", "sig") == "sig"
                            and key.get("alg", "RS256") in (None, "RS256")
                        ]
                        if not valid_keys:
                            raise ValueError("JWKS contains no usable RS256 signing keys")
                        self._jwks = {"keys": valid_keys}
                        self._jwks_loaded_at = time.monotonic()
                    except (httpx.HTTPError, ValueError) as exc:
                        self._jwks = None
                        self._jwks_loaded_at = 0.0
                        raise HTTPException(
                            status_code=503,
                            detail="Identity verification service unavailable",
                        ) from exc
        return self._jwks or {"keys": []}

    async def check_jwks(self) -> None:
        settings = get_settings()
        if not all((settings.oidc_issuer, settings.oidc_audience, settings.oidc_jwks_url)):
            raise HTTPException(status_code=503, detail="Identity provider is not configured")
        await self._load_jwks(settings.oidc_jwks_url or "")

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
            key_data = next((key for key in jwks["keys"] if key.get("kid") == kid), None)
            if not key_data:
                jwks = await self._load_jwks(settings.oidc_jwks_url or "", force_refresh=True)
                key_data = next((key for key in jwks["keys"] if key.get("kid") == kid), None)
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


async def check_identity_provider_ready() -> None:
    await _verifier.check_jwks()


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
    """Return an active role only when facility and assignment are currently effective."""
    db = getattr(request.app.state, "mongo_database", None)
    if db is None:
        raise HTTPException(status_code=503, detail="Authorization store unavailable")
    now = datetime.now(timezone.utc)
    facility = await db.facilities.find_one({
        "tenant_id": tenant_id, "facility_id": facility_id, "status": "active",
    })
    if facility is None:
        raise HTTPException(status_code=403, detail="Facility is not active or accessible")
    assignment = await db.role_assignments.find_one({
        "tenant_id": tenant_id,
        "facility_id": facility_id,
        "user_issuer": principal.issuer,
        "user_id": principal.subject,
        "status": "active",
        "role": {"$in": list(allowed_roles)},
        "$and": [
            {"$or": [{"effective_from": None}, {"effective_from": {"$exists": False}}, {"effective_from": {"$lte": now}}]},
            {"$or": [{"effective_until": None}, {"effective_until": {"$exists": False}}, {"effective_until": {"$gt": now}}]},
        ],
    })
    if assignment is None:
        raise HTTPException(status_code=403, detail="No currently effective role for this facility")
    return str(assignment["role"])
