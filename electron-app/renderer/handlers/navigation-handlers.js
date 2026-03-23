/**
 * Navigation Handlers — agent switching, space navigation, shuttle voice nav, gestures.
 * Extracted from index.html message handler.
 *
 * Dependencies: window.multiverseApp, window.spaceNavigator, window.bubbleNavigation
 */
(function() {
    'use strict';
    var H = window._messageHandlers = window._messageHandlers || {};

    H['agent_switched'] = function(msg) {
        console.log('[Agent] Switched from', msg.from_agent, 'to', msg.to_agent);
        window.spaceNavigator.updateAgentDisplay(msg.to_agent);
        window.showTranscript('System', 'Agent switched to ' + msg.to_agent);
        if (msg.auto_navigate && msg.target_space) {
            console.log('[Agent] Auto-navigating to space:', msg.target_space);
        }
    };

    H['calibration_target'] = function(msg) {
        var calOverlay = document.getElementById('calibration-overlay');
        if (calOverlay) {
            calOverlay.classList.add('active');
            while (calOverlay.firstChild) calOverlay.removeChild(calOverlay.firstChild);
            var dot = document.createElement('div');
            dot.className = 'calibration-dot';
            dot.style.left = msg.x + 'px';
            dot.style.top = msg.y + 'px';
            calOverlay.appendChild(dot);
            var info = document.createElement('div');
            info.className = 'calibration-info';
            info.textContent = 'Kalibrierung: Punkt ' + (msg.index + 1) + '/' + msg.total;
            calOverlay.appendChild(info);
        }
    };

    H['calibration_done'] = function(msg) {
        var calOverlay = document.getElementById('calibration-overlay');
        if (calOverlay) {
            calOverlay.classList.remove('active');
            while (calOverlay.firstChild) calOverlay.removeChild(calOverlay.firstChild);
        }
    };

    H['space_changed'] = function(msg) {
        console.log('[Space] Changed to:', msg.space);
        if (msg.space !== window.currentSpace) {
            window.currentSpace = msg.space;

            document.querySelectorAll('.space-tab').forEach(function(tab) {
                tab.classList.toggle('active', tab.dataset.space === msg.space);
            });

            var spaceIcon = document.getElementById('current-space-icon');
            var spaceName = document.getElementById('current-space-name');
            var spaceConfig = {
                'ideas': { icon: '\uD83D\uDCAD', name: 'Ideas Universe' },
                'projects': { icon: '\uD83E\uDDEC', name: 'Project Space' },
                'desktop': { icon: '\uD83C\uDF1F', name: 'Desktop Automation' },
                'swedesign': { icon: '\uD83C\uDFED', name: 'SWE Design' },
                'roarboot': { icon: '\uD83D\uDEA3', name: 'Rowboat' }
            };
            var cfg = spaceConfig[msg.space] || { icon: '\u2753', name: msg.space };
            if (spaceIcon) spaceIcon.textContent = cfg.icon;
            if (spaceName) spaceName.textContent = cfg.name;

            if (window.multiverseApp) {
                console.log('[Space] Triggering animated navigation to:', msg.space);
                window.multiverseApp.navigateToSpace(msg.space);
            }

            if (msg.space === 'thebrain' && window.vibemind && window.vibemind.showBrain) {
                window.vibemind.showBrain();
                console.log('[Space] Showing Brain Dashboard');
            }

            if (msg.reason) {
                window.showTranscript('System', msg.reason);
            }
        } else {
            console.log('[Space] Already in space:', msg.space);
            if (msg.space === 'thebrain' && window.vibemind && window.vibemind.showBrain) {
                window.vibemind.showBrain();
                console.log('[Space] Showing Brain Dashboard (already in space)');
            }
        }
    };

    H['space_suggestion'] = function(msg) {
        console.log('[Space] Suggestion:', msg.suggested_space);
        window.showTranscript('System', 'Suggestion: Switch to ' + msg.suggested_space + ' space');
    };

    H['navigate_space'] = function(msg) {
        console.log('[Voice Nav] Navigate to space:', msg.space);
        if (msg.space && window.multiverseApp) {
            window.multiverseApp.navigateToSpace(msg.space);
            window.currentSpace = msg.space;
            document.querySelectorAll('.space-tab').forEach(function(tab) {
                tab.classList.toggle('active', tab.dataset.space === msg.space);
            });
        }
    };

    H['select_item'] = function(msg) {
        console.log('[Voice Nav] Select item:', msg.direction, msg.item_type);
        if (window.multiverseApp) {
            var direction = msg.direction || 1;
            if (msg.item_type === 'project' || window.currentSpace === 'projects') {
                window.multiverseApp.selectNextProject(direction);
            } else {
                window.multiverseApp.selectNextBubble(direction);
            }
        }
    };

    H['select_by_name'] = function(msg) {
        console.log('[Voice Nav] Select by name:', msg.name);
        if (window.multiverseApp && msg.name) {
            var bubbleIndex = window.multiverseApp.getBubbleIndexById(msg.name);
            if (bubbleIndex >= 0) {
                window.multiverseApp.selectBubble(bubbleIndex);
            }
        }
    };

    H['select_by_index'] = function(msg) {
        console.log('[Voice Nav] Select by index:', msg.index);
        if (window.multiverseApp && msg.index !== undefined) {
            if (window.currentSpace === 'projects') {
                window.multiverseApp.selectProject(msg.index);
            } else {
                window.multiverseApp.selectBubble(msg.index);
            }
        }
    };

    H['enter_selection'] = function(msg) {
        console.log('[Voice Nav] Enter selection');
        if (window.multiverseApp) window.multiverseApp.enterCurrentSelection();
    };

    H['exit_view'] = function(msg) {
        console.log('[Voice Nav] Exit view');
        window.bubbleNavigation.exitSpace(true);
    };

    // Shuttle voice navigation
    H['enter_shuttle'] = function(msg) {
        console.log('[Voice Nav] Enter shuttle');
        if (window.multiverseApp && window.multiverseApp.shuttleManager) {
            var selectedShuttle = window.multiverseApp.shuttleManager.getSelectedShuttle();
            if (selectedShuttle) {
                window.enterShuttleFromClick(selectedShuttle.id);
            } else {
                window.showTranscript('System', 'No shuttle selected. Say "select shuttle" first.');
            }
        }
    };

    H['enter_shuttle_by_name'] = function(msg) {
        console.log('[Voice Nav] Enter shuttle by name:', msg.name);
        if (window.multiverseApp && window.multiverseApp.shuttleManager) {
            var shuttle = window.multiverseApp.shuttleManager.findShuttleByName(msg.name);
            if (shuttle) {
                window.enterShuttleFromClick(shuttle.id);
            } else {
                window.showTranscript('System', 'Shuttle "' + msg.name + '" not found.');
            }
        }
    };

    H['exit_shuttle'] = function(msg) {
        console.log('[Voice Nav] Exit shuttle');
        if (window.multiverseApp && window.multiverseApp.shuttleManager) {
            window.multiverseApp.shuttleManager.exitCurrentShuttle();
        }
    };

    H['select_shuttle'] = function(msg) {
        console.log('[Voice Nav] Select shuttle, direction:', msg.direction);
        if (window.multiverseApp && window.multiverseApp.shuttleManager) {
            window.multiverseApp.shuttleManager.selectShuttle(msg.direction || 1);
        }
    };

    H['select_shuttle_by_name'] = function(msg) {
        console.log('[Voice Nav] Select shuttle by name:', msg.name);
        if (window.multiverseApp && window.multiverseApp.shuttleManager) {
            var shuttle = window.multiverseApp.shuttleManager.findShuttleByName(msg.name);
            if (shuttle) {
                window.multiverseApp.shuttleManager.setSelectedShuttle(shuttle.id);
                window.showTranscript('System', 'Selected shuttle: ' + shuttle.bubbleName);
            } else {
                window.showTranscript('System', 'Shuttle "' + msg.name + '" not found.');
            }
        }
    };

    H['list_shuttles'] = function(msg) {
        console.log('[Voice Nav] List shuttles');
        if (window.multiverseApp && window.multiverseApp.shuttleManager) {
            var shuttles = window.multiverseApp.shuttleManager.getShuttleList();
            if (shuttles.length > 0) {
                var names = shuttles.map(function(s) { return s.bubbleName; }).join(', ');
                window.showTranscript('System', 'Active shuttles: ' + names);
            } else {
                window.showTranscript('System', 'No active shuttles.');
            }
        }
    };

    H['shuttle_continue_to_project'] = function(msg) {
        console.log('[Voice Nav] Continue to project');
        var btn = document.getElementById('shuttle-continue-to-project');
        if (btn) btn.click();
    };

    H['hand_gesture'] = function(msg) {
        console.log('[Hand] Gesture:', msg.gesture, 'Position:', msg.position);
        if (msg.gesture === 'POINTING' && window.currentSpace === 'desktop') {
            window.showTranscript('Hand', 'Pointing at ' + Math.round((msg.position ? msg.position.x : 0) * 100) + '%, ' + Math.round((msg.position ? msg.position.y : 0) * 100) + '%');
        }
    };
})();
