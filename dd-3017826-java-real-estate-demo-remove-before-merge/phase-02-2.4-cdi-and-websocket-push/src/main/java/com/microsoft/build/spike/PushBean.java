package com.microsoft.build.spike;

import jakarta.enterprise.context.ApplicationScoped;
import jakarta.faces.push.Push;
import jakarta.faces.push.PushContext;
import jakarta.inject.Inject;
import jakarta.inject.Named;

@Named
@ApplicationScoped
public class PushBean {

    @Inject
    @Push(channel = "spikeChannel")
    private PushContext pushContext;

    /**
     * Simulates a background push (like an agent event handler would do).
     * Sends a confirmation message via f:websocket CDI push.
     */
    public void triggerPush() {
        String message = "SPIKE CONFIRMED: f:websocket CDI push works on OpenLiberty 26.0.0.5 "
                + "with faces-4.0. PushContext.send() delivered this message from a CDI bean.";
        pushContext.send(message);
    }
}
