package com.microsoft.build.realestate;

import jakarta.enterprise.context.ApplicationScoped;
import jakarta.faces.push.Push;
import jakarta.faces.push.PushContext;
import jakarta.inject.Inject;
import jakarta.inject.Named;

@Named
@ApplicationScoped
public class UiUpdateSocket {

    @Inject
    @Push(channel = "pipelineChannel")
    private PushContext pushContext;

    public void sendUpdate(String agentId, String eventType) {
        pushContext.send(agentId + ":" + eventType);
    }
}
