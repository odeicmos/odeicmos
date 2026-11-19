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
