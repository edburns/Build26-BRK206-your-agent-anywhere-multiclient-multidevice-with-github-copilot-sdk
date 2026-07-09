package com.microsoft.build.realestate;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.time.Instant;
import java.util.List;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Unit tests for {@link Agent} — validates phase transitions, event capture, and
 * concurrent-safety without requiring a Copilot CLI or Jakarta EE container.
 *
 * <p>These tests use a no-op {@link UiUpdateSocket} stub so the push context
 * (which requires a running Jakarta Faces runtime) is never invoked.
 */
class AgentTest {

    /** No-op stub so we can test Agent without a running Faces/WebSocket runtime. */
    private static final UiUpdateSocket NO_OP_SOCKET = new UiUpdateSocket() {
        @Override public void pushPhaseChange(String agentId) { /* no-op */ }
        @Override public void pushDetailUpdate(String agentId) { /* no-op */ }
        @Override public void pushAgentRemoved(String agentId) { /* no-op */ }
    };

    private Agent agent;

    @BeforeEach
    void createAgent() {
        agent = new Agent("test01", "Looking for a flat in London", null, NO_OP_SOCKET);
    }

    // -----------------------------------------------------------------------
    // Initial state
    // -----------------------------------------------------------------------

    @Test
    void newAgentStartsQueued() {
        assertEquals(Phase.QUEUED, agent.getPhase());
    }

    @Test
    void newAgentIsActive() {
        assertTrue(agent.isActive());
        assertFalse(agent.isDone());
        assertFalse(agent.isRejected());
    }

    @Test
    void newAgentHasOneInitialEvent() {
        List<AgentEvent> events = agent.getEvents();
        assertEquals(1, events.size(), "Agent should have exactly one initial QUEUED phase event");
        AgentEvent first = events.get(0);
        assertEquals("phase_change", first.getEventType());
        assertEquals(Phase.QUEUED.name(), first.getDetail());
    }

    @Test
    void enquiryAndIdArePreserved() {
        assertEquals("test01", agent.getId());
        assertEquals("Looking for a flat in London", agent.getEnquiry());
    }

    @Test
    void startedAtIsNotNull() {
        assertNotNull(agent.getStartedAt());
        assertTrue(agent.getStartedAt().isBefore(Instant.now().plusSeconds(1)));
    }

    // -----------------------------------------------------------------------
    // setCurrentPhase via the @CopilotTool method
    // -----------------------------------------------------------------------

    @Test
    void setCurrentPhaseValidating() {
        String result = agent.setCurrentPhase("VALIDATING");
        assertEquals(Phase.VALIDATING, agent.getPhase());
        assertTrue(result.contains("VALIDATING") || result.toLowerCase().contains("validating"),
                "Expected confirmation message, got: " + result);
    }

    @Test
    void setCurrentPhaseSearching() {
        agent.setCurrentPhase("SEARCHING");
        assertEquals(Phase.SEARCHING, agent.getPhase());
        assertTrue(agent.isActive());
    }

    @Test
    void setCurrentPhaseDone() {
        agent.setCurrentPhase("DONE");
        assertEquals(Phase.DONE, agent.getPhase());
        assertTrue(agent.isDone());
        assertFalse(agent.isActive());
        assertFalse(agent.isRejected());
        assertNotNull(agent.getFinishedAt(), "finishedAt must be set when reaching DONE");
    }

    @Test
    void setCurrentPhaseRejectedGarbage() {
        agent.setCurrentPhase("REJECTED_GARBAGE");
        assertEquals(Phase.REJECTED_GARBAGE, agent.getPhase());
        assertTrue(agent.isRejected());
        assertFalse(agent.isActive());
        assertFalse(agent.isDone());
        assertNotNull(agent.getFinishedAt());
    }

    @Test
    void setCurrentPhaseRejectedNoMatches() {
        agent.setCurrentPhase("REJECTED_NO_MATCHES");
        assertEquals(Phase.REJECTED_NO_MATCHES, agent.getPhase());
        assertTrue(agent.isRejected());
    }

    @Test
    void setCurrentPhaseUnknownReturnsErrorMessage() {
        String result = agent.setCurrentPhase("TOTALLY_WRONG");
        assertEquals(Phase.QUEUED, agent.getPhase(), "Phase must not change on unknown value");
        assertTrue(result.toLowerCase().contains("unknown") || result.toLowerCase().contains("totally"),
                "Expected error message, got: " + result);
    }

    @Test
    void setCurrentPhaseIsCaseInsensitive() {
        agent.setCurrentPhase("validating");
        assertEquals(Phase.VALIDATING, agent.getPhase());
        agent.setCurrentPhase("done");
        assertEquals(Phase.DONE, agent.getPhase());
    }

    // -----------------------------------------------------------------------
    // Full happy-path transition sequence
    // -----------------------------------------------------------------------

    @Test
    void fullHappyPathTransitions() {
        for (String phase : new String[]{"VALIDATING", "SEARCHING", "WRITING_REPORT", "DONE"}) {
            agent.setCurrentPhase(phase);
        }
        assertEquals(Phase.DONE, agent.getPhase());
        assertTrue(agent.isDone());
        assertFalse(agent.isActive());
    }

    @Test
    void spamRejectionTransitions() {
        agent.setCurrentPhase("VALIDATING");
        agent.setCurrentPhase("REJECTED_GARBAGE");

        assertEquals(Phase.REJECTED_GARBAGE, agent.getPhase());
        assertTrue(agent.isRejected());
    }

    @Test
    void noMatchesTransitions() {
        agent.setCurrentPhase("VALIDATING");
        agent.setCurrentPhase("SEARCHING");
        agent.setCurrentPhase("REJECTED_NO_MATCHES");

        assertEquals(Phase.REJECTED_NO_MATCHES, agent.getPhase());
        assertTrue(agent.isRejected());
    }

    // -----------------------------------------------------------------------
    // Event log
    // -----------------------------------------------------------------------

    @Test
    void phaseChangeAddsEventToLog() {
        int before = agent.getEvents().size();
        agent.setCurrentPhase("VALIDATING");
        int after = agent.getEvents().size();
        assertEquals(before + 1, after, "setCurrentPhase must add a phase_change event");

        AgentEvent last = agent.getEvents().get(after - 1);
        assertEquals("phase_change", last.getEventType());
        assertEquals("VALIDATING", last.getDetail());
    }

    @Test
    void eventListIsDefensiveCopy() {
        List<AgentEvent> first = agent.getEvents();
        agent.setCurrentPhase("VALIDATING");
        List<AgentEvent> second = agent.getEvents();
        assertEquals(first.size() + 1, second.size(),
                "getEvents() should return fresh snapshot each time");
    }

    // -----------------------------------------------------------------------
    // Concurrent phase updates (thread-safety)
    // -----------------------------------------------------------------------

    @Test
    void concurrentPhaseUpdatesDoNotCorruptEventLog() throws InterruptedException {
        int threadCount = 20;
        CountDownLatch ready = new CountDownLatch(1);
        CountDownLatch done = new CountDownLatch(threadCount);
        AtomicInteger errors = new AtomicInteger();

        for (int i = 0; i < threadCount; i++) {
            final String phase = (i % 2 == 0) ? "VALIDATING" : "SEARCHING";
            Thread.ofVirtual().start(() -> {
                try {
                    ready.await();
                    agent.setCurrentPhase(phase);
                } catch (Exception e) {
                    errors.incrementAndGet();
                } finally {
                    done.countDown();
                }
            });
        }

        ready.countDown();
        assertTrue(done.await(5, TimeUnit.SECONDS), "All threads should finish within 5 seconds");
        assertEquals(0, errors.get(), "No thread should throw an exception");

        // The event log should contain at least the initial QUEUED + threadCount events
        assertTrue(agent.getEvents().size() >= threadCount + 1,
                "Expected at least " + (threadCount + 1) + " events (initial QUEUED + " + threadCount + " thread events), got " + agent.getEvents().size());
    }

}
