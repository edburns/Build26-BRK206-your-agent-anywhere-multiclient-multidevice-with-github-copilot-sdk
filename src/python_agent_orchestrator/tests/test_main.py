from python_agent_orchestrator.main import app
from fastapi.testclient import TestClient


def test_app_importable() -> None:
    assert app is not None


def test_health_endpoint() -> None:
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
