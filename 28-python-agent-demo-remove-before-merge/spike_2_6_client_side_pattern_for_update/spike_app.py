"""
Spike 2.6 -- Option C: Alpine.js reactive + HTMX reconciliation + WebSocket push.

Demonstrates:
1. WebSocket delivers small JSON state updates.
2. Alpine.js immediately updates reactive data -> CSS transitions fire (card slides).
3. HTMX hx-get fetches server-rendered partial for reconciliation.
4. Yellow pulsing indicator follows the active card.
5. Cards animate between pipeline columns (Queued -> Validating -> Searching -> Done).

Run:
    python spike_app.py
    Open http://localhost:8043 in a browser
    Click "Start Demo Agent" to watch the pipeline animation

The server also prints verifiable status messages showing each state push.
"""

import asyncio
import json
import os
import signal
import sys
from datetime import datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import uvicorn


# ---------------------------------------------------------------------------
# Pipeline state (server is the source of truth)
# ---------------------------------------------------------------------------

class PipelineState:
    """Server-side pipeline state — the single source of truth."""

    def __init__(self):
        self.queries: dict[str, dict] = {}

    def add_query(self, query_id: str, text: str):
        self.queries[query_id] = {
            "id": query_id,
            "text": text,
            "phase": "Queued",
            "intent": "",
        }

    def update_phase(self, query_id: str, phase: str, intent: str = ""):
        if query_id in self.queries:
            self.queries[query_id]["phase"] = phase
            if intent:
                self.queries[query_id]["intent"] = intent

    def get_state(self) -> dict:
        """Return the full pipeline state for reconciliation."""
        phases = ["Queued", "Validating", "Searching", "WritingReport", "Done", "Rejected"]
        columns = {p: [] for p in phases}
        for q in self.queries.values():
            phase = q["phase"]
            if phase in columns:
                columns[phase].append(q)
        return {"columns": columns, "queries": self.queries}


pipeline = PipelineState()


# ---------------------------------------------------------------------------
# WebSocket connection manager
# ---------------------------------------------------------------------------

class ConnectionManager:
    def __init__(self):
        self.connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.connections.append(ws)

    def disconnect(self, ws: WebSocket):
        if ws in self.connections:
            self.connections.remove(ws)

    async def broadcast(self, message: dict):
        text = json.dumps(message)
        dead = []
        for ws in self.connections:
            try:
                await ws.send_text(text)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.connections.remove(ws)


ws_manager = ConnectionManager()


def log(msg: str):
    ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"[{ts}] {msg}")


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

# Templates directory is alongside this script
TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")
os.makedirs(TEMPLATE_DIR, exist_ok=True)

app = FastAPI()
templates = Jinja2Templates(directory=TEMPLATE_DIR)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    state = pipeline.get_state()
    return templates.TemplateResponse(request, "index.html", {"state": state})


@app.get("/partials/pipeline", response_class=HTMLResponse)
async def pipeline_partial(request: Request):
    """HTMX reconciliation endpoint -- returns server-truth as rendered HTML."""
    state = pipeline.get_state()
    log(f"  [HTMX] Reconciliation fetch: {len(pipeline.queries)} queries")
    return templates.TemplateResponse(request, "partials/pipeline.html", {"state": state})


@app.websocket("/ws/pipeline")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    log("[WS] Client connected")
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
        log("[WS] Client disconnected")


@app.post("/api/start-demo")
async def start_demo():
    """Start a simulated agent pipeline progression."""
    asyncio.create_task(run_demo_pipeline())
    return {"status": "started"}


async def run_demo_pipeline():
    """Simulate an agent progressing through pipeline phases."""
    query_id = f"q-{len(pipeline.queries) + 1}"
    text = "Waterfront property in Miami"

    # Phase 1: Queued
    pipeline.add_query(query_id, text)
    msg = {"type": "phase_change", "queryId": query_id, "phase": "Queued",
           "text": text, "intent": ""}
    await ws_manager.broadcast(msg)
    log(f"  [PIPELINE] {query_id} -> Queued")
    await asyncio.sleep(2)

    # Phase 2: Validating
    pipeline.update_phase(query_id, "Validating", "Checking query legitimacy")
    msg = {"type": "phase_change", "queryId": query_id, "phase": "Validating",
           "text": text, "intent": "Checking query legitimacy"}
    await ws_manager.broadcast(msg)
    log(f"  [PIPELINE] {query_id} -> Validating")
    await asyncio.sleep(2.5)

    # Phase 3: Searching
    pipeline.update_phase(query_id, "Searching", "Looking for matches")
    msg = {"type": "phase_change", "queryId": query_id, "phase": "Searching",
           "text": text, "intent": "Looking for matches"}
    await ws_manager.broadcast(msg)
    log(f"  [PIPELINE] {query_id} -> Searching")
    await asyncio.sleep(3)

    # Phase 4: Writing Report
    pipeline.update_phase(query_id, "WritingReport", "Preparing summary")
    msg = {"type": "phase_change", "queryId": query_id, "phase": "WritingReport",
           "text": text, "intent": "Preparing summary"}
    await ws_manager.broadcast(msg)
    log(f"  [PIPELINE] {query_id} -> WritingReport")
    await asyncio.sleep(2)

    # Phase 5: Done
    pipeline.update_phase(query_id, "Done", "Complete")
    msg = {"type": "phase_change", "queryId": query_id, "phase": "Done",
           "text": text, "intent": "Complete"}
    await ws_manager.broadcast(msg)
    log(f"  [PIPELINE] {query_id} -> Done")


# ---------------------------------------------------------------------------
# Template writer (creates files alongside the script)
# ---------------------------------------------------------------------------

def write_templates():
    """Write Jinja2 templates to disk."""
    partials_dir = os.path.join(TEMPLATE_DIR, "partials")
    os.makedirs(partials_dir, exist_ok=True)

    # Main page
    with open(os.path.join(TEMPLATE_DIR, "index.html"), "w", encoding="utf-8") as f:
        f.write(INDEX_HTML)

    # Pipeline partial (for HTMX reconciliation)
    with open(os.path.join(partials_dir, "pipeline.html"), "w", encoding="utf-8") as f:
        f.write(PIPELINE_PARTIAL_HTML)


# ---------------------------------------------------------------------------
# Templates as strings (avoids separate files for a spike)
# ---------------------------------------------------------------------------

INDEX_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Spike 2.6 - Pipeline UI</title>
    <!-- Alpine.js for reactive state -->
    <script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3.x.x/dist/cdn.min.js"></script>
    <!-- HTMX for server reconciliation -->
    <script src="https://unpkg.com/htmx.org@2.0.4"></script>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: 'Segoe UI', system-ui, sans-serif;
            background: #0f1117;
            color: #e4e4e7;
            min-height: 100vh;
        }
        header {
            background: #1a1b26;
            padding: 16px 24px;
            border-bottom: 1px solid #2a2b3d;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        header h1 { font-size: 18px; font-weight: 600; }
        .btn {
            background: #3b82f6;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 14px;
        }
        .btn:hover { background: #2563eb; }

        /* Pipeline columns */
        .pipeline {
            display: grid;
            grid-template-columns: repeat(5, 1fr);
            gap: 12px;
            padding: 24px;
            min-height: calc(100vh - 60px);
        }
        .column {
            background: #1a1b26;
            border-radius: 8px;
            padding: 12px;
            border: 1px solid #2a2b3d;
        }
        .column-header {
            font-size: 13px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: #9ca3af;
            margin-bottom: 12px;
            padding-bottom: 8px;
            border-bottom: 1px solid #2a2b3d;
        }
        .column-header .count {
            float: right;
            background: #2a2b3d;
            padding: 1px 8px;
            border-radius: 10px;
            font-size: 11px;
        }

        /* Query cards */
        .card {
            background: #262738;
            border: 1px solid #3a3b4d;
            border-radius: 6px;
            padding: 10px 12px;
            margin-bottom: 8px;
            position: relative;
            /* CSS transition for smooth appearance */
            transition: transform 0.4s ease, opacity 0.4s ease, box-shadow 0.3s ease;
            animation: cardEnter 0.4s ease-out;
        }
        @keyframes cardEnter {
            from { opacity: 0; transform: translateY(-10px) scale(0.95); }
            to { opacity: 1; transform: translateY(0) scale(1); }
        }
        .card .query-text {
            font-size: 13px;
            font-weight: 500;
            margin-bottom: 4px;
        }
        .card .intent {
            font-size: 11px;
            color: #9ca3af;
            font-style: italic;
        }

        /* Yellow pulsing indicator for active card */
        .card.active {
            border-color: #eab308;
            box-shadow: 0 0 12px rgba(234, 179, 8, 0.3);
        }
        .card.active::before {
            content: '';
            position: absolute;
            top: 8px;
            right: 8px;
            width: 10px;
            height: 10px;
            background: #eab308;
            border-radius: 50%;
            animation: pulse 1.5s ease-in-out infinite;
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.5; transform: scale(1.3); }
        }

        /* Done state */
        .card.done {
            border-color: #22c55e;
            opacity: 0.8;
        }
        .card.done::before {
            content: '\2713';
            position: absolute;
            top: 8px;
            right: 10px;
            color: #22c55e;
            font-size: 14px;
            font-weight: bold;
        }

        /* Status bar */
        .status-bar {
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            background: #1a1b26;
            border-top: 1px solid #2a2b3d;
            padding: 8px 24px;
            font-size: 12px;
            color: #6b7280;
            display: flex;
            gap: 20px;
        }
        .status-bar .ws-status { color: #22c55e; }
        .status-bar .ws-status.disconnected { color: #ef4444; }
    </style>
</head>
<body x-data="pipelineApp()" x-init="init()">

<header>
    <h1>Real Estate Agent Pipeline</h1>
    <div style="display: flex; gap: 10px; align-items: center;">
        <button class="btn" @click="startDemo()">Start Demo Agent</button>
        <!-- HTMX reconciliation button (Option C: manual reconcile) -->
        <button class="btn" style="background: #6b7280;"
                hx-get="/partials/pipeline"
                hx-target="#pipeline-container"
                hx-swap="innerHTML">
            Reconcile
        </button>
    </div>
</header>

<!-- Pipeline grid: Alpine.js owns the visual state -->
<div class="pipeline" id="pipeline-container">
    <template x-for="phase in phases" :key="phase">
        <div class="column">
            <div class="column-header">
                <span x-text="phaseLabels[phase]"></span>
                <span class="count" x-text="queriesInPhase(phase).length"></span>
            </div>
            <template x-for="q in queriesInPhase(phase)" :key="q.id">
                <div class="card"
                     :class="{
                         'active': q.phase !== 'Done' && q.phase !== 'Rejected' && q.phase !== 'Queued',
                         'done': q.phase === 'Done'
                     }">
                    <div class="query-text" x-text="q.text"></div>
                    <div class="intent" x-text="q.intent || q.id"></div>
                </div>
            </template>
        </div>
    </template>
</div>

<div class="status-bar">
    <span :class="'ws-status ' + (wsConnected ? '' : 'disconnected')">
        WS: <span x-text="wsConnected ? 'Connected' : 'Disconnected'"></span>
    </span>
    <span>Updates received: <span x-text="updateCount"></span></span>
    <span>Last event: <span x-text="lastEvent"></span></span>
</div>

<script>
function pipelineApp() {
    return {
        // Reactive state (Alpine owns this for immediate visual updates)
        queries: {},
        phases: ['Queued', 'Validating', 'Searching', 'WritingReport', 'Done'],
        phaseLabels: {
            'Queued': 'Queued',
            'Validating': 'Validating',
            'Searching': 'Searching',
            'WritingReport': 'Writing Report',
            'Done': 'Done',
            'Rejected': 'Rejected',
        },
        wsConnected: false,
        updateCount: 0,
        lastEvent: 'none',
        ws: null,

        init() {
            this.connectWebSocket();
        },

        connectWebSocket() {
            const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
            this.ws = new WebSocket(`${protocol}//${location.host}/ws/pipeline`);

            this.ws.onopen = () => {
                this.wsConnected = true;
                this.lastEvent = 'connected';
            };

            this.ws.onclose = () => {
                this.wsConnected = false;
                this.lastEvent = 'disconnected';
                // Auto-reconnect after 2s
                setTimeout(() => this.connectWebSocket(), 2000);
            };

            this.ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                this.handleMessage(data);
            };
        },

        handleMessage(data) {
            // Alpine reactive update -- immediate visual feedback
            if (data.type === 'phase_change') {
                this.updateCount++;
                this.lastEvent = `${data.queryId} -> ${data.phase}`;

                // Update or create the query in reactive state
                this.queries[data.queryId] = {
                    id: data.queryId,
                    text: data.text || this.queries[data.queryId]?.text || '',
                    phase: data.phase,
                    intent: data.intent || '',
                };

                // Force Alpine reactivity (reassign object)
                this.queries = { ...this.queries };
            }
        },

        queriesInPhase(phase) {
            return Object.values(this.queries).filter(q => q.phase === phase);
        },

        async startDemo() {
            const resp = await fetch('/api/start-demo', { method: 'POST' });
            const result = await resp.json();
            this.lastEvent = 'demo started';
        },
    };
}
</script>

</body>
</html>
"""

PIPELINE_PARTIAL_HTML = r"""<!-- HTMX reconciliation partial: server-truth rendered as HTML -->
<!-- This replaces the Alpine template when reconciliation is triggered -->
{% for phase in ['Queued', 'Validating', 'Searching', 'WritingReport', 'Done'] %}
<div class="column">
    <div class="column-header">
        <span>{{ {'Queued':'Queued','Validating':'Validating','Searching':'Searching','WritingReport':'Writing Report','Done':'Done'}[phase] }}</span>
        <span class="count">{{ state.columns[phase]|length }}</span>
    </div>
    {% for q in state.columns[phase] %}
    <div class="card {{ 'active' if q.phase not in ['Done','Rejected','Queued'] else '' }} {{ 'done' if q.phase == 'Done' else '' }}">
        <div class="query-text">{{ q.text }}</div>
        <div class="intent">{{ q.intent or q.id }}</div>
    </div>
    {% endfor %}
</div>
{% endfor %}
"""


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    write_templates()
    print()
    print("[SPIKE 2.6] Option C: Alpine.js + HTMX + WebSocket pipeline UI")
    print("=" * 65)
    print()
    print("  Open http://localhost:8043 in a browser")
    print("  Click 'Start Demo Agent' to watch cards animate through phases")
    print("  Watch this console for server-side status messages")
    print("  Press Ctrl-C to stop")
    print()
    print("=" * 65)
    # Handle Ctrl-C cleanly on Windows
    signal.signal(signal.SIGINT, lambda *_: sys.exit(0))
    uvicorn.run(app, host="0.0.0.0", port=8043)
