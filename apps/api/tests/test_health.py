from fastapi.testclient import TestClient

from odei_api.main import create_app


def test_liveness_reports_process_health() -> None:
    client = TestClient(create_app())
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "alive"}


def test_readiness_does_not_claim_unconfigured_dependencies_are_ready() -> None:
    client = TestClient(create_app())
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {
        "status": "not_ready",
        "reason": "dependencies_not_configured",
    }
