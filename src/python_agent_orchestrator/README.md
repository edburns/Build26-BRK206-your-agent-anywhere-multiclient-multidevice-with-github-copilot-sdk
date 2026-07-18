# Python Real Estate Agent Orchestrator

Python scaffolding for the BRK206 Real Estate Agent Orchestrator demo.

## Requirements

- Python 3.13+

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