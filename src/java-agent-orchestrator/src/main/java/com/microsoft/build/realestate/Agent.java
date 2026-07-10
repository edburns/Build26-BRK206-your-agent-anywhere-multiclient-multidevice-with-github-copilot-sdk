package com.microsoft.build.realestate;

import com.github.copilot.CopilotClient;
import com.github.copilot.CopilotSession;
import com.github.copilot.SystemMessageMode;
import com.github.copilot.generated.AssistantMessageEvent;
import com.github.copilot.generated.AssistantMessageToolRequest;
import com.github.copilot.rpc.PermissionHandler;
import com.github.copilot.rpc.SectionOverride;
import com.github.copilot.rpc.SectionOverrideAction;
import com.github.copilot.rpc.BuiltInTools;
import com.github.copilot.rpc.SessionConfig;
import com.github.copilot.rpc.SystemMessageConfig;
import com.github.copilot.rpc.SystemMessageSections;
import com.github.copilot.rpc.ToolDefinition;
import com.github.copilot.rpc.ToolSet;
import com.github.copilot.tool.CopilotTool;
import com.github.copilot.tool.CopilotToolParam;
import com.github.copilot.tool.Param;
import java.io.Closeable;
import java.time.Instant;
import java.util.ArrayDeque;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.locks.Lock;
import java.util.concurrent.locks.ReentrantLock;
import java.util.logging.Logger;

/**
 * Represents a single real-estate enquiry agent session.
 * Each agent owns a CopilotSession that runs on a virtual thread.
 *
 * <p>Demonstrates three Copilot SDK tool definition styles:
 * <ol>
 *   <li>{@code @CopilotTool} annotations — {@code setCurrentPhase} and {@code searchProperties}</li>
 *   <li>{@code ToolDefinition.from(...)} lambda — {@code reportIntent}</li>
 *   <li>{@code ToolDefinition.fromObject(...)} registration — annotated tools on this class</li>
 * </ol>
 */
public class Agent {

    private static final Logger LOG = Logger.getLogger(Agent.class.getName());
    private static final int MAX_EVENTS = 100;

    private final String id;
    private final String enquiry;
    private final PropertyDatabase propertyDatabase;
    private final UiUpdateSocket uiUpdateSocket;
    private final Lock eventsLock = new ReentrantLock();
    private final ArrayDeque<AgentEvent> events = new ArrayDeque<>();
    private final Map<String, ToolCallSnapshot> toolCallsById = new ConcurrentHashMap<>();

    private volatile Phase phase = Phase.QUEUED;
    private volatile String currentIntent;
    private volatile String finalReport;
    private volatile String errorMessage;
    private final Instant startedAt = Instant.now();
    private volatile Instant finishedAt;
    private CopilotSession session;

    public Agent(String id, String enquiry, PropertyDatabase propertyDatabase,
                 UiUpdateSocket uiUpdateSocket) {
        this.id = id;
        this.enquiry = enquiry;
        this.propertyDatabase = propertyDatabase;
        this.uiUpdateSocket = uiUpdateSocket;
        addEvent(startedAt, "phase_change", "Phase changed to QUEUED", Phase.QUEUED.name());
    }

    /**
     * Runs the agent session against the given CopilotClient.
     * Blocks (on a virtual thread) until the session completes.
     */
    public void run(CopilotClient client) {
        LOG.info("Agent " + id + " starting run. Enquiry: " + enquiry);
        SystemMessageConfig systemMessage = new SystemMessageConfig()
                .setMode(SystemMessageMode.CUSTOMIZE)
                .setSections(Map.of(SystemMessageSections.IDENTITY,
                new SectionOverride()
                        .setAction(SectionOverrideAction.REPLACE)
                        .setContent("""
                            You are part of a real estate recommendation system. You will receive enquiries
                            from customers, and you must carry out the following workflow. As you proceed,
                            update your current phase and intent, which will be visible to the user.
                            Do not stop until the phase reaches a final state.
                            Start by setting phase to "VALIDATING".

                            - Validation phase
                              - Check the enquiry is genuine and not spam, garbage, or off-topic.
                              - If it's not genuine, set phase to "REJECTED_GARBAGE" and stop.
                            - Search phase
                              - Extract relevant search criteria and search our property listings.
                              - To search our property listings, call the search_properties tool.
                                You may call it multiple times with different filters to refine results.
                              - At the end of this phase, if you don't find any relevant properties,
                                set phase to "REJECTED_NO_MATCHES" and stop.
                            - Report phase
                              - Write up a report for our salesperson to use when calling the customer.
                              - Your report should include a summary of the customer's needs and the top
                                1-3 matching properties. For each property, include key selling points.
                              - At the end of this phase, set phase to "DONE" and stop.

                            Always use set_current_phase each time you enter a new phase, and use
                            report_intent to report your intent at each step.
                            """)));

        // report_intent as inline lambda (ToolDefinition.from) — demonstrates ADR-006 style
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
                .overridesBuiltInTool(true);

        // @CopilotTool annotated methods on this instance — demonstrates ADR-005 style
        LOG.info("Agent " + id + " registering tools...");
        List<ToolDefinition> annotatedTools = ToolDefinition.fromObject(this);

        LOG.info("Agent " + id + " registered " + annotatedTools.size()
                + " annotated tool(s) + reportIntentTool");

        SessionConfig sessionConfig = new SessionConfig()
                .setOnPermissionRequest(PermissionHandler.APPROVE_ALL)
                .setSystemMessage(systemMessage)
                .setAvailableTools(new ToolSet().addCustom("*").addBuiltIn("web_fetch"))
                .setTools(concatLists(annotatedTools, List.of(reportIntentTool)));

        Closeable sessionSubscription = null;
        try {
            LOG.info("Agent " + id + " creating Copilot session...");
            session = client.createSession(sessionConfig).get();
            LOG.info("Agent " + id + " Copilot session established and authenticated successfully.");
            sessionSubscription = session.on(event -> {
                captureSessionEvent(event);
                uiUpdateSocket.pushDetailUpdate(id);
            });
            String escapedEnquiry = "<enquiry>" + xmlEscape(enquiry) + "</enquiry>";
            LOG.info("Agent " + id + " calling sendAndWait. Payload: " + escapedEnquiry);
            AssistantMessageEvent result = session.sendAndWait(escapedEnquiry).get();
            LOG.info("Agent " + id + " sendAndWait completed successfully.");
            LOG.info("Agent " + id + " final response: " + result.getData().content());
        } catch (Exception e) {
            LOG.severe("Agent " + id + " failed: " + e.getClass().getName() + ": " + e.getMessage());
            if (e.getCause() != null) {
                LOG.severe("Agent " + id + " root cause: " + e.getCause().getClass().getName() + ": " + e.getCause().getMessage());
            }
            String msg = e.getMessage() != null ? e.getMessage() : e.getClass().getSimpleName();
            errorMessage = msg;
            addEvent(Instant.now(), "session_error", "Session failed", msg);
            if (!phase.isTerminal()) {
                phase = Phase.REJECTED_GARBAGE;
                addEvent(Instant.now(), "phase_change", "Phase changed to " + phase.name(), phase.name());
                notifyUi();
            }
        } finally {
            if (sessionSubscription != null) {
                try { sessionSubscription.close(); } catch (Exception e) {
                    LOG.warning("Error unsubscribing session events for agent " + id + ": " + e.getMessage());
                }
            }
            if (session != null) {
                try { session.close(); } catch (Exception e) {
                    LOG.warning("Error closing CopilotSession for agent " + id + ": " + e.getMessage());
                }
            }
            finishedAt = Instant.now();
            LOG.info("Agent " + id + " run() finished. Phase=" + phase
                    + ", Duration=" + java.time.Duration.between(startedAt, finishedAt));
        }
    }

    /** Called by the set_current_phase tool to advance the pipeline stage. */
    @CopilotTool(value = "Sets the current phase of the agent. Use this to report progress.",
                 name = "set_current_phase")
    public String setCurrentPhase(
            @CopilotToolParam("The phase to transition to (VALIDATING, SEARCHING, WRITING_REPORT, "
                    + "REJECTED_GARBAGE, REJECTED_NO_MATCHES, or DONE)") String phaseName) {
        try {
            phase = Phase.valueOf(phaseName.trim().toUpperCase(Locale.ROOT));
        } catch (IllegalArgumentException e) {
            LOG.warning("Agent " + id + " set_current_phase called with unknown phase: " + phaseName);
            return "Unknown phase: " + phaseName;
        }
        LOG.info("Agent " + id + " phase -> " + phase.name());
        addEvent(Instant.now(), "phase_change", "Phase changed to " + phase.name(), phase.name());
        if (phase.isTerminal()) {
            finishedAt = Instant.now();
        }
        notifyUi();
        return "Phase set to " + phase.getLabel();
    }

    @CopilotTool(value = "Searches the real estate listings database. Returns up to 10 matching properties.",
                 name = "search_properties")
    public List<Property> searchProperties(
            @CopilotToolParam("Property type substring (e.g. 'flat', 'house', 'bungalow'). Empty string for no filter.")
            String type,
            @CopilotToolParam("City substring (e.g. 'London', 'Bristol'). Empty string for no filter.")
            String city,
            @CopilotToolParam("Minimum number of bedrooms (0 for no minimum).")
            int minBedrooms,
            @CopilotToolParam("Maximum price in GBP (0 for no maximum).")
            double maxPriceGbp) {
        return propertyDatabase.searchProperties(type, city, minBedrooms, maxPriceGbp);
    }

    private void captureSessionEvent(Object event) {
        if (event == null) {
            return;
        }
        String eventClassName = event.getClass().getSimpleName();
        switch (eventClassName) {
            case "AssistantMessageEvent" -> captureAssistantMessageEvent((AssistantMessageEvent) event);
            case "ToolExecutionStartEvent" -> captureToolExecutionStart(event);
            case "ToolExecutionCompleteEvent" -> captureToolExecutionComplete(event);
            default -> addEvent(Instant.now(), "session_event", eventClassName, event.toString());
        }
    }

    private void captureAssistantMessageEvent(AssistantMessageEvent event) {
        String messageContent = event.getData().content();
        if (messageContent != null && !messageContent.isBlank()) {
            finalReport = messageContent;
            addEvent(Instant.now(), "assistant_message", "Assistant message", messageContent);
        }

        // Pre-populate toolCallsById for result correlation; the visible "tool_call"
        // event is emitted by captureToolExecutionStart to avoid duplicate UI entries.
        for (AssistantMessageToolRequest request : event.getData().toolRequests()) {
            String toolCallId = request.toolCallId();
            if (toolCallId != null && !toolCallId.isBlank()) {
                toolCallsById.put(toolCallId,
                        new ToolCallSnapshot(request.name(), asText(request.arguments())));
            }
        }
    }

    private void captureToolExecutionStart(Object event) {
        Object data = invokeNoArg(event, "getData");
        String toolCallId = asText(invokeNoArg(data, "toolCallId"));
        String toolName = asText(invokeNoArg(data, "toolName"));
        String toolArgs = asText(invokeNoArg(data, "arguments"));
        LOG.info("Agent " + id + " tool execution START: " + nullSafe(toolName, "unknown")
                + " args=" + nullSafe(toolArgs, "(none)"));
        if (toolCallId != null && !toolCallId.isBlank()) {
            toolCallsById.put(toolCallId, new ToolCallSnapshot(toolName, toolArgs));
        }
        addEvent(Instant.now(),
                "tool_call",
                "Tool call: " + nullSafe(toolName, "unknown"),
                formatToolDetail(toolName, toolArgs, null));
    }

    private void captureToolExecutionComplete(Object event) {
        Object data = invokeNoArg(event, "getData");
        String toolCallId = asText(invokeNoArg(data, "toolCallId"));
        boolean success = asBoolean(invokeNoArg(data, "success"), true);

        String toolName = asText(invokeNoArg(data, "toolName"));
        String toolArgs = asText(invokeNoArg(data, "arguments"));
        ToolCallSnapshot snapshot = toolCallId == null ? null : toolCallsById.remove(toolCallId);
        if ((toolName == null || toolName.isBlank()) && snapshot != null) {
            toolName = snapshot.toolName();
        }
        if ((toolArgs == null || toolArgs.isBlank()) && snapshot != null) {
            toolArgs = snapshot.toolArgs();
        }

        Object result = invokeNoArg(data, "result");
        String resultContent = asText(invokeNoArg(result, "content"));
        if (resultContent == null || resultContent.isBlank()) {
            resultContent = asText(result);
        }
        LOG.info("Agent " + id + " tool execution COMPLETE: " + nullSafe(toolName, "unknown")
                + " success=" + success
                + " result=" + (resultContent == null ? "(null)" : resultContent.substring(0, Math.min(resultContent.length(), 200))));

        addEvent(Instant.now(),
                "tool_result",
                "Tool result: " + nullSafe(toolName, "unknown") + (success ? " (ok)" : " (failed)"),
                formatToolDetail(toolName, toolArgs, resultContent));
    }

    private void addEvent(Instant timestamp, String eventType, String summary, String detail) {
        eventsLock.lock();
        try {
            events.addLast(new AgentEvent(timestamp, eventType, summary, detail));
            while (events.size() > MAX_EVENTS) {
                events.removeFirst();
            }
        } finally {
            eventsLock.unlock();
        }
    }

    private static Object invokeNoArg(Object target, String methodName) {
        if (target == null) {
            return null;
        }
        try {
            return target.getClass().getMethod(methodName).invoke(target);
        } catch (Exception e) {
            return null;
        }
    }

    private static String asText(Object value) {
        return value == null ? null : String.valueOf(value);
    }

    private static boolean asBoolean(Object value, boolean fallback) {
        if (value instanceof Boolean b) {
            return b;
        }
        return fallback;
    }

    private static String nullSafe(String value, String fallback) {
        return value == null || value.isBlank() ? fallback : value;
    }

    private static String formatToolDetail(String toolName, String toolArgs, String result) {
        StringBuilder sb = new StringBuilder();
        if (toolName != null && !toolName.isBlank()) {
            sb.append("tool: ").append(toolName).append('\n');
        }
        if (toolArgs != null && !toolArgs.isBlank()) {
            sb.append("params: ").append(toolArgs).append('\n');
        }
        if (result != null && !result.isBlank()) {
            sb.append("result: ").append(result);
        }
        return sb.toString().trim();
    }

    private record ToolCallSnapshot(String toolName, String toolArgs) { }

    private void notifyUi() {
        uiUpdateSocket.pushPhaseChange(id);
    }

    private static String xmlEscape(String text) {
        return text.replace("&", "&amp;")
                   .replace("<", "&lt;")
                   .replace(">", "&gt;")
                   .replace("\"", "&quot;")
                   .replace("'", "&apos;");
    }

    @SafeVarargs
    private static <T> List<T> concatLists(List<T>... lists) {
        return java.util.Arrays.stream(lists)
                .flatMap(java.util.Collection::stream)
                .toList();
    }

    // --- Getters ---

    public String getId() { return id; }
    public String getEnquiry() { return enquiry; }
    public Phase getPhase() { return phase; }
    public String getCurrentIntent() { return currentIntent; }
    public Instant getStartedAt() { return startedAt; }
    public Instant getFinishedAt() { return finishedAt; }
    public List<AgentEvent> getEvents() {
        eventsLock.lock();
        try {
            return List.copyOf(events);
        } finally {
            eventsLock.unlock();
        }
    }
    public String getFinalReport() { return finalReport; }

    public String getErrorMessage() { return errorMessage; }

    public boolean isActive() {
        return !phase.isTerminal();
    }

    public boolean isDone() {
        return phase == Phase.DONE;
    }

    public boolean isRejected() {
        return phase.isRejected();
    }

    /** Returns true when the session failed due to an unhandled exception (as opposed to intentional rejection by the agent). */
    public boolean isFailed() {
        return errorMessage != null;
    }
}
