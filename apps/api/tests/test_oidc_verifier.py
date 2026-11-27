import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from odei_api import security


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeAsyncClient:
    calls = 0
    payload = {"keys": [{"kty": "RSA", "kid": "key-1", "use": "sig", "alg": "RS256"}]}

    def __init__(self, timeout):
        self.timeout = timeout

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url):
        type(self).calls += 1
        return FakeResponse(type(self).payload)


def configure_settings(monkeypatch, ttl=300):
    monkeypatch.setattr(
        security,
        "get_settings",
        lambda: SimpleNamespace(
            oidc_jwks_cache_seconds=ttl,
            oidc_issuer="https://issuer.example",
            oidc_audience="odei-api",
            oidc_jwks_url="https://issuer.example/.well-known/jwks.json",
            oidc_allowed_algorithms=("RS256",),
        ),
    )


def test_jwks_cache_is_bounded_and_refresh_is_explicit(monkeypatch):
    configure_settings(monkeypatch)
    FakeAsyncClient.calls = 0
    monkeypatch.setattr(security.httpx, "AsyncClient", FakeAsyncClient)
    verifier = security.OidcVerifier()

    async def scenario():
        first = await verifier._load_jwks("https://issuer.example/keys")
        second = await verifier._load_jwks("https://issuer.example/keys")
        refreshed = await verifier._load_jwks(
            "https://issuer.example/keys", force_refresh=True
        )
        return first, second, refreshed

    first, second, refreshed = asyncio.run(scenario())
    assert first == second == refreshed
    assert FakeAsyncClient.calls == 2


def test_jwks_rejects_documents_without_usable_signing_keys(monkeypatch):
    configure_settings(monkeypatch)
    FakeAsyncClient.calls = 0
    FakeAsyncClient.payload = {"keys": [{"kty": "EC", "kid": "wrong-key"}]}
    monkeypatch.setattr(security.httpx, "AsyncClient", FakeAsyncClient)
    verifier = security.OidcVerifier()

    with pytest.raises(HTTPException) as exc:
        asyncio.run(verifier._load_jwks("https://issuer.example/keys"))
    assert exc.value.status_code == 503
    FakeAsyncClient.payload = {"keys": [{"kty": "RSA", "kid": "key-1", "use": "sig", "alg": "RS256"}]}


def test_jwks_cache_setting_has_safe_bounds(monkeypatch):
    from odei_api.config import Settings

    with pytest.raises(Exception):
        Settings(oidc_jwks_cache_seconds=1)
    with pytest.raises(Exception):
        Settings(oidc_jwks_cache_seconds=3601)
