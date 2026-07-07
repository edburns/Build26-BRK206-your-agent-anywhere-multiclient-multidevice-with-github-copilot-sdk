# Copilot Code Review Instructions

## Project Context

This is a Java demo porting a C# Blazor real-estate agent pipeline to Jakarta EE 11 + PrimeFaces + OpenLiberty, using the Copilot SDK for Java 1.0.7-SNAPSHOT. The C# original is in `src/AgentOrchestrator/`.

## Review Focus Areas

### Jakarta EE 11 Correctness

- Verify feature versions are EE 11 level: `faces-4.1`, `cdi-4.1`, `websocket-2.2`, `data-1.0`, `persistence-3.2`
- Do NOT mix EE 10 (`faces-4.0`, `cdi-4.0`, `websocket-2.1`) with EE 11 features — this causes `CWWKF1405E` singleton conflicts on Liberty
- `persistence.xml` must use `xmlns="http://xmlns.jcp.org/xml/ns/persistence"` (Liberty rejects the `jakarta.ee` namespace)
- Jakarta Data `@Repository` interfaces must use `@Find` + `@By("fieldName")` or `@Query` — Spring Data-style method name derivation is NOT supported

### Copilot SDK for Java Usage

- `CopilotClient` should use try-with-resources or explicit `close()`
- Permission handler is mandatory: `setOnPermissionRequest(PermissionHandler.APPROVE_ALL)` or custom
- `sendAndWait()` returns `CompletableFuture<AssistantMessageEvent>` — ensure `.get()` is called or properly chained
- Event subscription: prefer typed `session.on(EventClass.class, handler)` over untyped
- Tool definitions: this demo showcases THREE styles:
  - `@CopilotTool` annotation on methods (headline feature)
  - `ToolDefinition.from(...)` lambda with `Param.of(...)` for inline tools
  - `.overridesBuiltInTool(true)` fluent modifier for tool overrides

### OpenLiberty Configuration

- `server.xml` datasource: H2 URL property must be capital `URL` (matches `JdbcDataSource.setURL()`)
- H2 needs `eclipselink.target-database=org.eclipse.persistence.platform.database.H2Platform`
- Use `GenerationType.AUTO` not `IDENTITY` for H2 2.x compatibility
- `web.xml` must include `jakarta.faces.ENABLE_WEBSOCKET_ENDPOINT=true` for `f:websocket` to work

### PrimeFaces Patterns

- Real-time updates use: `f:websocket` push → client JS → `p:remoteCommand` → partial update
- `PushContext.send()` can be called from any thread (including virtual threads) when the bean is `@ApplicationScoped`
- Pipeline animation uses CSS `transition` on class changes — no FLIP needed

### Security

- No secrets, API keys, or credentials in code — use environment variables
- No hardcoded tokens in `CopilotClientOptions` — use `System.getenv()`
- H2 in-memory database is acceptable for this demo only

### Code Quality

- Favor CDI `@Inject` over `new` for managed beans
- Use `@ApplicationScoped` for singleton services, `@SessionScoped` for per-user state
- Virtual threads (`Thread.startVirtualThread()`) are acceptable for background agent work on Java 25
- Check that `CompletableFuture` chains handle exceptions (don't swallow `ExecutionException`)

### Things NOT to Flag

- The `dd-3017826-java-real-estate-demo-remove-before-merge/` folder is planning docs — don't review for code quality
- PrimeFaces theming/styling decisions are deliberate — don't suggest alternatives
- Using H2 instead of a "real" database is intentional for demo simplicity
