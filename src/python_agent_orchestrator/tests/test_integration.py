import asyncio
import os
from pathlib import Path

import pytest
from copilot import CopilotClient

from python_agent_orchestrator.agent import Agent
from python_agent_orchestrator.phase import Phase
from python_agent_orchestrator.property_database import create_engine_and_tables, seed_database

pytestmark = pytest.mark.integration

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "properties"


def _integration_enabled() -> bool:
    return os.getenv("RUN_COPILOT_INTEGRATION", "").lower() in {"1", "true", "yes", "on"}


async def _create_client_or_skip() -> CopilotClient:
    if not _integration_enabled():
        pytest.skip("Set RUN_COPILOT_INTEGRATION=1 to run integration tests")

    base_directory = os.getenv("COPILOT_BASE_DIRECTORY") or str(Path.home() / ".copilot")
    client = CopilotClient(mode="empty", base_directory=base_directory)
    try:
        await client.start()
    except Exception as exc:
        pytest.skip(f"Copilot runtime unavailable: {exc}")
    return client


@pytest.mark.asyncio
async def test_full_pipeline_reaches_done_and_logs_tools() -> None:
    engine = create_engine_and_tables()
    seed_database(engine, DATA_DIR)
    candidate_queries = [
        "Looking for a property in Toronto with at least 1 bedroom under 900000",
        "Please find 2 Toronto homes under 900000 with at least 1 bedroom",
        "Need a Toronto condo under 900000 with one or more bedrooms",
    ]

    client = await _create_client_or_skip()
    terminal_phases: list[Phase] = []
    done_agent: Agent | None = None
    try:
        for index, query_text in enumerate(candidate_queries, start=1):
            agent = Agent(
                query_id=f"q-int-1-{index}",
                query_text=query_text,
                db_engine=engine,
            )
            await agent.run(client)
            terminal_phases.append(agent.current_phase)
            if agent.current_phase == Phase.DONE:
                done_agent = agent
                break
    finally:
        await client.stop()

    assert done_agent is not None, f"Expected at least one DONE run, got {terminal_phases}"
    tool_starts = [event for event in done_agent.events if event["type"] == "tool_start"]
    assert tool_starts
    assert any(event["toolName"] == "search_properties" for event in tool_starts)
    assert done_agent.report_text


@pytest.mark.asyncio
async def test_two_concurrent_agents_complete_independently() -> None:
    engine = create_engine_and_tables()
    seed_database(engine, DATA_DIR)
    first = Agent(
        query_id="q-int-2a",
        query_text="Condo in Toronto with 2 bedrooms",
        db_engine=engine,
    )
    second = Agent(
        query_id="q-int-2b",
        query_text="Townhouse in Toronto with 4 bedrooms",
        db_engine=engine,
    )

    client = await _create_client_or_skip()
    try:
        await asyncio.gather(first.run(client), second.run(client))
    finally:
        await client.stop()

    assert first.current_phase in {Phase.DONE, Phase.NO_MATCHES, Phase.REJECTED}
    assert second.current_phase in {Phase.DONE, Phase.NO_MATCHES, Phase.REJECTED}
    assert first.query_id != second.query_id
    assert first.events
    assert second.events
