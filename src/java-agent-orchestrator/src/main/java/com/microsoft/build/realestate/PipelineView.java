package com.microsoft.build.realestate;

import jakarta.enterprise.context.RequestScoped;
import jakarta.faces.application.FacesMessage;
import jakarta.faces.context.FacesContext;
import jakarta.inject.Inject;
import jakarta.inject.Named;
import java.util.Collection;
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
    public java.util.List<Agent> getAgentsAtPhase(Phase phase) {
        return appState.getAgents().stream()
                .filter(a -> a.getPhase() == phase)
                .toList();
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

    public String getEnquiryText() { return enquiryText; }
    public void setEnquiryText(String enquiryText) { this.enquiryText = enquiryText; }
}
