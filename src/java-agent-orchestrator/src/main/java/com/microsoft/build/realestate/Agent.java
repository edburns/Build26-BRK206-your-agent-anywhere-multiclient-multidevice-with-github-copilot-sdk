package com.microsoft.build.realestate;

import com.github.copilot.CopilotClient;
import com.github.copilot.CopilotSession;
import com.github.copilot.PermissionHandler;
import com.github.copilot.SectionOverride;
import com.github.copilot.SectionOverrideAction;
import com.github.copilot.SessionConfig;
import com.github.copilot.SystemMessageConfig;
import com.github.copilot.SystemMessageMode;
import com.github.copilot.SystemMessageSection;
import com.github.copilot.event.AssistantMessageEvent;
import com.github.copilot.tool.Param;
import com.github.copilot.tool.ToolDefinition;
import com.github.copilot.tool.annotation.CopilotTool;
import com.github.copilot.tool.annotation.CopilotToolParam;
import java.io.Closeable;
import java.time.Instant;
import java.util.Collection;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.CopyOnWriteArrayList;
import java.util.logging.Logger;

/**
 * Represents a single real-estate enquiry agent session.
 * Each agent owns a CopilotSession that runs on a virtual thread.
 *
 * <p>Demonstrates three Copilot SDK tool definition styles:
 * <ol>
 *   <li>{@code @CopilotTool} annotation — {@code setCurrentPhase}</li>
 *   <li>{@code ToolDefinition.from(...)} lambda — {@code reportIntent}</li>
 *   <li>{@code ToolDefinition.fromObject(...)} — {@code searchProperties} in {@link PropertyDatabase}</li>
 * </ol>
 */
public class Agent {

    private static final Logger LOG = Logger.getLogger(Agent.class.getName());
    private static final int MAX_EVENTS = 100;

    private final String id;
    private final String enquiry;
    private final PropertyDatabase propertyDatabase;
    private final UiUpdateSocket uiUpdateSocket;
    private final List<AgentEvent> events = new CopyOnWriteArrayList<>();
    private final Map<String, ToolCallSnapshot> toolCallsById = new ConcurrentHashMap<>();

    private volatile Phase phase = Phase.QUEUED;
    private volatile String currentIntent;
    private volatile String finalReport;
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
        SystemMessageConfig systemMessage = new SystemMessageConfig()
                .setMode(SystemMessageMode.CUSTOMIZE);
        systemMessage.getSections().put(SystemMessageSection.IDENTITY,
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
                            """));

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
        List<ToolDefinition> annotatedTools = ToolDefinition.fromObject(this);

        // search_properties from PropertyDatabase — demonstrates cross-class @CopilotTool
        List<ToolDefinition> dbTools = ToolDefinition.fromObject(propertyDatabase);

        SessionConfig sessionConfig = new SessionConfig()
                .setOnPermissionRequest(PermissionHandler.APPROVE_ALL)
                .setSystemMessage(systemMessage)
                .setTools(concatLists(annotatedTools, dbTools, List.of(reportIntentTool)));

        Closeable sessionSubscription = null;
        try {
            session = client.createSession(sessionConfig).get();
            sessionSubscription = session.on(event -> {
                captureSessionEvent(event);
                notifyUi();
            });
            AssistantMessageEvent result = session.sendAndWait(
                    "<enquiry>" + xmlEscape(enquiry) + "</enquiry>").get();
            LOG.info("Agent " + id + " completed: " + result.getData().content());
        } catch (Exception e) {
            LOG.severe("Agent " + id + " failed: " + e.getMessage());
            addEvent(Instant.now(), "session_error", "Session failed", e.getMessage());
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
            return "Unknown phase: " + phaseName;
        }
        addEvent(Instant.now(), "phase_change", "Phase changed to " + phase.name(), phase.name());
        if (phase.isTerminal()) {
            finishedAt = Instant.now();
        }
        notifyUi();
        return "Phase set to " + phase.getLabel();
    }

    private void captureSessionEvent(Object event) {
        if (event == null) {
            return;
        }
        String eventClassName = event.getClass().getSimpleName();
        switch (eventClassName) {
            case "AssistantMessageEvent" -> captureAssistantMessageEvent(event);
            case "ToolExecutionStartEvent" -> captureToolExecutionStart(event);
            case "ToolExecutionCompleteEvent" -> captureToolExecutionComplete(event);
            default -> addEvent(Instant.now(), "session_event", eventClassName, event.toString());
        }
    }

    private void captureAssistantMessageEvent(Object event) {
        Object data = invokeNoArg(event, "getData");
        String messageContent = asText(invokeNoArg(data, "content"));
        if (messageContent != null && !messageContent.isBlank()) {
            finalReport = messageContent;
            addEvent(Instant.now(), "assistant_message", "Assistant message", messageContent);
        }

        Object toolRequests = invokeNoArg(data, "toolRequests");
        for (Object request : asIterable(toolRequests)) {
            String toolCallId = asText(invokeNoArg(request, "toolCallId"));
            String toolName = asText(invokeNoArg(request, "name"));
            String toolArgs = asText(invokeNoArg(request, "arguments"));
            if (toolCallId != null && !toolCallId.isBlank()) {
                toolCallsById.put(toolCallId, new ToolCallSnapshot(toolName, toolArgs));
            }
            addEvent(Instant.now(),
                    "tool_call",
                    "Tool call: " + nullSafe(toolName, "unknown"),
                    formatToolDetail(toolName, toolArgs, null));
        }
    }

    private void captureToolExecutionStart(Object event) {
        Object data = invokeNoArg(event, "getData");
        String toolCallId = asText(invokeNoArg(data, "toolCallId"));
        String toolName = asText(invokeNoArg(data, "toolName"));
        String toolArgs = asText(invokeNoArg(data, "arguments"));
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

        addEvent(Instant.now(),
                "tool_result",
                "Tool result: " + nullSafe(toolName, "unknown") + (success ? " (ok)" : " (failed)"),
                formatToolDetail(toolName, toolArgs, resultContent));
    }

    private void addEvent(Instant timestamp, String eventType, String summary, String detail) {
        synchronized (events) {
            events.add(new AgentEvent(timestamp, eventType, summary, detail));
            int excess = events.size() - MAX_EVENTS;
            if (excess > 0) {
                events.subList(0, excess).clear();
            }
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

    private static Collection<?> asIterable(Object value) {
        if (value instanceof Collection<?> collection) {
            return collection;
        }
        if (value instanceof Object[] array) {
            return List.of(array);
        }
        return List.of();
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
    public List<AgentEvent> getEvents() { return List.copyOf(events); }
    public String getFinalReport() { return finalReport; }

    public boolean isActive() {
        return !phase.isTerminal();
    }

    public boolean isDone() {
        return phase == Phase.DONE;
    }

    public boolean isRejected() {
        return phase.isRejected();
    }
}
