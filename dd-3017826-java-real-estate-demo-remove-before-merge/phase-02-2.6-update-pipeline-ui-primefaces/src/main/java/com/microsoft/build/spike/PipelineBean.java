package com.microsoft.build.spike;

import jakarta.enterprise.context.ApplicationScoped;
import jakarta.faces.push.Push;
import jakarta.faces.push.PushContext;
import jakarta.inject.Inject;
import jakarta.inject.Named;

/**
 * Manages pipeline state and pushes phase-change notifications to the client
 * via f:websocket. Simulates what the Copilot SDK agent event handler would do.
 */
@Named
@ApplicationScoped
public class PipelineBean {

    @Inject
    @Push(channel = "pipelineChannel")
    private PushContext pushContext;

    private Phase currentPhase = Phase.QUEUED;

    public Phase getCurrentPhase() {
        return currentPhase;
    }

    public String getCurrentPhaseLabel() {
        return currentPhase.getLabel();
    }

    public int getCurrentPhaseIndex() {
        return currentPhase.ordinal();
    }

    public Phase[] getAllPhases() {
        return Phase.values();
    }

    /**
     * Simulates an agent advancing to the next phase.
     * Called from the UI button to demonstrate the push mechanism.
     */
    public void advancePhase() {
        currentPhase = currentPhase.next();
        // Push phase change to all connected clients
        pushContext.send("phase-changed:" + currentPhase.name());
    }

    /**
     * Resets the pipeline back to QUEUED for re-testing.
     */
    public void reset() {
        currentPhase = Phase.QUEUED;
        pushContext.send("phase-changed:" + currentPhase.name());
    }

    /**
     * Simulates a background agent running through all phases with delays.
     * In the real demo, this would be driven by Copilot SDK tool calls.
     */
    public void simulateAgent() {
        Thread.startVirtualThread(() -> {
            try {
                currentPhase = Phase.QUEUED;
                pushContext.send("phase-changed:" + currentPhase.name());
                for (int i = 0; i < 4; i++) {
                    Thread.sleep(1500);
                    currentPhase = currentPhase.next();
                    pushContext.send("phase-changed:" + currentPhase.name());
                }
            } catch (InterruptedException e) {
                Thread.currentThread().interrupt();
            }
        });
    }
}
