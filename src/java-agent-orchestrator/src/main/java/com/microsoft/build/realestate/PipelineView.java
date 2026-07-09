package com.microsoft.build.realestate;

import jakarta.enterprise.context.RequestScoped;
import jakarta.faces.application.FacesMessage;
import jakarta.faces.context.FacesContext;
import jakarta.inject.Inject;
import jakarta.inject.Named;
import java.util.Collection;
import java.util.Comparator;
import java.util.List;
import java.util.logging.Logger;

/**
 * JSF request-scoped backing bean for index.xhtml.
 * Provides the pipeline data for rendering and handles the "submit enquiry" action.
 */
@Named
@RequestScoped
public class PipelineView {

    private static final Logger LOG = Logger.getLogger(PipelineView.class.getName());

    @Inject
    private AppState appState;

    /** Text bound to the enquiry input field. */
    private String enquiryText;

    /**
     * Returns all phases in order, used to render pipeline column headers.
     */
    public Phase[] getAllPhases() {
        return Phase.values();
    }

    /**
     * Returns all active agents in the pipeline.
     */
    public Collection<Agent> getAgents() {
        return appState.getAgents();
    }

    /**
     * Returns agents currently in a specific phase.
     */
    public List<Agent> getAgentsAtPhase(Phase phase) {
        return appState.getAgents().stream()
                .filter(a -> a.getPhase() == phase)
                .sorted(Comparator.comparing(Agent::getStartedAt))
                .toList();
    }

    public Agent getSelectedAgent() {
        return appState.getSelectedAgent();
    }

    public void selectAgent(String agentId) {
        appState.setSelectedAgentId(agentId);
    }

    public void clearSelectedAgent() {
        appState.setSelectedAgentId(null);
    }

    /**
     * JSF action method: submits the enquiry text to AppState and launches an agent.
     */
    public void submitEnquiry() {
        if (enquiryText == null || enquiryText.isBlank()) {
            FacesContext.getCurrentInstance().addMessage(null,
                    new FacesMessage(FacesMessage.SEVERITY_WARN,
                            "Please enter an enquiry.", null));
            return;
        }
        String agentId = appState.submitEnquiry(enquiryText.trim());
        LOG.info("Submitted enquiry, agent ID: " + agentId);
        enquiryText = "";
    }

    /**
     * Returns the CSS class(es) for a phase column header.
     * Used in index.xhtml to avoid complex inline EL ternary expressions.
     */
    public String getPhaseHeaderClass(Phase phase) {
        if (phase == Phase.DONE) {
            return "phase-header done";
        }
        if (phase.isRejected()) {
            return "phase-header rejected";
        }
        return "phase-header";
    }

    /**
     * Returns the CSS class(es) for an agent card based on the agent's current state.
     * Used in index.xhtml to centralise the conditional class logic.
     */
    public String getAgentCardClass(Agent agent) {
        StringBuilder sb = new StringBuilder("agent-card");
        if (agent.isActive()) {
            sb.append(" active");
        } else if (agent.isDone()) {
            sb.append(" completed");
        } else if (agent.isRejected()) {
            sb.append(" rejected");
        }
        return sb.toString();
    }

    /**
     * Returns the CSS class(es) for an agent's status dot.
     */
    public String getStatusDotClass(Agent agent) {
        if (agent.isActive()) {
            return "status-dot active-dot";
        } else if (agent.isDone()) {
            return "status-dot done-dot";
        } else if (agent.isRejected()) {
            return "status-dot rejected-dot";
        }
        return "status-dot";
    }

    public String getEventTypeBadgeClass(AgentEvent event) {
        return switch (event.getEventType()) {
            case "assistant_message" -> "event-type event-type-assistant";
            case "tool_call" -> "event-type event-type-tool-call";
            case "tool_result" -> "event-type event-type-tool-result";
            case "phase_change" -> "event-type event-type-phase";
            case "session_error" -> "event-type event-type-error";
            default -> "event-type";
        };
    }

    public String getEnquiryText() { return enquiryText; }
    public void setEnquiryText(String enquiryText) { this.enquiryText = enquiryText; }
}
