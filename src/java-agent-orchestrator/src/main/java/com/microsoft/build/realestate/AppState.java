package com.microsoft.build.realestate;

import java.io.Serial;
import java.io.Serializable;
import java.time.Duration;
import java.util.Collection;
import java.util.List;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.Semaphore;
import java.util.logging.Level;
import java.util.logging.Logger;
import java.util.stream.Collectors;

import com.github.copilot.CopilotClient;

import jakarta.annotation.PostConstruct;
import jakarta.enterprise.context.SessionScoped;
import jakarta.faces.context.FacesContext;
import jakarta.inject.Inject;
import jakarta.inject.Named;

@Named
@SessionScoped
public class AppState implements Serializable {

    @Serial
    private static final long serialVersionUID = 1L;

    private static final Logger LOGGER = Logger.getLogger(AppState.class.getName());

    @Inject
    CopilotClient copilotClient;

    @Inject
    PropertyDatabase propertyDatabase;

    @Inject
    UiUpdateSocket uiUpdateSocket;

    // Captured once per session from FacesContext; String is serializable.
    private String sessionId;

    // Draft enquiry text bound to the add-enquiry dialog textarea.
    private String enquiryDraft;

    // Live agent state: not passivation-safe, marked transient.
    // An activated (deserialized) session will start with an empty agent map
    // and full semaphore, which is acceptable for this demo.
    private transient ConcurrentHashMap<String, Agent> agents;
    private static final int MAX_CONCURRENT_ENQUIRIES = 5;
    private transient Semaphore sessionSemaphore;

    @PostConstruct
    void init() {
        LOGGER.info("AppState: initialized, CopilotClient injected: " + (copilotClient != null));
    }

    public String getSessionId() {
        if (sessionId == null) {
            sessionId = FacesContext.getCurrentInstance()
                    .getExternalContext().getSessionId(true);
        }
        return sessionId;
    }

    private synchronized ConcurrentHashMap<String, Agent> agents() {
        if (agents == null) {
            agents = new ConcurrentHashMap<>();
        }
        return agents;
    }

    private synchronized Semaphore semaphore() {
        if (sessionSemaphore == null) {
            sessionSemaphore = new Semaphore(MAX_CONCURRENT_ENQUIRIES);
        }
        return sessionSemaphore;
    }

    public void submitEnquiry(String enquiryText) {
        if (!semaphore().tryAcquire()) {
            LOGGER.warning("AppState: at capacity (" + MAX_CONCURRENT_ENQUIRIES + " concurrent enquiries); rejecting enquiry");
            return;
        }
        Agent agent;
        try {
            agent = new Agent(enquiryText, uiUpdateSocket, getSessionId());
            agents().put(agent.getId(), agent);
        } catch (Exception e) {
            semaphore().release();
            LOGGER.log(Level.WARNING, "AppState: failed to create agent, permit released", e);
            return;
        }
        LOGGER.info("AppState: created agent " + agent.getId() + ", total agents=" + agents().size());
        notifyUi(agent.getId(), "agent-added");

        Thread.ofVirtual().start(() -> {
            LOGGER.info("AppState: virtual thread started for agent " + agent.getId());
            boolean permitReleased = false;
            try {
                agent.run(copilotClient, propertyDatabase);
                if (!agent.isRejected()) {
                    // Non-rejected agents remain visible
                    return;
                }
                // Release the semaphore permit before the cosmetic linger so that the slot
                // is immediately available for new enquiries.
                semaphore().release();
                permitReleased = true;
                // Rejected agents linger for 15 seconds then are removed
                Thread.sleep(Duration.ofSeconds(15));
                removeAgent(agent.getId());
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                LOGGER.warning("AppState: virtual thread interrupted for agent " + agent.getId());
                removeAgent(agent.getId());
            } catch (Exception e) {
                LOGGER.log(Level.WARNING, "AppState: agent " + agent.getId() + " failed: " + e.getMessage(), e);
                removeAgent(agent.getId());
            } finally {
                if (!permitReleased) {
                    semaphore().release();
                }
            }
        });
    }

    public void submitSampleEnquiry() {
        submitEnquiry("Looking for a three-bedroom home near good schools in Seattle for under $900000.");
    }

    public void submitDraftEnquiry() {
        if (enquiryDraft != null && !enquiryDraft.isBlank()) {
            submitEnquiry(enquiryDraft);
            enquiryDraft = null;
        }
    }

    public String getEnquiryDraft() {
        return enquiryDraft;
    }

    public void setEnquiryDraft(String enquiryDraft) {
        this.enquiryDraft = enquiryDraft;
    }

    public Collection<Agent> getAgents() {
        return agents().values();
    }

    public List<Agent> getAgentsByPhase(String phaseName) {
        Phase target;
        try {
            target = Phase.valueOf(phaseName);
        } catch (IllegalArgumentException e) {
            return List.of();
        }
        return agents().values().stream()
                .filter(a -> a.getPhase() == target)
                .sorted(java.util.Comparator.comparing(Agent::getStartedAt).thenComparing(Agent::getId))
                .collect(Collectors.toList());
    }

    public Agent getAgent(String id) {
        return agents().get(id);
    }

    public void removeAgent(String id) {
        Agent removed = agents().remove(id);
        if (removed != null) {
            LOGGER.info("AppState: removed agent " + id);
            notifyUi(id, "agent-removed");
        }
    }

    public void notifyUi(String agentId, String eventType) {
        uiUpdateSocket.sendUpdate(agentId, eventType, getSessionId());
    }
}
