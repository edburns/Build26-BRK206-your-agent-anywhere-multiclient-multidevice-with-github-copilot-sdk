"""
Spike 2.7 -- Tool definition styles and agent-instance binding.

Validates three questions:
1. Can @define_tool tools close over agent instance state (factory pattern)?
2. Does overrides_built_in_tool=True work for report_intent?
3. Does a multi-field Pydantic model generate the expected JSON schema?

Also compares decorator style vs function-call style.

Run:
    python spike_app.py
"""

import asyncio
import enum
import json
import os
import signal
import sys
from dataclasses import dataclass, field

from pydantic import BaseModel, Field

from copilot import CopilotClient
from copilot.tools import Tool, ToolInvocation, ToolResult, define_tool
from copilot.session import PermissionHandler
from copilot._mode import ToolSet


# ---------------------------------------------------------------------------
# Domain model (mirrors C#/Java demo)
# ---------------------------------------------------------------------------

class Phase(str, enum.Enum):
    QUEUED = "Queued"
    VALIDATING = "Validating"
    SEARCHING = "Searching"
    WRITING_REPORT = "WritingReport"
    DONE = "Done"
    REJECTED = "Rejected"


@dataclass
class AgentContext:
    """Per-query agent state that tools need to mutate."""
    query_id: str = ""
    current_phase: Phase = Phase.QUEUED
    current_intent: str = ""
    search_results: list[dict] = field(default_factory=list)
    events: list[str] = field(default_factory=list)

    def log(self, msg: str):
        self.events.append(msg)
        print(f"  [AGENT {self.query_id}] {msg}")


# ---------------------------------------------------------------------------
# SPIKE A: Factory function that creates tools closing over an AgentContext
# ---------------------------------------------------------------------------

def create_tools_for_agent(agent: AgentContext) -> list[Tool]:
    """
    Factory that returns Tool instances bound to a specific agent instance.
    This is the key pattern: tools are created per-session, closing over
    the agent context they need to mutate.
    """

    # Tool 1: set_current_phase -- @define_tool decorator with Pydantic params
    class SetPhaseParams(BaseModel):
        phase: str = Field(description="The lifecycle phase to transition to")

    @define_tool(description="Sets the current phase of the agent. Use this to report progress.")
    def set_current_phase(params: SetPhaseParams) -> str:
        try:
            agent.current_phase = Phase(params.phase)
        except ValueError:
            return f"Unknown phase: {params.phase}"
        agent.log(f"Phase -> {agent.current_phase.value}")
        return f"Phase set to {agent.current_phase.value}"

    # Tool 2: report_intent -- overrides built-in tool
    class ReportIntentParams(BaseModel):
        intent: str = Field(description="The current intent in max 4 words")

    @define_tool(
        name="report_intent",
        description="Reports the current intent of the agent. Call this before each action.",
        overrides_built_in_tool=True,
    )
    def report_intent(params: ReportIntentParams) -> str:
        agent.current_intent = params.intent
        agent.log(f"Intent -> '{agent.current_intent}'")
        return f"Intent recorded: {agent.current_intent}"

    # Tool 3: search_properties -- multi-field Pydantic model
    class SearchPropertiesParams(BaseModel):
        min_bedrooms: int = Field(default=1, description="Minimum number of bedrooms")
        max_price: float = Field(default=1_000_000, description="Maximum price in USD")
        city: str = Field(description="City to search in")
        waterfront: bool = Field(default=False, description="Whether waterfront is required")

    @define_tool(description="Search the property database for matching listings.")
    def search_properties(params: SearchPropertiesParams) -> str:
        agent.log(
            f"Search: city={params.city}, beds>={params.min_bedrooms}, "
            f"price<={params.max_price}, waterfront={params.waterfront}"
        )
        # Simulated results
        results = [
            {"address": "123 Ocean Dr", "city": params.city,
             "bedrooms": max(params.min_bedrooms, 3), "price": 850000,
             "waterfront": params.waterfront},
            {"address": "456 Palm Ave", "city": params.city,
             "bedrooms": max(params.min_bedrooms, 2), "price": 650000,
             "waterfront": False},
        ]
        agent.search_results = results
        return json.dumps(results)

    return [set_current_phase, report_intent, search_properties]


# ---------------------------------------------------------------------------
# SPIKE B: Function-call style (non-decorator) for comparison
# ---------------------------------------------------------------------------

def create_tools_function_style(agent: AgentContext) -> list[Tool]:
    """Alternative: define_tool as a function call with handler= and params_type=."""

    class SetPhaseParams(BaseModel):
        phase: str = Field(description="The lifecycle phase to transition to")

    def handle_set_phase(params: SetPhaseParams, invocation: ToolInvocation) -> str:
        agent.current_phase = Phase(params.phase)
        agent.log(f"[fn-style] Phase -> {agent.current_phase.value} (call_id={invocation.tool_call_id})")
        return f"Phase set to {agent.current_phase.value}"

    set_phase = define_tool(
        "set_current_phase",
        description="Sets the current phase of the agent.",
        handler=handle_set_phase,
        params_type=SetPhaseParams,
    )

    return [set_phase]


# ---------------------------------------------------------------------------
# Test 1: Verify tool definitions and schemas (no SDK needed)
# ---------------------------------------------------------------------------

def test_tool_definitions():
    """Validate that tools are created with correct metadata and schemas."""
    print("\n" + "=" * 65)
    print("TEST 1: Tool definitions and JSON schema generation")
    print("=" * 65)

    agent = AgentContext(query_id="test-1")
    tools = create_tools_for_agent(agent)

    for tool in tools:
        print(f"\n  Tool: {tool.name}")
        print(f"    description: {tool.description}")
        print(f"    overrides_built_in: {tool.overrides_built_in_tool}")
        print(f"    has handler: {tool.handler is not None}")
        if tool.parameters:
            print(f"    schema: {json.dumps(tool.parameters, indent=6)}")

    # Verify specific attributes
    assert tools[0].name == "set_current_phase", f"Expected 'set_current_phase', got '{tools[0].name}'"
    assert tools[1].name == "report_intent", f"Expected 'report_intent', got '{tools[1].name}'"
    assert tools[1].overrides_built_in_tool is True, "report_intent should override built-in"
    assert tools[2].name == "search_properties", f"Expected 'search_properties', got '{tools[2].name}'"

    # Verify search_properties schema has all fields
    schema = tools[2].parameters
    props = schema.get("properties", {})
    assert "min_bedrooms" in props, "Missing min_bedrooms in schema"
    assert "max_price" in props, "Missing max_price in schema"
    assert "city" in props, "Missing city in schema"
    assert "waterfront" in props, "Missing waterfront in schema"
    assert "city" in schema.get("required", []), "city should be required"

    print("\n  [PASS] All tool definitions correct")
    print(f"  [PASS] search_properties has {len(props)} fields in schema")
    print(f"  [PASS] report_intent.overrides_built_in_tool = True")


# ---------------------------------------------------------------------------
# Test 2: Verify closure binding (tools mutate the agent they close over)
# ---------------------------------------------------------------------------

async def test_closure_binding():
    """Call tool handlers directly to verify they mutate the right agent."""
    print("\n" + "=" * 65)
    print("TEST 2: Closure binding -- tools mutate their bound agent")
    print("=" * 65)

    agent_a = AgentContext(query_id="agent-A")
    agent_b = AgentContext(query_id="agent-B")

    tools_a = create_tools_for_agent(agent_a)
    tools_b = create_tools_for_agent(agent_b)

    # Call set_current_phase on agent_a
    inv_a = ToolInvocation(session_id="s1", tool_call_id="tc1",
                           tool_name="set_current_phase",
                           arguments={"phase": "Validating"})
    result_a = await tools_a[0].handler(inv_a)
    print(f"  Agent A phase: {agent_a.current_phase.value}")

    # Call set_current_phase on agent_b with a different phase
    inv_b = ToolInvocation(session_id="s2", tool_call_id="tc2",
                           tool_name="set_current_phase",
                           arguments={"phase": "Searching"})
    result_b = await tools_b[0].handler(inv_b)
    print(f"  Agent B phase: {agent_b.current_phase.value}")

    # Verify they are independent
    assert agent_a.current_phase == Phase.VALIDATING, \
        f"Agent A should be Validating, got {agent_a.current_phase}"
    assert agent_b.current_phase == Phase.SEARCHING, \
        f"Agent B should be Searching, got {agent_b.current_phase}"

    print(f"  [PASS] Agent A = {agent_a.current_phase.value}, Agent B = {agent_b.current_phase.value}")
    print(f"  [PASS] Two independent agents with separate tool closures -- no cross-contamination")


# ---------------------------------------------------------------------------
# Test 3: Verify function-call style works too
# ---------------------------------------------------------------------------

async def test_function_call_style():
    """Verify define_tool(..., handler=, params_type=) works."""
    print("\n" + "=" * 65)
    print("TEST 3: Function-call style (non-decorator)")
    print("=" * 65)

    agent = AgentContext(query_id="fn-style")
    tools = create_tools_function_style(agent)

    inv = ToolInvocation(session_id="s3", tool_call_id="tc3",
                         tool_name="set_current_phase",
                         arguments={"phase": "WritingReport"})
    result = await tools[0].handler(inv)

    assert agent.current_phase == Phase.WRITING_REPORT
    print(f"  [PASS] Function-call style works: phase = {agent.current_phase.value}")


# ---------------------------------------------------------------------------
# Test 4: End-to-end with CopilotClient (tools bound to agent instance)
# ---------------------------------------------------------------------------

async def test_e2e_with_copilot():
    """Full integration: tools close over agent, session uses them, model calls them."""
    print("\n" + "=" * 65)
    print("TEST 4: End-to-end with CopilotClient")
    print("=" * 65)

    agent = AgentContext(query_id="e2e-1")
    tools = create_tools_for_agent(agent)

    print(f"  Tools registered: {[t.name for t in tools]}")

    async with CopilotClient(mode="empty", base_directory=os.getcwd()) as client:
        print("  CopilotClient started (mode=empty)")

        session = await client.create_session(
            tools=tools,
            available_tools=ToolSet().add_custom("*"),
            on_permission_request=PermissionHandler.approve_all,
        )
        print(f"  Session created: {session.session_id[:12]}...")

        # Subscribe to events
        from copilot.session_events import (
            ToolExecutionStartData,
            ToolExecutionCompleteData,
            SessionIdleData,
            AssistantMessageData,
        )

        tool_calls_seen = []
        done = asyncio.Event()
        loop = asyncio.get_running_loop()

        def on_event(event):
            d = event.data
            if isinstance(d, ToolExecutionStartData):
                tool_calls_seen.append(d.tool_name)
                print(f"    [EVENT] Tool start: {d.tool_name}")
            elif isinstance(d, ToolExecutionCompleteData):
                print(f"    [EVENT] Tool complete: call_id={d.tool_call_id}")
            elif isinstance(d, AssistantMessageData):
                snippet = (d.content or "")[:80]
                print(f"    [EVENT] Assistant: {snippet}...")
            elif isinstance(d, SessionIdleData):
                print(f"    [EVENT] Session idle")
                loop.call_soon_threadsafe(done.set)

        session.on(on_event)

        # Send a prompt that should trigger all three tools
        prompt = (
            "You are a real estate agent. A customer asks: "
            "'I want a waterfront property in Miami with at least 3 bedrooms under $900,000.' "
            "Use the tools in this order: "
            "1) report_intent with a short intent description, "
            "2) set_current_phase to 'Validating', "
            "3) set_current_phase to 'Searching', "
            "4) search_properties with the customer's criteria, "
            "5) set_current_phase to 'WritingReport', "
            "6) set_current_phase to 'Done', "
            "then write a brief summary of the results."
        )

        print(f"\n  Sending prompt...")
        await session.send(prompt)
        await asyncio.wait_for(done.wait(), timeout=60)

        print(f"\n  -- Results --")
        print(f"  Agent phase: {agent.current_phase.value}")
        print(f"  Agent intent: '{agent.current_intent}'")
        print(f"  Search results: {len(agent.search_results)} properties")
        print(f"  Tool calls seen: {tool_calls_seen}")
        print(f"  Agent event log ({len(agent.events)} entries):")
        for ev in agent.events:
            print(f"    - {ev}")

        # Verify tools actually mutated the agent
        assert len(tool_calls_seen) >= 3, f"Expected >= 3 tool calls, got {len(tool_calls_seen)}"
        assert "report_intent" in tool_calls_seen, "report_intent should have been called"
        assert "search_properties" in tool_calls_seen, "search_properties should have been called"
        assert "set_current_phase" in tool_calls_seen, "set_current_phase should have been called"
        assert agent.current_intent != "", "Intent should have been set"
        assert len(agent.search_results) > 0, "Search should have produced results"

        print(f"\n  [PASS] All three tools invoked and mutated the agent instance")
        print(f"  [PASS] Closure binding works end-to-end with CopilotClient")
        print(f"  [PASS] overrides_built_in_tool=True accepted by runtime")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main():
    print()
    print("[SPIKE 2.7] Tool definition styles and agent-instance binding")
    print("=" * 65)
    print()
    print("Questions under test:")
    print("  1. Can @define_tool tools close over agent instance state?")
    print("  2. Does overrides_built_in_tool=True work for report_intent?")
    print("  3. Does multi-field Pydantic model generate correct JSON schema?")
    print("  4. Decorator style vs function-call style?")
    print()

    # Tests 1-3 don't need CopilotClient
    test_tool_definitions()
    await test_closure_binding()
    await test_function_call_style()

    # Test 4 needs CopilotClient
    await test_e2e_with_copilot()

    print("\n" + "=" * 65)
    print("[SPIKE 2.7] ALL TESTS PASSED")
    print("=" * 65)
    print()
    print("Findings:")
    print("  1. @define_tool inside a factory function WORKS -- tools close over agent state")
    print("  2. Two agents get independent tool closures -- no cross-contamination")
    print("  3. overrides_built_in_tool=True is accepted by the runtime")
    print("  4. Multi-field Pydantic model generates correct JSON schema with types")
    print("  5. Both decorator and function-call styles produce valid Tool objects")
    print("  6. Pattern: create_tools_for_agent(agent) returns [Tool] per session")
    print()


if __name__ == "__main__":
    signal.signal(signal.SIGINT, lambda *_: sys.exit(0))
    asyncio.run(main())
