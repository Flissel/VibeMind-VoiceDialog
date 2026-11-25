/**
 * The live preview of a project: one message name per state and one field for the address.
 *
 *   project_preview_starting  { project_id }
 *   project_preview_ready     { project_id, vnc_url, port }
 *   project_preview_error     { project_id, error }
 *   project_preview_stopped   { project_id }
 *
 * Python (python/ipc/project_manager.py) and the main process send exactly these; the window
 * (index.html) reads them. A ready message without a usable address shows the sandbox screen of
 * the Coding service (noVNC on 6090), as the page on 8163 does.
 */
(function (root, factory) {
    const api = factory();
    if (typeof module === 'object' && module.exports) module.exports = api;
    else root.VibePreviewMessage = api;
}(typeof self !== 'undefined' ? self : this, function () {
    'use strict';

    const DEFAULT_VNC_URL = 'http://localhost:6090/vnc.html?autoconnect=true&resize=scale&reconnect=true';
    const TYPES = Object.freeze({
        starting: 'project_preview_starting',
        ready: 'project_preview_ready',
        error: 'project_preview_error',
        stopped: 'project_preview_stopped',
    });

    function httpUrl(value) {
        if (typeof value !== 'string' || !value.trim()) return '';
        try {
            const url = new URL(value.trim());
            return url.protocol === 'http:' || url.protocol === 'https:' ? url.href : '';
        } catch (_) {
            return '';
        }
    }

    /** What the preview panel shows for a ready message. */
    function previewOf(message) {
        const m = message && typeof message === 'object' ? message : {};
        return {
            url: httpUrl(m.vnc_url) || DEFAULT_VNC_URL,
            title: typeof m.project_title === 'string' && m.project_title ? m.project_title : 'Live-Vorschau',
            projectId: typeof m.project_id === 'string' ? m.project_id : null,
        };
    }

    return { TYPES, DEFAULT_VNC_URL, previewOf };
}));
