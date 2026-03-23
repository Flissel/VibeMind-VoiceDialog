/**
 * Dashboard Handlers — wizard dispatch, roarboot/rowboat status, flowzen messages.
 * Extracted from index.html message handler.
 *
 * Dependencies: window.flowzenPanel, window.multiverseApp, window.vibemind
 */
(function() {
    'use strict';
    var H = window._messageHandlers = window._messageHandlers || {};

    // Wizard messages — dispatch to shuttle-wizard.js via custom event
    var wizardTypes = ['wizard_initialized', 'wizard_state', 'wizard_step_saved', 'wizard_agent_result', 'wizard_finalized', 'wizard_suggestion_resolved'];
    wizardTypes.forEach(function(type) {
        H[type] = function(msg) {
            window.dispatchEvent(new CustomEvent('message-from-python', { detail: msg }));
        };
    });

    // Roarboot/Rowboat
    H['roarboot_status'] = function(msg) {
        if (window.multiverseApp && window.multiverseApp.updateRoarbootStatus) {
            window.multiverseApp.updateRoarbootStatus(msg.status);
        }
    };

    H['rowboat_view_status'] = function(msg) {
        if (window.multiverseApp && window.multiverseApp.updateRoarbootStatus) {
            window.multiverseApp.updateRoarbootStatus(msg.status);
        }
    };

    H['roarboot_open_webview'] = function(msg) {
        if (window.multiverseApp) {
            window.multiverseApp.navigateToSpace('roarboot');
        }
    };

    H['rowboat_update_available'] = function(msg) {
        console.log('[UI] Rowboat update available: ' + msg.current_version + ' \u2192 ' + msg.latest_version);
        var rTab = document.getElementById('tab-roarboot');
        if (rTab) {
            var nameSpan = rTab.querySelector('.space-name');
            if (nameSpan && nameSpan.textContent.indexOf('Update') === -1) {
                nameSpan.textContent = 'Rowboat \uD83D\uDD34 Update';
            }
        }
        window._rowboatUpdateInfo = msg;
    };

    H['rowboat_update_applied'] = function(msg) {
        console.log('[UI] Rowboat auto-updated: ' + msg.old_version + ' -> ' + msg.new_version);
        var rTab = document.getElementById('tab-roarboot');
        if (rTab) {
            var nameSpan = rTab.querySelector('.space-name');
            if (nameSpan) {
                nameSpan.textContent = 'Rowboat \u2705 Updated';
                setTimeout(function() { nameSpan.textContent = 'Rowboat'; }, 10000);
            }
        }
    };

    // Flowzen messages
    H['flowzen_rose_state'] = function(msg) {
        if (window.multiverseApp && window.multiverseApp.spaces.flowzen) {
            window.multiverseApp.spaces.flowzen.roseState = msg.state || 'idle';
            console.log('[Flowzen] Rose state:', msg.state);
        }
        window.flowzenPanel.updateFlowzenPanel({ state: msg.state });
        if (msg.state === 'diary_new' && msg.diary_entry) {
            window.flowzenPanel.addSingleDiaryEntry(msg.diary_entry);
        }
    };

    H['flowzen_status_result'] = function(msg) {
        window.flowzenPanel.updateFlowzenPanel(msg);
    };

    H['flowzen_recommend_result'] = function(msg) {
        if (msg.recommendation) {
            window.flowzenPanel.updateFlowzenPanel({
                mood: msg.recommendation.mood,
                category: msg.recommendation.category,
                current_time_window: msg.recommendation.time_window,
            });
        }
        if (msg.diary_entry) {
            window.flowzenPanel.addSingleDiaryEntry(msg.diary_entry);
        }
        var fzBtn = document.getElementById('fz-recommend-btn');
        if (fzBtn) { fzBtn.classList.remove('loading'); fzBtn.textContent = 'Was soll ich machen?'; }
    };

    H['flowzen_diary_entries_result'] = function(msg) {
        window.flowzenPanel.renderDiaryEntries(msg.entries || []);
    };
})();
