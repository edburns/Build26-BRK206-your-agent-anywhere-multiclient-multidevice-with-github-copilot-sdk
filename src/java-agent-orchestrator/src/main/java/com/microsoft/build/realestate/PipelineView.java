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
import java.util.Arrays;

/**
 * JSF request-scoped backing bean for index.xhtml.
 * Provides the pipeline data for rendering and handles the "submit enquiry" action.
 */
@Named
@RequestScoped
public class PipelineView {

    private static final Logger LOG = Logger.getLogger(PipelineView.class.getName());

    private static final String[] SAMPLE_ENQUIRIES = {
        "Looking for a 3-bed family home near good schools in the suburbs, budget around $500k",
        "Need a downtown condo with parking, 1-2 bedrooms, under $350k",
        "Seeking waterfront property with at least 4 bedrooms for retirement",
        "Budget max $450k, want to be near Sugar Wharf Podium School",
        "Want a rural property with land, at least 5 acres, horse-friendly",
        "asdkjh asdkjhasd this is spam garbage text!!!",
        "Investor looking for multi-unit rental property near university campus",
        "Need an accessible single-story home with wheelchair modifications, 2+ bed",
        "Looking for a fixer-upper Victorian in the historic district",
        "BUY CRYPTO NOW!!! Not actually looking for property lol"
    };

    @Inject
    private AppState appState;

    @Inject
    private SelectionState selectionState;

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

    /** Dashboard: count of agents in non-terminal (processing) phases. */
    public long getProcessingCount() {
        return appState.getAgents().stream()
                .filter(a -> !a.getPhase().isTerminal())
                .count();
    }

    /** Dashboard: count of agents in DONE phase. */
    public long getCompletedCount() {
        return appState.getAgents().stream()
                .filter(a -> a.getPhase() == Phase.DONE)
                .count();
    }

    /** Dashboard: count of agents in rejected phases. */
    public long getRejectedCount() {
        return appState.getAgents().stream()
                .filter(a -> a.getPhase().isRejected())
                .count();
    }

    /**
     * Overload accepting a phase name string (used in XHTML EL expressions).
     */
    public List<Agent> getAgentsAtPhase(String phaseName) {
        return getAgentsAtPhase(Phase.valueOf(phaseName));
    }

    public Agent getSelectedAgent() {
        return selectionState.getSelectedAgent();
    }

    public void selectAgent(String agentId) {
        selectionState.setSelectedAgentId(agentId);
    }

    public void clearSelectedAgent() {
        selectionState.setSelectedAgentId(null);
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
     * Returns the list of canned sample enquiries for the "+" popup.
     */
    public List<String> getSampleEnquiries() {
        return Arrays.asList(SAMPLE_ENQUIRIES);
    }

    /**
     * JSF action method: submits a canned query by text.
     */
    public void submitSampleEnquiry(String enquiry) {
        if (enquiry != null && !enquiry.isBlank()) {
            String agentId = appState.submitEnquiry(enquiry);
            LOG.info("Submitted sample enquiry, agent ID: " + agentId);
        }
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
     * Overload accepting a phase name string (used in XHTML EL expressions).
     */
    public String getPhaseHeaderClass(String phaseName) {
        return getPhaseHeaderClass(Phase.valueOf(phaseName));
    }

    /**
     * Returns the CSS class(es) for an agent card based on the agent's current state.
     * Used in index.xhtml to centralise the conditional class logic.
     */
    public String getAgentCardClass(Agent agent) {
        StringBuilder sb = new StringBuilder("agent-card");
        if (agent.isFailed()) {
            sb.append(" failed");
        } else if (agent.isActive()) {
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
        if (agent.isFailed()) {
            return "status-dot failed-dot";
        } else if (agent.isActive()) {
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
