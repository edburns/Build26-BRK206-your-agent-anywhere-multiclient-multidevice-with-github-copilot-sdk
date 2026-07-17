from contextlib import asynccontextmanager
import os

import uvicorn
from fastapi import FastAPI


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield


app = FastAPI(lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run(
        "python_agent_orchestrator.main:app",
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "8000")),
    )
