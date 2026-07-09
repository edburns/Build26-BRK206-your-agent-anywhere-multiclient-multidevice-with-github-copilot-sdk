package com.microsoft.build.realestate;

import com.github.copilot.CopilotClient;
import com.github.copilot.CopilotClientMode;
import com.github.copilot.CopilotClientOptions;
import jakarta.annotation.PreDestroy;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;
import java.nio.file.Path;
import java.util.Collection;
import java.util.Collections;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.logging.Logger;

/**
 * Application-scoped CDI bean that owns the CopilotClient and manages the
 * collection of active agent sessions.
 *
 * <p>Equivalent to the C# {@code AppState} class. All state is concurrent-safe
 * because multiple virtual threads may submit new enquiries simultaneously.
 */
@ApplicationScoped
public class AppState {

    private static final Logger LOG = Logger.getLogger(AppState.class.getName());

    /** How long (ms) a rejected agent stays visible before being removed. */
    private static final long REJECTED_LINGER_MS = 15_000L;

    private final CopilotClient copilotClient;
    private final Map<String, Agent> agents = new ConcurrentHashMap<>();
    private volatile String selectedAgentId;

    @Inject
    private PropertyDatabase propertyDatabase;

    @Inject
    private UiUpdateSocket uiUpdateSocket;

    public AppState() {
        String copilotHome = Path.of(System.getProperty("user.home"), ".copilot").toString();
        this.copilotClient = new CopilotClient(
                new CopilotClientOptions()
                        .setMode(CopilotClientMode.EMPTY)
                        .setCopilotHome(copilotHome));
    }

    /**
     * Submits a new enquiry and launches an agent session on a virtual thread.
     *
     * @param enquiry the customer's natural-language enquiry text
     * @return the new agent's ID
     */
    public String submitEnquiry(String enquiry) {
        String agentId = UUID.randomUUID().toString().replace("-", "").substring(0, 8);
        Agent agent = new Agent(agentId, enquiry, propertyDatabase, uiUpdateSocket);
        agents.put(agentId, agent);
        uiUpdateSocket.pushPhaseChange(agentId);

        Thread.ofVirtual().name("agent-" + agentId).start(() -> {
            try {
                agent.run(copilotClient);
            } finally {
                if (agent.isRejected()) {
                    scheduleRemoval(agentId);
                }
            }
        });

        return agentId;
    }

    /** Returns an unmodifiable view of all current agents (active, done, and pending removal). */
    public Collection<Agent> getAgents() {
        return Collections.unmodifiableCollection(agents.values());
    }

    /** Returns the agent with the given ID, or {@code null} if not found. */
    public Agent getAgent(String agentId) {
        return agents.get(agentId);
    }

    public String getSelectedAgentId() {
        return selectedAgentId;
    }

    public void setSelectedAgentId(String selectedAgentId) {
        this.selectedAgentId = selectedAgentId;
    }

    public Agent getSelectedAgent() {
        if (selectedAgentId == null || selectedAgentId.isBlank()) {
            return null;
        }
        return agents.get(selectedAgentId);
    }

    /**
     * Schedules removal of a rejected agent after the linger period.
     * After removal, pushes an agent-removed event so the browser clears the card.
     */
    private void scheduleRemoval(String agentId) {
        Thread.ofVirtual().name("removal-" + agentId).start(() -> {
            try {
                Thread.sleep(REJECTED_LINGER_MS);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                return;
            }
            agents.remove(agentId);
            if (agentId.equals(selectedAgentId)) {
                selectedAgentId = null;
            }
            uiUpdateSocket.pushAgentRemoved(agentId);
        });
    }

    @PreDestroy
    public void shutdown() {
        try {
            copilotClient.close();
        } catch (Exception e) {
            LOG.warning("Error closing CopilotClient: " + e.getMessage());
        }
    }
}
