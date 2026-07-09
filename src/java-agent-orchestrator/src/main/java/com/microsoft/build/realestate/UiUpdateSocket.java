package com.microsoft.build.realestate;

import jakarta.enterprise.context.ApplicationScoped;
import jakarta.faces.push.Push;
import jakarta.faces.push.PushContext;
import jakarta.inject.Inject;

/**
 * CDI bean wrapping the Jakarta Faces PushContext for the pipeline channel.
 * Can be called from any thread (including virtual threads running agent sessions)
 * because PushContext.send() is thread-safe when the bean is @ApplicationScoped.
 *
 * <p>Message format sent to the browser: {@code "agentId:eventType"}
 * <ul>
 *   <li>{@code "agentId:phase-changed"} — agent moved to a new phase</li>
 *   <li>{@code "agentId:agent-removed"} — agent was removed from the pipeline</li>
 * </ul>
 */
@ApplicationScoped
public class UiUpdateSocket {

    @Inject
    @Push(channel = "pipelineChannel")
    private PushContext pushContext;

    /**
     * Pushes a phase-change notification for the given agent to all connected browsers.
     */
    public void pushPhaseChange(String agentId) {
        pushContext.send(agentId + ":phase-changed");
    }

    /**
     * Pushes a removal notification for the given agent to all connected browsers.
     * Called when a rejected agent is removed from the pipeline after its linger period.
     */
    public void pushAgentRemoved(String agentId) {
        pushContext.send(agentId + ":agent-removed");
    }
}
