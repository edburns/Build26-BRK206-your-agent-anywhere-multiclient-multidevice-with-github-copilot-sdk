# Python Real Estate Agent Orchestrator

Python scaffolding for the BRK206 Real Estate Agent Orchestrator demo.

## Requirements

- Python 3.13+
- GitHub Copilot runtime available locally (Copilot CLI installed/authenticated)

## Environment variables

- `COPILOT_BASE_DIRECTORY` (optional): defaults to `~/.copilot`
- `PROPERTY_DATA_DIR` (optional): defaults to `src/python_agent_orchestrator/data/properties`
- `RUN_COPILOT_INTEGRATION=1` (optional): enables real-runtime integration tests

## Install

From this directory (`src/python_agent_orchestrator/`):

```bash
python -m pip install -e ".[dev]"
```

## Run

```bash
python -m python_agent_orchestrator.main
```

or

```bash
uvicorn python_agent_orchestrator.main:app --reload
```

Health check:

```bash
curl http://localhost:8000/health
```

## Validate

```bash
ruff check src/ tests/
pytest tests/
```

Run real-runtime integration tests:

```bash
RUN_COPILOT_INTEGRATION=1 pytest tests/ -m integration
```