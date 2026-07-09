/**
 * pipeline.js — Real Estate Agent Pipeline UI (issue 3.6)
 *
 * Implements the WebSocket → remoteCommand → partial update → CSS transition chain.
 * handlePipelinePush() dispatches on event type:
 *
 *   phase-changed / agent-removed:
 *     1. f:websocket calls handlePipelinePush(message)
 *     2. handlePipelinePush calls refreshPipeline() (p:remoteCommand)
 *     3. PrimeFaces re-renders pipelineGrid + detailContent via partial update
 *     4. oncomplete fires onPipelineRefreshed() which applies CSS animation classes
 *
 *   detail-updated (non-phase session events — tool calls, assistant messages, etc.):
 *     1. f:websocket calls handlePipelinePush(message)
 *     2. handlePipelinePush calls refreshDetailOnly() (p:remoteCommand)
 *     3. PrimeFaces re-renders only detailContent (inner panel) — no card animations,
 *        and the dialog widget state is preserved
 */

'use strict';

/**
 * Called by the f:websocket onmessage handler when the server sends a push event.
 *
 * Message format is "agentId:eventType" (e.g. "a3f1b2c4:phase-changed").
 * - "phase-changed" and "agent-removed": full grid + detail refresh with card animations.
 * - "detail-updated": lightweight refresh of the detail panel only (no card animations).
 *
 * @param {string} message - Server push message (agentId:eventType).
 *   Known eventTypes: "phase-changed", "agent-removed", "detail-updated"
 */
function handlePipelinePush(message) {
    console.log('[Pipeline] WebSocket push received:', message);

    var parts = message.split(':');
    var eventType = parts.length > 1 ? parts[parts.length - 1] : '';

    if (eventType === 'detail-updated') {
        // Only the detail panel needs refreshing; skip full-grid re-render and animations.
        if (typeof refreshDetailOnly === 'function') {
            refreshDetailOnly();
        } else {
            console.warn('[Pipeline] refreshDetailOnly() not yet available for detail-updated event.');
        }
        return;
    }

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
            } else {
                console.error('[Pipeline] refreshPipeline() still unavailable after retry. ' +
                    'Check that p:remoteCommand name="refreshPipeline" is present in the form.');
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

        // Apply the transitioning class briefly to produce a visible scale effect.
        // Cancel any previously scheduled removal to avoid stale timers overwriting new transitions.
        if (card._transitionTimer) {
            clearTimeout(card._transitionTimer);
        }
        card.classList.add('transitioning');
        card._transitionTimer = setTimeout(function () {
            card.classList.remove('transitioning');
            card._transitionTimer = null;
        }, 400);
    });

    // Update pulse indicators: all currently-active cards' status dots pulse
    var allDots = document.querySelectorAll('.status-dot');
    allDots.forEach(function (dot) {
        dot.classList.remove('pulse-indicator');
    });

    var activeDots = document.querySelectorAll('.agent-card.active .status-dot');
    activeDots.forEach(function (dot) {
        dot.classList.add('pulse-indicator');
    });
}
