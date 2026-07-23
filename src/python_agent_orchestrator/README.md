# Python Real Estate Agent Orchestrator

Python scaffolding for the BRK206 Real Estate Agent Orchestrator demo.

## Requirements

- Python 3.13+
- GitHub Copilot runtime available locally (Copilot CLI installed/authenticated)

## Environment variables

- `COPILOT_BASE_DIRECTORY` (optional): defaults to `~/.copilot`
- `PROPERTY_DATA_DIR` (optional): defaults to `src/python_agent_orchestrator/data/properties`
- `PYTHON_AGENT_ORCHESTRATOR_LOG_LEVEL` (optional): defaults to `INFO` (supported: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`)
- `PYTHON_AGENT_ORCHESTRATOR_SESSION_TIMEOUT_SECONDS` (optional): defaults to `180` seconds
- `PYTHON_AGENT_ORCHESTRATOR_REJECTED_LINGER_SECONDS` (optional): defaults to `15` seconds before `Rejected` / `NoMatches` cards are removed
- `RUN_COPILOT_INTEGRATION=1` (optional): enables real-runtime integration tests

## Install (with venv)

From this directory (`src/python_agent_orchestrator/`):

### PowerShell (Windows)

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip setuptools wheel
python -m pip install -e ".[dev]"
```

### bash/zsh (macOS/Linux)

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -e ".[dev]"
```

## Run

```bash
python -m python_agent_orchestrator.main
```

Run with verbose debug logs:

```bash
PYTHON_AGENT_ORCHESTRATOR_LOG_LEVEL=DEBUG python -m python_agent_orchestrator.main
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