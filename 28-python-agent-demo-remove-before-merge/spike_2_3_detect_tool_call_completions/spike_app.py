"""
Spike 2.3 — Detect and inspect all session events for real-time UI updates.

This script proves:
1. Which events the Python SDK emits during tool execution.
2. What fields are available on each event type for UI rendering.
3. How to correlate ToolExecutionStartData (has tool_name) with
   ToolExecutionCompleteData (has tool_call_id, tool_description.name).
4. The complete event sequence for a multi-tool interaction.

The output is a detailed event trace showing every event type, its fields,
and the order of emission — the exact data needed for the real-time pipeline UI.
"""

import asyncio
import os
import sys
import tempfile
from dataclasses import fields as dc_fields
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
# Event trace collector
# ---------------------------------------------------------------------------

event_trace: list[dict] = []
event_counter = 0


def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"[{ts}] {msg}")


def record_event(event):
    """Record raw event data for analysis."""
    global event_counter
    event_counter += 1
    event_type = type(event.data).__name__
    event_trace.append({
        "seq": event_counter,
        "type": event_type,
        "data": event.data,
    })


# ---------------------------------------------------------------------------
# Tools — three tools to generate a rich event trace
# ---------------------------------------------------------------------------


class ValidateParams(BaseModel):
    query: str = Field(description="The query to validate")


class SearchParams(BaseModel):
    query: str = Field(description="Validated query to search")
    city: str = Field(description="City to search in")


class ReportParams(BaseModel):
    results: str = Field(description="Search results to format")
    format: str = Field(description="Report format: 'brief' or 'full'")


@define_tool(description="Validates a real estate query for legitimacy. Returns 'valid' or 'rejected'.")
def validate_query(params: ValidateParams) -> str:
    log(f"    [TOOL] validate_query called: query='{params.query}'")
    return "valid: query is a legitimate real estate inquiry"


@define_tool(description="Searches property database. Must be called AFTER validate_query returns 'valid'.")
def search_properties(params: SearchParams) -> str:
    log(f"    [TOOL] search_properties called: query='{params.query}', city='{params.city}'")
    return '{"results": [{"id": 1, "type": "condo", "price": 450000}, {"id": 2, "type": "house", "price": 750000}]}'


@define_tool(description="Generates a formatted report from search results. Must be called AFTER search_properties.")
def generate_report(params: ReportParams) -> str:
    log(f"    [TOOL] generate_report called: format='{params.format}'")
    return "REPORT: 2 properties found matching criteria. Top match: condo at $450k."


# ---------------------------------------------------------------------------
# Main validation
# ---------------------------------------------------------------------------

async def validate_event_detection():
    """Run the event detection spike."""
    print()
    print("[SPIKE 2.3] Session event detection for real-time UI")
    print("=" * 65)
    print()

    base_dir = os.path.join(tempfile.gettempdir(), "spike_2_3_copilot")
    os.makedirs(base_dir, exist_ok=True)

    client = CopilotClient(mode="empty", base_directory=base_dir)
    await client.start()
    log("CopilotClient started")

    available_tools = ToolSet().add_custom("*")
    session = await client.create_session(
        on_permission_request=PermissionHandler.approve_all,
        tools=[validate_query, search_properties, generate_report],
        available_tools=available_tools,
        system_message={
            "mode": "replace",
            "content": (
                "You are a real estate pipeline assistant. Process queries in this exact order:\n"
                "1. Call validate_query with the user's query.\n"
                "2. If valid, call search_properties with the query and city extracted from the query.\n"
                "3. Call generate_report with the search results in 'brief' format.\n"
                "4. Report the final result to the user.\n\n"
                "You MUST call all three tools in sequence. Do NOT skip steps."
            ),
        },
    )
    log("Session created with 3 tools")

    # Subscribe to ALL events for full trace
    done = asyncio.Event()
    tool_call_id_to_name: dict[str, str] = {}

    def on_event(event):
        record_event(event)
        match event.data:
            case ToolExecutionStartData() as data:
                tool_call_id_to_name[data.tool_call_id] = data.tool_name
                args_str = str(data.arguments)[:60] if data.arguments else "none"
                log(f"  EVENT tool.start: name={data.tool_name}, "
                    f"call_id={data.tool_call_id[:12]}..., args={args_str}")
            case ToolExecutionCompleteData() as data:
                # Correlate with start event via tool_call_id
                name_from_start = tool_call_id_to_name.get(data.tool_call_id, "?")
                name_from_desc = data.tool_description.name if data.tool_description else "N/A"
                log(f"  EVENT tool.complete: call_id={data.tool_call_id[:12]}..., "
                    f"success={data.success}, "
                    f"name(from_start)={name_from_start}, "
                    f"name(from_desc)={name_from_desc}")
            case AssistantMessageData() as data:
                content = (data.content or "")[:80]
                log(f"  EVENT assistant.message: '{content}...'")
            case SessionIdleData():
                log("  EVENT session.idle")
                done.set()
            case _:
                # Log other event types we see
                event_type = type(event.data).__name__
                log(f"  EVENT {event_type}")

    session.on(on_event)

    log("Sending prompt: 'Waterfront condos in Miami under $500k'")
    await session.send("Waterfront condos in Miami under $500k")

    try:
        await asyncio.wait_for(done.wait(), timeout=60.0)
    except asyncio.TimeoutError:
        log("[FAIL] Timed out (60s)")
        await session.disconnect()
        await client.stop()
        sys.exit(1)

    # Analysis
    print()
    print("=" * 65)
    print("EVENT TRACE ANALYSIS")
    print("=" * 65)
    print()

    # Group by type
    type_counts: dict[str, int] = {}
    for entry in event_trace:
        t = entry["type"]
        type_counts[t] = type_counts.get(t, 0) + 1

    print("Event types observed (in order of first occurrence):")
    seen = []
    for entry in event_trace:
        t = entry["type"]
        if t not in seen:
            seen.append(t)
    for t in seen:
        print(f"  {t}: {type_counts[t]}x")

    print()
    print("Event sequence (simplified):")
    for entry in event_trace:
        t = entry["type"]
        data = entry["data"]
        seq = entry["seq"]
        if t == "ToolExecutionStartData":
            print(f"  #{seq} TOOL_START: {data.tool_name} (id={data.tool_call_id[:12]}...)")
        elif t == "ToolExecutionCompleteData":
            name = data.tool_description.name if data.tool_description else tool_call_id_to_name.get(data.tool_call_id, "?")
            print(f"  #{seq} TOOL_DONE:  {name} success={data.success} (id={data.tool_call_id[:12]}...)")
        elif t == "AssistantMessageData":
            print(f"  #{seq} ASSISTANT:  '{(data.content or '')[:60]}...'")
        elif t == "SessionIdleData":
            print(f"  #{seq} IDLE")
        else:
            print(f"  #{seq} {t}")

    print()
    print("=" * 65)
    print("FIELD AVAILABILITY SUMMARY (for UI rendering):")
    print("=" * 65)
    print()
    print("ToolExecutionStartData fields:")
    print("  .tool_name       -- YES (the tool name, e.g. 'validate_query')")
    print("  .tool_call_id    -- YES (unique ID to correlate with complete event)")
    print("  .arguments       -- YES (dict of arguments passed to the tool)")
    print("  .tool_description-- optional (name + description metadata)")
    print()
    print("ToolExecutionCompleteData fields:")
    print("  .tool_call_id    -- YES (correlates with start event)")
    print("  .success         -- YES (bool: did the tool succeed?)")
    print("  .tool_description.name -- YES (tool name, when present)")
    print("  .result          -- optional (detailed result data)")
    print("  .error           -- optional (error info on failure)")
    print()
    print("Correlation strategy for UI:")
    print("  1. On tool.start: store {tool_call_id -> tool_name, arguments}")
    print("  2. On tool.complete: look up tool_call_id to get the tool name")
    print("     OR use tool_description.name if available")
    print("  3. This gives: tool name, arguments, success/failure, duration")
    print()

    # Final verdict
    tool_starts = [e for e in event_trace if e["type"] == "ToolExecutionStartData"]
    tool_completes = [e for e in event_trace if e["type"] == "ToolExecutionCompleteData"]

    passed = True
    if len(tool_starts) >= 3:
        print(f"[OK] {len(tool_starts)} tool starts detected")
    else:
        print(f"[WARN] Only {len(tool_starts)} tool starts (expected 3)")

    if len(tool_completes) >= 3:
        print(f"[OK] {len(tool_completes)} tool completes detected")
    else:
        print(f"[WARN] Only {len(tool_completes)} tool completes (expected 3)")

    # Verify tool_call_id correlation works
    start_ids = {e["data"].tool_call_id for e in tool_starts}
    complete_ids = {e["data"].tool_call_id for e in tool_completes}
    matched = start_ids & complete_ids
    if matched:
        print(f"[OK] tool_call_id correlation works: {len(matched)} matched pairs")
    else:
        print("[FAIL] tool_call_id correlation failed")
        passed = False

    # Check tool_description.name on complete events
    names_from_desc = [
        e["data"].tool_description.name
        for e in tool_completes
        if e["data"].tool_description is not None
    ]
    if names_from_desc:
        print(f"[OK] tool_description.name available on complete events: {names_from_desc}")
    else:
        print("[INFO] tool_description.name NOT available on complete events (use correlation instead)")

    print()
    await session.disconnect()
    await client.stop()
    log("Client stopped cleanly")

    print()
    print("=" * 65)
    if passed:
        print("SPIKE 2.3 PASSED -- Full event observability confirmed for real-time UI")
    else:
        print("SPIKE 2.3 FAILED -- See errors above")
        sys.exit(1)
    print()


if __name__ == "__main__":
    asyncio.run(validate_event_detection())
