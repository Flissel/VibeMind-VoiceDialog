'use strict';
/**
 * Links in cards open in the system's default browser, never inside the app, and only http/https.
 * Main process side (main.js, ipc 'app:open-external'); card-view.js checks the same in the renderer.
 */

const MAX_LENGTH = 2048;

/** The address as it may be opened, or null. */
function safeUrl(value) {
    if (typeof value !== 'string') return null;
    const text = value.trim();
    if (!text || text.length > MAX_LENGTH || /[\s\u0000-\u001f]/.test(text)) return null;
    let url;
    try { url = new URL(text); } catch (_) { return null; }
    if (url.protocol !== 'http:' && url.protocol !== 'https:') return null;
    if (!url.hostname) return null;
    if (url.username || url.password) return null;
    return url.href;
}

/** @param {{openExternal: (url: string) => Promise<void>}} shell */
async function openExternal(shell, value) {
    const url = safeUrl(value);
    if (!url) return { success: false, error: 'only http and https addresses are opened' };
    try {
        await shell.openExternal(url);
        return { success: true };
    } catch (_) {
        return { success: false, error: 'the browser did not open' };
    }
}

module.exports = { safeUrl, openExternal };
