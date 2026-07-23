"""WebSocket connection manager for real-time pipeline push updates.

This is the Python/FastAPI equivalent of Jakarta's PushContext (@Push).
The key challenge: session.on() callbacks from the Copilot SDK are SYNCHRONOUS,
but FastAPI WebSocket sends are async.  The schedule_broadcast() method bridges
this gap via asyncio.run_coroutine_threadsafe().

See spike_2_4_state_of_art_for_dynamic_ui_update for full analysis.
"""

import asyncio
import json
from typing import Any


class ConnectionManager:
    """Manages WebSocket connections and broadcasts messages to all clients."""

    def __init__(self) -> None:
        self.connections: list[Any] = []
        self._broadcast_lock = asyncio.Lock()

    async def connect(self, ws: Any) -> None:
        """Accept and register a new WebSocket connection."""
        await ws.accept()
        self.connections.append(ws)

    def disconnect(self, ws: Any) -> None:
        """Remove a WebSocket connection."""
        if ws in self.connections:
            self.connections.remove(ws)

    async def broadcast(self, message: dict) -> None:
        """Broadcast a JSON message to all connected WebSocket clients.

        Serialized with an async lock so concurrent schedule_broadcast() calls
        do not interleave send_text() on the same WebSocket.
        """
        async with self._broadcast_lock:
            text = json.dumps(message)
            disconnected = []
            for connection in list(self.connections):
                try:
                    await connection.send_text(text)
                except Exception:  # noqa: BLE001 — any send failure means the client disconnected
                    disconnected.append(connection)
            for conn in disconnected:
                if conn in self.connections:
                    self.connections.remove(conn)

    def schedule_broadcast(self, loop: asyncio.AbstractEventLoop, message: dict) -> None:
        """Bridge from sync SDK callback to async WebSocket broadcast.

        session.on() callbacks are synchronous — we cannot await inside them.
        This method schedules the async broadcast on the already-running event loop
        using asyncio.run_coroutine_threadsafe(), which is safe to call from any thread.
        """
        asyncio.run_coroutine_threadsafe(self.broadcast(message), loop)


# Module-level singleton used by main.py and agent.py
ws_manager = ConnectionManager()
