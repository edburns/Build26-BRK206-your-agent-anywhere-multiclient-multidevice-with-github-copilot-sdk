from python_agent_orchestrator.main import app


def test_app_importable() -> None:
    assert app is not None
