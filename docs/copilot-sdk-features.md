# GitHub Copilot SDK Features Demonstrated in the Real Estate Demo

## Features (ranked by prominence / audience interest)

### 1. Custom Tool Definition via `CopilotTool.DefineTool`
The demo defines three custom tools (`set_current_phase`, `report_intent`, `search_properties`) that the LLM can invoke. This is the marquee SDK feature — it shows how to give the model structured access to your application's domain logic. The `SearchProperties` method with its rich `[Description]` annotations demonstrates how the SDK auto-generates tool schemas from C# method signatures.

### 2. Agentic Session Loop (`SendAndWaitAsync`)
The agent sends a single user message and the SDK autonomously loops — calling tools, processing results, and continuing — until the model decides it's done. This "fire-and-forget" agentic pattern (validation → search → report) is the core value proposition for building AI agents.

### 3. System Message Customization (`SystemMessageConfig`)
The demo replaces the default identity section of the system prompt to define a multi-phase real-estate workflow. This shows fine-grained control over model behavior via `SystemMessageSection` + `SectionOverrideAction.Replace`.

### 4. Built-in Tool Composition (`AddBuiltIn("web_fetch")`)
The agent mixes custom tools with Copilot's built-in `web_fetch` tool, enabling the model to browse the web (e.g., confirming school locations) without the developer implementing HTTP fetching. Demonstrates SDK extensibility through `AvailableTools = new ToolSet().AddCustom("*").AddBuiltIn("web_fetch")`.

### 5. Real-time Session Events (`Session.On<SessionEvent>`)
The demo subscribes to a stream of session events (`AssistantMessageEvent`, `ToolExecutionCompleteEvent`, `SessionErrorEvent`) to power a live UI that updates as the agent thinks. This event-driven pattern shows how to build observable AI workflows.

### 6. `CopilotClient` with `CopilotClientMode.Empty`
The demo creates a `CopilotClient` configured in `Empty` mode, meaning it doesn't inherit workspace context. This illustrates how to use the SDK as a headless AI backend inside a server-side Blazor app rather than a VS Code extension.

### 7. Multiple Concurrent Sessions
`AppState` spawns multiple `Agent` instances against the same `CopilotClient`. Each agent has its own `CopilotSession` running in parallel, demonstrating the SDK's support for concurrent multi-agent orchestration.

### 8. Permission Handling (`PermissionHandler.ApproveAll`)
The demo auto-approves all permission requests, showing the SDK's permission model that lets developers control tool execution policies programmatically.

### 9. Tool Overrides (`OverridesBuiltInTool = true`)
The `report_intent` tool is marked with `OverridesBuiltInTool = true`, replacing a built-in Copilot tool with a custom implementation. This demonstrates the SDK's extensibility for intercepting and customizing default behaviors.

### 10. Attribute-Driven Tool Metadata (`[DisplayName]`, `[Description]`)
The SDK uses standard .NET attributes to define tool names, descriptions, and parameter documentation — no JSON schema authoring required. This developer-friendly approach lowers the barrier to tool creation.
