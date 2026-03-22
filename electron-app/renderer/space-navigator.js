/**
 * Space Navigator — Tab handlers, switchSpace(), updateAgentDisplay().
 * Extracted from index.html inline script.
 *
 * Dependencies:
 *   window.multiverseApp (multiverse.js)
 *   window.vibemind.navigateToSpace (preload IPC)
 *   window.flowzenPanel (flowzen-panel.js)
 */
(function() {
    'use strict';

    // State shared via window globals
    window.currentSpace = 'ideas';
    window.currentAgent = 'rachel';

    var agentNameDisplay = document.getElementById('current-agent-name');

    // Helper to create tab click handler
    function makeTabHandler(tabId, spaceId, notifyBackend) {
        var tab = document.getElementById(tabId);
        if (tab) {
            tab.onclick = function() {
                switchSpace(spaceId);
                if (notifyBackend && window.vibemind && window.vibemind.navigateToSpace) {
                    try {
                        window.vibemind.navigateToSpace(spaceId);
                    } catch(e) {
                        console.error('[Space] Navigation failed:', e);
                    }
                }
            };
        }
    }

    // Space tab click handlers
    makeTabHandler('tab-ideas', 'ideas', true);
    makeTabHandler('tab-projects', 'projects', true);
    makeTabHandler('tab-desktop', 'desktop', true);
    makeTabHandler('tab-swedesign', 'swedesign', true);
    makeTabHandler('tab-roarboot', 'roarboot', true);
    makeTabHandler('tab-clawport', 'clawport', false);
    makeTabHandler('tab-agentfarm', 'agentfarm', false);
    makeTabHandler('tab-thebrain', 'thebrain', false);
    makeTabHandler('tab-flowzen', 'flowzen', false);
    makeTabHandler('tab-mirofish', 'mirofish', false);
    makeTabHandler('tab-video', 'video', false);

    async function switchSpace(spaceId) {
        if (spaceId === window.currentSpace) return;

        console.log('[Space] Switching to:', spaceId);
        window.currentSpace = spaceId;

        // Update UI tabs
        document.querySelectorAll('.space-tab').forEach(function(tab) {
            tab.classList.toggle('active', tab.dataset.space === spaceId);
        });

        // Update Nav Panel buttons
        document.querySelectorAll('.nav-space-btn').forEach(function(btn) {
            btn.classList.toggle('active', btn.dataset.space === spaceId);
        });

        // Navigate via MultiverseApp (visual navigation with camera animation)
        if (window.multiverseApp) {
            window.multiverseApp.navigateToSpace(spaceId);
        }

        // Also notify backend
        try {
            await window.vibemind.navigateToSpace(spaceId);
        } catch(e) {
            console.error('[Space] Navigation failed:', e);
        }

        // Update Space Indicator (top right)
        var spaceIndicator = document.getElementById('space-indicator');
        var spaceIcon = document.getElementById('current-space-icon');
        var spaceName = document.getElementById('current-space-name');

        var spaceInfo = {
            'ideas':      { icon: '\uD83D\uDCAD', name: 'Ideas Universe' },
            'projects':   { icon: '\uD83E\uDDEC', name: 'Project Space' },
            'desktop':    { icon: '\uD83C\uDF1F', name: 'Desktop Automation' },
            'swedesign':  { icon: '\uD83C\uDFED', name: 'SWE Design' },
            'roarboot':   { icon: '\uD83D\uDEA3', name: 'Rowboat' },
            'clawport':   { icon: '\uD83D\uDCCA', name: 'Dashboard' },
            'agentfarm':  { icon: '\uD83C\uDFE1', name: 'Agent Farm' },
            'thebrain':   { icon: '\uD83E\uDDE0', name: 'The Brain' },
            'mirofish':   { icon: '\uD83D\uDC1F', name: 'MiroFish' },
            'flowzen':    { icon: '\uD83C\uDF39', name: 'Blue Rose' },
            'video':      { icon: '\uD83C\uDFAC', name: 'Video Studio' },
        };

        var info = spaceInfo[spaceId];
        if (info) {
            if (spaceIcon) spaceIcon.textContent = info.icon;
            if (spaceName) spaceName.textContent = info.name;
        }
        // Show the indicator when space changes
        if (spaceIndicator) spaceIndicator.classList.remove('hidden');

        // Update agent display based on space
        var mvSpaceInfo = window.multiverseApp ? window.multiverseApp.getSpaceInfo(spaceId) : null;
        if (mvSpaceInfo && mvSpaceInfo.agent) {
            updateAgentDisplay(mvSpaceInfo.agent.slug);
        }

        // Hide/show appropriate info panels
        var bubbleInfo = document.getElementById('bubble-info');
        var projectInfo = document.getElementById('project-info');
        if (spaceId === 'projects') {
            if (bubbleInfo) bubbleInfo.classList.add('hidden');
        } else if (spaceId === 'ideas') {
            if (projectInfo) projectInfo.classList.add('hidden');
        }

        // Show/hide Flowzen panel
        var fzPanel = document.getElementById('flowzen-panel');
        if (fzPanel) {
            if (spaceId === 'flowzen') {
                fzPanel.classList.remove('hidden');
                if (window.flowzenPanel) {
                    window.flowzenPanel.requestFlowzenStatus();
                    window.flowzenPanel.requestFlowzenDiaryEntries();
                }
            } else {
                fzPanel.classList.add('hidden');
            }
        }
    }

    function updateAgentDisplay(agentName) {
        window.currentAgent = agentName;
        if (agentNameDisplay) {
            agentNameDisplay.textContent = agentName.charAt(0).toUpperCase() + agentName.slice(1);
        }
        // Update indicator color based on agent
        var indicator = document.querySelector('.agent-indicator');
        if (indicator) {
            indicator.className = 'agent-indicator ' + agentName.toLowerCase();
        }
    }

    // Public API
    window.spaceNavigator = {
        switchSpace: switchSpace,
        updateAgentDisplay: updateAgentDisplay
    };
})();
