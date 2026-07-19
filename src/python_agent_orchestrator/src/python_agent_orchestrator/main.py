import asyncio
from contextlib import asynccontextmanager
from datetime import UTC, datetime
import logging
import os
from pathlib import Path
from typing import TypedDict

import uvicorn
from copilot import CopilotClient
from fastapi import Body, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field, field_validator

from python_agent_orchestrator.agent import Agent
from python_agent_orchestrator.app_state import AppState
from python_agent_orchestrator.phase import Phase
from python_agent_orchestrator.property_database import (
    create_engine_and_tables,
    seed_database,
)
from python_agent_orchestrator.ws_manager import ws_manager

logger = logging.getLogger(__name__)

_PACKAGE_DIR = Path(__file__).resolve().parent
_DATA_DIR = Path(
    os.getenv("PROPERTY_DATA_DIR", "")
    or _PACKAGE_DIR.parent.parent / "data" / "properties"
)
_COPILOT_BASE_DIRECTORY = Path(
    os.getenv("COPILOT_BASE_DIRECTORY") or Path.home() / ".copilot"
)
_TEMPLATES_DIR = _PACKAGE_DIR / "templates"
_STATIC_DIR = _PACKAGE_DIR / "static"
_DEFAULT_QUERY_PREFIX = "Property search request #"
_LIFECYCLE_PHASES = [
    Phase.QUEUED.value,
    Phase.VALIDATING.value,
    Phase.SEARCHING.value,
    Phase.WRITING_REPORT.value,
]
_PIPELINE_PHASES = [phase.value for phase in Phase]


class QueryState(TypedDict):
    id: str
    text: str
    phase: str
    intent: str


class DashboardState(TypedDict):
    processing: int
    completed: int
    rejected: int


class PipelineState(TypedDict):
    queries: dict[str, QueryState]
    columns: dict[str, list[QueryState]]
    dashboard: DashboardState


class EndStateMapping(TypedDict):
    phase: str
    label: str
    box_class: str
    card_class: str


class SubmitQueryPayload(BaseModel):
    query: str | None = Field(default=None, max_length=200)

    @field_validator("query")
    @classmethod
    def normalize_query(cls, value: str | None) -> str | None:
        return value.strip() if value else value


_END_STATE_MAPPINGS: dict[str, EndStateMapping] = {
    Phase.VALIDATING.value: {
        "phase": Phase.REJECTED.value,
        "label": "Rejected",
        "box_class": "end-rejected",
        "card_class": "rejected",
    },
    Phase.SEARCHING.value: {
        "phase": Phase.NO_MATCHES.value,
        "label": "No Matches",
        "box_class": "end-no-matches",
        "card_class": "rejected",
    },
    Phase.WRITING_REPORT.value: {
        "phase": Phase.DONE.value,
        "label": "Done",
        "box_class": "end-done",
        "card_class": "done",
    },
}

templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")


def _resolve_copilot_base_directory() -> Path:
    trusted_root = Path.home().resolve()
    base_directory = _COPILOT_BASE_DIRECTORY.expanduser().resolve()
    if not base_directory.is_relative_to(trusted_root):
        raise ValueError(
            "COPILOT_BASE_DIRECTORY must be within the current user's home directory."
        )
    base_directory.mkdir(parents=True, exist_ok=True)
    return base_directory


def _create_copilot_client() -> CopilotClient:
    return CopilotClient(mode="empty", base_directory=str(_resolve_copilot_base_directory()))


def _serialize_agent(agent: Agent) -> QueryState:
    return {
        "id": agent.query_id,
        "text": agent.query_text,
        "phase": agent.current_phase.value,
        "intent": agent.current_intent,
    }


def _build_pipeline_state(app_state: AppState) -> PipelineState:
    columns = {phase: [] for phase in _PIPELINE_PHASES}
    queries: dict[str, QueryState] = {}

    for agent in app_state.agents.values():
        query_state = _serialize_agent(agent)
        queries[query_state["id"]] = query_state
        columns[query_state["phase"]].append(query_state)

    return {
        "queries": queries,
        "columns": columns,
        "dashboard": {
            "processing": sum(len(columns[phase]) for phase in _LIFECYCLE_PHASES),
            "completed": len(columns[Phase.DONE.value]),
            "rejected": len(columns[Phase.REJECTED.value]) + len(columns[Phase.NO_MATCHES.value]),
        },
    }


def _resolve_query_text(payload: SubmitQueryPayload | None, query_number: int) -> str:
    if payload and payload.query:
        return payload.query
    return f"{_DEFAULT_QUERY_PREFIX}{query_number}"


def _record_agent_error(agent: Agent, message: str) -> None:
    entry = {
        "type": "error",
        "timestamp": _now_iso(),
        "message": message,
    }
    agent.events.append(entry)


async def _run_agent_task(app_state: AppState, query_id: str) -> None:
    loop = asyncio.get_running_loop()
    agent = app_state.agents[query_id]
    # This task is isolated per query: trap all exceptions so one failed background
    # agent never becomes an unhandled task exception or impacts other queries.
    try:
        if app_state.copilot_client is None:
            raise RuntimeError("Copilot runtime is unavailable")
        await agent.run(app_state.copilot_client)
    except asyncio.CancelledError:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("Agent %s failed for query %r", query_id, agent.query_text)
        agent.current_phase = Phase.REJECTED
        agent.current_intent = "Failed"
        phase_event = {
            "type": "phase_change",
            "timestamp": _now_iso(),
            "phase": agent.current_phase.value,
            "intent": agent.current_intent,
        }
        agent.events.append(phase_event)
        ws_manager.schedule_broadcast(loop, {
            **phase_event,
            "queryId": query_id,
        })
        _record_agent_error(agent, f"{type(exc).__name__}: {exc}")
        ws_manager.schedule_broadcast(loop, {
            "type": "error",
            "timestamp": _now_iso(),
            "message": f"{type(exc).__name__}: {exc}",
            "queryId": query_id,
        })
    finally:
        app_state.agent_tasks.pop(query_id, None)


@asynccontextmanager
async def lifespan(fastapi_app: FastAPI):
    copilot_client = None
    startup_error: str | None = None
    engine = None
    try:
        copilot_client = _create_copilot_client()
        await copilot_client.start()
    except Exception as exc:  # noqa: BLE001
        startup_error = f"Copilot runtime startup failed ({type(exc).__name__}): {exc}"
        logger.exception(startup_error)
        # Best-effort cleanup of partially-started client to avoid leaked
        # subprocesses/tasks, then discard the reference.
        if copilot_client is not None:
            try:
                await copilot_client.stop()
            except Exception:  # noqa: BLE001
                logger.debug("Ignoring error during cleanup of failed client", exc_info=True)
        copilot_client = None
    try:
        engine = create_engine_and_tables()
        count = seed_database(engine, _DATA_DIR)
        logger.info("Seeded %d properties from %s", count, _DATA_DIR)
        fastapi_app.state.app_state = AppState(
            copilot_client=copilot_client,
            db_engine=engine,
            startup_error=startup_error,
        )
        yield
    finally:
        app_state = getattr(fastapi_app.state, "app_state", None)
        if app_state is not None:
            tasks = list(app_state.agent_tasks.values())
            # Iterate over a snapshot because tasks remove themselves from
            # app_state.agent_tasks when their finally blocks execute.
            for task in tasks:
                # Cancellation is non-blocking; asyncio.gather below waits for task cleanup.
                task.cancel()
            if tasks:
                # Keep shutdown graceful: wait for all task cleanup paths and ignore cancellation
                # exceptions from individual tasks. return_exceptions=True prevents one task's
                # failure from interrupting cleanup of the rest.
                await asyncio.gather(*tasks, return_exceptions=True)
            app_state.agent_tasks.clear()
        if engine is not None:
            engine.dispose()
        if copilot_client is not None:
            await copilot_client.stop()


app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    if request.url.path.startswith("/static/"):
        response.headers.setdefault("Cache-Control", "public, max-age=3600")
    else:
        response.headers.setdefault("Cache-Control", "no-store")
    return response


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    state = _build_pipeline_state(request.app.state.app_state)
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "state": state,
            "initial_state": state,
            "lifecycle_phases": _LIFECYCLE_PHASES,
            "end_state_mappings": _END_STATE_MAPPINGS,
        },
    )


@app.get("/partials/pipeline", response_class=HTMLResponse)
async def pipeline_partial(request: Request) -> HTMLResponse:
    state = _build_pipeline_state(request.app.state.app_state)
    return templates.TemplateResponse(
        request=request,
        name="partials/pipeline.html",
        context={
            "state": state,
            "lifecycle_phases": _LIFECYCLE_PHASES,
            "end_state_mappings": _END_STATE_MAPPINGS,
        },
    )


@app.get("/api/agent/{query_id}")
async def agent_detail(query_id: str, request: Request) -> dict[str, object]:
    app_state = request.app.state.app_state
    agent = app_state.agents.get(query_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent.to_dict()


@app.post("/api/submit-query")
async def submit_query(
    request: Request,
    payload: SubmitQueryPayload | None = Body(default=None),
) -> dict[str, object]:
    app_state = request.app.state.app_state
    async with app_state.query_lock:
        query_number = app_state.next_query_number
        query_id = f"q-{query_number}"
        query_text = _resolve_query_text(payload, query_number)
        app_state.agents[query_id] = Agent(
            query_id=query_id,
            query_text=query_text,
            db_engine=app_state.db_engine,
        )
        app_state.next_query_number += 1
        if app_state.copilot_client is not None:
            app_state.agent_tasks[query_id] = asyncio.create_task(
                _run_agent_task(app_state, query_id),
                name=f"agent-{query_id}",
            )
        else:
            agent = app_state.agents[query_id]
            agent.current_phase = Phase.REJECTED
            agent.current_intent = "Runtime unavailable"
            phase_event = {
                "type": "phase_change",
                "timestamp": _now_iso(),
                "phase": agent.current_phase.value,
                "intent": agent.current_intent,
            }
            agent.events.append(phase_event)
            error_msg = app_state.startup_error or "Copilot runtime is unavailable"
            _record_agent_error(agent, error_msg)
            ws_manager.schedule_broadcast(asyncio.get_running_loop(), {
                **phase_event,
                "queryId": query_id,
            })
            ws_manager.schedule_broadcast(asyncio.get_running_loop(), {
                "type": "error",
                "timestamp": _now_iso(),
                "message": error_msg,
                "queryId": query_id,
            })
    state = _build_pipeline_state(app_state)
    return {
        "status": "queued" if app_state.copilot_client is not None else "rejected",
        "queryId": query_id,
        "queryText": query_text,
        "phase": app_state.agents[query_id].current_phase.value,
        "intent": app_state.agents[query_id].current_intent,
        "state": state,
    }


@app.websocket("/ws/pipeline")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await ws_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        ws_manager.disconnect(websocket)


if __name__ == "__main__":
    reload_enabled = os.getenv("UVICORN_RELOAD", "false").lower() in {"1", "true", "yes", "on"}
    uvicorn.run(
        "python_agent_orchestrator.main:app",
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "8000")),
        reload=reload_enabled,
    )
