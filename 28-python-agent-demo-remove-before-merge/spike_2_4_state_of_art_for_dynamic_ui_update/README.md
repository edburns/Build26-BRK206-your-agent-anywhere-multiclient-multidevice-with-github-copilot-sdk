# Spike 2.4 -- WebSocket push from Copilot SDK callbacks to browser

## Goal

Prove that FastAPI WebSocket (the Python analog to Jakarta WebSocket /
`f:websocket` / `PushContext`) can deliver real-time updates from inside
Copilot SDK `session.on()` callbacks to connected browser clients.

## Key challenge

The SDK's `session.on()` callback is **synchronous** (`def on_event(event):`).
WebSocket `send_text()` is **async**. We need to bridge the two.

## Solution

Use `asyncio.run_coroutine_threadsafe(broadcast_coro, loop)` to schedule
the async WebSocket send onto the running event loop from inside the sync callback.

## Jakarta WebSocket equivalence

| Jakarta (Java) | Python (FastAPI) |
|----------------|-----------------|
| `@Inject @Push PushContext pushContext` | `ws_manager = ConnectionManager()` |
| `pushContext.send(jsonData)` | `ws_manager.schedule_broadcast(loop, data)` |
| `<f:websocket channel="pipeline" onmessage="handler"/>` | `new WebSocket('ws://host/ws/pipeline')` |
| `@ServerEndpoint` | `@app.websocket("/ws/pipeline")` |

## How to run

```bash
# Standalone validation (no browser):
python 28-python-agent-demo-remove-before-merge/spike_2_4_state_of_art_for_dynamic_ui_update/spike_app.py

# Web mode (opens a server for live browser testing):
python 28-python-agent-demo-remove-before-merge/spike_2_4_state_of_art_for_dynamic_ui_update/spike_app.py --serve
# Then: open http://localhost:8042 and POST to http://localhost:8042/trigger
```
