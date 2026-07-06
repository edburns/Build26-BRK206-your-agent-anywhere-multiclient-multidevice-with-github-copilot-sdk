package com.microsoft.build.spike;

/**
 * Pipeline phases matching the C# demo's Phase enum.
 */
public enum Phase {
    QUEUED("Queued"),
    VALIDATING("Validating"),
    SEARCHING("Searching"),
    WRITING_REPORT("Writing Report"),
    DONE("Done");

    private final String label;

    Phase(String label) {
        this.label = label;
    }

    public String getLabel() {
        return label;
    }

    public Phase next() {
        Phase[] values = values();
        int nextOrdinal = this.ordinal() + 1;
        if (nextOrdinal >= values.length) {
            return this; // stay at DONE
        }
        return values[nextOrdinal];
    }
}
