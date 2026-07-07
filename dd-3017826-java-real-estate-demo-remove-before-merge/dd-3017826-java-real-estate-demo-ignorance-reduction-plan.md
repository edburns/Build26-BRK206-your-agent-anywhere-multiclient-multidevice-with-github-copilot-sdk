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

**Resolution:**

**✅ RESOLVED (2026-07-06):** Confirmed. The Java API uses `setCopilotHome(String)` (not `baseDirectory`). In `EMPTY` mode the constructor requires either `copilotHome` or `cliUrl`, otherwise it throws `IllegalArgumentException`. Existing test: `copilot-sdk/java/src/test/java/com/github/copilot/CopilotClientModeTest.java` (`testEmptyModeRequiresCopilotHome`, `testEmptyModeWithCopilotHome`).

Java construction pattern for the demo:
```java
CopilotClient client = new CopilotClient(
    new CopilotClientOptions()
        .setMode(CopilotClientMode.EMPTY)
        .setCopilotHome(Path.of(System.getProperty("user.home"), ".copilot").toString())
);
```

### 2.2 — `sendAndWait` blocking semantics on virtual threads

**Question:** Does the Java SDK's `sendAndWait(...)` block the calling thread, or does it return a `CompletableFuture`?

The C# demo uses `await Session.SendAndWaitAsync(...)`. In Java, if the method returns `CompletableFuture`, we can call `.join()` on a virtual thread. If it's already synchronous, we can call it directly.



**Resolution:**
**✅ RESOLVED (2026-07-06):** `sendAndWait` returns `CompletableFuture<AssistantMessageEvent>` (async). Three overloads exist:
```java
CompletableFuture<AssistantMessageEvent> sendAndWait(String prompt)           // 60s default timeout
CompletableFuture<AssistantMessageEvent> sendAndWait(MessageOptions options)  // 60s default timeout
CompletableFuture<AssistantMessageEvent> sendAndWait(MessageOptions options, long timeoutMs)
```
Tests uniformly block via `.get(60, TimeUnit.SECONDS)`. For the demo on virtual threads, use `.get()` or `.join()` — both are safe since virtual threads don't pin platform threads on blocking calls. Existing tests confirming this pattern: `CopilotRequestHandlerE2ETest`, `CompactionTest`, `EventFidelityTest`, `McpAndAgentsTest` (all in `copilot-sdk/java/src/test/java/com/github/copilot/e2e/`).

### 2.3 — Session event subscription in Java SDK

**Question:** What is the Java equivalent of `Session.On<SessionEvent>(handler)`?

Need to confirm:
- The method name and signature
- Whether it accepts a `Class<T>` event type filter
- Whether the handler receives events on the calling thread or a callback thread

**Resolution:**

**✅ RESOLVED (2026-07-06):** Two overloads on `CopilotSession`:
```java
Closeable on(Consumer<SessionEvent> handler)                          // all events
<T extends SessionEvent> Closeable on(Class<T> eventType, Consumer<T> handler)  // typed filter
```
- Yes, accepts `Class<T>` filter (matches via `eventType.isInstance(event)`)
- Returns `Closeable` — call `.close()` to unsubscribe
- Handlers invoked **synchronously on the JSON-RPC reader/dispatch thread** (no separate callback executor)
- Demo pattern: `session.on(AssistantMessageEvent.class, msg -> { /* push to WebSocket */ })`
- README Quick Start shows this exact usage
- Tests: `SessionEventHandlingTest.java` (`testTypedEventHandler`, `testUnsubscribe`), `SessionEventsE2ETest.java`, `StreamingFidelityTest.java`

**Threading implication for the demo:** Since handlers run on the dispatch thread, any expensive work (like WebSocket push) should be offloaded or kept lightweight. For this demo the WebSocket push is trivial so inline is fine.

### 2.4 — WebSocket push from CDI to JSF

**Question:** How do we push UI updates from a background virtual thread (running the agent) to the browser?

Options:
| Option | Mechanism |
|--------|-----------|
| A | `f:websocket` (Jakarta Faces 4.0 built-in) with `PushContext.send(...)` |
| B | PrimeFaces `p:socket` (wraps Jakarta WebSocket) |
| C | Raw Jakarta WebSocket endpoint + JS `WebSocket` client |

**Recommendation:** Option A (`f:websocket`) — standard, no PrimeFaces-specific coupling for push.

**Resolution:**
**✅ RESOLVED (2026-07-06):** Spike confirmed. OpenLiberty 26.0.0.5 with `faces-4.0`, `cdi-4.0`, and `websocket-2.1` features fully supports `f:websocket` with `@Push PushContext` CDI injection. Tested in `dd-3017826-java-real-estate-demo-remove-before-merge/phase-02-2.4-cdi-and-websocket-push/`. Key requirements:
- `web.xml` must set `jakarta.faces.ENABLE_WEBSOCKET_ENDPOINT` = `true`
- `server.xml` needs features: `faces-4.1`, `cdi-4.1`, `websocket-2.1` (EE 11 level required for compatibility with `data-1.0`)
- CDI bean injects `@Inject @Push(channel="name") PushContext pushContext;` and calls `pushContext.send(data)`
- XHTML uses `<f:websocket channel="name" onmessage="jsCallback" />`

### 2.5 — Property database: Jakarta Data + H2 in-memory on OpenLiberty

**Question:** Does OpenLiberty support H2 in-memory via its `persistence-3.2` feature (EclipseLink)?

H2 is well-supported by EclipseLink and avoids native library concerns that SQLite would introduce.

**Resolution:**
**✅ RESOLVED (2026-07-06):** Confirmed. Jakarta Data 1.0 + H2 in-memory works on OpenLiberty 26.0.0.5. **Decision: Use Jakarta Data (`@Repository`) instead of raw JPA for the demo** — it's a cleaner, more modern API and a better showcase of Jakarta EE 11.

Spike app: `dd-3017826-java-real-estate-demo-remove-before-merge/phase-02-2.5-h2-in-memory-jpa-open-liberty/`

Key findings and gotchas:
1. **Feature versions must be EE 11 level** — `data-1.0` requires `cdi-4.1`, `faces-4.1`, `persistence-3.2` (NOT `cdi-4.0`/`faces-4.0` which are EE 10)
2. **Jakarta Data API not in the EE 11 umbrella jar** — add explicit `jakarta.data:jakarta.data-api:1.0.1` (scope: provided)
3. **persistence.xml namespace** — Liberty 26.0.0.5's parser requires `xmlns="http://xmlns.jcp.org/xml/ns/persistence"` (not the `jakarta.ee` namespace)
4. **H2 datasource config** — use `<properties URL="jdbc:h2:mem:name;DB_CLOSE_DELAY=-1" />` (capital `URL`)
5. **EclipseLink H2 platform** — must set `eclipselink.target-database` to `org.eclipse.persistence.platform.database.H2Platform` for correct DDL generation with H2 2.x
6. **`@Find` parameter binding** — requires either `-parameters` compiler flag OR `@By("attributeName")` annotations. The `@By` approach is more explicit and reliable.
7. **`@Query` for range queries** — `@Find` only does equality; use `@Query("WHERE attr >= ?1")` for comparisons
8. **`GenerationType.AUTO`** — use instead of `IDENTITY` for H2 2.x compatibility

server.xml features for the real demo:
```xml
<feature>data-1.0</feature>
<feature>persistence-3.2</feature>
<feature>faces-4.1</feature>
<feature>cdi-4.1</feature>
<feature>websocket-2.2</feature>
```

Note: The 2.4 spike used `faces-4.0`/`cdi-4.0` — those worked alone but are **incompatible** with `data-1.0`. The real demo must use EE 11 level (`faces-4.1`/`cdi-4.1`) throughout.

### 2.6 — PrimeFaces real-time UI update pattern

**Question:** What is the exact client-side pattern for updating the pipeline UI when a WebSocket message arrives?

**Resolution:**

**✅ RESOLVED (2026-07-06):** Confirmed. The pattern works on OpenLiberty 26.0.0.5 with PrimeFaces 15.0.16 (jakarta classifier).

Spike app: `dd-3017826-java-real-estate-demo-remove-before-merge/phase-02-2.6-update-pipeline-ui-primefaces/`

Validated flow:
1. Server CDI bean calls `pushContext.send("phase-changed:PHASE_NAME")` — works from any thread including virtual threads
2. Client receives WebSocket message via `<f:websocket channel="pipelineChannel" onmessage="handlePipelinePush" />`
3. Client JS calls `refreshPipeline()` — a `<p:remoteCommand>` that triggers server-side re-render
4. PrimeFaces partial update re-renders `<p:outputPanel id="pipelinePanel">` and `<p:outputPanel id="statusPanel">`
5. CSS transitions (`transition: border-color 0.5s, background-color 0.5s, transform 0.3s`) animate the phase change smoothly

Key configuration:
- **`websocket-2.2`** (NOT 2.1) required with EE 11 features — `faces-4.1` pulls in `servlet-6.1` which conflicts with `websocket-2.1`
- PrimeFaces `<p:remoteCommand name="refreshPipeline" update="pipelinePanel statusPanel" oncomplete="animationComplete()" />` bridges the websocket event to a JSF ajax lifecycle
- `web.xml` must set `jakarta.faces.ENABLE_WEBSOCKET_ENDPOINT=true`
- Background threads (virtual threads) can call `PushContext.send()` without being in a JSF request context — CDI `@ApplicationScoped` handles this correctly

server.xml features for the real demo (corrected from earlier spikes):
```xml
<feature>faces-4.1</feature>
<feature>cdi-4.1</feature>
<feature>websocket-2.2</feature>
```

Note: No FLIP animation needed — CSS `transition` on the phase cards handles the visual movement when classes change between `active`/`completed` states during the PrimeFaces partial update.

### 2.7 — Copilot SDK dependency resolution

Removed. User guarantees this is satisfied.

### 2.8 — Tool definition approach for this demo

**Question:** Should the demo use `@CopilotTool` annotations (ADR-005) or inline `ToolDefinition.from(...)` lambdas (ADR-006)?


**Resolution:**
**✅ RESOLVED (2026-07-06):** Use a **mix of both styles** to showcase the full breadth of the Java SDK's tool ergonomics. The C# demo's `ReportIntent` is a trivial 2-line method with `OverridesBuiltInTool = true` — it's a natural fit for the inline lambda API.

| Tool | Style | Rationale |
|------|-------|-----------|
| `set_current_phase` | `@CopilotTool` annotation on method in `Agent` | Shows headline annotation ergonomics |
| `report_intent` | `ToolDefinition.from(...)` lambda + `.overridesBuiltInTool(true)` | Shows lightweight inline tools + fluent option modifiers |
| `search_properties` | `@CopilotTool` annotation on method in `PropertyDatabase` | Shows multi-parameter schema generation + cross-class tools |

Example `report_intent` as lambda:

```java
ToolDefinition reportIntent = ToolDefinition
    .from(
        "report_intent",
        "Reports the current intent of the agent",
        Param.of(String.class, "intent", "Intent in max 4 words"),
        intent -> { currentIntent = intent; updateUi(); return "ok"; })
    .overridesBuiltInTool(true);
```

This gives the demo three distinct styles, making it a better showcase than using only annotations.

### 2.9 — OpenLiberty Maven plugin configuration

**Question:** What is the correct Liberty Maven Plugin configuration for Jakarta EE 11 with Faces 4.0?

**Resolution:**
**✅ RESOLVED (2026-07-06):** Proven across spikes 2.4, 2.5, and 2.6. The correct configuration:

**liberty-maven-plugin:** `3.12.0` (3.12.2 does not exist)

**pom.xml properties:**
```xml
<liberty.var.default.http.port>9080</liberty.var.default.http.port>
<liberty.runtime.groupId>io.openliberty</liberty.runtime.groupId>
<liberty.runtime.artifactId>openliberty-runtime</liberty.runtime.artifactId>
<liberty.runtime.version>26.0.0.5</liberty.runtime.version>
```

**server.xml features (full demo set):**
```xml
<featureManager>
    <feature>data-1.0</feature>
    <feature>persistence-3.2</feature>
    <feature>faces-4.1</feature>
    <feature>cdi-4.1</feature>
    <feature>websocket-2.2</feature>
</featureManager>
```

**Key constraints:**
- All features must be EE 11 level — mixing EE 10 (`faces-4.0`/`cdi-4.0`/`websocket-2.1`) with EE 11 (`data-1.0`) causes `CWWKF1405E` singleton conflicts
- H2 driver deployed via `copyDependencies` to `jdbc/` folder (not bundled in WAR)
- DataSource configured in `server.xml` with `<properties URL="jdbc:h2:mem:...;DB_CLOSE_DELAY=-1" />`
- `persistence.xml` must use `xmlns="http://xmlns.jcp.org/xml/ns/persistence"` (Liberty rejects the `jakarta.ee` namespace)

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

This was already added to the plan as of `e9c438a114e30d040ca871480af39a856ccb9fd3`.

### 4.2 — Docker / devcontainer support

Package the demo for easy reproduction with `Dockerfile` and `.devcontainer/devcontainer.json`.



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
