/**
 * pipeline.js — Real Estate Agent Pipeline UI (issue 3.6)
 *
 * Implements the WebSocket → remoteCommand → partial update → CSS transition chain:
 *
 *   1. f:websocket calls handlePipelinePush(message) when the server pushes
 *   2. handlePipelinePush calls refreshPipeline() (p:remoteCommand)
 *   3. PrimeFaces re-renders the pipelineGrid via partial update
 *   4. oncomplete fires onPipelineRefreshed() which applies CSS animation classes
 */

'use strict';

/**
 * Called by the f:websocket onmessage handler when the server sends a push event.
 *
 * @param {string} message - Server push message in the format "agentId:eventType"
 *   Known eventTypes:
 *     "phase-changed" - an agent moved to a new phase
 *     "agent-removed" - a rejected agent was removed from the pipeline
 */
function handlePipelinePush(message) {
    console.log('[Pipeline] WebSocket push received:', message);

    // Trigger server-side re-render via the p:remoteCommand bridge.
    // refreshPipeline() is defined by PrimeFaces as a JS function that
    // triggers an Ajax request to re-render the pipelineGrid component.
    if (typeof refreshPipeline === 'function') {
        refreshPipeline();
    } else {
        console.warn('[Pipeline] refreshPipeline() not yet available, retrying...');
        // Retry after a brief delay in case PrimeFaces hasn't initialised yet
        setTimeout(function () {
            if (typeof refreshPipeline === 'function') {
                refreshPipeline();
            }
        }, 250);
    }
}

/**
 * Called by the p:remoteCommand oncomplete callback AFTER PrimeFaces has
 * finished updating the DOM for the pipelineGrid.
 *
 * This is the correct place to apply CSS animation classes because at this
 * point the server-rendered HTML is already in the DOM.
 */
function onPipelineRefreshed() {
    console.log('[Pipeline] DOM updated — applying animation classes.');

    var cards = document.querySelectorAll('.agent-card');

    cards.forEach(function (card) {
        var phase = card.getAttribute('data-phase');
        var active = card.getAttribute('data-active') === 'true';
        var rejected = card.getAttribute('data-rejected') === 'true';
        var done = card.getAttribute('data-done') === 'true';

        // Remove existing state classes before reapplying
        card.classList.remove('active', 'completed', 'rejected');

        if (rejected) {
            card.classList.add('rejected');
        } else if (done) {
            card.classList.add('completed');
        } else if (active) {
            card.classList.add('active');
        }

        // Apply the transitioning class briefly to produce a visible scale effect
        card.classList.add('transitioning');
        setTimeout(function () {
            card.classList.remove('transitioning');
        }, 400);
    });

    // Update pulse indicators: only the currently-active card's status dot pulses
    var allDots = document.querySelectorAll('.status-dot');
    allDots.forEach(function (dot) {
        dot.classList.remove('pulse-indicator');
    });

    var activeDots = document.querySelectorAll('.agent-card.active .status-dot');
    activeDots.forEach(function (dot) {
        dot.classList.add('pulse-indicator');
    });
}
