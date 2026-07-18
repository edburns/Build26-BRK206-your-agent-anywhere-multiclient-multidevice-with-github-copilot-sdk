from fastapi.testclient import TestClient

from python_agent_orchestrator.agent import Agent
from python_agent_orchestrator import main
from python_agent_orchestrator.phase import Phase


def test_app_importable() -> None:
    assert main.app is not None


def _patch_fake_copilot_client(monkeypatch):
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
    return mock_copilot_client


def test_health_endpoint(monkeypatch) -> None:
    mock_copilot_client = _patch_fake_copilot_client(monkeypatch)

    with TestClient(main.app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert mock_copilot_client.started is True
    assert mock_copilot_client.stopped is True
    assert main.app.state.app_state.copilot_client is mock_copilot_client
    assert isinstance(main.app.state.app_state.agents, dict)


def test_index_renders_pipeline_page(monkeypatch) -> None:
    _patch_fake_copilot_client(monkeypatch)

    with TestClient(main.app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert "Real Estate Agent Pipeline" in response.text
    assert "GitHub Copilot SDK for Python -- BRK206 Demo" in response.text
    assert 'hx-get="/partials/pipeline"' in response.text
    assert 'x-data="pipelinePage(' in response.text


def test_pipeline_partial_renders_existing_agent_state(monkeypatch) -> None:
    _patch_fake_copilot_client(monkeypatch)

    with TestClient(main.app) as client:
        app_state = main.app.state.app_state
        app_state.agents["q-1"] = Agent(
            query_id="q-1",
            query_text="Need a waterfront condo",
            current_phase=Phase.SEARCHING,
            current_intent="Looking for matches",
        )
        app_state.agents["q-2"] = Agent(
            query_id="q-2",
            query_text="Write the follow-up report",
            current_phase=Phase.DONE,
            current_intent="Complete",
        )

        response = client.get("/partials/pipeline")

    assert response.status_code == 200
    assert "Need a waterfront condo" in response.text
    assert "Write the follow-up report" in response.text
    assert "No Matches" in response.text
    assert ">1<" in response.text


def test_submit_query_stubs_queued_state_and_increments_ids(monkeypatch) -> None:
    _patch_fake_copilot_client(monkeypatch)

    with TestClient(main.app) as client:
        first = client.post("/api/submit-query")
        second = client.post("/api/submit-query", json={"query": "Lakefront villa"})

    assert first.status_code == 200
    assert first.json()["status"] == "queued"
    assert first.json()["queryId"] == "q-1"
    assert first.json()["phase"] == "Queued"
    assert second.status_code == 200
    assert second.json()["queryId"] == "q-2"
    assert second.json()["queryText"] == "Lakefront villa"
    assert main.app.state.app_state.agents["q-2"].current_phase == Phase.QUEUED
    assert second.json()["state"]["dashboard"]["processing"] == 2
