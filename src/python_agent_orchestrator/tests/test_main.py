from fastapi.testclient import TestClient

from python_agent_orchestrator import main


def test_app_importable() -> None:
    assert main.app is not None


def test_health_endpoint(monkeypatch) -> None:
    class FakeCopilotClient:
        def __init__(self):
            self.started = False
            self.stopped = False

        async def start(self) -> None:
            self.started = True

        async def stop(self) -> None:
            self.stopped = True

    mock_copilot_client = FakeCopilotClient()
    monkeypatch.setattr(main, "_create_copilot_client", lambda: mock_copilot_client)

    with TestClient(main.app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert mock_copilot_client.started is True
    assert mock_copilot_client.stopped is True
    assert main.app.state.app_state.copilot_client is mock_copilot_client
    assert isinstance(main.app.state.app_state.agents, dict)
