from contextlib import asynccontextmanager
import logging
import os
from pathlib import Path

import uvicorn
from copilot import CopilotClient
from fastapi import FastAPI

from python_agent_orchestrator.app_state import AppState
from python_agent_orchestrator.property_database import (
    create_engine_and_tables,
    seed_database,
)

logger = logging.getLogger(__name__)

_DATA_DIR = Path(
    os.getenv("PROPERTY_DATA_DIR", "")
    or Path(__file__).resolve().parent.parent.parent / "data" / "properties"
)
_COPILOT_BASE_DIRECTORY = Path(
    os.getenv("COPILOT_BASE_DIRECTORY") or Path.home() / ".copilot"
)


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


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


if __name__ == "__main__":
    reload_enabled = os.getenv("UVICORN_RELOAD", "false").lower() in {"1", "true", "yes", "on"}
    uvicorn.run(
        "python_agent_orchestrator.main:app",
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "8000")),
        reload=reload_enabled,
    )
