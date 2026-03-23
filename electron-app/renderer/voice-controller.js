/**
 * Voice Controller — Voice start/stop button with debounce and timeout safety.
 * Extracted from index.html inline script.
 *
 * Dependencies: window.vibemind.startVoice/stopVoice (preload IPC)
 *
 * Exposes voice DOM elements on window for voice-handlers.js:
 *   window.voiceController.{ voiceBtn, voiceIndicator, voiceStatus, state }
 */
(function() {
    'use strict';

    var voiceBtn = document.getElementById('voice-btn');
    var voiceIndicator = document.getElementById('voice-indicator');
    var voiceStatus = document.getElementById('voice-status');

    var voiceActive = false;
    var voiceConnecting = false;
    var voiceConnectTimer = null;

    if (voiceBtn) {
        voiceBtn.onclick = function() {
            if (voiceConnecting) return;
            if (voiceActive) {
                window.vibemind.stopVoice();
                voiceActive = false;
                voiceIndicator.className = 'inactive';
                voiceStatus.textContent = 'Voice: Inactive';
                voiceBtn.textContent = 'Start Voice';
            } else {
                voiceConnecting = true;
                window.vibemind.startVoice();
                voiceIndicator.className = 'connecting';
                voiceStatus.textContent = 'Verbinde... (bis zu 30s beim ersten Mal)';
                voiceBtn.textContent = 'Verbinde...';
                voiceBtn.style.opacity = '0.6';
                if (voiceConnectTimer) clearTimeout(voiceConnectTimer);
                voiceConnectTimer = setTimeout(function() {
                    if (voiceConnecting) {
                        console.warn('[Voice] Connection timeout — resetting button');
                        voiceConnecting = false;
                        voiceBtn.textContent = 'Start Voice';
                        voiceBtn.style.opacity = '1';
                        voiceIndicator.className = 'inactive';
                        voiceStatus.textContent = 'Voice: Timeout';
                    }
                }, 35000);
            }
        };
    }

    // Public API (for voice-handlers.js to update UI state)
    window.voiceController = {
        btn: voiceBtn,
        indicator: voiceIndicator,
        statusEl: voiceStatus,
        setActive: function(active) { voiceActive = active; },
        setConnecting: function(connecting) { voiceConnecting = connecting; },
        clearTimer: function() {
            if (voiceConnectTimer) { clearTimeout(voiceConnectTimer); voiceConnectTimer = null; }
        }
    };
})();
