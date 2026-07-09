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
import java.time.Instant;
import java.util.List;
import java.util.Locale;
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

    private final String id;
    private final String enquiry;
    private final PropertyDatabase propertyDatabase;
    private final UiUpdateSocket uiUpdateSocket;

    private volatile Phase phase = Phase.QUEUED;
    private volatile String currentIntent;
    private final Instant startedAt = Instant.now();
    private volatile Instant finishedAt;
    private CopilotSession session;

    public Agent(String id, String enquiry, PropertyDatabase propertyDatabase,
                 UiUpdateSocket uiUpdateSocket) {
        this.id = id;
        this.enquiry = enquiry;
        this.propertyDatabase = propertyDatabase;
        this.uiUpdateSocket = uiUpdateSocket;
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
                              - If the customer is looking for a neighbourhood with a particular feature,
                                always perform at least one web search to confirm locations.
                              - At the end of this phase, if you don't find any relevant properties,
                                set phase to "REJECTED_NO_MATCHES" and stop.
                            - Report phase
                              - Write up a report for our salesperson to use when calling the customer.
                              - Your report should include a summary of the customer's needs and the top
                                1-3 matching properties. For each property, include key selling points.
                              - At the end of this phase, set phase to "DONE" and stop.

                            Always use set_current_phase each time you enter a new phase, and report your
                            intent at each step.
                            """));

        // report_intent as inline lambda (ToolDefinition.from) — demonstrates ADR-006 style
        ToolDefinition reportIntentTool = ToolDefinition
                .from("report_intent",
                      "Reports the current intent of the agent",
                      Param.of(String.class, "intent", "Intent in max 4 words"),
                      (String intent) -> { currentIntent = intent; notifyUi(); return "ok"; })
                .overridesBuiltInTool(true);

        // @CopilotTool annotated methods on this instance — demonstrates ADR-005 style
        List<ToolDefinition> annotatedTools = ToolDefinition.fromObject(this);

        // search_properties from PropertyDatabase — demonstrates cross-class @CopilotTool
        List<ToolDefinition> dbTools = ToolDefinition.fromObject(propertyDatabase);

        SessionConfig sessionConfig = new SessionConfig()
                .setOnPermissionRequest(PermissionHandler.APPROVE_ALL)
                .setSystemMessage(systemMessage)
                .setAvailableTools(List.of("*"))
                .setTools(concatLists(annotatedTools, dbTools, List.of(reportIntentTool)));

        try {
            session = client.createSession(sessionConfig).get();
            AssistantMessageEvent result = session.sendAndWait(
                    "<enquiry>" + enquiry + "</enquiry>").get();
            LOG.info("Agent " + id + " completed: " + result.getData().content());
        } catch (Exception e) {
            LOG.severe("Agent " + id + " failed: " + e.getMessage());
            if (!phase.isTerminal()) {
                phase = Phase.REJECTED_GARBAGE;
                notifyUi();
            }
        } finally {
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
        if (phase.isTerminal()) {
            finishedAt = Instant.now();
        }
        notifyUi();
        return "Phase set to " + phase.getLabel();
    }

    private void notifyUi() {
        uiUpdateSocket.pushPhaseChange(id);
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
