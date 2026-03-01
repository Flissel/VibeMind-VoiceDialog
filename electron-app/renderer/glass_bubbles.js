/**
 * glass_bubbles.js — MultiverseApp bootstrap + Roarboot tab status
 *
 * Contains:
 *  1. updateRoarbootStatus — patched onto MultiverseApp prototype (tab dot only)
 *  2. DOMContentLoaded handler that creates MultiverseApp instance
 *
 * Note: The old RoarbootWebview class (iframe management) has been removed.
 * Roarboot Space now uses a BrowserView managed by rowboat-manager.js.
 */

// =========================================================================
// updateRoarbootStatus — patched onto MultiverseApp prototype
// =========================================================================

if (typeof MultiverseApp !== 'undefined') {
    MultiverseApp.prototype.updateRoarbootStatus = function (connectionStatus) {
        const tab = document.getElementById('tab-roarboot');

        const statusMap = {
            'connected':    { dot: '\u{1F7E2}' },  // green
            'ready':        { dot: '\u{1F7E2}' },  // green (BrowserView loaded)
            'starting':     { dot: '\u{1F7E1}' },  // yellow
            'restarting':   { dot: '\u{1F7E1}' },  // yellow
            'disconnected': { dot: '\u{1F534}' },  // red
            'error':        { dot: '\u{1F534}' },  // red
        };
        const info = statusMap[connectionStatus] || { dot: '\u26AA' };

        if (tab) {
            const nameSpan = tab.querySelector('.space-name');
            if (nameSpan) {
                nameSpan.textContent = `Rowboat ${info.dot}`;
            }
        }

        this._roarbootConnected = (connectionStatus === 'connected' || connectionStatus === 'ready');
        console.log(`[MultiverseApp] Roarboot status: ${connectionStatus}`);
    };
}

// =========================================================================
// Bootstrap — create MultiverseApp instance
// =========================================================================

document.addEventListener('DOMContentLoaded', () => {
    const container = document.getElementById('canvas-container');
    if (!container || typeof MultiverseApp === 'undefined') {
        console.error('[glass_bubbles] Cannot bootstrap: container or MultiverseApp missing');
        return;
    }

    // Create the app (class from multiverse.js)
    const app = new MultiverseApp('canvas-container');
    window.multiverseApp = app;

    // Request bubbles from DB now that multiverseApp exists
    if (window.vibemind?.requestBubbles) {
        window.vibemind.requestBubbles();
    }

    console.log('[glass_bubbles] MultiverseApp bootstrapped');
});
