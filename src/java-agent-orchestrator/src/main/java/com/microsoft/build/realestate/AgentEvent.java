package com.microsoft.build.realestate;

import java.time.Instant;

/**
 * Lightweight UI-facing summary of an agent session event.
 */
public class AgentEvent {

    private final Instant timestamp;
    private final String eventType;
    private final String summary;
    private final String detail;

    public AgentEvent(Instant timestamp, String eventType, String summary, String detail) {
        this.timestamp = timestamp;
        this.eventType = eventType;
        this.summary = summary;
        this.detail = detail;
    }

    public Instant getTimestamp() { return timestamp; }
    public String getEventType() { return eventType; }
    public String getSummary() { return summary; }
    public String getDetail() { return detail; }
}
