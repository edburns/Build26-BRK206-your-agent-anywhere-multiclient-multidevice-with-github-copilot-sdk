package com.microsoft.build.realestate;

import java.io.Serial;
import java.io.Serializable;
import java.time.Duration;
import java.util.Collection;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.Semaphore;
import java.util.logging.Level;
import java.util.logging.Logger;

import com.github.copilot.CopilotClient;

import jakarta.annotation.PostConstruct;
import jakarta.enterprise.context.SessionScoped;
import jakarta.inject.Inject;
import jakarta.inject.Named;
import jakarta.servlet.http.HttpSession;

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

    @Inject
    HttpSession httpSession;

    private final ConcurrentHashMap<String, Agent> agents = new ConcurrentHashMap<>();
    private static final int MAX_CONCURRENT_SESSIONS = 5;
    private final Semaphore sessionSemaphore = new Semaphore(MAX_CONCURRENT_SESSIONS);

    @PostConstruct
    void init() {
        LOGGER.info("AppState: initialized, CopilotClient injected: " + (copilotClient != null));
    }

    public void submitEnquiry(String enquiryText) {
        if (!sessionSemaphore.tryAcquire()) {
            LOGGER.warning("AppState: at capacity (" + MAX_CONCURRENT_SESSIONS + " concurrent sessions); rejecting enquiry");
            return;
        }
        var agent = new Agent(enquiryText, uiUpdateSocket, httpSession.getId());
        agents.put(agent.getId(), agent);
        LOGGER.info("AppState: created agent " + agent.getId() + ", total agents=" + agents.size());
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
                sessionSemaphore.release();
                permitReleased = true;
                // Rejected agents linger for 15 seconds then are removed
                Thread.sleep(Duration.ofSeconds(15));
                removeAgent(agent.getId());
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
                LOGGER.warning("AppState: virtual thread interrupted for agent " + agent.getId());
            } catch (Exception e) {
                LOGGER.log(Level.WARNING, "AppState: agent " + agent.getId() + " failed: " + e.getMessage(), e);
                removeAgent(agent.getId());
            } finally {
                if (!permitReleased) {
                    sessionSemaphore.release();
                }
            }
        });
    }

    public void submitSampleEnquiry() {
        submitEnquiry("Looking for a three-bedroom home near good schools in Seattle for under $900000.");
    }

    public Collection<Agent> getAgents() {
        return agents.values();
    }

    public Agent getAgent(String id) {
        return agents.get(id);
    }

    public void removeAgent(String id) {
        Agent removed = agents.remove(id);
        if (removed != null) {
            LOGGER.info("AppState: removed agent " + id);
            notifyUi(id, "agent-removed");
        }
    }

    public void notifyUi(String agentId, String eventType) {
        uiUpdateSocket.sendUpdate(agentId, eventType, httpSession.getId());
    }
}
