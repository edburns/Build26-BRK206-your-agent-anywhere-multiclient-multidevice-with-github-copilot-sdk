package com.microsoft.build.realestate;

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.*;

/**
 * Unit tests for the {@link Phase} enum — validates the pipeline state machine rules
 * without requiring a Copilot CLI or Jakarta EE container.
 */
class PhaseTest {

    @Test
    void doneIsTerminal() {
        assertTrue(Phase.DONE.isTerminal(), "DONE must be a terminal phase");
    }

    @Test
    void rejectedGarbageIsTerminalAndRejected() {
        assertTrue(Phase.REJECTED_GARBAGE.isTerminal());
        assertTrue(Phase.REJECTED_GARBAGE.isRejected());
    }

    @Test
    void rejectedNoMatchesIsTerminalAndRejected() {
        assertTrue(Phase.REJECTED_NO_MATCHES.isTerminal());
        assertTrue(Phase.REJECTED_NO_MATCHES.isRejected());
    }

    @Test
    void activePhaseIsNotTerminal() {
        assertFalse(Phase.QUEUED.isTerminal());
        assertFalse(Phase.VALIDATING.isTerminal());
        assertFalse(Phase.SEARCHING.isTerminal());
        assertFalse(Phase.WRITING_REPORT.isTerminal());
    }

    @Test
    void doneIsNotRejected() {
        assertFalse(Phase.DONE.isRejected(), "DONE is terminal but not rejected");
    }

    @Test
    void activePhaseIsNotRejected() {
        for (Phase p : new Phase[]{Phase.QUEUED, Phase.VALIDATING, Phase.SEARCHING, Phase.WRITING_REPORT}) {
            assertFalse(p.isRejected(), p + " should not be a rejected phase");
        }
    }

    @Test
    void allPhasesHaveNonBlankLabels() {
        for (Phase p : Phase.values()) {
            assertNotNull(p.getLabel(), "Phase " + p + " has null label");
            assertFalse(p.getLabel().isBlank(), "Phase " + p + " has blank label");
        }
    }

    @Test
    void exactlyThreeTerminalPhases() {
        long count = java.util.Arrays.stream(Phase.values())
                .filter(Phase::isTerminal)
                .count();
        assertEquals(3, count, "Expected exactly 3 terminal phases: DONE, REJECTED_GARBAGE, REJECTED_NO_MATCHES");
    }

    @Test
    void exactlyTwoRejectedPhases() {
        long count = java.util.Arrays.stream(Phase.values())
                .filter(Phase::isRejected)
                .count();
        assertEquals(2, count, "Expected exactly 2 rejected phases");
    }
}
