# Spike 2.1 — FastAPI + CopilotClient(mode="empty") lifecycle

## Goal

Prove that `CopilotClient(mode="empty")` works for server-side orchestration
in a FastAPI lifespan context without a VS Code host or TUI.

## What it validates

1. `CopilotClient(mode="empty", base_directory=...)` starts successfully.
2. The client can create a session with `available_tools` (required in empty mode).
3. A custom `@define_tool` tool is invoked by the model within that session.
4. `SessionIdleData` event signals session completion.
5. The FastAPI lifespan pattern (startup/shutdown) correctly manages client lifecycle.

## How to run

```bash
# From the repo root with .venv activated:
pip install -r 28-python-agent-demo-remove-before-merge/spike_2_1_fastapi_and_copilotclient/requirements.txt
python 28-python-agent-demo-remove-before-merge/spike_2_1_fastapi_and_copilotclient/spike_app.py
```

The script runs a standalone validation (no web server needed) that:
- Creates a CopilotClient in empty mode
- Creates a session with a custom tool
- Sends a prompt that triggers the tool
- Waits for SessionIdleData
- Reports success/failure

## Expected output

```
[SPIKE 2.1] CopilotClient(mode="empty") lifecycle validation
=============================================================
[OK] CopilotClient created in mode="empty" with base_directory=...
[OK] Session created with available_tools and custom tool
[OK] Tool 'ping' was invoked by the model
[OK] SessionIdleData received — session completed
[OK] Client stopped cleanly
=============================================================
SPIKE 2.1 PASSED — empty mode works for server-side orchestration
```
