"""FastAPI application for the Python Real Estate Agent Orchestrator demo."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
import uvicorn


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: CopilotClient initialization will go here in a later task.
    yield
    # Shutdown: CopilotClient cleanup will go here in a later task.


app = FastAPI(title="Python Agent Orchestrator", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    uvicorn.run("python_agent_orchestrator.main:app", host="127.0.0.1", port=8000)
