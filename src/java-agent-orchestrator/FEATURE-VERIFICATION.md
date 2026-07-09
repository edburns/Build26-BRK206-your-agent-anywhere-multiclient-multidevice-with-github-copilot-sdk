# SDK Feature Verification — Java Real Estate Agent Orchestrator

This document maps each of the **9 Copilot SDK for Java features** from the demo goal to the
exact class, method, and line(s) in the codebase where the feature is demonstrated.
It also records the test scenarios used to verify end-to-end behaviour.

---

## SDK Feature Checklist

| # | Feature | Status | Location |
|---|---------|--------|----------|
| 1 | Custom tool definition via `@CopilotTool` annotations | ✅ | `Agent.java`, `PropertyDatabase.java` |
| 2 | Agentic session loop (`session.sendAndWait`) | ✅ | `Agent.java` — `run()` |
| 3 | System message customisation (`SystemMessageConfig`) | ✅ | `Agent.java` — `run()` |
| 4 | Built-in tool composition (`web_fetch`) | ⚠️ | System message hints; requires live CLI |
| 5 | Real-time session events (`session.on`) | ✅ | `Agent.java` — `run()` |
| 6 | `CopilotClient` in `EMPTY` mode | ✅ | `AppState.java` — constructor |
| 7 | Multiple concurrent sessions | ✅ | `AppState.java` — `submitEnquiry()` |
| 8 | Permission handling (`PermissionHandler.APPROVE_ALL`) | ✅ | `Agent.java` — `SessionConfig` setup |
| 9 | Tool overrides (`overridesBuiltInTool`) | ✅ | `Agent.java` — `report_intent` lambda |

**Result: 8 of 9 features confirmed in source code; `web_fetch` requires a live CLI.**

---

## Feature Detail

### Feature 1 — `@CopilotTool` annotation (ADR-005)

Two classes use `@CopilotTool` to expose methods as SDK tools:

**`Agent.java`** — `setCurrentPhase` method:
```java
@CopilotTool(value = "Sets the current phase of the agent. Use this to report progress.",
             name = "set_current_phase")
public String setCurrentPhase(
        @CopilotToolParam("The phase to transition to ...") String phaseName) { ... }
```

**`PropertyDatabase.java`** — `searchProperties` method:
```java
@CopilotTool(value = "Searches the real estate listings database. Returns up to 10 matching properties.",
             name = "search_properties")
@Transactional
public List<Property> searchProperties(
        @CopilotToolParam("Property type substring ...") String type,
        @CopilotToolParam("City substring ...") String city,
        @CopilotToolParam("Minimum number of bedrooms ...") int minBedrooms,
        @CopilotToolParam("Maximum price in GBP ...") double maxPriceGbp) { ... }
```

Tools are registered via `ToolDefinition.fromObject(this)` and
`ToolDefinition.fromObject(propertyDatabase)` in `Agent.run()`.

---

### Feature 2 — Agentic session loop (`session.sendAndWait`)

In `Agent.run()`, the agent session is created and the enquiry is dispatched with a single
blocking `sendAndWait` call. The SDK drives the full agentic loop internally — repeatedly
calling tools and sending follow-up prompts until the model stops.

```java
AssistantMessageEvent result = session.sendAndWait(
        "<enquiry>" + xmlEscape(enquiry) + "</enquiry>").get();
```

---

### Feature 3 — System message customisation

`Agent.run()` creates a `SystemMessageConfig` in `CUSTOMIZE` mode and replaces the
`IDENTITY` section with a real-estate workflow prompt:

```java
SystemMessageConfig systemMessage = new SystemMessageConfig()
        .setMode(SystemMessageMode.CUSTOMIZE);
systemMessage.getSections().put(SystemMessageSections.IDENTITY,
        new SectionOverride()
                .setAction(SectionOverrideAction.REPLACE)
                .setContent("""
                    You are part of a real estate recommendation system. ...
                    """));
```

The prompt instructs the model about the full workflow (VALIDATING → SEARCHING →
WRITING_REPORT → DONE or REJECTED) and mandates calling `set_current_phase` and
`report_intent` at each step.

---

### Feature 4 — Built-in tool composition (`web_fetch`)

**Status: ⚠️ Conditional on live CLI availability.**

The `web_fetch` built-in tool is part of the SDK's default tool set and is available
to the agent automatically when a real Copilot CLI is connected. The system message
does not explicitly exclude it, so the model can call `web_fetch` if it chooses to
supplement property listings with external information.

To verify during a live run:
1. Connect Liberty to a real Copilot CLI (`~/.copilot` must be populated).
2. Submit an enquiry with a specific city query.
3. Check the detail panel for a `tool_call` event with `tool: web_fetch`.

If the model does not call `web_fetch` spontaneously, the system message can be amended
to include: _"You may use web_fetch to look up additional neighbourhood information."_

---

### Feature 5 — Real-time session events (`session.on`)

In `Agent.run()`, all session events are subscribed with a typed-untyped handler:

```java
sessionSubscription = session.on(event -> {
    captureSessionEvent(event);
    uiUpdateSocket.pushDetailUpdate(id);
});
```

`captureSessionEvent` branches on event class name (using a `switch` on
`event.getClass().getSimpleName()`) to handle:
- `AssistantMessageEvent` — captures the final report text and tool requests
- `ToolExecutionStartEvent` — records tool name and arguments
- `ToolExecutionCompleteEvent` — records tool result and correlates with prior start event

Each captured event is stored in the agent's bounded `ArrayDeque<AgentEvent>` (max 100
entries) and surfaced in the detail panel on the right-hand side of the UI.

---

### Feature 6 — `CopilotClient` in `EMPTY` mode

`AppState` creates a single application-scoped `CopilotClient` in `EMPTY` mode,
which is the headless server-side mode where no browser window is spawned:

```java
// AppState constructor
String copilotHome = Path.of(System.getProperty("user.home"), ".copilot").toString();
this.copilotClient = new CopilotClient(
        new CopilotClientOptions()
                .setMode(CopilotClientMode.EMPTY)
                .setCopilotHome(copilotHome));
```

`@PreDestroy` in `AppState` calls `copilotClient.close()` to clean up on
application shutdown.

---

### Feature 7 — Multiple concurrent sessions

`AppState.submitEnquiry()` creates a new `Agent` and launches it on a **virtual thread**
for each submitted enquiry. Each agent creates its own `CopilotSession` independently:

```java
Thread.ofVirtual().name("agent-" + agentId).start(() -> {
    try {
        agent.run(copilotClient);
    } finally {
        if (agent.isRejected()) {
            scheduleRemoval(agentId);
        }
    }
});
```

`ConcurrentHashMap<String, Agent>` in `AppState` protects the shared agent map.
Virtual threads avoid platform-thread-pool exhaustion under concurrent load
(JDK 25 `Thread.ofVirtual()`).

**Concurrent-submission test:** Submit three enquiries within 5 seconds and confirm
all three agent cards appear in the pipeline grid and progress independently.

---

### Feature 8 — Permission handling

`SessionConfig` in `Agent.run()` sets the permission handler to `APPROVE_ALL`, which
is the built-in handler that auto-approves all tool-call permission requests:

```java
SessionConfig sessionConfig = new SessionConfig()
        .setOnPermissionRequest(PermissionHandler.APPROVE_ALL)
        ...
```

This ensures the demo runs without manual intervention. In a production scenario,
`APPROVE_ALL` would be replaced with a handler that validates each request against
a policy.

---

### Feature 9 — Tool override (`overridesBuiltInTool`)

The `report_intent` tool is defined as an **inline lambda** (ADR-006 style) that overrides
the SDK's built-in `report_intent` tool so the demo can intercept and display the model's
stated intent in the UI detail panel:

```java
ToolDefinition reportIntentTool = ToolDefinition
        .from("report_intent",
              "Reports the current intent of the agent",
              Param.of(String.class, "intent", "Intent in max 4 words"),
              (String intent) -> {
                  currentIntent = intent;
                  addEvent(Instant.now(), "intent", "Intent updated", intent);
                  notifyUi();
                  return "ok";
              })
        .overridesBuiltInTool(true);  // <-- override marker
```

This also serves as the example of the ADR-006 inline lambda style (contrast with
ADR-005 annotation style used for `set_current_phase` and `search_properties`).

---

## End-to-End Test Scenarios

These scenarios require the application to be running (`mvn clean package liberty:run`
from `src/java-agent-orchestrator/`) with a functioning Copilot CLI installation
(~/.copilot populated via `gh copilot login` or equivalent).

### Scenario 1 — Valid home-buyer enquiry

**Input:** _"I'm looking for a 3-bedroom house in Bristol under £700,000"_

| Step | Expected Phase | Verification |
|------|---------------|-------------|
| Submit | QUEUED | Agent card appears in Queued column |
| Agent starts | VALIDATING | Card moves to Validating; `report_intent` shows in detail panel |
| After validation | SEARCHING | `set_current_phase("SEARCHING")` called; card moves to Searching |
| After search | WRITING_REPORT | `search_properties` called with city="Bristol", minBedrooms=3; card moves to Writing Report |
| Completion | DONE | Final report visible in detail panel; card in Done column |

**Verify in detail panel:**
- `phase_change` events: QUEUED → VALIDATING → SEARCHING → WRITING_REPORT → DONE
- `intent` events at each stage (from `report_intent` tool calls)
- `tool_call` event for `search_properties` with appropriate parameters
- `assistant_message` event containing property listings from the database

### Scenario 2 — Spam / irrelevant enquiry

**Input:** _"Buy cheap viagra online now! Best prices guaranteed!!!"_

| Step | Expected Phase | Verification |
|------|---------------|-------------|
| Submit | QUEUED | Agent card appears |
| Agent starts | VALIDATING | Card moves to Validating |
| After validation | REJECTED_GARBAGE | Card moves to Rejected column (label: "Rejected") |
| After 15 seconds | (removed) | Card disappears from UI (auto-removal after linger period) |

**Verify:**
- No `tool_call` event for `search_properties` (spam rejected before search phase)
- `phase_change` event: QUEUED → VALIDATING → REJECTED_GARBAGE
- `intent` event shows something like "Spam detected" or "Invalid enquiry"

### Scenario 3 — Valid request, no matching listings

**Input:** _"I need a 10-bedroom castle in Antarctica under £50"_

| Step | Expected Phase | Verification |
|------|---------------|-------------|
| Submit | QUEUED → VALIDATING | Genuine enquiry, passes validation |
| Search | SEARCHING | `search_properties` called; returns empty list |
| Completion | REJECTED_NO_MATCHES or DONE | Agent completes without hanging |

**Verify:**
- `search_properties` was called (visible as `tool_call` event in detail panel)
- Agent reaches a terminal state (no infinite loop)
- Final report (or rejection message) acknowledges no matches

### Scenario 4 — Concurrent submissions

Submit three enquiries within 5 seconds:
1. "3-bedroom flat in London under £600,000"
2. "Buy crypto now!!!" (spam)
3. "2-bedroom bungalow in Brighton under £500,000"

**Verify:**
- All three agent cards appear in the pipeline grid simultaneously
- Each agent progresses independently (no cross-contamination of state)
- Spam agent (enquiry 2) reaches REJECTED_GARBAGE; others proceed to DONE
- No Liberty log errors mentioning deadlock, thread starvation, or unhandled exceptions

---

## Error Handling Validation

### CLI unavailable

When `~/.copilot` is not populated or the CLI is unreachable:

1. Submit an enquiry
2. Agent transitions to QUEUED, then the `run()` method throws an exception
3. **Expected:** Agent transitions to `REJECTED_GARBAGE` with an error event in the
   detail panel (no stack trace surfaced in the browser UI)

Code path: `Agent.run()` `catch (Exception e)` block:
```java
} catch (Exception e) {
    LOG.severe("Agent " + id + " failed: " + e.getMessage());
    addEvent(Instant.now(), "session_error", "Session failed", e.getMessage());
    if (!phase.isTerminal()) {
        phase = Phase.REJECTED_GARBAGE;
        ...
    }
}
```

### Rapid submissions

Submit 5+ enquiries within 2 seconds and verify:
- No `NullPointerException` or `ConcurrentModificationException` in Liberty logs
- All agents progress independently on separate virtual threads
- `ConcurrentHashMap` in `AppState` prevents lost-update issues

---

## Testing Approach Notes

### Live CLI approach (preferred for demo)

1. Ensure GitHub Copilot CLI is installed and authenticated:
   ```
   gh extension install github/gh-copilot
   gh copilot --version
   ```
2. Start Liberty: `mvn clean package liberty:run`
3. Open http://localhost:9080 in a browser
4. Submit test scenarios 1–4 above manually
5. Observe pipeline grid and detail panel

### Replay proxy approach (CI-friendly)

The Copilot SDK test harness (`copilot-sdk/test/harness/`) provides a replay proxy that
can serve pre-recorded YAML snapshots of CLI responses. To use it:

1. Record a real session using the SDK's capture mode
2. Place the YAML snapshot in `src/test/resources/replay/`
3. Set `CopilotClientOptions.setCliUrl("localhost:<proxy-port>")` in `AppState`

Full replay integration tests are out of scope for this release; they require access to
the SDK's internal test harness infrastructure which is not bundled with the demo.

---

## Acceptance Checklist (from Phase 3.8)

- [x] All 9 SDK features identified and mapped to source code locations
- [x] Pipeline UI shows real-time agent progression (WebSocket push via `f:websocket`)
- [x] System message drives VALIDATING → SEARCHING → WRITING_REPORT → DONE/REJECTED workflow
- [x] `@CopilotTool` annotation style demonstrated (`set_current_phase`, `search_properties`)
- [x] `ToolDefinition.from(...)` lambda style demonstrated (`report_intent`)
- [x] `overridesBuiltInTool(true)` demonstrated on `report_intent`
- [x] Virtual threads used for concurrent agent sessions (JDK 25 `Thread.ofVirtual()`)
- [x] `PermissionHandler.APPROVE_ALL` configured for unattended demo execution
- [x] `CopilotClient` in `EMPTY` mode (no browser window)
- [x] Error handling: CLI-unavailable scenario handled gracefully in `Agent.run()` catch block
- [x] Auto-removal of rejected agents after 15-second linger (`AppState.scheduleRemoval()`)
- [x] No secrets or API keys committed to the repository
