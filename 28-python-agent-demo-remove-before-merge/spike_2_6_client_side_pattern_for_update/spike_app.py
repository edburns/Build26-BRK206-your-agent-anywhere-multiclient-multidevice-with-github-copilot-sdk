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
        phases = ["Queued", "Validating", "Searching", "WritingReport", "Done", "Rejected", "NoMatches"]
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
    <script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3.x.x/dist/cdn.min.js"></script>
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
            padding: 24px 32px 8px;
        }
        header h1 { font-size: 22px; font-weight: 600; }
        header .subtitle { font-size: 13px; color: #6b7280; margin-top: 4px; }

        /* Main layout: pipeline on the left, dashboard on the right */
        .main-layout {
            display: grid;
            grid-template-columns: 1fr 200px;
            gap: 24px;
            padding: 16px 32px 40px;
            align-items: start;
        }

        /* Pipeline area: two columns (lifecycle states, end states) */
        .pipeline-area {
            display: grid;
            grid-template-columns: 220px 220px;
            gap: 0;
            position: relative;
        }
        .pipeline-area .col-label {
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            color: #6b7280;
            margin-bottom: 12px;
        }

        /* Phase box (lifecycle or end-state) */
        .phase-box {
            background: #1a1b26;
            border: 1px solid #2a2b3d;
            border-radius: 6px;
            padding: 10px 14px;
            min-height: 90px;
            width: 200px;
            position: relative;
        }
        .phase-box .phase-label {
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: #9ca3af;
            margin-bottom: 8px;
        }
        .phase-box .empty-dash {
            color: #3a3b4d;
            font-size: 18px;
        }

        /* End-state boxes have colored borders */
        .phase-box.end-rejected { border-color: #ef4444; }
        .phase-box.end-rejected .phase-label { color: #ef4444; }
        .phase-box.end-no-matches { border-color: #ef4444; }
        .phase-box.end-no-matches .phase-label { color: #ef4444; }
        .phase-box.end-done { border-color: #22c55e; }
        .phase-box.end-done .phase-label { color: #22c55e; }

        /* Vertical arrow between lifecycle boxes */
        .arrow-down {
            display: flex;
            justify-content: center;
            padding: 6px 0;
            width: 200px;
        }
        .arrow-down svg { color: #4b5563; }

        /* Horizontal arrow to end-state boxes */
        .arrow-right {
            display: flex;
            align-items: center;
            padding: 0 8px;
        }
        .arrow-right svg { color: #4b5563; }

        /* Pipeline row: lifecycle box + arrow + end-state box */
        .pipeline-row {
            display: flex;
            align-items: flex-start;
        }
        /* The end-state column is offset so arrows align with the boxes */
        .end-state-slot {
            display: flex;
            align-items: flex-start;
        }

        /* Query cards */
        .card {
            background: #262738;
            border: 1px solid #3a3b4d;
            border-radius: 5px;
            padding: 8px 10px;
            margin-bottom: 6px;
            position: relative;
            transition: transform 0.4s ease, opacity 0.4s ease, box-shadow 0.3s ease;
            animation: cardEnter 0.4s ease-out;
        }
        @keyframes cardEnter {
            from { opacity: 0; transform: translateY(-8px) scale(0.95); }
            to { opacity: 1; transform: translateY(0) scale(1); }
        }
        .card .query-text { font-size: 12px; font-weight: 500; margin-bottom: 2px; }
        .card .intent { font-size: 10px; color: #9ca3af; font-style: italic; }

        /* Yellow pulsing indicator for active card */
        .card.active {
            border-color: #eab308;
            box-shadow: 0 0 10px rgba(234, 179, 8, 0.25);
        }
        .card.active::before {
            content: '';
            position: absolute;
            top: 7px; right: 7px;
            width: 8px; height: 8px;
            background: #eab308;
            border-radius: 50%;
            animation: pulse 1.5s ease-in-out infinite;
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.5; transform: scale(1.3); }
        }
        .card.done { border-color: #22c55e; opacity: 0.85; }
        .card.rejected { border-color: #ef4444; opacity: 0.85; }

        /* Dashboard panel */
        .dashboard {
            background: #1e1f2e;
            border: 1px solid #2a2b3d;
            border-radius: 8px;
            padding: 16px;
            position: sticky;
            top: 24px;
        }
        .dashboard h2 {
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.1em;
            color: #6b7280;
            margin-bottom: 16px;
        }
        .dash-stat {
            display: flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 14px;
        }
        .dash-stat .indicator {
            width: 3px;
            height: 36px;
            border-radius: 2px;
        }
        .dash-stat .indicator.processing { background: #6366f1; }
        .dash-stat .indicator.completed  { background: #22c55e; }
        .dash-stat .indicator.rejected   { background: #ef4444; }
        .dash-stat .number { font-size: 26px; font-weight: 700; line-height: 1; }
        .dash-stat .label  { font-size: 11px; color: #9ca3af; }

        /* + button */
        .add-btn {
            width: 32px; height: 32px;
            border-radius: 50%;
            background: #2a2b3d;
            border: 1px solid #3a3b4d;
            color: #9ca3af;
            font-size: 18px;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            position: absolute;
            top: 16px;
            right: 220px;
        }
        .add-btn:hover { background: #3b82f6; color: white; border-color: #3b82f6; }

        /* Status bar */
        .status-bar {
            position: fixed;
            bottom: 0; left: 0; right: 0;
            background: #1a1b26;
            border-top: 1px solid #2a2b3d;
            padding: 6px 24px;
            font-size: 11px;
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
    <div class="subtitle">GitHub Copilot SDK for Python -- BRK206 Demo</div>
</header>

<div style="position: relative;">
    <button class="add-btn" @click="startDemo()" title="Add query">+</button>
</div>

<div class="main-layout" id="pipeline-container">

    <!-- Left: vertical pipeline -->
    <div class="pipeline-area">

        <!-- Column labels -->
        <div class="col-label">Lifecycle State</div>
        <div class="col-label" style="padding-left: 50px;">End State</div>

        <!-- Row 1: Queued (no end-state off-ramp) -->
        <div class="pipeline-row">
            <div class="phase-box">
                <div class="phase-label">Queued</div>
                <template x-for="q in queriesInPhase('Queued')" :key="q.id">
                    <div class="card"><div class="query-text" x-text="q.text"></div>
                        <div class="intent" x-text="q.intent || q.id"></div></div>
                </template>
                <template x-if="queriesInPhase('Queued').length === 0">
                    <div class="empty-dash">--</div>
                </template>
            </div>
        </div>
        <div></div><!-- empty end-state slot -->

        <!-- Arrow down -->
        <div class="arrow-down">
            <svg width="16" height="24" viewBox="0 0 16 24"><path d="M8 0v20M3 16l5 5 5-5" stroke="currentColor" stroke-width="1.5" fill="none"/></svg>
        </div>
        <div></div>

        <!-- Row 2: Validating -> Rejected -->
        <div class="pipeline-row">
            <div class="phase-box">
                <div class="phase-label">Validating</div>
                <template x-for="q in queriesInPhase('Validating')" :key="q.id">
                    <div class="card active"><div class="query-text" x-text="q.text"></div>
                        <div class="intent" x-text="q.intent || q.id"></div></div>
                </template>
                <template x-if="queriesInPhase('Validating').length === 0">
                    <div class="empty-dash">--</div>
                </template>
            </div>
            <div class="arrow-right">
                <svg width="32" height="16" viewBox="0 0 32 16"><path d="M0 8h26M22 3l5 5-5 5" stroke="currentColor" stroke-width="1.5" fill="none"/></svg>
            </div>
            <div class="phase-box end-rejected">
                <div class="phase-label">Rejected</div>
                <template x-for="q in queriesInPhase('Rejected')" :key="q.id">
                    <div class="card rejected"><div class="query-text" x-text="q.text"></div>
                        <div class="intent" x-text="q.intent || q.id"></div></div>
                </template>
                <template x-if="queriesInPhase('Rejected').length === 0">
                    <div class="empty-dash">--</div>
                </template>
            </div>
        </div>
        <div></div>

        <!-- Arrow down -->
        <div class="arrow-down">
            <svg width="16" height="24" viewBox="0 0 16 24"><path d="M8 0v20M3 16l5 5 5-5" stroke="currentColor" stroke-width="1.5" fill="none"/></svg>
        </div>
        <div></div>

        <!-- Row 3: Searching -> No Matches -->
        <div class="pipeline-row">
            <div class="phase-box">
                <div class="phase-label">Searching</div>
                <template x-for="q in queriesInPhase('Searching')" :key="q.id">
                    <div class="card active"><div class="query-text" x-text="q.text"></div>
                        <div class="intent" x-text="q.intent || q.id"></div></div>
                </template>
                <template x-if="queriesInPhase('Searching').length === 0">
                    <div class="empty-dash">--</div>
                </template>
            </div>
            <div class="arrow-right">
                <svg width="32" height="16" viewBox="0 0 32 16"><path d="M0 8h26M22 3l5 5-5 5" stroke="currentColor" stroke-width="1.5" fill="none"/></svg>
            </div>
            <div class="phase-box end-no-matches">
                <div class="phase-label">No Matches</div>
                <template x-for="q in queriesInPhase('NoMatches')" :key="q.id">
                    <div class="card rejected"><div class="query-text" x-text="q.text"></div>
                        <div class="intent" x-text="q.intent || q.id"></div></div>
                </template>
                <template x-if="queriesInPhase('NoMatches').length === 0">
                    <div class="empty-dash">--</div>
                </template>
            </div>
        </div>
        <div></div>

        <!-- Arrow down -->
        <div class="arrow-down">
            <svg width="16" height="24" viewBox="0 0 16 24"><path d="M8 0v20M3 16l5 5 5-5" stroke="currentColor" stroke-width="1.5" fill="none"/></svg>
        </div>
        <div></div>

        <!-- Row 4: Writing Report -> Done -->
        <div class="pipeline-row">
            <div class="phase-box">
                <div class="phase-label">Writing Report</div>
                <template x-for="q in queriesInPhase('WritingReport')" :key="q.id">
                    <div class="card active"><div class="query-text" x-text="q.text"></div>
                        <div class="intent" x-text="q.intent || q.id"></div></div>
                </template>
                <template x-if="queriesInPhase('WritingReport').length === 0">
                    <div class="empty-dash">--</div>
                </template>
            </div>
            <div class="arrow-right">
                <svg width="32" height="16" viewBox="0 0 32 16"><path d="M0 8h26M22 3l5 5-5 5" stroke="currentColor" stroke-width="1.5" fill="none"/></svg>
            </div>
            <div class="phase-box end-done">
                <div class="phase-label">Done</div>
                <template x-for="q in queriesInPhase('Done')" :key="q.id">
                    <div class="card done"><div class="query-text" x-text="q.text"></div>
                        <div class="intent" x-text="q.intent || q.id"></div></div>
                </template>
                <template x-if="queriesInPhase('Done').length === 0">
                    <div class="empty-dash">--</div>
                </template>
            </div>
        </div>
        <div></div>

    </div>

    <!-- Right: Dashboard -->
    <div class="dashboard">
        <h2>Dashboard</h2>
        <div class="dash-stat">
            <div class="indicator processing"></div>
            <div>
                <div class="number" x-text="processingCount()"></div>
                <div class="label">Processing</div>
            </div>
        </div>
        <div class="dash-stat">
            <div class="indicator completed"></div>
            <div>
                <div class="number" x-text="queriesInPhase('Done').length"></div>
                <div class="label">Completed</div>
            </div>
        </div>
        <div class="dash-stat">
            <div class="indicator rejected"></div>
            <div>
                <div class="number" x-text="queriesInPhase('Rejected').length + queriesInPhase('NoMatches').length"></div>
                <div class="label">Rejected</div>
            </div>
        </div>
    </div>

</div>

<div class="status-bar">
    <span :class="'ws-status ' + (wsConnected ? '' : 'disconnected')">
        WS: <span x-text="wsConnected ? 'Connected' : 'Disconnected'"></span>
    </span>
    <span>Updates: <span x-text="updateCount"></span></span>
    <span>Last: <span x-text="lastEvent"></span></span>
</div>

<script>
function pipelineApp() {
    return {
        queries: {},
        wsConnected: false,
        updateCount: 0,
        lastEvent: 'none',
        ws: null,

        init() { this.connectWebSocket(); },

        connectWebSocket() {
            const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
            this.ws = new WebSocket(`${proto}//${location.host}/ws/pipeline`);
            this.ws.onopen = () => { this.wsConnected = true; this.lastEvent = 'connected'; };
            this.ws.onclose = () => {
                this.wsConnected = false; this.lastEvent = 'disconnected';
                setTimeout(() => this.connectWebSocket(), 2000);
            };
            this.ws.onmessage = (event) => this.handleMessage(JSON.parse(event.data));
        },

        handleMessage(data) {
            if (data.type === 'phase_change') {
                this.updateCount++;
                this.lastEvent = `${data.queryId} -> ${data.phase}`;
                this.queries[data.queryId] = {
                    id: data.queryId,
                    text: data.text || this.queries[data.queryId]?.text || '',
                    phase: data.phase,
                    intent: data.intent || '',
                };
                this.queries = { ...this.queries };
            }
        },

        queriesInPhase(phase) {
            return Object.values(this.queries).filter(q => q.phase === phase);
        },

        processingCount() {
            return Object.values(this.queries).filter(q =>
                !['Done','Rejected','NoMatches'].includes(q.phase)
            ).length;
        },

        async startDemo() {
            await fetch('/api/start-demo', { method: 'POST' });
            this.lastEvent = 'demo started';
        },
    };
}
</script>
</body>
</html>
"""

PIPELINE_PARTIAL_HTML = r"""<!-- HTMX reconciliation partial -->
<div class="pipeline-area">
    <div class="col-label">Lifecycle State</div>
    <div class="col-label" style="padding-left: 50px;">End State</div>

    {% set lifecycle = ['Queued', 'Validating', 'Searching', 'WritingReport'] %}
    {% set end_map = {'Validating': ('Rejected','end-rejected','rejected'),
                      'Searching': ('NoMatches','end-no-matches','rejected'),
                      'WritingReport': ('Done','end-done','done')} %}

    {% for phase in lifecycle %}
    {% if not loop.first %}
    <div class="arrow-down"><svg width="16" height="24" viewBox="0 0 16 24"><path d="M8 0v20M3 16l5 5 5-5" stroke="currentColor" stroke-width="1.5" fill="none"/></svg></div>
    <div></div>
    {% endif %}
    <div class="pipeline-row">
        <div class="phase-box">
            <div class="phase-label">{{ phase if phase != 'WritingReport' else 'Writing Report' }}</div>
            {% for q in state.columns.get(phase, []) %}
            <div class="card {{ 'active' if phase not in ['Queued'] else '' }}">
                <div class="query-text">{{ q.text }}</div>
                <div class="intent">{{ q.intent or q.id }}</div>
            </div>
            {% endfor %}
            {% if not state.columns.get(phase, []) %}<div class="empty-dash">--</div>{% endif %}
        </div>
        {% if phase in end_map %}
        {% set end_phase, end_class, card_class = end_map[phase] %}
        <div class="arrow-right"><svg width="32" height="16" viewBox="0 0 32 16"><path d="M0 8h26M22 3l5 5-5 5" stroke="currentColor" stroke-width="1.5" fill="none"/></svg></div>
        <div class="phase-box {{ end_class }}">
            <div class="phase-label">{{ end_phase.replace('NoMatches','No Matches') }}</div>
            {% for q in state.columns.get(end_phase, []) %}
            <div class="card {{ card_class }}">
                <div class="query-text">{{ q.text }}</div>
                <div class="intent">{{ q.intent or q.id }}</div>
            </div>
            {% endfor %}
            {% if not state.columns.get(end_phase, []) %}<div class="empty-dash">--</div>{% endif %}
        </div>
        {% endif %}
    </div>
    <div></div>
    {% endfor %}
</div>

<div class="dashboard">
    <h2>Dashboard</h2>
    {% set processing = (state.columns.get('Queued',[])|length + state.columns.get('Validating',[])|length + state.columns.get('Searching',[])|length + state.columns.get('WritingReport',[])|length) %}
    <div class="dash-stat"><div class="indicator processing"></div><div><div class="number">{{ processing }}</div><div class="label">Processing</div></div></div>
    <div class="dash-stat"><div class="indicator completed"></div><div><div class="number">{{ state.columns.get('Done',[])|length }}</div><div class="label">Completed</div></div></div>
    <div class="dash-stat"><div class="indicator rejected"></div><div><div class="number">{{ state.columns.get('Rejected',[])|length + state.columns.get('NoMatches',[])|length }}</div><div class="label">Rejected</div></div></div>
</div>
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
