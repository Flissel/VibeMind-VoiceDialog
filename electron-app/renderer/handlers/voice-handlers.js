/**
 * Voice Handlers — voice_status, voice_started, voice_stopped, voice_error.
 * Extracted from index.html message handler.
 *
 * Dependencies: window.voiceController (voice-controller.js)
 */
(function() {
    'use strict';
    var H = window._messageHandlers = window._messageHandlers || {};

    H['voice_status'] = function(msg) {
        var vc = window.voiceController;
        if (!vc) return;
        vc.indicator.className = 'connecting';
        vc.statusEl.textContent = msg.message || 'Verbinde...';
        vc.btn.textContent = 'Verbinde...';
    };

    H['voice_started'] = function(msg) {
        var vc = window.voiceController;
        if (!vc) return;
        vc.setActive(true);
        vc.setConnecting(false);
        vc.clearTimer();
        vc.indicator.className = 'active';
        vc.statusEl.textContent = 'Voice: Listening...';
        vc.btn.textContent = 'Stop Voice';
        vc.btn.style.opacity = '1';
    };

    H['voice_stopped'] = function(msg) {
        var vc = window.voiceController;
        if (!vc) return;
        vc.setActive(false);
        vc.setConnecting(false);
        vc.clearTimer();
        vc.indicator.className = 'inactive';
        vc.statusEl.textContent = 'Voice: Inactive';
        vc.btn.textContent = 'Start Voice';
        vc.btn.style.opacity = '1';
    };

    H['voice_error'] = function(msg) {
        var vc = window.voiceController;
        if (!vc) return;
        vc.setActive(false);
        vc.setConnecting(false);
        vc.clearTimer();
        vc.indicator.className = 'inactive';
        vc.statusEl.textContent = 'Voice: Error';
        vc.btn.textContent = 'Start Voice';
        vc.btn.style.opacity = '1';
    };
})();
