package com.microsoft.build.realestate;

import jakarta.enterprise.context.SessionScoped;
import jakarta.inject.Inject;
import jakarta.inject.Named;
import java.io.Serializable;

/**
 * Session-scoped CDI bean that tracks which agent is currently selected
 * in the detail panel for this user's browser session.
 *
 * <p>Keeping selection state per-session ensures that one user's agent-card
 * click does not change the detail view for other connected users.
 */
@Named
@SessionScoped
public class SelectionState implements Serializable {

    @Inject
    private AppState appState;

    private String selectedAgentId;

    public String getSelectedAgentId() {
        return selectedAgentId;
    }

    public void setSelectedAgentId(String selectedAgentId) {
        this.selectedAgentId = selectedAgentId;
    }

    /** Returns the currently selected {@link Agent}, or {@code null} if none is selected. */
    public Agent getSelectedAgent() {
        if (selectedAgentId == null || selectedAgentId.isBlank()) {
            return null;
        }
        return appState.getAgent(selectedAgentId);
    }
}
