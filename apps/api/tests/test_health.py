import pytest
from fastapi.testclient import TestClient
from odei_api.main import create_app


def test_liveness_reports_process_health() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "alive"}


def test_readiness_fails_closed_without_mongodb_configuration() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json()["detail"]["status"] == "not_ready"


def test_control_plane_routes_reject_missing_identity() -> None:
    with TestClient(create_app()) as client:
        response = client.post("/api/v1/control-plane/organizations", json={})
    assert response.status_code in (401, 503)


@pytest.mark.parametrize(
    ("migration_record", "expected_status", "expected_reason"),
    [
        (None, 503, "schema_migrations_pending"),
        ({"_id": "2026.11.28.1", "status": "applied"}, 200, None),
    ],
)
def test_readiness_requires_applied_schema_migration(
    monkeypatch, migration_record, expected_status, expected_reason
) -> None:
    from unittest.mock import AsyncMock

    import odei_api.main as main
    from odei_api.config import get_settings

    class FakeCollection:
        async def find_one(self, query):
            assert query == {"_id": "2026.11.28.1", "status": "applied"}
            return migration_record

    class FakeDatabase:
        schema_migrations = FakeCollection()

        async def command(self, command):
            assert command == "ping"
            return {"ok": 1}

    class FakeAdmin:
        async def command(self, command):
            assert command == "ping"
            return {"ok": 1}

    class FakeMongoClient:
        admin = FakeAdmin()

        def __init__(self, *args, **kwargs):
            pass

        def __getitem__(self, name):
            assert name == "odei_clinic"
            return FakeDatabase()

        async def close(self):
            return None

    monkeypatch.setenv("ODEI_MONGODB_URI", "mongodb://localhost:27017/test")
    monkeypatch.setattr(main, "AsyncMongoClient", FakeMongoClient)
    monkeypatch.setattr(main, "check_identity_provider_ready", AsyncMock())
    get_settings.cache_clear()
    try:
        with TestClient(main.create_app()) as client:
            response = client.get("/health/ready")
        assert response.status_code == expected_status
        if expected_reason:
            assert response.json()["detail"]["reason"] == expected_reason
        else:
            assert response.json() == {
                "status": "ready",
                "dependencies": "mongodb,schema_migrations,oidc_jwks",
            }
    finally:
        get_settings.cache_clear()
