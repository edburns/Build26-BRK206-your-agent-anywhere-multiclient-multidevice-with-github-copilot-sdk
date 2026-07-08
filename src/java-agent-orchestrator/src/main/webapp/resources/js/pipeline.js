/* pipeline.js — placeholder; animation and FLIP logic added in issue 3.6 */

function handlePipelinePush(message) {
    console.log('[Pipeline] WebSocket push received:', message);
    refreshPipeline();
}
