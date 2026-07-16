# Implementation plan: Python Real Estate Agent Orchestrator Demo (28-python-agent-demo)

Human DRI: Ed Burns  
Reference C# demo: `src/AgentOrchestrator/`  
Python project root: `src/python_agent_orchestrator/`  
Reference Java plan: `BRK206-00/dd-3017826-java-real-estate-demo-remove-before-merge/dd-3017826-java-real-estate-demo-ignorance-reduction-plan.md`

---

## Goal

Create a Python analog of the C# Blazor AgentOrchestrator demo that showcases the GitHub Copilot SDK for Python. The demo should implement the same real-estate lead-management pipeline (Queued -> Validating -> Searching -> Writing Report -> Done/Rejected) powered by multiple concurrent agent sessions, custom tools, system message customization, and real-time UI updates.

### Technology stack

| Concern | Technology |
|---------|-----------|
| Runtime | CPython 3.12+ (virtualenv project) |
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
