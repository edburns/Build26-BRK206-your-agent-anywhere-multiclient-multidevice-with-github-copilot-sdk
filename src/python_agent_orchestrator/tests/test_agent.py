from types import SimpleNamespace
from pathlib import Path

import pytest
from copilot.session_events import (
    AssistantMessageData,
    SessionIdleData,
    ToolExecutionCompleteData,
    ToolExecutionStartData,
)
from copilot.tools import ToolInvocation

from python_agent_orchestrator.agent import Agent, create_tools_for_agent
from python_agent_orchestrator.phase import Phase
from python_agent_orchestrator.property_database import create_engine_and_tables, seed_database


DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "properties"


def test_create_tools_for_agent_has_required_tools_and_schema() -> None:
    engine = create_engine_and_tables()
    seed_database(engine, DATA_DIR)
    agent = Agent(query_id="q1", query_text="waterfront in toronto", db_engine=engine)

    tools = create_tools_for_agent(agent)
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

    agent_a = Agent(query_id="a", query_text="query a", db_engine=engine)
    agent_b = Agent(query_id="b", query_text="query b", db_engine=engine)
    tools_a = create_tools_for_agent(agent_a)
    tools_b = create_tools_for_agent(agent_b)

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
    agent = Agent(query_id="q2", query_text="Need 3 bedrooms in toronto", db_engine=engine)

    captured_session_args = {}

    class MockSession:
        def on(self, callback):
            self._callback = callback

        async def send(self, prompt: str) -> None:
            captured_session_args["prompt"] = prompt
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

        async def disconnect(self) -> None:
            pass

    class MockCopilotClient:
        async def create_session(self, **kwargs):
            captured_session_args.update(kwargs)
            return MockSession()

    await agent.run(MockCopilotClient())

    assert captured_session_args["available_tools"] is not None
    assert captured_session_args["on_permission_request"] is not None
    assert captured_session_args["tools"][0].name == "set_current_phase"
    assert captured_session_args["prompt"] == "<enquiry>Need 3 bedrooms in toronto</enquiry>"
    assert agent.to_dict()["phase"] == Phase.QUEUED.value
    assert "identity" in captured_session_args["system_message"]["sections"]


def test_agent_to_dict_is_json_serializable_shape() -> None:
    agent = Agent(query_id="q3", query_text="hello", current_phase=Phase.DONE, current_intent="Summarize")
    state = agent.to_dict()
    assert state == {
        "queryId": "q3",
        "phase": "Done",
        "intent": "Summarize",
        "queryText": "hello",
        "reportText": "",
        "events": [],
    }


def test_agent_instantiation_with_valid_query() -> None:
    agent = Agent(query_id="q-inst", query_text="Waterfront property in Toronto")
    assert agent.query_id == "q-inst"
    assert agent.query_text == "Waterfront property in Toronto"
    assert agent.current_phase == Phase.QUEUED


@pytest.mark.asyncio
async def test_agent_run_appends_events_to_history() -> None:
    """Agent.events receives tool_start and tool_complete entries from on_event."""
    engine = create_engine_and_tables()
    seed_database(engine, DATA_DIR)
    agent = Agent(query_id="q-ev", query_text="event test", db_engine=engine)

    class MockSession:
        def on(self, callback):
            self._callback = callback

        async def send(self, _prompt: str) -> None:
            self._callback(SimpleNamespace(
                data=ToolExecutionStartData(
                    tool_call_id="tc-10",
                    tool_name="search_properties",
                    arguments={"city": "Toronto"},
                )
            ))
            self._callback(SimpleNamespace(
                data=ToolExecutionCompleteData(
                    tool_call_id="tc-10",
                    success=True,
                )
            ))
            self._callback(SimpleNamespace(
                data=AssistantMessageData(content="Here is a great property.", message_id="msg-1")
            ))
            self._callback(SimpleNamespace(data=SessionIdleData()))

        async def disconnect(self) -> None:
            pass

    class MockCopilotClient:
        async def create_session(self, **kwargs):
            return MockSession()

    await agent.run(MockCopilotClient())

    types = [e["type"] for e in agent.events]
    assert "tool_start" in types
    assert "tool_complete" in types
    assert "assistant_message" in types

    tool_start = next(e for e in agent.events if e["type"] == "tool_start")
    assert tool_start["toolName"] == "search_properties"
    assert tool_start["args"] == {"city": "Toronto"}
    assert "timestamp" in tool_start

    tool_complete = next(e for e in agent.events if e["type"] == "tool_complete")
    assert tool_complete["success"] is True
    assert tool_complete["toolCallId"] == "tc-10"

    assistant = next(e for e in agent.events if e["type"] == "assistant_message")
    assert assistant["content"] == "Here is a great property."
    assert agent.report_text == "Here is a great property."


@pytest.mark.asyncio
async def test_multi_turn_assistant_messages_report_text_is_last() -> None:
    """When multiple AssistantMessageData events fire, report_text equals the last one."""
    engine = create_engine_and_tables()
    seed_database(engine, DATA_DIR)
    agent = Agent(query_id="q-mt", query_text="multi-turn test", db_engine=engine)

    class MockSession:
        def on(self, callback):
            self._callback = callback

        async def send(self, _prompt: str) -> None:
            self._callback(SimpleNamespace(
                data=AssistantMessageData(content="Intermediate turn 1.", message_id="msg-1")
            ))
            self._callback(SimpleNamespace(
                data=AssistantMessageData(content="Final answer.", message_id="msg-2")
            ))
            self._callback(SimpleNamespace(data=SessionIdleData()))

        async def disconnect(self) -> None:
            pass

    class MockCopilotClient:
        async def create_session(self, **kwargs):
            return MockSession()

    await agent.run(MockCopilotClient())

    assert agent.report_text == "Final answer."
    assistant_events = [e for e in agent.events if e["type"] == "assistant_message"]
    assert len(assistant_events) == 2


@pytest.mark.asyncio
async def test_set_current_phase_tool_appends_phase_change_event() -> None:
    engine = create_engine_and_tables()
    seed_database(engine, DATA_DIR)
    agent = Agent(query_id="q-ph", query_text="phase event test", db_engine=engine)
    tools = create_tools_for_agent(agent)

    await tools[0].handler(
        ToolInvocation(
            session_id="s-ph",
            tool_call_id="tc-ph",
            tool_name="set_current_phase",
            arguments={"phase": "Searching"},
        )
    )

    assert len(agent.events) == 1
    ev = agent.events[0]
    assert ev["type"] == "phase_change"
    assert ev["phase"] == "Searching"
    assert "timestamp" in ev


@pytest.mark.asyncio
async def test_phase_transitions_fire_in_expected_order() -> None:
    engine = create_engine_and_tables()
    seed_database(engine, DATA_DIR)
    agent = Agent(query_id="q-order", query_text="phase order test", db_engine=engine)
    tools = create_tools_for_agent(agent)

    await tools[0].handler(
        ToolInvocation(
            session_id="s-order",
            tool_call_id="tc-1",
            tool_name="set_current_phase",
            arguments={"phase": "Validating"},
        )
    )
    await tools[0].handler(
        ToolInvocation(
            session_id="s-order",
            tool_call_id="tc-2",
            tool_name="set_current_phase",
            arguments={"phase": "Searching"},
        )
    )
    await tools[0].handler(
        ToolInvocation(
            session_id="s-order",
            tool_call_id="tc-3",
            tool_name="set_current_phase",
            arguments={"phase": "WritingReport"},
        )
    )
    await tools[0].handler(
        ToolInvocation(
            session_id="s-order",
            tool_call_id="tc-4",
            tool_name="set_current_phase",
            arguments={"phase": "Done"},
        )
    )

    phases = [event["phase"] for event in agent.events if event["type"] == "phase_change"]
    assert phases == ["Validating", "Searching", "WritingReport", "Done"]
    assert all(event.get("timestamp") for event in agent.events if event["type"] == "phase_change")
    assert all("intent" in event for event in agent.events if event["type"] == "phase_change")


@pytest.mark.asyncio
async def test_agent_run_handles_session_creation_failure() -> None:
    engine = create_engine_and_tables()
    seed_database(engine, DATA_DIR)
    agent = Agent(query_id="q-fail", query_text="runtime fail", db_engine=engine)

    class FailingClient:
        async def create_session(self, **_kwargs):
            raise RuntimeError("session create failed")

    await agent.run(FailingClient())
    assert agent.current_phase == Phase.REJECTED
    errors = [event for event in agent.events if event["type"] == "error"]
    assert errors
    assert "Session creation failed" in errors[-1]["message"]


@pytest.mark.asyncio
async def test_agent_run_handles_timeout(monkeypatch) -> None:
    engine = create_engine_and_tables()
    seed_database(engine, DATA_DIR)
    agent = Agent(query_id="q-timeout", query_text="timeout", db_engine=engine)

    class MockSession:
        def on(self, callback):
            self._callback = callback

        async def send(self, _prompt: str) -> None:
            return

        async def disconnect(self) -> None:
            pass

    class MockClient:
        async def create_session(self, **_kwargs):
            return MockSession()

    async def raise_timeout(awaitable, timeout):
        close = getattr(awaitable, "close", None)
        if callable(close):
            close()
        raise TimeoutError(f"timed out after {timeout}")

    monkeypatch.setattr("python_agent_orchestrator.agent.asyncio.wait_for", raise_timeout)
    await agent.run(MockClient())
    assert agent.current_phase == Phase.REJECTED
    assert any(event["type"] == "error" and "timed out" in event["message"] for event in agent.events)
