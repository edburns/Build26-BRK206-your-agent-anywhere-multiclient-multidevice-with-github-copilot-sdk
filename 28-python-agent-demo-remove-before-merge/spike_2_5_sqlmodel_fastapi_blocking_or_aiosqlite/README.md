# Spike 2.5 -- SQLModel + SQLite in-memory blocking analysis

## Goal

Determine whether synchronous SQLModel with SQLite in-memory is safe for
the FastAPI demo (i.e., won't block the asyncio event loop), or if we need
aiosqlite for async database access.

## How to run

```bash
pip install sqlmodel  # if not already installed
python 28-python-agent-demo-remove-before-merge/spike_2_5_sqlmodel_fastapi_blocking_or_aiosqlite/spike_app.py
```

## Expected result

Synchronous reads from a pre-seeded in-memory SQLite DB take <1ms,
which is below asyncio's event loop resolution. No aiosqlite needed.
