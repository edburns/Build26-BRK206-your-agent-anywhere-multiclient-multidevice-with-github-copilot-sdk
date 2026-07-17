# Implementation plan: Python Real Estate Agent Orchestrator Demo (28-python-agent-demo)

Human DRI: Ed Burns  
Reference C# demo: `src/AgentOrchestrator/`  
Reference Java demo: `src/java-agent-orchestrator/`  
Python project root: `src/python_agent_orchestrator/`  
Reference Java plan: `BRK206-00/dd-3017826-java-real-estate-demo-remove-before-merge/dd-3017826-java-real-estate-demo-ignorance-reduction-plan.md`

---

## Goal

Create a Python analog of the C# Blazor AgentOrchestrator demo that showcases the GitHub Copilot SDK for Python. The demo should implement the same real-estate lead-management pipeline (Queued -> Validating -> Searching -> Writing Report -> Done/Rejected) powered by multiple concurrent agent sessions, custom tools, system message customization, and real-time UI updates.

### Technology stack

| Concern | Technology |
|---------|-----------|
| Runtime | CPython 3.14 (virtualenv project) |
| Backend web framework | FastAPI (ASGI, asyncio-native) |
| ASGI server | Uvicorn |
| UI framework | Server-rendered Jinja2 + HTMX + Alpine.js + Tailwind CSS |
| Real-time updates | FastAPI WebSocket endpoint broadcasting pipeline state changes |
| Animation model | CSS transitions/keyframes for box-to-box movement + yellow pulsing in-progress indicator |
| AI orchestration | GitHub Copilot SDK for Python (latest stable at implementation time) |
| Database | SQLite (in-memory for demo mode) via SQLModel |
| Build / dependency management | `pyproject.toml` + editable install (`pip install -e .[dev]`), with `uv` as optional fast path |
| Tooling | `pytest`, `pytest-asyncio`, `ruff`, `pyright` |

### SDK features to demonstrate

1. Custom tool definition for property lookup, report intent, and pipeline status updates.
2. Agentic session loop equivalent to the Java/C# flow (send message, wait for assistant/tool activity, continue).
3. System message customization per agent role.
4. Built-in tool composition (`web_fetch`) where relevant to user requests.
5. Real-time session event handling for UI updates.
6. Headless server-side Copilot client usage for backend orchestration.
7. Multiple concurrent sessions (one per enquiry).
8. Explicit permission handling strategy for demo-safe automation.
9. Override/extension behavior for built-in tools where needed to preserve C# demo parity.

---

## Phase 1 — Define the architecture mapping (C# → Python)

### 1.1 — Component mapping

| C# Component | Python Equivalent | Notes |
|---|---|---|
| `Program.cs` (WebApplication builder) | `main.py` (FastAPI app factory + Uvicorn entrypoint) | ASGI app with lifespan handler for startup/shutdown |
| `AppState.cs` (singleton) | `app_state.py` module-level singleton or FastAPI dependency | Holds `CopilotClient` and active agents dict |
| `Agent.cs` | `agent.py` — async class with `run()` coroutine | Each agent owns a `CopilotSession`; runs as `asyncio.Task` |
| `PropertyDatabase.cs` | `property_database.py` — SQLModel + async session | SQLite in-memory backend |
| `PropertyDbContext` (EF Core) | SQLModel `Session` (wraps SQLAlchemy async) | Standard ORM approach |
| Blazor Server interactive render | Jinja2 templates + HTMX partial swaps + Alpine.js state | Server-rendered with progressive enhancement |
| `Session.On<SessionEvent>` | `session.on(callback)` | Callback pushes update via WebSocket |
| `CopilotTool.DefineTool(method)` | `@define_tool` decorator with Pydantic params | SDK's decorator-based tool API |
| `async Task RunAsync(...)` | `async def run(...)` as `asyncio.Task` | Native Python async/await |
| Tailwind CSS + Blazor components | Tailwind CSS + HTMX `hx-swap` + Alpine.js | ~80% declarative; animation is custom CSS/JS |

### 1.2 — Threading/concurrency model

| C# | Python |
|---|---|
| `Task.Run(() => agent.RunAsync(client))` | `asyncio.create_task(agent.run(client))` |
| `await Session.SendAndWaitAsync(...)` | `await session.send(...)` + `await done_event.wait()` |
| `Task.Delay(15000)` | `await asyncio.sleep(15)` |
| `event Action? UpdateUi` / `InvokeAsync(StateHasChanged)` | WebSocket broadcast via `ConnectionManager.broadcast(json)` |

### 1.3 — Project structure

```
src/python_agent_orchestrator/
├── pyproject.toml
├── README.md
├── src/
│   └── python_agent_orchestrator/
│       ├── __init__.py
│       ├── main.py              (FastAPI app, lifespan, routes)
│       ├── app_state.py         (singleton: CopilotClient + agents registry)
│       ├── agent.py             (Agent class: session, tools, run loop)
│       ├── phase.py             (Phase enum)
│       ├── models.py            (SQLModel: Property, Address)
│       ├── property_database.py (search logic, seed data loader)
│       ├── ws_manager.py        (WebSocket connection manager for real-time push)
│       ├── templates/
│       │   ├── base.html        (layout: Tailwind + Alpine.js + HTMX head)
│       │   ├── index.html       (pipeline view with stage columns)
│       │   └── partials/
│       │       ├── pipeline.html    (HTMX partial: all agent cards in stages)
│       │       └── agent_detail.html (HTMX partial: event stream + tool calls)
│       └── static/
│           ├── css/
│           │   └── pipeline.css (dark theme, animations, pulse keyframes)
│           └── js/
│               └── pipeline.js  (WebSocket client, FLIP animation, Alpine data)
├── data/
│   └── properties/              (100 JSON seed files copied from C# demo)
└── tests/
    ├── conftest.py
    ├── test_agent.py
    ├── test_property_database.py
    └── test_ws_manager.py
```

### 1.4 — SDK API mapping (C# → Python)

| C# SDK Concept | Python SDK Equivalent | Source |
|---|---|---|
| `new CopilotClient(CopilotClientMode.Empty, ...)` | `CopilotClient(mode="empty", ...)` | `copilot/_mode.py` |
| `client.CreateSessionAsync(config)` | `await client.create_session(tools=[...], system_message={...}, ...)` | `copilot/client.py` |
| `session.SendAndWaitAsync(msg)` | `await session.send(msg)` + event-driven `SessionIdleData` signal | `copilot/session.py` |
| `session.On<AssistantMessageEvent>(...)` | `session.on(callback)` matching `AssistantMessageData` | `copilot/session.py` |
| `PermissionHandler.ApproveAll` | `PermissionHandler.approve_all` | `copilot/session.py` |
| `CopilotTool.DefineTool(method)` | `@define_tool(description="...")` decorator | `copilot/tools.py` |
| `OverridesBuiltInTool = true` | `overrides_built_in_tool=True` kwarg on `@define_tool` | `copilot/tools.py` |
| `ToolSet().AddCustom("*").AddBuiltIn("web_fetch")` | `ToolSet().add_custom("*").add_builtin("web_fetch")` | `copilot/_mode.py` |
| `SystemMessageConfig { Sections = [...] }` | `system_message={"mode": "customize", "sections": {...}}` | README §System Message |

---

## Phase 2 — Ignorance reduction: questions to answer before writing code

### 2.1 — CopilotClient lifecycle in FastAPI

**Question:** How should `CopilotClient` be created and managed in a FastAPI app?

The C# demo creates `CopilotClient` as a singleton in `AppState`. In Python, `CopilotClient` is an async context manager (`async with CopilotClient() as client`). We need:

1. A FastAPI lifespan handler that creates the client on startup and calls `stop()` on shutdown.
2. A decision on whether to use `mode="empty"` (headless, no workspace context) or default `"copilot-cli"` mode.

**Spike needed:** Confirm that `CopilotClient(mode="empty")` works for server-side orchestration without a VS Code host. Verify what `available_tools` / `ToolSet` configuration is required in `"empty"` mode (the `_mode.py` source shows `_require_available_tools_for_empty_mode`).

**Resolution:**

**✅ RESOLVED (2026-07-17):** Confirmed. `CopilotClient(mode="empty", base_directory=...)` works for headless server-side orchestration. Spike app: `28-python-agent-demo-remove-before-merge/spike_2_1_fastapi_and_copilotclient/`.

Key findings:
1. **`mode="empty"` requires `base_directory`** — without it, the SDK raises `ValueError` ("requires base_directory, session_fs, or a UriRuntimeConnection").
2. **`available_tools` is required per-session** — empty mode raises `ValueError` if `create_session()` is called without `available_tools`. Use `ToolSet().add_custom("*")` to allow all custom tools.
3. **FastAPI lifespan pattern works perfectly** — `client.start()` on startup, `client.stop()` on shutdown.
4. **Tool invocation confirmed** — `@define_tool` with Pydantic params works end-to-end; model invokes tools and SDK handles the loop automatically.
5. **`SessionIdleData` signals completion** — reliable signal that the agentic loop has finished.

Python construction pattern for the demo:
```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from copilot import CopilotClient

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.copilot_client = CopilotClient(
        mode="empty",
        base_directory=os.path.join(Path.home(), ".copilot"),
    )
    await app.state.copilot_client.start()
    yield
    await app.state.copilot_client.stop()

app = FastAPI(lifespan=lifespan)
```

### 2.2 — Session send-and-wait pattern in Python SDK

**Question:** The C# demo uses `session.SendAndWaitAsync(prompt)` which loops internally until the model finishes (calling tools, etc.). The Python SDK's `session.send(msg)` appears to just send the message — completion is signaled by a `SessionIdleData` event. How do we replicate the "fire-and-forget agentic loop" pattern?

Expected pattern:
```python
done = asyncio.Event()
session.on(lambda ev: done.set() if isinstance(ev.data, SessionIdleData) else None)
await session.send(prompt)
await done.wait()
```

**Spike needed:** Confirm this pattern handles multi-turn tool calls correctly (i.e., the SDK internally handles tool execution and only fires `SessionIdleData` after the model produces a final assistant message with no pending tool calls). Verify with a simple tool that the above pattern works end-to-end.

**Resolution:** *(to be filled after spike)*

### 2.3 — Session event subscription and types

**Question:** What events does the Python SDK emit, and how do we subscribe to specific event types for UI updates?

From the source code, `session.on(callback)` receives `SessionEvent` instances with a `.data` field that is pattern-matched:
- `AssistantMessageData` — final assistant message
- `SessionIdleData` — session finished processing
- `ExternalToolRequestedData` — for declaration-only tools
- `SessionErrorData` — errors
- `PermissionRequestedData` — permission requests

**Spike needed:** Confirm there is a `ToolExecutionCompleteData` or equivalent event (for UI showing tool call progress). If not, determine how to detect individual tool call completions for real-time UI updates.

**Resolution:** *(to be filled after spike)*

### 2.4 — WebSocket push from asyncio to browser

**Question:** How do we push UI updates from an `asyncio.Task` (running the agent) to the browser in real time?

Proposed pattern:
- `ws_manager.py` maintains a set of active WebSocket connections
- Agent callbacks call `await ws_manager.broadcast(json_msg)` when phase changes
- Browser JS receives WebSocket message and triggers HTMX partial swap or Alpine.js state update

**Spike needed:** Verify that broadcasting from inside a `session.on()` callback works correctly (since the callback may run on a different asyncio context or be synchronous). Determine if we need `asyncio.run_coroutine_threadsafe()` or if the SDK's event dispatch is already on the event loop.

**Resolution:** *(to be filled after spike)*

### 2.5 — Property database: SQLModel + SQLite in-memory

**Question:** Can SQLModel handle async operations with SQLite in-memory for the property search?

SQLModel wraps SQLAlchemy. For async, we'd use `aiosqlite` + `create_async_engine`. Alternatively, since the database is read-only after seeding, synchronous access may be simpler and sufficient.

**Spike needed:** Confirm that SQLModel with `sqlite:///:memory:` (synchronous) works in a FastAPI app without blocking the event loop (given that all queries are fast reads from a pre-seeded in-memory DB). If blocking is a concern, confirm `aiosqlite` works with SQLModel.

**Resolution:** *(to be filled after spike)*

### 2.6 — HTMX + WebSocket real-time UI update pattern

**Question:** What is the exact client-side pattern for updating the pipeline UI when a WebSocket message arrives?

Options:
| Option | Mechanism |
|--------|-----------|
| A | WebSocket message triggers HTMX `hx-trigger` on a hidden element → server-side partial re-render |
| B | WebSocket message triggers Alpine.js reactive state update (client-side DOM manipulation) |
| C | Hybrid: Alpine.js for immediate visual feedback + HTMX `hx-get` for full state reconciliation |

**Recommendation:** Option C — Alpine.js handles immediate state transitions and animations; HTMX fetches authoritative server-rendered partials for reconciliation.

**Spike needed:** Build a minimal FastAPI + HTMX + Alpine.js + WebSocket prototype that demonstrates an item moving between columns with CSS animation on WebSocket push. Validate that FLIP animation works with HTMX morphing/swapping.

**Resolution:** *(to be filled after spike)*

### 2.7 — Tool definition approach for this demo

**Question:** How should the three demo tools be defined using the Python SDK?

Based on the SDK's `@define_tool` decorator API and the Java demo's mixed-style approach:

| Tool | Style | Rationale |
|------|-------|-----------|
| `set_current_phase` | `@define_tool` decorator with Pydantic params | Shows headline decorator ergonomics |
| `report_intent` | `@define_tool(overrides_built_in_tool=True)` | Shows built-in tool override |
| `search_properties` | `@define_tool` decorator with multi-field Pydantic model | Shows rich parameter schema generation |

Example `set_current_phase`:
```python
class SetPhaseParams(BaseModel):
    phase: Phase = Field(description="The phase to transition to")

@define_tool(description="Sets the current phase of the agent. Use this to report progress.")
def set_current_phase(params: SetPhaseParams) -> str:
    agent.phase = params.phase
    agent.notify_ui()
    return "ok"
```

Example `report_intent` (override):
```python
class ReportIntentParams(BaseModel):
    intent: str = Field(description="Intent in max 4 words")

@define_tool(
    name="report_intent",
    description="Reports the current intent of the agent",
    overrides_built_in_tool=True,
)
def report_intent(params: ReportIntentParams) -> str:
    agent.current_intent = params.intent
    agent.notify_ui()
    return "ok"
```

**Question:** The tools reference `agent` instance state. In the Python SDK, tools receive a `ToolInvocation` context but not the agent. How do we bind tools to a specific agent instance?

**Spike needed:** Determine if tools are defined per-session (allowing closure over agent instance) or must be module-level singletons. If per-session, confirm that defining tools inside a method/factory works with `@define_tool`.

**Resolution:** *(to be filled after spike)*

### 2.8 — System message customization for the real-estate workflow

**Question:** What system message configuration replicates the C# demo's multi-phase workflow instructions?

The C# demo uses `SystemMessageSection` with `SectionOverrideAction.Replace` on the identity section. The Python SDK supports:
```python
system_message={
    "mode": "customize",
    "sections": {
        "identity": {"action": "replace", "content": "You are a real-estate lead validation agent..."},
    },
}
```

**Spike needed:** Confirm that `"mode": "customize"` with `"identity"` section replacement works and the agent receives the custom instructions correctly. Test that the agent follows the multi-phase workflow (validate → search → report) with appropriate tool calls.

**Resolution:** *(to be filled after spike)*

### 2.9 — `mode="empty"` + ToolSet configuration

**Question:** The C# demo uses `CopilotClientMode.Empty` and explicitly adds `web_fetch` as a built-in tool. How is this configured in Python?

From `_mode.py`, `mode="empty"` requires explicit `available_tools` on session creation. The `ToolSet` builder pattern:
```python
from copilot import ToolSet

available_tools = ToolSet().add_custom("*").add_builtin("web_fetch")

session = await client.create_session(
    tools=[set_current_phase, report_intent, search_properties],
    available_tools=available_tools,
    ...
)
```

**Spike needed:** Verify that `mode="empty"` + `available_tools` + custom tools works end-to-end. Confirm what `base_directory` value to use (the Java demo uses `~/.copilot`).

**Resolution:** *(to be filled after spike)*

### 2.10 — Multiple concurrent sessions

**Question:** Can we create multiple `CopilotSession` instances from a single `CopilotClient` concurrently?

The C# demo spawns multiple agents, each with their own session, against the same client. In Python, this would be multiple `asyncio.Task`s each calling `client.create_session()`.

**Spike needed:** Confirm that multiple concurrent sessions work without interference. Test with 2-3 sessions sending messages simultaneously.

**Resolution:** *(to be filled after spike)*

---

## Phase 3 — Implementation (build order)

Each step should be a separately testable commit.

### 3.1 — Project scaffolding

**What:** Create `pyproject.toml`, directory structure, virtualenv setup, basic FastAPI app.

**Key files:**
- `pyproject.toml` — dependencies (FastAPI, Uvicorn, SQLModel, Jinja2, github-copilot-sdk, Pydantic, aiosqlite)
- `src/python_agent_orchestrator/__init__.py`
- `src/python_agent_orchestrator/main.py` — minimal FastAPI app with health endpoint

**Gating criteria:** `pip install -e .[dev]` succeeds; `uvicorn python_agent_orchestrator.main:app` starts and responds to `/health`.

### 3.2 — Domain model and database seeding

**What:** SQLModel models (`Property`, `Address`), in-memory SQLite engine, JSON data loader.

**Key files:**
- `models.py` — SQLModel classes
- `property_database.py` — search method, seed data loader
- Copy 100 JSON seed files from C# demo's `Data/Properties/`

**Gating criteria:** Application starts, seeds database, `PropertyDatabase.search(...)` returns results. Unit test passes.

### 3.3 — Core agent infrastructure

**What:** `Phase` enum, `Agent` class, `AppState` module, `CopilotClient` lifecycle.

**Key files:**
- `phase.py` — `Phase` enum (Queued, Validating, Searching, WritingReport, Done, Rejected)
- `agent.py` — holds session, defines tools via `@define_tool`, implements `run()` coroutine
- `app_state.py` — manages agents dict, owns `CopilotClient` lifecycle

**Gating criteria:** Agent constructs with `CopilotSession`, sends enquiry, tools get invoked, phase transitions occur (validated via logs or unit test with mock).

### 3.4 — WebSocket push infrastructure

**What:** FastAPI WebSocket endpoint + connection manager for real-time UI updates.

**Key files:**
- `ws_manager.py` — `ConnectionManager` class (connect, disconnect, broadcast)
- WebSocket route in `main.py`
- Agent integration — calls `broadcast()` on phase change

**Gating criteria:** Phase changes push to browser; browser receives WebSocket messages with agent state JSON.

### 3.5 — Pipeline UI (static layout)

**What:** The main page with pipeline stages, agent cards, and the "+" button overlay.

**Key files:**
- `templates/base.html` — Tailwind + Alpine.js + HTMX boilerplate
- `templates/index.html` — pipeline layout with stage columns
- `templates/partials/pipeline.html` — HTMX partial for agent cards
- `static/css/pipeline.css` — dark theme, grid layout matching C# demo

**Gating criteria:** Page renders the pipeline stages with correct layout. Static sample cards display in correct positions.

### 3.6 — Dynamic UI updates and animation

**What:** Wire WebSocket messages to DOM updates with FLIP animation and pulsing indicator.

**Key files:**
- `static/js/pipeline.js` — WebSocket client, FLIP animation, Alpine.js reactive state
- `static/css/pipeline.css` — `@keyframes pulse` animation, CSS transitions
- HTMX partial swap integration for state reconciliation

**Gating criteria:** Enquiry cards animate between pipeline stages. Yellow pulse indicator follows the active card.

### 3.7 — Agent detail view

**What:** Side panel showing session events, tool calls, and agent report for a selected agent.

**Key files:**
- `templates/partials/agent_detail.html` — event stream and tool call display
- HTMX route for fetching agent detail
- WebSocket updates for real-time event streaming

**Gating criteria:** Clicking an agent card shows its event stream and tool interactions in real time.

### 3.8 — End-to-end integration testing

**What:** Verify the full demo works against a real Copilot CLI runtime.

**Testing approaches:**
- With real CLI: ensure `github-copilot-sdk` runtime is downloaded, run FastAPI, submit enquiries, observe pipeline
- Mock mode: pytest with mocked `CopilotClient` for CI/CD

**Gating criteria:** Full pipeline flow (Queued → Validating → Searching → Writing Report → Done) completes for a valid enquiry; invalid enquiry reaches Rejected state.

---

## Research spikes needed

Based on the unknowns above, the following research spikes are recommended before implementation begins:

### Spike A — Python SDK server-side orchestration pattern

**Goal:** Prove that `CopilotClient(mode="empty")` + custom tools + `session.send()` + `SessionIdleData` event-driven completion works end-to-end in a headless server context (no VS Code, no TUI).

**Covers questions:** 2.1, 2.2, 2.3, 2.9, 2.10

**Deliverable:** A minimal Python script that:
1. Creates a `CopilotClient` in `"empty"` mode
2. Creates a session with one custom `@define_tool` tool and `web_fetch` built-in
3. Sends a prompt that triggers the tool
4. Waits for `SessionIdleData`
5. Creates a second concurrent session to prove multi-session works

**Location:** `28-python-agent-demo-remove-before-merge/spike-a-server-orchestration/`

### Spike B — FastAPI + HTMX + WebSocket real-time UI

**Goal:** Prove the UI update pattern (WebSocket push → Alpine.js state change → CSS animation → HTMX partial reconciliation) works with FastAPI.

**Covers questions:** 2.4, 2.6

**Deliverable:** A minimal FastAPI app with:
1. A WebSocket endpoint that broadcasts "phase changed" messages
2. An HTMX page with cards in columns
3. Alpine.js reactive state that moves cards between columns on WebSocket message
4. CSS FLIP animation for the card movement
5. Yellow pulse CSS animation on the active card

**Location:** `28-python-agent-demo-remove-before-merge/spike-b-realtime-ui/`

### Spike C — Tool-to-agent binding

**Goal:** Confirm that `@define_tool`-decorated functions can close over agent instance state (or receive it via `ToolInvocation` context).

**Covers questions:** 2.7

**Deliverable:** A test showing tools defined inside a factory function that captures an agent instance, registered per-session, and correctly mutating agent state on invocation.

**Location:** `28-python-agent-demo-remove-before-merge/spike-c-tool-binding/`

