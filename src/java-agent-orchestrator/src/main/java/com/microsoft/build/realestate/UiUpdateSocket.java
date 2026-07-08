package com.microsoft.build.realestate;

import java.util.logging.Level;
import java.util.logging.Logger;

import jakarta.enterprise.context.ApplicationScoped;
import jakarta.faces.push.Push;
import jakarta.faces.push.PushContext;
import jakarta.inject.Inject;
import jakarta.inject.Named;

@Named
@ApplicationScoped
public class UiUpdateSocket {

    private static final Logger LOGGER = Logger.getLogger(UiUpdateSocket.class.getName());

    @Inject
    @Push(channel = "pipelineChannel")
    private PushContext pushContext;

    public void sendUpdate(String agentId, String eventType, String sessionId) {
        try {
            pushContext.send(agentId + ":" + eventType, sessionId);
        } catch (Exception e) {
            LOGGER.log(Level.WARNING, "Failed to push UI update for agent " + agentId + " event " + eventType, e);
        }
    }
}
