# Spike 2.2 — Multi-turn agentic loop validation

## Goal

Prove that the Python SDK's `session.send()` + `SessionIdleData` pattern
handles multi-turn tool calls correctly — i.e., the SDK internally executes
tools and loops until the model produces a final assistant message.

## What it validates

1. Two tools (`step_one`, `step_two`) that must be called in sequence.
2. The SDK automatically handles: model calls step_one → SDK executes → sends
   result back → model calls step_two → SDK executes → sends result → model
   responds → SessionIdleData fires.
3. `ToolExecutionStartData` and `ToolExecutionCompleteData` events are emitted
   for real-time UI observability.
4. `SessionIdleData` only fires AFTER all tool calls and the final message.

## How to run

```bash
# From the repo root with .venv activated:
python 28-python-agent-demo-remove-before-merge/spike_2_2_multi_turn_in_python/spike_app.py
```

## Expected output

```
[SPIKE 2.2] Multi-turn agentic loop validation
=============================================================
[HH:MM:SS] Starting validation...
[HH:MM:SS] CopilotClient started in empty mode
[HH:MM:SS] Session created with step_one and step_two tools
[HH:MM:SS] Sending prompt: 'Find waterfront properties in Miami'
[HH:MM:SS]   EVENT tool.execution_start: step_one
[HH:MM:SS]   TOOL step_one invoked with query='...'
[HH:MM:SS]   EVENT tool.execution_complete: step_one
[HH:MM:SS]   EVENT tool.execution_start: step_two
[HH:MM:SS]   TOOL step_two invoked with data='...', format='summary'
[HH:MM:SS]   EVENT tool.execution_complete: step_two
[HH:MM:SS]   EVENT assistant.message: ...
[HH:MM:SS]   EVENT session.idle — session finished!
=============================================================
RESULTS:
  Tool calls made: ['step_one', 'step_two']
  ...
[OK] step_one was called
[OK] step_two was called
[OK] Tools called in correct order: step_one → step_two
[OK] Final assistant message received after all tool calls
[OK] SessionIdleData fired AFTER all tool calls completed
=============================================================
SPIKE 2.2 PASSED — Multi-turn agentic loop works correctly
```
