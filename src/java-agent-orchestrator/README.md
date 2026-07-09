# Java Real Estate Agent Orchestrator

A Jakarta EE 11 demo showcasing the **GitHub Copilot SDK for Java** as part of the
Microsoft Build 2026 session **BRK206 — Your Agent Anywhere**.

This is a direct Java port of the companion [C# Blazor demo](../AgentOrchestrator/), implementing
the same real-estate lead-management pipeline:

```
Customer Enquiry → QUEUED → VALIDATING → SEARCHING → WRITING_REPORT → DONE / REJECTED
```

Each enquiry spins up an isolated `CopilotSession` that uses custom tools, system message
customization, and real-time WebSocket push to update a pipeline dashboard in the browser.

---

## Technology stack

| Concern | Technology |
|---------|-----------|
| Runtime | OpenLiberty 26.0.0.5 |
| Platform | Jakarta EE 11 — Faces 4.1, CDI 4.1, WebSocket 2.2, Data 1.0, Persistence 3.2 |
| UI framework | PrimeFaces 15.0.16 (jakarta classifier) |
| AI orchestration | Copilot SDK for Java 1.0.7-SNAPSHOT |
| Database | H2 in-memory (10 seed property listings) |
| Build | Maven 3.9+ with Liberty Maven Plugin 3.12.0 |
| JDK | 25+ (virtual threads used for concurrent agent sessions) |

---

## Prerequisites

1. **JDK 25 or later** — required for virtual threads and SDK API compatibility.
   Verify with: `java -version`

2. **Maven 3.9 or later** — used to build and start OpenLiberty.
   Verify with: `mvn -version`

3. **Copilot SDK for Java stub** — the SDK jar (`com.github:copilot-sdk-java:1.0.7-SNAPSHOT`)
   must be installed in your local Maven repository (`.m2`).

4. **GitHub Copilot CLI** — the agent runtime.  The demo resolves the CLI from
   `~/.copilot/` by default (matching `CopilotClientMode.EMPTY`).  If your CLI is
   installed elsewhere, set the environment variable:
   ```bash
   export COPILOT_HOME=/path/to/your/.copilot
   ```

5. A **GitHub account with an active Copilot subscription** that the CLI can authenticate
   against (run `gh auth login` if prompted).

---

## Quick start

```bash
# 1. Navigate to the Java demo directory
cd src/java-agent-orchestrator

# 2. Build and start OpenLiberty
mvn clean package liberty:run

# 3. Open the pipeline dashboard
# http://localhost:9080/
```

Liberty prints a `The defaultServer server is ready to run a smarter planet.` banner when
the server is ready (typically within 30–60 seconds on first run while features download).

To stop the server, press `Ctrl+C` or run `mvn liberty:stop` in a second terminal.

### Sample enquiries to try

| Enquiry | Expected outcome |
|---------|-----------------|
| `3-bed house in London under £600k` | Searches → finds matches → DONE with report |
| `2-bed flat in Edinburgh` | Searches → finds matches → DONE with report |
| `cheap beachfront villa with infinity pool in Monaco` | REJECTED_NO_MATCHES |
| `asdfjkl;` | REJECTED_GARBAGE (spam) |

Submit multiple enquiries simultaneously to see concurrent virtual-thread agents in action.

---

## SDK feature mapping

| # | Feature | File | Line / method |
|---|---------|------|---------------|
| 1 | `@CopilotTool` annotation — ADR-005 ergonomic tool definition | `Agent.java` | `setCurrentPhase()` |
| 2 | `ToolDefinition.from(...)` lambda — ADR-006 inline tool | `Agent.java` | `reportIntentTool` |
| 3 | `ToolDefinition.fromObject(...)` — cross-class annotation tools | `Agent.java` | `dbTools` / `PropertyDatabase.searchProperties()` |
| 4 | `.overridesBuiltInTool(true)` — tool override | `Agent.java` | `reportIntentTool.overridesBuiltInTool(true)` |
| 5 | `SessionConfig.setSystemMessage(...)` — `CUSTOMIZE` mode | `Agent.java` | `Agent.run()` → `SystemMessageMode.CUSTOMIZE` |
| 6 | `session.sendAndWait(...)` — agentic loop | `Agent.java` | `session.sendAndWait(...).get()` |
| 7 | `session.on(handler)` — real-time session events | `Agent.java` | `session.on(event -> captureSessionEvent(...))` |
| 8 | `CopilotClientMode.EMPTY` — headless server-side client | `AppState.java` | `AppState()` constructor |
| 9 | `PermissionHandler.APPROVE_ALL` — permission handling | `Agent.java` | `sessionConfig.setOnPermissionRequest(...)` |

> **`web_fetch`** built-in tool is available to all sessions via the default toolset; the
> agent may call it during the Searching phase to look up real-time property information.

---

## Architecture

```
Browser                    OpenLiberty (Jakarta EE 11)
  │                              │
  │   HTTP/JSF partial update    │   ┌─────────────────────────────────┐
  │◄────────────────────────────►│   │  AppState (@ApplicationScoped)  │
  │                              │   │  ┌──────────────────────────┐   │
  │  WebSocket push              │   │  │ CopilotClient (EMPTY)    │   │
  │◄─────────────────────────────│   │  │  (one per Liberty app)   │   │
  │                              │   │  └──────────────────────────┘   │
  │  Submit enquiry (Ajax)       │   │  Map<id, Agent>                 │
  │─────────────────────────────►│   └─────────────────────────────────┘
                                 │
                    submitEnquiry()
                                 │   Virtual thread per agent:
                                 │   ┌─────────────────────────────────┐
                                 │   │  Agent.run(copilotClient)       │
                                 │   │    createSession() → QUEUED     │
                                 │   │    sendAndWait(enquiry)         │
                                 │   │      ↓ tool calls ↓             │
                                 │   │    set_current_phase(VALIDATING)│
                                 │   │    search_properties(...)       │
                                 │   │    report_intent(...)           │
                                 │   │    set_current_phase(DONE)      │
                                 │   │    ← AssistantMessageEvent      │
                                 │   └─────────────────────────────────┘
                                 │
                    UiUpdateSocket.pushPhaseChange(agentId)
                                 │   f:websocket → browser JS →
                                 │   p:remoteCommand → partial update
```

**Pipeline phases:**
- `QUEUED` — Agent is created, waiting for the Copilot session to start.
- `VALIDATING` — Agent checks whether the enquiry is genuine.
- `SEARCHING` — Agent queries the property database with `search_properties`.
- `WRITING_REPORT` — Agent writes a salesperson briefing report.
- `DONE` — Report is complete; visible in the detail panel.
- `REJECTED_GARBAGE` — Enquiry was spam or off-topic.
- `REJECTED_NO_MATCHES` — No matching properties found.

After 15 seconds, rejected agents are automatically removed from the pipeline
(using a virtual thread + `Thread.sleep`), mirroring the C# demo's `Task.Delay(15000)`.

---

## Project structure

```
src/java-agent-orchestrator/
├── pom.xml                          Maven build, Liberty plugin, dependencies
├── src/
│   ├── main/
│   │   ├── java/com/microsoft/build/realestate/
│   │   │   ├── Agent.java           Agent session logic + @CopilotTool methods
│   │   │   ├── AgentEvent.java      Lightweight event record for the detail panel
│   │   │   ├── AppState.java        Singleton: CopilotClient + active agent map
│   │   │   ├── Phase.java           Pipeline phase enum
│   │   │   ├── PipelineView.java    JSF request-scoped backing bean
│   │   │   ├── Property.java        JPA entity: property listing
│   │   │   ├── PropertyDatabase.java  CDI bean + search_properties @CopilotTool
│   │   │   ├── SelectionState.java  Session-scoped selected-agent tracker
│   │   │   └── UiUpdateSocket.java  Wraps Jakarta Faces PushContext
│   │   ├── resources/
│   │   │   └── META-INF/
│   │   │       └── persistence.xml  JPA config (H2 + EclipseLink)
│   │   └── webapp/
│   │       ├── index.xhtml          Main pipeline dashboard page
│   │       ├── WEB-INF/
│   │       │   ├── web.xml          Enables f:websocket endpoint
│   │       │   └── faces-config.xml Jakarta Faces configuration
│   │       └── resources/
│   │           ├── css/pipeline.css Dark theme + CSS transitions
│   │           └── js/pipeline.js   WebSocket push → remoteCommand → DOM animation
│   ├── liberty/config/
│   │   └── server.xml               Liberty features + H2 datasource
│   └── test/java/…/
│       ├── AgentTest.java           Unit tests for Agent (no container needed)
│       └── PhaseTest.java           Unit tests for Phase enum
└── README.md                        This file
```

---

## Comparison with the C# demo

| Aspect | C# Blazor | Java (Jakarta EE 11) |
|--------|-----------|----------------------|
| **Concurrency** | `async`/`await` + `Task.Run` | Virtual threads (`Thread.ofVirtual()`) |
| **Agentic loop** | `await Session.SendAndWaitAsync(...)` | `session.sendAndWait(...).get()` (blocks virtual thread) |
| **Timed removal** | `await Task.Delay(15000)` | `Thread.sleep(Duration.ofSeconds(15))` on virtual thread |
| **UI framework** | Blazor Server (interactive components) | PrimeFaces + JSF `f:websocket` push |
| **Real-time push** | `InvokeAsync(StateHasChanged)` | `PushContext.send(agentId + ":phase-changed")` |
| **DI container** | Microsoft.Extensions.DependencyInjection | Jakarta CDI 4.1 (`@ApplicationScoped`, `@Inject`) |
| **Database** | EF Core `DbContext` | Jakarta Data `@Repository` + JPA 3.2 |
| **Tool definition** | `CopilotTool.DefineTool(method)` | `@CopilotTool` annotation (ADR-005) |
| **Deployment** | `dotnet run` (self-hosted Kestrel) | `mvn liberty:run` (embedded OpenLiberty) |

Both demos implement identical agent behaviour: the pipeline phases, the prompt structure,
and the three sample enquiry scenarios are the same. The SDK API shapes are intentionally
analogous, showing that the Copilot SDK design is language-idiomatic rather than prescriptive.

---

## Running the tests

Unit tests for `Agent` and `Phase` run without a container or CLI:

```bash
mvn test
```

Tests use an anonymous `UiUpdateSocket` stub (no-op) to avoid the Jakarta Faces runtime
dependency. The Copilot SDK jar must be installed in `~/.m2` for the tests to compile.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|-------------|-----|
| `Could not find artifact com.github:copilot-sdk-java` | Stub not installed | Install the SDK jar to `~/.m2` per setup instructions |
| `CWWKF1405E` feature conflict | Mixed EE 10 + EE 11 features | Ensure `server.xml` uses only EE 11 features (`faces-4.1`, not `faces-4.0`) |
| Agent stuck in QUEUED, never progresses | Copilot CLI not found | Verify `~/.copilot/` exists or set `COPILOT_HOME` |
| Agent shows error state (red border) | CLI not running or auth failed | Check Liberty logs (`target/liberty/wlp/usr/servers/defaultServer/logs/messages.log`) |
| WebSocket push not updating cards | `ENABLE_WEBSOCKET_ENDPOINT` not set | Verify `web.xml` has `jakarta.faces.ENABLE_WEBSOCKET_ENDPOINT=true` |
