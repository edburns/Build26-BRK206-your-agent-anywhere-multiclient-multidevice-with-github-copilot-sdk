package com.microsoft.build.realestate;

/**
 * Pipeline phases matching the C# demo's Phase enum.
 * Agents move through the main sequence (QUEUED → VALIDATING → SEARCHING → WRITING_REPORT → DONE)
 * or branch to a terminal rejection phase.
 */
public enum Phase {
    QUEUED("Queued"),
    VALIDATING("Validating"),
    SEARCHING("Searching"),
    WRITING_REPORT("Writing Report"),
    REJECTED_GARBAGE("Rejected"),
    REJECTED_NO_MATCHES("No Matches"),
    DONE("Done");

    private final String label;

    Phase(String label) {
        this.label = label;
    }

    public String getLabel() {
        return label;
    }

    /** Returns true if this phase is a terminal (finished) state. */
    public boolean isTerminal() {
        return this == DONE || this == REJECTED_GARBAGE || this == REJECTED_NO_MATCHES;
    }

    /** Returns true if this phase is a rejection state. */
    public boolean isRejected() {
        return this == REJECTED_GARBAGE || this == REJECTED_NO_MATCHES;
    }
}
