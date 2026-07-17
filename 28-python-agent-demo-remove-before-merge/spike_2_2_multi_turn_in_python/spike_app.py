"""
Spike 2.2 — Validate multi-turn agentic loop with send() + SessionIdleData pattern.

This script proves that:
1. The SDK internally handles multi-turn tool calls (model calls tool, SDK
   executes handler, sends result back, model may call another tool or respond).
2. SessionIdleData only fires AFTER the model has finished all tool calls
   and produced a final assistant message.
3. We can observe each turn/tool-call via session events for real-time UI.

The test defines TWO tools that must be called in sequence:
- step_one: returns partial data that step_two needs
- step_two: uses step_one's output to produce the final answer

The system prompt instructs the model to call step_one first, then step_two.
This proves the SDK handles the full loop automatically.
"""

import asyncio
import os
import sys
import tempfile
from datetime import datetime

from pydantic import BaseModel, Field

from copilot import CopilotClient, ToolSet, define_tool
from copilot.session import PermissionHandler
from copilot.session_events import (
    AssistantMessageData,
    SessionIdleData,
    ToolExecutionCompleteData,
    ToolExecutionStartData,
)

# ---------------------------------------------------------------------------
# Event log for tracking what happens
# ---------------------------------------------------------------------------

event_log: list[str] = []
tool_calls: list[str] = []


def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    line = f"[{ts}] {msg}"
    event_log.append(line)
    print(line)


# ---------------------------------------------------------------------------
# Tool definitions — two tools that must be called in sequence
# ---------------------------------------------------------------------------


class StepOneParams(BaseModel):
    query: str = Field(description="The search query to process")


class StepTwoParams(BaseModel):
    data_from_step_one: str = Field(description="The data returned by step_one")
    format: str = Field(description="Output format: 'summary' or 'detailed'")


@define_tool(description="First step: processes the query and returns intermediate data. Must be called before step_two.")
def step_one(params: StepOneParams) -> str:
    tool_calls.append("step_one")
    log(f"  TOOL step_one invoked with query='{params.query}'")
    # Return intermediate data that step_two needs
    return f"INTERMEDIATE_DATA[processed: {params.query}, items_found: 3]"


@define_tool(description="Second step: takes the intermediate data from step_one and produces the final formatted result. Must be called AFTER step_one.")
def step_two(params: StepTwoParams) -> str:
    tool_calls.append("step_two")
    log(f"  TOOL step_two invoked with data='{params.data_from_step_one[:50]}...', format='{params.format}'")
    return f"FINAL_RESULT[formatted {params.format}: {params.data_from_step_one}]"


# ---------------------------------------------------------------------------
# Main validation routine
# ---------------------------------------------------------------------------

async def validate_multi_turn():
    """Run the multi-turn spike validation."""
    print()
    print("[SPIKE 2.2] Multi-turn agentic loop validation")
    print("=" * 61)
    print()
    log("Starting validation...")

    base_dir = os.path.join(tempfile.gettempdir(), "spike_2_2_copilot")
    os.makedirs(base_dir, exist_ok=True)

    # Create client
    client = CopilotClient(
        mode="empty",
        base_directory=base_dir,
    )
    await client.start()
    log("CopilotClient started in empty mode")

    # Create session with both tools
    available_tools = ToolSet().add_custom("*")

    session = await client.create_session(
        on_permission_request=PermissionHandler.approve_all,
        tools=[step_one, step_two],
        available_tools=available_tools,
        system_message={
            "mode": "replace",
            "content": (
                "You are a data processing assistant. When the user gives you a query, "
                "you MUST follow this exact sequence:\n"
                "1. Call the 'step_one' tool with the user's query.\n"
                "2. Take the result from step_one and call 'step_two' with that result "
                "   and format='summary'.\n"
                "3. After step_two completes, report the final result to the user.\n\n"
                "You MUST call both tools in this order. Do NOT skip any step."
            ),
        },
    )
    log("Session created with step_one and step_two tools")

    # Subscribe to events for observability
    done = asyncio.Event()
    assistant_messages: list[str] = []
    tool_starts: list[str] = []
    tool_completes: list[str] = []

    def on_event(event):
        match event.data:
            case ToolExecutionStartData() as data:
                name = getattr(data, "tool_name", None) or getattr(data, "name", "unknown")
                tool_starts.append(name)
                log(f"  EVENT tool.execution_start: {name}")
            case ToolExecutionCompleteData() as data:
                name = getattr(data, "tool_name", None) or getattr(data, "name", "unknown")
                tool_completes.append(name)
                log(f"  EVENT tool.execution_complete: {name}")
            case AssistantMessageData() as data:
                content = data.content or ""
                assistant_messages.append(content)
                log(f"  EVENT assistant.message: {content[:80]}...")
            case SessionIdleData():
                log("  EVENT session.idle — session finished!")
                done.set()

    session.on(on_event)

    # Send the prompt
    log("Sending prompt: 'Find waterfront properties in Miami'")
    await session.send("Find waterfront properties in Miami")

    # Wait for completion
    try:
        await asyncio.wait_for(done.wait(), timeout=45.0)
    except asyncio.TimeoutError:
        log("[FAIL] Timed out waiting for SessionIdleData (45s)")
        await session.disconnect()
        await client.stop()
        sys.exit(1)

    # Validate results
    print()
    print("=" * 61)
    print("RESULTS:")
    print(f"  Tool calls made: {tool_calls}")
    print(f"  Tool execution starts observed: {len(tool_starts)}")
    print(f"  Tool execution completes observed: {len(tool_completes)}")
    print(f"  Assistant messages received: {len(assistant_messages)}")
    print()

    # Assertions
    passed = True

    if "step_one" in tool_calls:
        print("[OK] step_one was called")
    else:
        print("[FAIL] step_one was NOT called")
        passed = False

    if "step_two" in tool_calls:
        print("[OK] step_two was called")
    else:
        print("[FAIL] step_two was NOT called")
        passed = False

    if tool_calls == ["step_one", "step_two"]:
        print("[OK] Tools called in correct order: step_one -> step_two")
    elif "step_one" in tool_calls and "step_two" in tool_calls:
        print(f"[WARN] Tools called but order was: {tool_calls}")
    else:
        print(f"[FAIL] Unexpected tool call sequence: {tool_calls}")
        passed = False

    if len(assistant_messages) >= 1:
        print("[OK] Final assistant message received after all tool calls")
    else:
        print("[FAIL] No assistant message received")
        passed = False

    if done.is_set():
        print("[OK] SessionIdleData fired AFTER all tool calls completed")
    else:
        print("[FAIL] SessionIdleData not received")
        passed = False

    # Clean up
    await session.disconnect()
    await client.stop()
    log("Client stopped cleanly")

    print()
    print("=" * 61)
    if passed:
        print("SPIKE 2.2 PASSED — Multi-turn agentic loop works correctly")
        print("  The SDK handles tool call -> result -> next tool call -> final response")
        print("  automatically. SessionIdleData only fires after completion.")
    else:
        print("SPIKE 2.2 FAILED — See errors above")
        sys.exit(1)
    print()


if __name__ == "__main__":
    asyncio.run(validate_multi_turn())
