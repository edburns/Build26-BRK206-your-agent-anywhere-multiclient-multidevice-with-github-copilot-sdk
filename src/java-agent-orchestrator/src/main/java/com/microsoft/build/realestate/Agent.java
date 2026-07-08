package com.microsoft.build.realestate;

import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.Objects;
import java.util.UUID;
import java.util.logging.Level;
import java.util.logging.Logger;

import com.github.copilot.AvailableTools;
import com.github.copilot.CopilotClient;
import com.github.copilot.CopilotSession;
import com.github.copilot.MessageOptions;
import com.github.copilot.PermissionHandler;
import com.github.copilot.SectionOverride;
import com.github.copilot.SectionOverrideAction;
import com.github.copilot.SessionConfig;
import com.github.copilot.SystemMessageConfig;
import com.github.copilot.SystemMessageMode;
import com.github.copilot.SystemMessageSection;
import com.github.copilot.event.AssistantMessageEvent;
import com.github.copilot.event.SessionEvent;
import com.github.copilot.tool.CopilotTool;
import com.github.copilot.tool.CopilotToolParam;
import com.github.copilot.tool.Param;
import com.github.copilot.tool.ToolDefinition;

public class Agent {

    private static final Logger LOGGER = Logger.getLogger(Agent.class.getName());

    private static final String SYSTEM_MESSAGE = """
            You are part of a real estate recommendation system. You will receive enquiries from customers,
            and you must carry out the following workflow. As you proceed, you will update your current phase
            and intent, which will be visible to the user. Do not stop until the phase reaches a final state.
            Start by setting phase to "VALIDATING".

            - Validation phase
              - Check the enquiry is genuine and not spam, garbage, or off-topic.
              - If it's not genuine, set phase to "REJECTED" and stop.
            - Search phase
              - Extract relevant search criteria and search our property listings.
              - To search our property listings, call the search_properties tool.
                You may call it multiple times with different filters to refine results.
              - If the customer is looking for a neighbourhood with a particular feature (such as schools)
                always perform at least one web search to confirm locations.
              - At the end of this phase, if you don't find any relevant properties, set phase to
                "REJECTED" and stop. We are very busy and do not want to talk to any customers
                that don't match our offerings. Don't write reports for customers that won't convert.
            - Report phase
              - Write up a report for our salesperson to use when calling the customer.
              - Your report should include a summary of the customer's needs and the top 1-3 matching
                properties. For each property, include key selling points for this customer.
              - At the end of this phase, set phase to "DONE" and stop.

            As you go, always use set_current_phase each time you enter a new phase, and report your
            intent at each step using report_intent.
            """;

    private final String id;
    private final String enquiryText;
    private final UiUpdateSocket uiUpdateSocket;
    private volatile Phase phase = Phase.QUEUED;
    private volatile String currentIntent;
    private volatile String report;
    private final List<SessionEvent> sessionEvents = new ArrayList<>();
    private final Instant startedAt = Instant.now();
    private volatile Instant finishedAt;

    public Agent(String enquiryText, UiUpdateSocket uiUpdateSocket) {
        this.id = UUID.randomUUID().toString().replace("-", "").substring(0, 8);
        this.enquiryText = enquiryText;
        this.uiUpdateSocket = Objects.requireNonNull(uiUpdateSocket, "uiUpdateSocket must not be null");
    }

    public void run(CopilotClient client, PropertyDatabase db) {
        LOGGER.info("Agent " + id + ": run() entered, enquiry=\"" + sanitizeForLog(enquiryText) + "\"");

        // Set initial phase deterministically so the UI sees activity even if session startup fails.
        setCurrentPhase(Phase.VALIDATING);

        var systemMessageConfig = new SystemMessageConfig();
        systemMessageConfig.setMode(SystemMessageMode.CUSTOMIZE);
        systemMessageConfig.getSections().put(SystemMessageSection.IDENTITY, new SectionOverride()
            .setAction(SectionOverrideAction.REPLACE)
            .setContent(SYSTEM_MESSAGE));

        // Tool 2: report_intent — inline lambda style to showcase ToolDefinition.from(...)
        ToolDefinition reportIntent = ToolDefinition
            .from(
                "report_intent",
                "Reports the current intent of the agent to the user interface",
                Param.of(String.class, "intent", "Intent in max 4 words"),
                (String intent) -> { this.currentIntent = intent; notifyUi("intent-changed"); return "ok"; })
            .overridesBuiltInTool(true);

        // Tool 1 (set_current_phase) and Tool 3 (search_properties) are defined via @CopilotTool annotations
        var agentTools = ToolDefinition.fromObject(this);
        var dbTools = ToolDefinition.fromObject(db);

        LOGGER.info("Agent " + id + ": registering tools: " + agentTools.size() + " agent tools, " + dbTools.size() + " db tools");

        try (CopilotSession session = client.createSession(new SessionConfig()
                // APPROVE_ALL is intentional: this demo agent runs autonomously and requires
                // web_fetch for neighbourhood lookups as directed by the system prompt.
                .setOnPermissionRequest(PermissionHandler.APPROVE_ALL)
                .setSystemMessage(systemMessageConfig)
                .setAvailableTools(new AvailableTools().addCustom("*").addBuiltIn("web_fetch"))
                .setTools(concat(agentTools, List.of(reportIntent), dbTools))
            ).get()) {

            LOGGER.info("Agent " + id + ": session created with id=" + session.getSessionId());

            session.on(SessionEvent.class, evt -> {
                synchronized (sessionEvents) {
                    sessionEvents.add(evt);
                }
                notifyUi();
            });

            AssistantMessageEvent response = session.sendAndWait(
                new MessageOptions().setContent(enquiryText)
            ).join();

            this.report = response.getData().content();
            this.finishedAt = Instant.now();
            LOGGER.info("Agent " + id + ": completed with phase=" + phase);
            notifyUi();

        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            LOGGER.log(Level.WARNING, "Agent " + id + ": interrupted during session setup", e);
            throw new RuntimeException("Agent run interrupted", e);
        } catch (Exception e) {
            LOGGER.log(Level.WARNING, "Agent " + id + ": error during run: " + e.getMessage(), e);
            throw new RuntimeException("Agent run failed", e);
        }
    }

    @CopilotTool(name = "set_current_phase", value = "Sets the current phase of the agent. Use this to report progress through the pipeline.")
    void setCurrentPhase(@CopilotToolParam("The phase to transition to") Phase phase) {
        this.phase = phase;
        notifyUi("phase-changed");
    }

    public void notifyUi() {
        notifyUi("agent-updated");
    }

    public void notifyUi(String eventType) {
        uiUpdateSocket.sendUpdate(this.id, eventType);
    }

    public boolean isRejected() {
        return phase == Phase.REJECTED;
    }

    public boolean isDone() {
        return phase == Phase.DONE;
    }

    // Getters

    public String getId() {
        return id;
    }

    public String getEnquiryText() {
        return enquiryText;
    }

    public Phase getPhase() {
        return phase;
    }

    public String getCurrentIntent() {
        return currentIntent;
    }

    public String getReport() {
        return report;
    }

    public List<SessionEvent> getSessionEvents() {
        synchronized (sessionEvents) {
            return List.copyOf(sessionEvents);
        }
    }

    public Instant getStartedAt() {
        return startedAt;
    }

    public Instant getFinishedAt() {
        return finishedAt;
    }

    @SafeVarargs
    private static <T> List<T> concat(List<T>... lists) {
        var result = new ArrayList<T>();
        for (var list : lists) {
            result.addAll(list);
        }
        return result;
    }

    private static String sanitizeForLog(String value) {
        if (value == null) {
            return "<null>";
        }
        return value.replace("\r", "\\r").replace("\n", "\\n");
    }
}
