# Spike 2.6 -- Option C: Alpine.js + HTMX + WebSocket pipeline UI

## Goal

Prove that Option C (Alpine.js reactive state + HTMX reconciliation) works
for real-time pipeline UI updates via WebSocket push from FastAPI.

## Architecture

```
Server (FastAPI)                    Browser
=================                   ================
Agent phase change                  
  |                                 
  v                                 
WebSocket broadcast ----ws----->  Alpine.js reactive data
  {"type": "phase_change",          |
   "queryId": "q-1",                v
   "phase": "Searching"}          CSS transition fires
                                  (card slides to new column,
                                   yellow pulse activates)
                                    
                                  On reconnect / manual:
Server state (truth)               HTMX hx-get /partials/pipeline
  |                                 |
  v                                 v
Jinja2 partial render --http--->  DOM reconciliation
                                  (server-truth replaces Alpine state)
```

## Key principle

Alpine reads WebSocket JSON and toggles CSS classes.
It never computes business logic. Server is the source of truth.

## How to run

```bash
python 28-python-agent-demo-remove-before-merge/spike_2_6_client_side_pattern_for_update/spike_app.py
# Open http://localhost:8043
# Click "Start Demo Agent"
```

## What to observe

1. Card appears in "Queued" column with entrance animation
2. Card slides to "Validating" with yellow pulsing indicator
3. Card slides to "Searching" (pulse follows)
4. Card slides to "Writing Report" (pulse follows)
5. Card arrives in "Done" with green checkmark, pulse stops
6. "Reconcile" button fetches server-truth via HTMX (verifies state match)
7. Console shows server-side status messages for each phase transition
