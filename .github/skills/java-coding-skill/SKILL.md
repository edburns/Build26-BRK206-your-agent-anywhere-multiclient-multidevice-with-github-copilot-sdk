---
name: java-coding-skill
description: "Use this skill whenever editing `*.java` files in order to write idiomatic, well-structured Java code using the Copilot SDK for Java"
---

# Java Coding Skill

## Core Principles

- Requires Java 25 or later.
- Uses `CompletableFuture` for all async operations.
- Implements `AutoCloseable` for resource cleanup (try-with-resources).

## Installation

### Maven

```xml
<dependency>
    <groupId>com.github</groupId>
    <artifactId>copilot-sdk-java</artifactId>
    <version>${copilot-sdk-java.version}</version>
</dependency>
```

## Client Initialization

### Basic Client Setup

```java
try (var client = new CopilotClient()) {
    client.start().get();
    // Use client...
}
```

### Client Configuration Options

When creating a CopilotClient, use `CopilotClientOptions`:

- `cliPath` - Path to CLI executable (default: "copilot" from PATH)
- `cliArgs` - Extra arguments prepended before SDK-managed flags
- `cliUrl` - URL of existing CLI server (e.g., "localhost:8080"). When provided, client won't spawn a process
- `port` - Server port (default: 0 for random, only when `useStdio` is false)
- `useStdio` - Use stdio transport instead of TCP (default: true)
- `logLevel` - Log level: "error", "warn", "info", "debug", "trace" (default: "info")
- `autoStart` - Auto-start server on first request (default: true)
- `autoRestart` - Auto-restart on crash (default: true)
- `cwd` - Working directory for the CLI process
- `environment` - Environment variables for the CLI process
- `gitHubToken` - GitHub token for authentication
- `useLoggedInUser` - Use logged-in `gh` CLI auth (default: true unless token provided)
- `onListModels` - Custom model list handler for BYOK scenarios

```java
var options = new CopilotClientOptions()
    .setCliPath("/path/to/copilot")
    .setLogLevel("debug")
    .setAutoStart(true)
    .setAutoRestart(true)
    .setGitHubToken(System.getenv("GITHUB_TOKEN"));

try (var client = new CopilotClient(options)) {
    client.start().get();
    // Use client...
}
```

## Session Management

### Creating Sessions

Use `SessionConfig` for configuration. The permission handler is **required**:

```java
var session = client.createSession(new SessionConfig()
    .setModel("gpt-5")
    .setStreaming(true)
    .setTools(List.of(...))
    .setSystemMessage(new SystemMessageConfig()
        .setMode(SystemMessageMode.APPEND)
        .setContent("Custom instructions"))
    .setAvailableTools(List.of("tool1", "tool2"))
    .setExcludedTools(List.of("tool3"))
    .setProvider(new ProviderConfig().setType("openai"))
    .setOnPermissionRequest(PermissionHandler.APPROVE_ALL)
).get();
```

### Session Operations

- `session.getSessionId()` - Get session identifier
- `session.send(prompt)` / `session.send(MessageOptions)` - Send message, returns message ID
- `session.sendAndWait(prompt)` / `session.sendAndWait(MessageOptions)` - Send and wait for response (60s timeout)
- `session.sendAndWait(options, timeoutMs)` - Send and wait with custom timeout
- `session.abort()` - Abort current processing
- `session.getMessages()` - Get all events/messages
- `session.setModel(modelId)` - Switch to a different model
- `session.close()` - Clean up resources

## Event Handling

### Type-Safe Event Handling

```java
session.on(AssistantMessageEvent.class, msg -> {
    System.out.println(msg.getData().content());
});

session.on(SessionIdleEvent.class, idle -> {
    done.complete(null);
});
```

### Event Types

Use pattern matching (Java 17+) for event handling:

```java
session.on(event -> {
    if (event instanceof AssistantMessageEvent assistantMsg) {
        System.out.println(assistantMsg.getData().content());
    } else if (event instanceof AssistantMessageDeltaEvent delta) {
        System.out.print(delta.getData().deltaContent());
    } else if (event instanceof ToolExecutionStartEvent toolStart) {
        // Tool execution started
    } else if (event instanceof ToolExecutionCompleteEvent toolComplete) {
        // Tool execution completed
    } else if (event instanceof SessionIdleEvent idle) {
        // Session is idle (processing complete)
    } else if (event instanceof SessionErrorEvent error) {
        System.err.println("Error: " + error.getData().message());
    }
});
```

## Custom Tools

### Ergonomic Tool Definition (ADR-005 — @CopilotTool annotations)

The preferred approach for this demo. Annotate methods with `@CopilotTool` and parameters with `@CopilotToolParam`:

```java
class MyTools {

    @CopilotTool("Sets the current phase of the agent. Use this to report progress.")
    String setCurrentPhase(@CopilotToolParam("The phase to transition to") Phase phase) {
        this.phase = phase;
        return "Phase set to " + phase;
    }

    @CopilotTool(name = "report_intent", value = "Reports the agent's intent",
                 overridesBuiltInTool = true)
    String reportIntent(@CopilotToolParam("The intent") String intent) {
        return "Intent: " + intent;
    }
}

// Registration:
var tools = ToolDefinition.fromObject(myToolsInstance);
```

### Inline Lambda Tool Definition (ADR-006)

For tools defined at the call site:

```java
ToolDefinition tool = ToolDefinition.from(
    "set_current_phase",
    "Sets the current phase of the agent",
    Param.of(String.class, "phase", "The phase to transition to"),
    (String phase) -> {
        currentPhase = phase;
        return "Phase set to " + phase;
    });
```

### Low-Level Tool Definition

Use `ToolDefinition.create()` with JSON Schema parameters and a `ToolHandler`:

```java
var tool = ToolDefinition.create(
    "get_weather",
    "Get weather for a location",
    Map.of(
        "type", "object",
        "properties", Map.of(
            "location", Map.of("type", "string", "description", "City name")
        ),
        "required", List.of("location")
    ),
    invocation -> {
        String location = (String) invocation.getArguments().get("location");
        return CompletableFuture.completedFuture("Sunny in " + location);
    }
);
```

### Overriding Built-In Tools

```java
var override = ToolDefinition.createOverride(
    "built_in_tool_name",
    "Custom description",
    Map.of("type", "object", "properties", Map.of(...)),
    invocation -> CompletableFuture.completedFuture("custom result")
);
```

## System Message Customization

### Customize Mode (Section-level control)

```java
var systemMessageConfig = new SystemMessageConfig();
systemMessageConfig.setMode(SystemMessageMode.CUSTOMIZE);
systemMessageConfig.getSections().put(SystemMessageSection.IDENTITY, new SectionOverride()
    .setAction(SectionOverrideAction.REPLACE)
    .setContent("You are a real estate recommendation system..."));
```

### Append Mode (Preserves Guardrails)

```java
new SystemMessageConfig()
    .setMode(SystemMessageMode.APPEND)
    .setContent("Additional instructions here")
```

## Permission Handling

```java
// Approve all requests (for development/testing)
new SessionConfig()
    .setOnPermissionRequest(PermissionHandler.APPROVE_ALL)
```

## Send and Wait (Agentic Loop)

```java
AssistantMessageEvent response = session.sendAndWait("Process this enquiry").get();
System.out.println(response.getData().content());
```

## Multiple Sessions

Sessions are independent and can run concurrently:

```java
var session1 = client.createSession(config1).get();
var session2 = client.createSession(config2).get();

Thread.ofVirtual().start(() -> session1.sendAndWait("Task 1").join());
Thread.ofVirtual().start(() -> session2.sendAndWait("Task 2").join());
```

## Best Practices

1. **Always use try-with-resources** for `CopilotClient` and `CopilotSession`
2. **Always provide a permission handler** — it is required for `createSession`
3. **Use `sendAndWait()`** for simple agentic loops
4. **Handle `SessionErrorEvent`** for robust error handling
5. **Use `@CopilotTool` annotations** for ergonomic tool definitions
6. **Use `SystemMessageMode.APPEND`** to preserve safety guardrails (unless you need full control)
7. **Provide descriptive tool names and descriptions** for better model understanding
8. **Use virtual threads** for concurrent session execution (JDK 25)
