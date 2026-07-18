from types import SimpleNamespace
from pathlib import Path

import pytest
from copilot.session_events import SessionIdleData, ToolExecutionStartData
from copilot.tools import ToolInvocation

from python_agent_orchestrator.agent import Agent, create_tools_for_agent
from python_agent_orchestrator.phase import Phase
from python_agent_orchestrator.property_database import create_engine_and_tables, seed_database


DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "properties"


def test_create_tools_for_agent_has_required_tools_and_schema() -> None:
    engine = create_engine_and_tables()
    seed_database(engine, DATA_DIR)
    agent = Agent(query_id="q1", query_text="waterfront in toronto")

    tools = create_tools_for_agent(agent, engine)
    names = [tool.name for tool in tools]
    assert names == ["set_current_phase", "report_intent", "search_properties"]
    assert tools[1].overrides_built_in_tool is True

    props = tools[2].parameters["properties"]
    assert "city" in props
    assert "min_bedrooms" in props
    assert "max_price" in props
    assert "waterfront" in props


@pytest.mark.asyncio
async def test_tool_closures_are_independent_between_agents() -> None:
    engine = create_engine_and_tables()
    seed_database(engine, DATA_DIR)

    agent_a = Agent(query_id="a", query_text="query a")
    agent_b = Agent(query_id="b", query_text="query b")
    tools_a = create_tools_for_agent(agent_a, engine)
    tools_b = create_tools_for_agent(agent_b, engine)

    await tools_a[0].handler(
        ToolInvocation(
            session_id="s-a",
            tool_call_id="tc-a",
            tool_name="set_current_phase",
            arguments={"phase": "Validating"},
        )
    )
    await tools_b[0].handler(
        ToolInvocation(
            session_id="s-b",
            tool_call_id="tc-b",
            tool_name="set_current_phase",
            arguments={"phase": "Searching"},
        )
    )
    assert agent_a.current_phase == Phase.VALIDATING
    assert agent_b.current_phase == Phase.SEARCHING


@pytest.mark.asyncio
async def test_agent_run_waits_for_session_idle_and_updates_state() -> None:
    engine = create_engine_and_tables()
    seed_database(engine, DATA_DIR)
    agent = Agent(query_id="q2", query_text="Need 3 bedrooms in toronto")

    created = {}

    class FakeSession:
        def on(self, callback):
            self._callback = callback

        async def send(self, prompt: str) -> None:
            created["prompt"] = prompt
            self._callback(
                SimpleNamespace(
                    data=ToolExecutionStartData(
                        tool_call_id="tc-1",
                        tool_name="search_properties",
                        arguments={"city": "Toronto"},
                    )
                )
            )
            self._callback(SimpleNamespace(data=SessionIdleData()))

    class FakeClient:
        async def create_session(self, **kwargs):
            created.update(kwargs)
            return FakeSession()

    await agent.run(FakeClient(), engine)

    assert created["available_tools"] is not None
    assert created["on_permission_request"] is not None
    assert created["tools"][0].name == "set_current_phase"
    assert created["prompt"] == "<enquiry>Need 3 bedrooms in toronto</enquiry>"
    assert agent.to_dict()["phase"] == Phase.QUEUED.value
    assert "identity" in created["system_message"]["sections"]


def test_agent_to_dict_is_json_serializable_shape() -> None:
    agent = Agent(query_id="q3", query_text="hello", current_phase=Phase.DONE, current_intent="Summarize")
    state = agent.to_dict()
    assert state == {
        "queryId": "q3",
        "phase": "Done",
        "intent": "Summarize",
        "queryText": "hello",
        "reportText": "",
    }
