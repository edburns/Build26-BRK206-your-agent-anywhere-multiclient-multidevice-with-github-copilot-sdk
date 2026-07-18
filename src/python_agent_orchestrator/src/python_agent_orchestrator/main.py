from contextlib import asynccontextmanager
import logging
import os
from pathlib import Path

import uvicorn
from fastapi import FastAPI

from python_agent_orchestrator.property_database import (
    create_engine_and_tables,
    seed_database,
)

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "properties"


@asynccontextmanager
async def lifespan(fastapi_app: FastAPI):
    engine = create_engine_and_tables()
    count = seed_database(engine, _DATA_DIR)
    logger.info("Seeded %d properties from %s", count, _DATA_DIR)
    fastapi_app.state.engine = engine
    yield


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
