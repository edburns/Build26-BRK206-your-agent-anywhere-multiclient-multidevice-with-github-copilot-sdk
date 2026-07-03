# Implementation plan: Java Real Estate Agent Orchestrator Demo (dd-3017826)

Human DRI: Ed Burns  
Reference C# demo: `BRK206-00/src/AgentOrchestrator/`  
Copilot SDK for Java: `copilot-sdk/java/` (version 1.0.7-SNAPSHOT)  
Related ADRs: `java/docs/adr/adr-005-tool-definition.md`, `java/docs/adr/adr-006-tool-definition-inline.md`

---

## Goal

Create a Java analog of the C# Blazor AgentOrchestrator demo that showcases the Copilot SDK for Java. The demo implements a real-estate lead-management pipeline (Queued → Validating → Searching → Writing Report → Done/Rejected) powered by multiple concurrent `CopilotSession` agents with custom tools, system message customization, and real-time UI updates.

### Technology stack

| Concern | Technology |
|---------|-----------|
| Runtime | OpenLiberty 26.0.0.5 |
| Platform | Jakarta EE 11 (Faces 4.0, CDI 4.0, WebSocket 2.1, JSON-B 3.0, JSON-P 2.1, Persistence 3.2) |
| UI framework | PrimeFaces 15.0.16 (jakarta classifier) |
| AI orchestration | Copilot SDK for Java 1.0.7-SNAPSHOT |
| Database | H2 in-memory for property listings |
| Build | Maven, Liberty Maven Plugin |
| JDK | 25+ (virtual threads available) |

### SDK features to demonstrate

1. Custom tool definition via `@CopilotTool` annotations (ADR-005) or `ToolDefinition.from(...)` lambdas (ADR-006)
2. Agentic session loop (`session.sendAndWait(...)`)
3. System message customization (`SystemMessageConfig`)
4. Built-in tool composition (`web_fetch`)
5. Real-time session events (`session.on(...)`)
6. `CopilotClient` in `Empty` mode (headless server-side)
7. Multiple concurrent sessions (one per enquiry)
8. Permission handling (`PermissionHandler.approveAll()`)
9. Tool overrides (`overridesBuiltInTool`)

---

## Completed phases

(None yet.)

---

## Phase 1 — Define the architecture mapping (C# → Java)

### 1.1 — Component mapping

| C# Component | Java Equivalent | Notes |
|---|---|---|
| `Program.cs` (WebApplication builder) | `server.xml` + CDI beans | Liberty features: `faces-4.0`, `cdi-4.0`, `websocket-2.1`, `persistence-3.2`, `jsonb-3.0` |
| `AppState.cs` (singleton) | `@ApplicationScoped` CDI bean | Holds `CopilotClient` and active agents map |
| `Agent.cs` | POJO managed by `AppState` | Each agent owns a `CopilotSession`; runs on virtual thread |
| `PropertyDatabase.cs` | `@ApplicationScoped` CDI bean + JPA `EntityManager` | H2 in-memory backend |
| `PropertyDbContext` (EF Core) | JPA `EntityManager` + `@Entity` classes | Standard Jakarta Persistence |
| Blazor Server interactive render | JSF + PrimeFaces + `f:websocket` push | Real-time updates via WebSocket push |
| `Session.On<SessionEvent>` | `session.on(SessionEvent.class, handler)` | Handler pushes update via `f:websocket` |
| `CopilotTool.DefineTool(method)` | `@CopilotTool` annotation on method | ADR-005 ergonomic API |
| `async Task RunAsync(...)` | Virtual thread (`Thread.ofVirtual().start(...)`) | JDK 25 virtual threads replace C# async/await |
| Tailwind CSS + Blazor components | PrimeFaces `p:outputPanel` + custom CSS/JS | ~70-75% stock components; animation is custom |

### 1.2 — Threading model

| C# | Java |
|---|---|
| `Task.Run(() => agent.RunAsync(client))` | `Thread.ofVirtual().start(() -> agent.run(client))` |
| `await Session.SendAndWaitAsync(...)` | `session.sendAndWait(...)` (blocks virtual thread) |
| `Task.Delay(15000)` | `Thread.sleep(Duration.ofSeconds(15))` on virtual thread |
| `event Action? UpdateUi` / `InvokeAsync(StateHasChanged)` | CDI `Event<UiUpdate>` → `f:websocket` push channel |

### 1.3 — Project structure

```
BRK206-00/src/java-agent-orchestrator/
├── pom.xml
├── src/
│   ├── main/
│   │   ├── java/
│   │   │   └── com/microsoft/build/realestate/
│   │   │       ├── Agent.java
│   │   │       ├── AppState.java
│   │   │       ├── Phase.java
│   │   │       ├── PipelineConfig.java
│   │   │       ├── Property.java
│   │   │       ├── Address.java
│   │   │       ├── PropertyDatabase.java
│   │   │       └── UiUpdateSocket.java
│   │   ├── resources/
│   │   │   ├── META-INF/
│   │   │   │   └── persistence.xml
│   │   │   └── data/
│   │   │       └── properties/  (copy 100 JSON seed files)
│   │   └── webapp/
│   │       ├── WEB-INF/
│   │       │   ├── web.xml
│   │       │   └── faces-config.xml
│   │       ├── index.xhtml (home page with pipeline view)
│   │       ├── resources/
│   │       │   ├── css/
│   │       │   │   └── pipeline.css
│   │       │   └── js/
│   │       │       └── pipeline.js (FLIP animation + pulse)
│   │       └── templates/
│   │           └── layout.xhtml
│   └── liberty/
│       └── config/
│           └── server.xml
└── README.md
```

---

## Phase 2 — Ignorance reduction: questions to answer before writing code

### 2.1 — CopilotClient lifecycle in Jakarta CDI

**Question:** How should `CopilotClient` be created and managed in CDI?

The C# demo creates `CopilotClient` as a singleton field in `AppState`. In Java, `CopilotClient` implements `AutoCloseable`. We need:

1. A `@Produces @ApplicationScoped` method that creates the client in `Empty` mode.
2. A `@Disposes` method that calls `close()` on shutdown.

**Spike needed:** Verify `CopilotClient` constructor options in 1.0.7-SNAPSHOT support `Empty` mode and `baseDirectory`.

**Action:** Read `CopilotClient` and `CopilotClientOptions` source to confirm API.

### 2.2 — `sendAndWait` blocking semantics on virtual threads

**Question:** Does the Java SDK's `sendAndWait(...)` block the calling thread, or does it return a `CompletableFuture`?

The C# demo uses `await Session.SendAndWaitAsync(...)`. In Java, if the method returns `CompletableFuture`, we can call `.join()` on a virtual thread. If it's already synchronous, we can call it directly.

**Action:** Read the Java SDK `CopilotSession` API to determine the method signature.

### 2.3 — Session event subscription in Java SDK

**Question:** What is the Java equivalent of `Session.On<SessionEvent>(handler)`?

Need to confirm:
- The method name and signature
- Whether it accepts a `Class<T>` event type filter
- Whether the handler receives events on the calling thread or a callback thread

**Action:** Read `CopilotSession` event API.

### 2.4 — WebSocket push from CDI to JSF

**Question:** How do we push UI updates from a background virtual thread (running the agent) to the browser?

Options:
| Option | Mechanism |
|--------|-----------|
| A | `f:websocket` (Jakarta Faces 4.0 built-in) with `PushContext.send(...)` |
| B | PrimeFaces `p:socket` (wraps Jakarta WebSocket) |
| C | Raw Jakarta WebSocket endpoint + JS `WebSocket` client |

**Recommendation:** Option A (`f:websocket`) — standard, no PrimeFaces-specific coupling for push.

**Spike needed:** Confirm OpenLiberty 26.0.0.5 `faces-4.0` feature supports `f:websocket` with CDI push.

### 2.5 — Property database: JPA on H2 with OpenLiberty

**Question:** Does OpenLiberty support H2 in-memory via its `persistence-3.2` feature (EclipseLink)?

H2 is well-supported by EclipseLink and avoids native library concerns that SQLite would introduce.

**Action:** Confirm H2 in-memory works with Liberty `persistence-3.2` and document `persistence.xml` configuration.

### 2.6 — PrimeFaces real-time UI update pattern

**Question:** What is the exact client-side pattern for updating the pipeline UI when a WebSocket message arrives?

Expected flow:
1. Agent moves to new phase → `PushContext.send(agentId, "phase-changed")`
2. Client receives WebSocket message
3. Client-side JS triggers FLIP animation (capture old position, update DOM, animate)
4. After animation, call `PrimeFaces.ajax.update('pipeline-panel')` for server-side re-render

**Spike needed:** Build a minimal prototype with `f:websocket` + `p:outputPanel` + `p:remoteCommand` to validate this pattern.

### 2.7 — Copilot SDK dependency resolution

**Question:** Is the 1.0.7-SNAPSHOT available in the local Maven repository, and what are its coordinates?

Expected GAV: `com.github:copilot-sdk-java:1.0.7-SNAPSHOT`

**Action:** Verify with `mvn dependency:resolve` or check `~/.m2/repository/com/github/copilot-sdk-java/`.

### 2.8 — Tool definition approach for this demo

**Question:** Should the demo use `@CopilotTool` annotations (ADR-005) or inline `ToolDefinition.from(...)` lambdas (ADR-006)?

The C# demo uses `CopilotTool.DefineTool(MethodGroup)` which maps to the annotation approach. For a demo that showcases the Java SDK ergonomics:

| Tool | Approach | Rationale |
|------|----------|-----------|
| `set_current_phase` | `@CopilotTool` on method in `Agent` | Shows annotation ergonomics (headline feature) |
| `report_intent` | `@CopilotTool` with `overridesBuiltInTool=true` | Shows tool override via annotation attribute |
| `search_properties` | `@CopilotTool` on method in `PropertyDatabase` | Shows multi-parameter schema generation |

**Recommendation:** Use annotations for all three — this is the closest Java analog to C#'s attribute-driven approach and the primary feature to demonstrate.

### 2.9 — OpenLiberty Maven plugin configuration

**Question:** What is the correct Liberty Maven Plugin configuration for Jakarta EE 11 with Faces 4.0?

**Action:** Look up `liberty-maven-plugin` latest version and `server.xml` feature list for faces + websocket + cdi + jpa.

---

## Phase 3 — Implementation (build order)

Each step should be a separately testable commit.

### 3.1 — Project scaffolding

**What:** Create Maven project with `pom.xml`, `server.xml`, empty source directories.

**Key files:**
- `pom.xml` — dependencies (PrimeFaces, Copilot SDK, H2, Jakarta EE API)
- `src/liberty/config/server.xml` — Liberty features
- `src/main/webapp/WEB-INF/web.xml`
- `src/main/webapp/WEB-INF/faces-config.xml`

**Gating criteria:** `mvn clean package liberty:run` starts an empty Liberty server with Faces enabled.

### 3.2 — Domain model and database seeding

**What:** JPA entities (`Property`, `Address`), persistence configuration, JSON data loader.

**Key files:**
- `Property.java`, `Address.java` (JPA entities)
- `META-INF/persistence.xml`
- `PropertyDatabase.java` (CDI bean with search method)
- Copy 100 JSON seed files from C# demo's `Data/Properties/`

**Gating criteria:** Application starts, seeds database from JSON files, `PropertyDatabase.search(...)` returns results.

### 3.3 — Core agent infrastructure

**What:** `Phase` enum, `Agent` class, `AppState` CDI bean, `CopilotClient` producer.

**Key files:**
- `Phase.java` — enum matching C# phases
- `Agent.java` — holds session, defines tools, runs agent loop
- `AppState.java` — `@ApplicationScoped`, manages agents map, owns `CopilotClient`

**Tool definitions in `Agent.java`:**
```java
@CopilotTool("Sets the current phase of the agent. Use this to report progress.")
void setCurrentPhase(@CopilotToolParam("The phase to transition to") Phase phase) {
    this.phase = phase;
    notifyUi();
}

@CopilotTool(name = "report_intent",
             value = "Reports the current intent of the agent",
             overridesBuiltInTool = true)
void reportIntent(@CopilotToolParam("Intent in max 4 words") String intent) {
    this.currentIntent = intent;
    notifyUi();
}
```

**Tool definition in `PropertyDatabase.java`:**
```java
@CopilotTool("Searches the real estate listings database...")
List<Property> searchProperties(
    @CopilotToolParam("Property type substring") String type,
    @CopilotToolParam("City substring") String city,
    // ... remaining parameters
) { ... }
```

**Gating criteria:** Agent constructs with `CopilotSession`, sends enquiry, tools get invoked, phase transitions occur (validated via logs or unit test with mock session).

### 3.4 — WebSocket push infrastructure

**What:** `f:websocket` channel for real-time UI updates.

**Key files:**
- `UiUpdateSocket.java` — CDI bean that wraps `PushContext`
- Integration in `Agent.java` — calls `pushContext.send(...)` when phase changes
- Client-side `<f:websocket>` tag in XHTML

**Gating criteria:** Phase changes push to browser; browser receives WebSocket messages with agent state.

### 3.5 — JSF pipeline view (static layout)

**What:** The main page with pipeline stages, agent cards, and the "+" button overlay.

**Key files:**
- `index.xhtml` — pipeline layout with `p:outputPanel` per stage
- `layout.xhtml` — page template
- `pipeline.css` — dark theme, grid layout matching C# demo's Tailwind styling
- Sample enquiries dropdown via `p:overlayPanel`

**Gating criteria:** Page renders the pipeline stages with correct layout. Static cards display in correct positions.

### 3.6 — Dynamic UI updates and animation

**What:** Wire WebSocket messages to DOM updates with FLIP animation and pulsing indicator.

**Key files:**
- `pipeline.js` — FLIP animation logic, pulse CSS class toggle
- `pipeline.css` — `@keyframes pulse` animation
- `p:remoteCommand` integrations for ajax updates after animation

**Gating criteria:** Enquiry cards animate between pipeline stages. Yellow pulse indicator follows the active card.

### 3.7 — Agent detail view

**What:** Side panel showing session events, tool calls, and agent report for a selected agent.

**Key files:**
- Detail panel in `index.xhtml` (or separate `detail.xhtml` fragment)
- `ToolCallView` equivalent — renders tool call/result pairs

**Gating criteria:** Clicking an agent card shows its event stream and tool interactions in real time.

### 3.8 — End-to-end integration testing

**What:** Verify the full demo works against a real or mocked Copilot CLI.

**Testing approaches:**
- With real CLI: source `env-java25.ps1`, run Liberty, submit enquiries, observe pipeline
- With replay proxy: use the SDK's test harness to replay canned responses

**Gating criteria:** At least two enquiries (one valid, one spam) flow through the pipeline to their expected terminal states.

### 3.9 — Demo polish and README

**What:** Final visual polish, error handling, and documentation.

**Key files:**
- `README.md` — setup instructions, screenshots, feature mapping
- Error display for failed agents
- Auto-removal of rejected agents after 15 seconds (matching C# behavior)

**Gating criteria:** Demo is presentable, README enables someone to clone and run it.

---

## Phase 4 — Follow-on work (not blocking demo)

### 4.1 — Alternative: inline lambda tools

Add a second code path that demonstrates `ToolDefinition.from(...)` lambda style alongside the annotation approach, showing both APIs. Could be a toggle or a separate agent variant.

### 4.2 — Docker / devcontainer support

Package the demo for easy reproduction with `Dockerfile` and `.devcontainer/devcontainer.json`.

### 4.3 — Slide deck integration

Add links to slides and recording in README once session is delivered.

---

## Acceptance checklist

Before calling the demo complete:

1. [ ] All 9 SDK features from the feature list are demonstrated
2. [ ] Pipeline UI shows real-time agent progression with animation
3. [ ] At least 3 sample enquiries work end-to-end (valid match, spam rejection, no-match rejection)
4. [ ] `@CopilotTool` annotation approach is clearly visible in source
5. [ ] Virtual threads handle concurrent agents without thread-pool exhaustion
6. [ ] `web_fetch` built-in tool is used for real-time web search
7. [ ] README documents setup, run, and feature mapping
8. [ ] No secrets or API keys committed to repo

---

## Risk register

| Risk | Mitigation |
|------|-----------|
| OpenLiberty `faces-4.0` + `f:websocket` push may have bugs | Fall back to PrimeFaces `p:socket` or raw WebSocket endpoint |
| PrimeFaces 15.x jakarta classifier may not align with Liberty's Faces impl | Test early in Phase 3.1; fallback to Mojarra standalone if needed |
| Copilot SDK 1.0.7-SNAPSHOT `@CopilotTool` may have unresolved edge cases | The annotation processor is tested in copilot-sdk CI; fall back to `ToolDefinition.from(...)` lambda API |
| H2 in-memory data loss on restart | Acceptable for demo; re-seed from JSON on each start |
| FLIP animation complexity in JSF partial updates | Accept simpler fade-in/fade-out if full FLIP proves too fragile with JSF DOM diffing |
| Virtual thread compatibility with Liberty internals | Liberty 26.x officially supports virtual threads; verify with spike |
