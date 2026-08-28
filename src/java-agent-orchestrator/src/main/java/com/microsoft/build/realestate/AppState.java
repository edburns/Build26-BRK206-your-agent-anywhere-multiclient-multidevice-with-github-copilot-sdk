package com.microsoft.build.realestate;

import com.github.copilot.CopilotClient;
import com.github.copilot.rpc.CopilotClientMode;
import com.github.copilot.rpc.CopilotClientOptions;
import com.github.copilot.rpc.RuntimeConnection;
import jakarta.annotation.PostConstruct;
import jakarta.annotation.PreDestroy;
import jakarta.annotation.Resource;
import jakarta.enterprise.concurrent.ManagedThreadFactory;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.inject.Inject;
import java.nio.file.Path;
import java.util.Collection;
import java.util.Collections;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.Executor;
import java.util.concurrent.ExecutionException;
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

    private final Map<String, Agent> agents = new ConcurrentHashMap<>();

    @Resource(lookup = "concurrent/virtualThreadFactory")
    private ManagedThreadFactory virtualThreadFactory;

    @Inject
    private PropertyDatabase propertyDatabase;

    @Inject
    private UiUpdateSocket uiUpdateSocket;

    private CopilotClient copilotClient;

    public AppState() {
        // CopilotClient created in init() after @Resource/@Inject fields are available
    }

    @PostConstruct
    public void init() {
        // The ManagedThreadFactory (virtual=true) creates container-managed virtual
        // threads that automatically propagate CDI, JNDI, and transaction context.
        Executor managedVirtualExecutor = runnable ->
                virtualThreadFactory.newThread(runnable).start();

        String copilotHome = Path.of(System.getProperty("user.home"), ".copilot").toString();
        CopilotClientOptions copilotClientOptions = new CopilotClientOptions()
                .setMode(CopilotClientMode.EMPTY)
                .setCopilotHome(copilotHome)
                .setExecutor(managedVirtualExecutor)
                .setConnection(RuntimeConnection.forInProcess());
        copilotClient = new CopilotClient(copilotClientOptions);
        try {
            copilotClient.start().get();
            String runtimeVersion = copilotClient.getStatus().get().getVersion();
            LOG.info(("CopilotClient initialized with in-process runtime version=%s "
                    + "and managed virtual-thread executor.")
                    .formatted(runtimeVersion));
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new IllegalStateException("Interrupted while starting the in-process Copilot runtime", e);
        } catch (ExecutionException e) {
            throw new IllegalStateException("Unable to start the in-process Copilot runtime", e.getCause());
        }
    }

    /**
     * Submits a new enquiry and launches an agent session on a virtual thread.
     *
     * @param enquiry the customer's natural-language enquiry text
     * @return the new agent's ID
     */
    public String submitEnquiry(String enquiry) {
        String agentId = UUID.randomUUID().toString().replace("-", "").substring(0, 8);
        LOG.info("Submitting enquiry. AgentId=" + agentId + ", Enquiry=" + enquiry);

        Agent agent = new Agent(agentId, enquiry, propertyDatabase, uiUpdateSocket);
        agents.put(agentId, agent);
        uiUpdateSocket.pushPhaseChange(agentId);

        virtualThreadFactory.newThread(() -> {
            LOG.info("Virtual thread started for agent " + agentId);
            try {
                agent.run(copilotClient);
            } finally {
                if (agent.isRejected()) {
                    scheduleRemoval(agentId);
                }
            }
        }).start();

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

    /**
     * Schedules removal of a rejected agent after the linger period.
     * After removal, pushes an agent-removed event so the browser clears the card.
     */
    private void scheduleRemoval(String agentId) {
        virtualThreadFactory.newThread(() -> {
            try {
                Thread.sleep(REJECTED_LINGER_MS);
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                return;
            }
            agents.remove(agentId);
            uiUpdateSocket.pushAgentRemoved(agentId);
        }).start();
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
