# Python Real Estate Agent Orchestrator

A Python demo of the GitHub Copilot SDK, implementing the same real-estate
lead-management agent pipeline as the C# Blazor and Java demos.

Built with **FastAPI**, **Jinja2 + HTMX**, **SQLModel**, and the
**GitHub Copilot SDK for Python**.

## Prerequisites

- Python 3.13+
- A GitHub Copilot license (for SDK features in later tasks)

## Quick start

```powershell
# Create and activate a virtual environment
py -3.13 -m venv .venv
. .\.venv\Scripts\Activate.ps1

# Install in editable mode with dev dependencies
python -m pip install --upgrade pip setuptools wheel
pip install -e ".[dev]"

# Run the application
python -m python_agent_orchestrator.main
# Or: uvicorn python_agent_orchestrator.main:app --reload

# Verify it works
curl http://localhost:8000/health
# → {"status":"ok"}
```

## Development

```powershell
# Lint
ruff check src/

# Type check
pyright

# Test
pytest
```

## Project structure

```
src/python_agent_orchestrator/
├── pyproject.toml
├── README.md
├── src/
│   └── python_agent_orchestrator/
│       ├── __init__.py
│       ├── main.py          # FastAPI app, lifespan, routes
│       ├── templates/       # Jinja2 templates (future)
│       └── static/          # CSS/JS assets (future)
└── tests/
    └── test_smoke.py
```