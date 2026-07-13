# Blog Post Outline: Introducing the GitHub Copilot SDK for Java

**Target publication:** Apps on Azure Blog (Microsoft Tech Community)  
**Author:** Ed Burns  
**Working subtitle:** *Enterprise Java developers have a new superpower: drive GitHub Copilot from idiomatic Java code — annotations, virtual threads, and all. 🚀*

---

## 1. Beginning: Introducing the Copilot SDK for Java

### 1.1 What is it?

- A Java-idiomatic client library for the GitHub Copilot agent platform.
- Lets server-side Java code create Copilot sessions, register tools, send prompts, and receive structured responses — all programmatically.
- Runs headless (`CopilotClientMode.EMPTY`) so it works in server environments with no IDE or editor required.

### 1.2 Where to get it

- Maven coordinates: `com.github:copilot-sdk-java:1.0.7-preview.1` (current preview; update version when GA).
- Link to the SDK repository / install instructions (TBD — confirm public URL at publication time).
- Prerequisites: JDK 17 or 25, Maven 3.9+, a GitHub account with an active Copilot subscription, and the Copilot CLI (`~/.copilot/`).

### 1.3 Why you want it

**Java-idiomatic API for driving GitHub Copilot.**

The SDK is not a thin REST wrapper or a language-agnostic shim. It was designed to feel natural to Java developers:

- **`CompletableFuture` everywhere** — all async operations (`client.start()`, `client.createSession()`, `session.sendAndWait()`) return `CompletableFuture`. Chain them, compose them, or `.get()` on a virtual thread — your choice.
- **`AutoCloseable` / try-with-resources** — `CopilotClient` and `CopilotSession` both implement `AutoCloseable`, so resource cleanup follows the standard Java pattern.
- **Annotation-driven tool definitions** — `@CopilotTool` and `@CopilotToolParam` let you declare tools the way enterprise Java developers declare endpoints, EJBs, and REST resources. Annotations are the lingua franca of enterprise Java.
- **Lambdas for inline tools** — `ToolDefinition.from(...)` supports functional-style tool definitions when you want something lighter.

**Much-beloved Java features the SDK supports:**

| Feature | How the SDK uses it |
|---------|-------------------|
| **Virtual Threads (JDK 21+)** | Each agent session runs on its own virtual thread — spin up thousands of concurrent agents without thread-pool tuning. |
| **Multi-Release JARs** | The SDK runs on JDK 17 or 25 and extracts the best from each. (MRJAR packaging means newer JDK features are used when available, older runtimes still work.) |
| **Text Blocks (JDK 15+)** | Write system prompts as readable multi-line `"""..."""` strings — no concatenation gymnastics. |
| **Records (JDK 16+)** | SDK event data uses record-like accessor patterns; your own tool code can use records freely (the sample app uses `record ToolCallSnapshot`). |
| **Pattern Matching `instanceof` (JDK 16+)** | Handle session events with `if (event instanceof AssistantMessageEvent msg)` — clean, type-safe dispatching. |

> **Copilot note to author:** The SDK also supports **Structured Concurrency** (JDK 25 preview) if you want to coordinate multiple sessions, and **Sealed classes** could be used with the event type hierarchy. These are more niche; consider whether they merit a callout or a footnote.

> ** Author note to Copilot:** put them as a footnote.

**Tool support, inspired by LangChain4j and also supporting tools as lambdas.**

- Three tool-definition styles: annotations (`@CopilotTool`), lambdas (`ToolDefinition.from(...)`), and low-level JSON Schema (`ToolDefinition.create(...)`).
- Cross-class tool scanning with `ToolDefinition.fromObject(instance)`.
- Override built-in tools with `.overridesBuiltInTool(true)`.

---

## 2. Middle: Walk Through the Sample App

### 2.1 Get the code

- Direct link: <https://github.com/microsoft/Build26-BRK206-your-agent-anywhere-multiclient-multidevice-with-github-copilot-sdk>
- The Java demo lives in `src/java-agent-orchestrator/`.
- Quick start: `mvn clean package liberty:run` → open <http://localhost:9080/>.
- Technology stack callout (brief table): OpenLiberty 26 + Jakarta EE 11 + PrimeFaces 15 + H2 in-memory DB.

### 2.2 What the app does (the pipeline)

- Brief description: a real-estate lead-management agent pipeline.
- Visual: include the a mermaid architecture diagram based on the ascii one from the README.
- Pipeline phases: `QUEUED → VALIDATING → SEARCHING → WRITING_REPORT → DONE` (or rejection branches).
- Each enquiry spins up an isolated `CopilotSession` on a virtual thread.

### 2.3 SDK features in action — code samples

Walk through the **SDK feature mapping** table from the README, grouping related features into narrative subsections. Each subsection includes a code snippet pulled directly from the sample app.

#### 2.3.1 Defining tools with `@CopilotTool` (Feature #1)

- Show `Agent.setCurrentPhase()` with `@CopilotTool` and `@CopilotToolParam` annotations.
- Explain: "This is the headline API. If you've ever written a `@GET` endpoint in JAX-RS or an `@MessageDriven` bean, this will feel instantly familiar."
- **Code snippet:** the `setCurrentPhase` method from [Agent.java](../src/java-agent-orchestrator/src/main/java/com/microsoft/build/realestate/Agent.java#L169).

#### 2.3.2 Inline lambda tools with `ToolDefinition.from(...)` (Feature #2)

- Show the `reportIntentTool` lambda definition.
- Call out `.overridesBuiltInTool(true)` (Feature #4) — this tool deliberately overrides a built-in.
- **Code snippet:** the `reportIntentTool` block from [Agent.java](../src/java-agent-orchestrator/src/main/java/com/microsoft/build/realestate/Agent.java#L102).

#### 2.3.3 Cross-class tool scanning with `ToolDefinition.fromObject(...)` (Feature #3)

- Show how `PropertyDatabase.searchProperties()` is annotated with `@CopilotTool` in a separate CDI bean.
- Explain: `ToolDefinition.fromObject(this)` scans the Agent for annotated methods; `ToolDefinition.fromObject(propertyDatabase)` would do the same for the DB bean (note the CDI proxy workaround with a lambda wrapper in the sample).
- **Code snippet:** the `searchProperties` method signature + annotation from [PropertyDatabase.java](../src/java-agent-orchestrator/src/main/java/com/microsoft/build/realestate/PropertyDatabase.java#L61).

#### 2.3.4 Customizing the system message (Feature #5)

- Show `SystemMessageMode.CUSTOMIZE` with `SectionOverride` to replace the `IDENTITY` section.
- Explain the difference between `CUSTOMIZE` (full control) and `APPEND` (preserve guardrails).
- **Code snippet:** the `SystemMessageConfig` setup from [Agent.java](../src/java-agent-orchestrator/src/main/java/com/microsoft/build/realestate/Agent.java#L82).

#### 2.3.5 The agentic loop: `sendAndWait(...)` (Feature #6)

- Show `session.sendAndWait(escapedEnquiry).get()`.
- Explain: one line kicks off the full agentic loop — the model calls tools, the SDK dispatches them, and control returns when the model is done. On a virtual thread, `.get()` is cheap.
- **Code snippet:** the `sendAndWait` call from [Agent.java](../src/java-agent-orchestrator/src/main/java/com/microsoft/build/realestate/Agent.java#L140).

#### 2.3.6 Real-time event handling with `session.on(...)` (Feature #7)

- Show the event subscription lambda and how events drive the UI via WebSocket push.
- **Code snippet:** the `session.on(event -> ...)` block from [Agent.java](../src/java-agent-orchestrator/src/main/java/com/microsoft/build/realestate/Agent.java#L137).

#### 2.3.7 Headless client and permission handling (Features #8 & #9)

- Show `CopilotClientMode.EMPTY` and `PermissionHandler.APPROVE_ALL`.
- Explain: `EMPTY` mode means no IDE; the client talks directly to the Copilot CLI. `APPROVE_ALL` is for demo/dev use; production apps should implement a real permission policy.
- **Code snippet:** the `CopilotClientOptions` setup from [AppState.java](../src/java-agent-orchestrator/src/main/java/com/microsoft/build/realestate/AppState.java#L63).

### 2.4 Jakarta EE integration patterns

- Mention how the ability to pass an `Executor` allows the CDI injection to work even on tool callback threads.
- Brief callout: CDI `@ApplicationScoped` for singleton client, virtual-thread executor with `ContextService.contextualRunnable()` for container-context propagation, JSF `f:websocket` for real-time push.
- This shows the SDK is not a framework island — it composes naturally with Jakarta EE, and of course also proprietary frameworks such as Spring.

> **Copilot note to author:** Consider also highlighting the `ToolSet` configuration (`new ToolSet().addCustom("*").addBuiltIn("web_fetch")`) — this fine-grained control over which tools the agent can access is an important production concern. It's Feature implicit in the SessionConfig setup but not listed as a numbered feature in the README.

> ** Author note to Copilot:** This is important. Put it in right here inline.


---

## 3. End: Summary and Conclusion

### 3.1 Recap

- Bullet list of what we showed:
  - Java-native API with `CompletableFuture`, annotations, lambdas, virtual threads.
  - Three tool-definition styles for maximum flexibility.
  - System message customization for controlling agent behaviour.
  - The agentic loop in one line: `sendAndWait(...)`.
  - Real-time event streaming for building responsive UIs.
  - Headless server-side operation — no IDE required.
  - Natural composition with Jakarta EE (CDI, JPA, WebSocket).

### 3.2 What to try next

- **Clone the sample app** and run it locally — submit multiple enquiries simultaneously to see virtual threads in action.
- **Swap the model** — try `session.setModel(...)` to experiment with different Copilot models.
- **Add your own tool** — define a new `@CopilotTool` method (e.g., a mortgage calculator) and watch the agent discover and use it.
- **Deploy to Azure** — OpenLiberty runs great on Azure App Service, AKS, or Azure Container Apps (link to Jakarta EE on Azure guidance: <https://aka.ms/java/ee>).
- Link to the BRK206 session recording (if available at publication time).

### 3.3 Call to action / closing line

- Something in the spirit of: "The Copilot SDK for Java puts the full power of GitHub Copilot behind your Java code — no IDE required, no framework lock-in. Clone the sample, run `mvn liberty:run`, and see for yourself."

---

## Style notes (for drafting)

- Match the tone of the [previous Apps on Azure Blog post](https://techcommunity.microsoft.com/blog/appsonazureblog/open-standard-enterprise-java-and-our-secure-future-initiative/4352618): professional but personable, structured with clear headers and tables, concrete code over abstract description.
- Use tables for reference/comparison (technology stack, feature mapping, Java features).
- Keep code snippets short and focused — show the 5-10 most important lines, not entire files.
- Link to the full source for readers who want the complete picture.
- Tags: `java`, `copilot`, `ai`, `github`, `jakarta ee`.
