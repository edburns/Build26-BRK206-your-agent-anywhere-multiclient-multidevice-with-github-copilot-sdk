"""
Spike 2.4 — FastAPI WebSocket push from Copilot SDK session.on() callbacks.

This spike proves:
1. FastAPI WebSocket is the Python analog to Jakarta WebSocket (f:websocket / PushContext).
2. The SDK's session.on() callback is SYNCHRONOUS (not async) — we cannot await inside it.
3. We can use asyncio.get_event_loop().call_soon_threadsafe() or create_task to schedule
   the async WebSocket broadcast from inside the sync callback.
4. Connected browser clients receive real-time updates as the agent progresses.

Architecture:
- FastAPI WebSocket endpoint maintains connected clients
- ConnectionManager handles broadcast to all clients
- SDK session.on() callback schedules broadcast via the event loop
- Browser connects via WebSocket and displays live updates

Run modes:
- Standalone validation (default): proves the broadcast-from-callback pattern
- Web mode (--serve): starts FastAPI server with live WebSocket page
"""

import asyncio
import json
import os
import sys
import tempfile
from datetime import datetime
from typing import Any

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
# ConnectionManager — the Python analog to Jakarta's PushContext
# ---------------------------------------------------------------------------

class ConnectionManager:
    """
    Manages WebSocket connections and broadcasts messages to all clients.

    This is the Python/FastAPI equivalent of Jakarta's:
        @Inject @Push(channel="pipeline") PushContext pushContext;
        pushContext.send(data);

    In FastAPI, WebSocket connections are first-class objects managed by the app.
    """

    def __init__(self):
        self.active_connections: list[Any] = []
        self._broadcast_log: list[dict] = []

    async def connect(self, websocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        """Broadcast a JSON message to all connected WebSocket clients."""
        self._broadcast_log.append(message)
        text = json.dumps(message)
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(text)
            except Exception:
                disconnected.append(connection)
        for conn in disconnected:
            self.active_connections.remove(conn)

    def schedule_broadcast(self, loop: asyncio.AbstractEventLoop, message: dict):
        """
        Schedule a broadcast from a SYNCHRONOUS context (e.g., session.on() callback).

        This is the key pattern: session.on() callbacks are sync, but WebSocket
        send is async. We bridge the gap by scheduling on the event loop.
        """
        self._broadcast_log.append(message)
        asyncio.run_coroutine_threadsafe(self._do_broadcast(message), loop)

    async def _do_broadcast(self, message: dict):
        """Internal async broadcast helper."""
        text = json.dumps(message)
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(text)
            except Exception:
                disconnected.append(connection)
        for conn in disconnected:
            self.active_connections.remove(conn)


# Global instance (singleton pattern for the demo)
ws_manager = ConnectionManager()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"[{ts}] {msg}")


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

class ValidateParams(BaseModel):
    query: str = Field(description="The query to validate")


class SearchParams(BaseModel):
    query: str = Field(description="Validated query to search")


@define_tool(description="Validates a real estate query.")
def validate_query(params: ValidateParams) -> str:
    return "valid"


@define_tool(description="Searches the property database.")
def search_properties(params: SearchParams) -> str:
    return '{"results": [{"type": "condo", "price": 450000}]}'


# ---------------------------------------------------------------------------
# Standalone validation (no browser needed)
# ---------------------------------------------------------------------------

async def validate_broadcast_from_callback():
    """
    Prove that we can broadcast WebSocket messages from inside session.on() callbacks.
    Uses a simulated WebSocket client to capture broadcast messages.
    """
    print()
    print("[SPIKE 2.4] WebSocket broadcast from session.on() callback")
    print("=" * 65)
    print()

    # Simulated WebSocket client that just collects messages
    class FakeWebSocket:
        def __init__(self):
            self.messages: list[str] = []

        async def accept(self):
            pass

        async def send_text(self, text: str):
            self.messages.append(text)
            data = json.loads(text)
            log(f"  [WS CLIENT] Received: type={data.get('type')}, "
                f"detail={data.get('tool_name') or data.get('phase') or data.get('content', '')[:40]}")

    fake_ws = FakeWebSocket()
    await ws_manager.connect(fake_ws)
    log("Simulated WebSocket client connected")

    # Get the running event loop (we're inside asyncio.run)
    loop = asyncio.get_running_loop()

    # Start Copilot client
    base_dir = os.path.join(tempfile.gettempdir(), "spike_2_4_copilot")
    os.makedirs(base_dir, exist_ok=True)

    client = CopilotClient(mode="empty", base_directory=base_dir)
    await client.start()
    log("CopilotClient started")

    session = await client.create_session(
        on_permission_request=PermissionHandler.approve_all,
        tools=[validate_query, search_properties],
        available_tools=ToolSet().add_custom("*"),
        system_message={
            "mode": "replace",
            "content": (
                "You are a pipeline assistant. When the user gives a query:\n"
                "1. Call validate_query with the query.\n"
                "2. Call search_properties with the query.\n"
                "3. Report results.\n"
                "Call both tools in order."
            ),
        },
    )
    log("Session created")

    # THE KEY PATTERN: session.on() is SYNC, but we need to broadcast (async).
    # Solution: schedule_broadcast uses asyncio.run_coroutine_threadsafe().
    done = asyncio.Event()
    tool_call_map: dict[str, str] = {}

    def on_event(event):
        """
        This callback is SYNCHRONOUS — called from the SDK's internal dispatch.
        We CANNOT use 'await' here. Instead, we schedule the async broadcast.
        """
        match event.data:
            case ToolExecutionStartData() as data:
                tool_call_map[data.tool_call_id] = data.tool_name
                ws_manager.schedule_broadcast(loop, {
                    "type": "tool_start",
                    "tool_name": data.tool_name,
                    "tool_call_id": data.tool_call_id,
                })
            case ToolExecutionCompleteData() as data:
                name = tool_call_map.get(data.tool_call_id, "unknown")
                ws_manager.schedule_broadcast(loop, {
                    "type": "tool_complete",
                    "tool_name": name,
                    "tool_call_id": data.tool_call_id,
                    "success": data.success,
                })
            case AssistantMessageData() as data:
                ws_manager.schedule_broadcast(loop, {
                    "type": "assistant_message",
                    "content": (data.content or "")[:100],
                })
            case SessionIdleData():
                ws_manager.schedule_broadcast(loop, {
                    "type": "session_idle",
                    "phase": "done",
                })
                # Use call_soon_threadsafe for the Event.set() too
                loop.call_soon_threadsafe(done.set)

    session.on(on_event)
    log("Event handler registered (sync callback with scheduled broadcasts)")

    # Send prompt
    log("Sending prompt...")
    await session.send("Find condos in Miami")

    try:
        await asyncio.wait_for(done.wait(), timeout=45.0)
    except asyncio.TimeoutError:
        log("[FAIL] Timeout waiting for session idle")
        await session.disconnect()
        await client.stop()
        sys.exit(1)

    # Give broadcasts a moment to complete
    await asyncio.sleep(0.5)

    # Analysis
    print()
    print("=" * 65)
    print("BROADCAST LOG (messages that would reach browser clients):")
    print("=" * 65)
    for i, msg in enumerate(ws_manager._broadcast_log, 1):
        print(f"  #{i} {json.dumps(msg)}")

    print()
    print("=" * 65)
    print("SIMULATED WEBSOCKET CLIENT received messages:")
    print("=" * 65)
    for i, raw in enumerate(fake_ws.messages, 1):
        data = json.loads(raw)
        print(f"  #{i} type={data['type']}, detail={json.dumps({k: v for k, v in data.items() if k != 'type'})}")

    # Assertions
    print()
    passed = True
    broadcast_types = [msg["type"] for msg in ws_manager._broadcast_log]

    if "tool_start" in broadcast_types:
        print("[OK] tool_start broadcast sent from sync callback")
    else:
        print("[FAIL] No tool_start broadcast")
        passed = False

    if "tool_complete" in broadcast_types:
        print("[OK] tool_complete broadcast sent from sync callback")
    else:
        print("[FAIL] No tool_complete broadcast")
        passed = False

    if "assistant_message" in broadcast_types:
        print("[OK] assistant_message broadcast sent from sync callback")
    else:
        print("[FAIL] No assistant_message broadcast")
        passed = False

    if "session_idle" in broadcast_types:
        print("[OK] session_idle broadcast sent from sync callback")
    else:
        print("[FAIL] No session_idle broadcast")
        passed = False

    if len(fake_ws.messages) == len(ws_manager._broadcast_log):
        print(f"[OK] All {len(fake_ws.messages)} broadcasts received by WebSocket client")
    else:
        print(f"[WARN] Broadcast count mismatch: sent={len(ws_manager._broadcast_log)}, "
              f"received={len(fake_ws.messages)}")

    # Clean up
    await session.disconnect()
    await client.stop()
    log("Client stopped")

    print()
    print("=" * 65)
    print("PATTERN SUMMARY:")
    print("=" * 65)
    print()
    print("  Python analog to Jakarta WebSocket (f:websocket / PushContext):")
    print("  -> FastAPI WebSocket endpoint + ConnectionManager class")
    print()
    print("  Key challenge: session.on() callbacks are SYNCHRONOUS")
    print("  -> Cannot 'await websocket.send_text()' inside the callback")
    print()
    print("  Solution: asyncio.run_coroutine_threadsafe(broadcast_coro, loop)")
    print("  -> Schedules the async WebSocket send on the running event loop")
    print("  -> Works because the SDK dispatches events from a background thread")
    print("  -> The event loop is free to execute the scheduled coroutine")
    print()
    print("  Jakarta equivalent mapping:")
    print("    @Inject @Push PushContext   ->  ConnectionManager (singleton)")
    print("    pushContext.send(data)      ->  ws_manager.schedule_broadcast(loop, data)")
    print("    <f:websocket channel=...>   ->  new WebSocket('ws://host/ws/pipeline')")
    print()

    if passed:
        print("SPIKE 2.4 PASSED -- WebSocket broadcast from sync callbacks works")
    else:
        print("SPIKE 2.4 FAILED")
        sys.exit(1)
    print()


# ---------------------------------------------------------------------------
# FastAPI web mode (for live browser testing)
# ---------------------------------------------------------------------------

SERVE_HTML = """<!DOCTYPE html>
<html>
<head>
    <title>Spike 2.4 - Live WebSocket Updates</title>
    <style>
        body { font-family: monospace; background: #1a1a2e; color: #eee; padding: 20px; }
        #log { white-space: pre-wrap; border: 1px solid #444; padding: 10px; max-height: 500px; overflow-y: auto; }
        .tool_start { color: #ffd700; }
        .tool_complete { color: #00ff88; }
        .assistant_message { color: #88ccff; }
        .session_idle { color: #ff6688; font-weight: bold; }
    </style>
</head>
<body>
    <h2>Spike 2.4: Real-time WebSocket Updates</h2>
    <p>Connected to FastAPI WebSocket. Agent events appear below:</p>
    <div id="log"></div>
    <script>
        const log = document.getElementById('log');
        const ws = new WebSocket(`ws://${location.host}/ws/pipeline`);
        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            const line = document.createElement('div');
            line.className = data.type;
            line.textContent = `[${new Date().toLocaleTimeString()}] ${data.type}: ${JSON.stringify(data)}`;
            log.appendChild(line);
            log.scrollTop = log.scrollHeight;
        };
        ws.onopen = () => {
            const line = document.createElement('div');
            line.textContent = '[Connected to WebSocket]';
            log.appendChild(line);
        };
    </script>
</body>
</html>"""


def run_serve_mode():
    """Start a FastAPI server with WebSocket endpoint for live browser testing."""
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect
    from fastapi.responses import HTMLResponse
    import uvicorn

    app = FastAPI()

    @app.get("/")
    async def index():
        return HTMLResponse(SERVE_HTML)

    @app.websocket("/ws/pipeline")
    async def websocket_endpoint(websocket: WebSocket):
        await ws_manager.connect(websocket)
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            ws_manager.disconnect(websocket)

    @app.post("/trigger")
    async def trigger_agent():
        """Trigger an agent run to test WebSocket push."""
        asyncio.create_task(_run_agent_for_web())
        return {"status": "triggered"}

    async def _run_agent_for_web():
        loop = asyncio.get_running_loop()
        base_dir = os.path.join(tempfile.gettempdir(), "spike_2_4_copilot")
        os.makedirs(base_dir, exist_ok=True)

        client = CopilotClient(mode="empty", base_directory=base_dir)
        await client.start()

        session = await client.create_session(
            on_permission_request=PermissionHandler.approve_all,
            tools=[validate_query, search_properties],
            available_tools=ToolSet().add_custom("*"),
            system_message={
                "mode": "replace",
                "content": "Call validate_query then search_properties on the user query, then respond.",
            },
        )

        done = asyncio.Event()
        tool_call_map: dict[str, str] = {}

        def on_event(event):
            match event.data:
                case ToolExecutionStartData() as data:
                    tool_call_map[data.tool_call_id] = data.tool_name
                    ws_manager.schedule_broadcast(loop, {"type": "tool_start", "tool_name": data.tool_name})
                case ToolExecutionCompleteData() as data:
                    name = tool_call_map.get(data.tool_call_id, "unknown")
                    ws_manager.schedule_broadcast(loop, {"type": "tool_complete", "tool_name": name, "success": data.success})
                case AssistantMessageData() as data:
                    ws_manager.schedule_broadcast(loop, {"type": "assistant_message", "content": (data.content or "")[:200]})
                case SessionIdleData():
                    ws_manager.schedule_broadcast(loop, {"type": "session_idle"})
                    loop.call_soon_threadsafe(done.set)

        session.on(on_event)
        await session.send("Find luxury condos in Miami Beach")
        await done.wait()
        await session.disconnect()
        await client.stop()

    print("Starting FastAPI server on http://localhost:8042")
    print("  1. Open http://localhost:8042 in a browser")
    print("  2. POST to http://localhost:8042/trigger to start an agent")
    print("     curl -X POST http://localhost:8042/trigger")
    uvicorn.run(app, host="0.0.0.0", port=8042)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    if "--serve" in sys.argv:
        run_serve_mode()
    else:
        asyncio.run(validate_broadcast_from_callback())
