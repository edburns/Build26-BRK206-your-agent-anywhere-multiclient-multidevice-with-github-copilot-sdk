/* pipeline.js — websocket-driven partial refresh + lightweight card transitions */

let previousAgentPhaseMap = {};

function captureAgentPhaseMap() {
    const phaseMap = {};
    document.querySelectorAll('.agent-card[id^="agent-"]').forEach((card) => {
        const agentId = card.id.replace('agent-', '');
        const phaseColumn = card.closest('.phase-column');
        if (!phaseColumn) {
            return;
        }
        const phaseClass = Array.from(phaseColumn.classList)
            .find((className) => className.startsWith('phase-'));
        if (phaseClass) {
            phaseMap[agentId] = phaseClass;
        }
    });
    return phaseMap;
}

function applyAgentStateClasses() {
    document.querySelectorAll('.agent-card[id^="agent-"]').forEach((card) => {
        const phaseColumn = card.closest('.phase-column');
        if (!phaseColumn) {
            return;
        }

        card.classList.remove('active', 'completed', 'rejected');

        if (phaseColumn.classList.contains('phase-done')) {
            card.classList.add('completed');
        } else if (phaseColumn.classList.contains('phase-rejected')) {
            card.classList.add('rejected');
        } else {
            card.classList.add('active');
        }
    });
}

function applyPulseIndicator() {
    document.querySelectorAll('.status-dot').forEach((dot) => dot.classList.remove('pulse-indicator'));
    document.querySelectorAll('.agent-card.active .status-dot').forEach((dot) => dot.classList.add('pulse-indicator'));
}

function animateMovedCards(newPhaseMap) {
    Object.keys(newPhaseMap).forEach((agentId) => {
        if (previousAgentPhaseMap[agentId] && previousAgentPhaseMap[agentId] !== newPhaseMap[agentId]) {
            const card = document.getElementById(`agent-${agentId}`);
            if (card) {
                card.classList.add('transitioning');
                requestAnimationFrame(() => {
                    card.classList.remove('transitioning');
                });
            }
        }
    });
}

function onPipelineRefreshed() {
    const newPhaseMap = captureAgentPhaseMap();
    applyAgentStateClasses();
    applyPulseIndicator();
    animateMovedCards(newPhaseMap);
    previousAgentPhaseMap = newPhaseMap;
}

function handlePipelinePush(message) {
    console.log('[Pipeline] WebSocket push received:', message);

    previousAgentPhaseMap = captureAgentPhaseMap();
    const parts = String(message || '').split(':');
    const agentId = parts[0];
    const eventType = parts[1];

    if (eventType === 'agent-removed' && agentId) {
        const removedCard = document.getElementById(`agent-${agentId}`);
        if (removedCard) {
            removedCard.classList.add('transitioning', 'rejected');
            setTimeout(() => refreshPipeline(), 300);
            return;
        }
    }

    refreshPipeline();
}

document.addEventListener('DOMContentLoaded', () => {
    onPipelineRefreshed();
});
