from contextlib import asynccontextmanager
import logging
import os
from pathlib import Path
from typing import TypedDict

import uvicorn
from copilot import CopilotClient
from fastapi import Body, FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

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
_DEFAULT_QUERY_TEMPLATE = "Demo query {query_number}"
_LIFECYCLE_PHASES = [
    Phase.QUEUED.value,
    Phase.VALIDATING.value,
    Phase.SEARCHING.value,
    Phase.WRITING_REPORT.value,
]
_PIPELINE_PHASES = _LIFECYCLE_PHASES + [
    Phase.REJECTED.value,
    Phase.NO_MATCHES.value,
    Phase.DONE.value,
]


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


@asynccontextmanager
async def lifespan(fastapi_app: FastAPI):
    copilot_client = _create_copilot_client()
    started = False
    engine = None
    try:
        await copilot_client.start()
        started = True
        engine = create_engine_and_tables()
        count = seed_database(engine, _DATA_DIR)
        logger.info("Seeded %d properties from %s", count, _DATA_DIR)
        fastapi_app.state.app_state = AppState(copilot_client=copilot_client, db_engine=engine)
        yield
    finally:
        if engine is not None:
            engine.dispose()
        if started:
            await copilot_client.stop()


app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")


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


@app.post("/api/submit-query")
async def submit_query(
    request: Request,
    payload: dict[str, str] | None = Body(default=None),
) -> dict[str, object]:
    app_state = request.app.state.app_state
    query_number = app_state.next_query_number
    query_id = f"q-{query_number}"
    query_text = (payload or {}).get("query") or _DEFAULT_QUERY_TEMPLATE.format(
        query_number=query_number
    )
    app_state.agents[query_id] = Agent(
        query_id=query_id,
        query_text=query_text,
        db_engine=app_state.db_engine,
    )
    app_state.next_query_number += 1
    state = _build_pipeline_state(app_state)
    return {
        "status": "queued",
        "queryId": query_id,
        "queryText": query_text,
        "phase": Phase.QUEUED.value,
        "intent": "",
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
