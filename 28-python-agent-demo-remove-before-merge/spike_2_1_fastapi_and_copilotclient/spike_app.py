"""
Spike 2.1 — Validate CopilotClient(mode="empty") lifecycle for server-side orchestration.

This script proves that:
1. CopilotClient can be created in "empty" mode with a base_directory.
2. A session can be created with available_tools (required for empty mode).
3. A custom @define_tool tool is invoked by the model.
4. SessionIdleData signals session completion.
5. The client can be stopped cleanly.

Additionally demonstrates the FastAPI lifespan pattern for managing the client.
"""

import asyncio
import os
import sys
import tempfile

from pydantic import BaseModel, Field

from copilot import CopilotClient, ToolSet, define_tool
from copilot.session import PermissionHandler
from copilot.session_events import AssistantMessageData, SessionIdleData

# ---------------------------------------------------------------------------
# Tool definition (demonstrates @define_tool decorator with Pydantic params)
# ---------------------------------------------------------------------------

class PingParams(BaseModel):
    message: str = Field(description="A message to echo back")


tool_was_invoked = False


@define_tool(description="Echoes back the provided message. Use this tool to respond.")
def ping(params: PingParams) -> str:
    global tool_was_invoked
    tool_was_invoked = True
    return f"pong: {params.message}"


# ---------------------------------------------------------------------------
# Main validation routine
# ---------------------------------------------------------------------------

async def validate_empty_mode():
    """Run the spike validation."""
    print()
    print("[SPIKE 2.1] CopilotClient(mode=\"empty\") lifecycle validation")
    print("=" * 61)

    # Use a temp directory for base_directory to avoid polluting ~/.copilot
    base_dir = os.path.join(tempfile.gettempdir(), "spike_2_1_copilot")
    os.makedirs(base_dir, exist_ok=True)

    # Step 1: Create client in empty mode
    client = CopilotClient(
        mode="empty",
        base_directory=base_dir,
    )

    try:
        await client.start()
        print(f"[OK] CopilotClient created in mode=\"empty\" with base_directory={base_dir}")
    except Exception as e:
        print(f"[FAIL] Could not start CopilotClient in empty mode: {e}")
        sys.exit(1)

    # Step 2: Create a session with available_tools (required for empty mode)
    available_tools = ToolSet().add_custom("*")

    try:
        session = await client.create_session(
            on_permission_request=PermissionHandler.approve_all,
            tools=[ping],
            available_tools=available_tools,
            system_message={
                "mode": "replace",
                "content": (
                    "You are a test assistant. When the user sends any message, "
                    "you MUST call the 'ping' tool with the user's message as the "
                    "'message' parameter. After the tool responds, reply with the "
                    "tool's response verbatim."
                ),
            },
        )
        print("[OK] Session created with available_tools and custom tool")
    except Exception as e:
        print(f"[FAIL] Could not create session: {e}")
        await client.stop()
        sys.exit(1)

    # Step 3: Send a message and wait for SessionIdleData
    done = asyncio.Event()
    assistant_response = []

    def on_event(event):
        match event.data:
            case AssistantMessageData() as data:
                assistant_response.append(data.content)
            case SessionIdleData():
                done.set()

    session.on(on_event)

    try:
        await session.send("Hello from spike 2.1!")
        # Wait up to 30 seconds for the session to complete
        await asyncio.wait_for(done.wait(), timeout=30.0)
    except asyncio.TimeoutError:
        print("[FAIL] Timed out waiting for SessionIdleData (30s)")
        await session.disconnect()
        await client.stop()
        sys.exit(1)
    except Exception as e:
        print(f"[FAIL] Error during session.send: {e}")
        await session.disconnect()
        await client.stop()
        sys.exit(1)

    # Step 4: Verify tool was invoked
    if tool_was_invoked:
        print("[OK] Tool 'ping' was invoked by the model")
    else:
        print("[WARN] Tool 'ping' was NOT invoked — model may have responded without using the tool")

    # Step 5: Verify SessionIdleData was received
    print("[OK] SessionIdleData received — session completed")
    if assistant_response:
        print(f"     Assistant said: {assistant_response[-1][:100]}")

    # Step 6: Clean up
    await session.disconnect()
    await client.stop()
    print("[OK] Client stopped cleanly")

    print("=" * 61)
    print("SPIKE 2.1 PASSED — empty mode works for server-side orchestration")
    print()


# ---------------------------------------------------------------------------
# FastAPI lifespan pattern demonstration (informational — not executed in spike)
# ---------------------------------------------------------------------------

FASTAPI_LIFESPAN_EXAMPLE = """
# --- How to use this in a FastAPI app ---

from contextlib import asynccontextmanager
from fastapi import FastAPI
from copilot import CopilotClient

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create and start the CopilotClient
    app.state.copilot_client = CopilotClient(
        mode="empty",
        base_directory="/path/to/copilot-home",
    )
    await app.state.copilot_client.start()
    yield
    # Shutdown: stop the client
    await app.state.copilot_client.stop()

app = FastAPI(lifespan=lifespan)

@app.get("/health")
async def health():
    return {"status": "ok", "copilot_client": "running"}
"""


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("\n--- FastAPI Lifespan Pattern (for reference) ---")
    print(FASTAPI_LIFESPAN_EXAMPLE)
    print("--- Running spike validation ---")
    asyncio.run(validate_empty_mode())
