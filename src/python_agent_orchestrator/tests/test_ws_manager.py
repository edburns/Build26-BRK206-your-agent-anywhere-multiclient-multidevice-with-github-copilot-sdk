"""Tests for ConnectionManager and the /ws/pipeline WebSocket endpoint."""

import asyncio
import json

import pytest
from fastapi.testclient import TestClient

from python_agent_orchestrator import main
from python_agent_orchestrator.ws_manager import ConnectionManager


# ---------------------------------------------------------------------------
# ConnectionManager unit tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_connect_adds_websocket_to_connections() -> None:
    manager = ConnectionManager()
    assert manager.connections == []

    class FakeWS:
        async def accept(self) -> None:
            pass

    ws = FakeWS()
    await manager.connect(ws)
    assert ws in manager.connections


@pytest.mark.asyncio
async def test_disconnect_removes_websocket() -> None:
    manager = ConnectionManager()

    class FakeWS:
        async def accept(self) -> None:
            pass

    ws = FakeWS()
    await manager.connect(ws)
    manager.disconnect(ws)
    assert ws not in manager.connections


@pytest.mark.asyncio
async def test_disconnect_noop_when_not_connected() -> None:
    """disconnect() on an unknown socket must not raise."""
    manager = ConnectionManager()

    class FakeWS:
        async def accept(self) -> None:
            pass

    manager.disconnect(FakeWS())  # should not raise


@pytest.mark.asyncio
async def test_broadcast_sends_json_to_all_connections() -> None:
    manager = ConnectionManager()
    received: list[str] = []

    class FakeWS:
        async def accept(self) -> None:
            pass

        async def send_text(self, text: str) -> None:
            received.append(text)

    ws1 = FakeWS()
    ws2 = FakeWS()
    await manager.connect(ws1)
    await manager.connect(ws2)

    await manager.broadcast({"type": "tool_start", "queryId": "q-1", "toolName": "search"})

    assert len(received) == 2
    parsed = [json.loads(m) for m in received]
    assert all(m["type"] == "tool_start" for m in parsed)
    assert all(m["queryId"] == "q-1" for m in parsed)


@pytest.mark.asyncio
async def test_broadcast_removes_disconnected_clients() -> None:
    """Clients that raise on send_text are removed from the list."""
    manager = ConnectionManager()

    class BrokenWS:
        async def accept(self) -> None:
            pass

        async def send_text(self, text: str) -> None:
            raise OSError("disconnected")

    ws = BrokenWS()
    await manager.connect(ws)
    assert ws in manager.connections

    await manager.broadcast({"type": "session_idle"})
    assert ws not in manager.connections


def test_schedule_broadcast_bridges_sync_to_async() -> None:
    """schedule_broadcast() must deliver the message via the event loop."""
    manager = ConnectionManager()
    received: list[str] = []
    broadcast_done = None  # will be an asyncio.Event once the loop is running

    class FakeWS:
        async def accept(self) -> None:
            pass

        async def send_text(self, text: str) -> None:
            received.append(text)
            broadcast_done.set()

    async def run() -> None:
        nonlocal broadcast_done
        broadcast_done = asyncio.Event()
        loop = asyncio.get_running_loop()
        await manager.connect(FakeWS())
        # simulate a sync SDK callback calling schedule_broadcast
        manager.schedule_broadcast(loop, {"type": "phase_change", "queryId": "q-1", "phase": "Searching"})
        # wait for broadcast to complete with a timeout instead of an arbitrary sleep
        await asyncio.wait_for(broadcast_done.wait(), timeout=5.0)

    asyncio.run(run())
    assert len(received) == 1
    assert json.loads(received[0])["type"] == "phase_change"


# ---------------------------------------------------------------------------
# WebSocket endpoint integration test
# ---------------------------------------------------------------------------


def test_websocket_pipeline_accepts_connection(monkeypatch) -> None:
    """Verify that /ws/pipeline accepts a WebSocket connection without error."""
    class FakeCopilotClient:
        async def start(self) -> None:
            pass

        async def stop(self) -> None:
            pass

    monkeypatch.setattr(main, "_create_copilot_client", lambda: FakeCopilotClient())

    with TestClient(main.app) as client:
        with client.websocket_connect("/ws/pipeline") as ws:
            # The endpoint is a push-only channel; clients can send text (ignored)
            # and wait for server-pushed JSON messages.  Verify the connection
            # is accepted without raising.
            ws.send_text("ping")


def test_websocket_pipeline_endpoint_is_registered() -> None:
    """The /ws/pipeline route must be present in the application router."""
    routes = {r.path for r in main.app.routes}  # type: ignore[attr-defined]
    assert "/ws/pipeline" in routes
