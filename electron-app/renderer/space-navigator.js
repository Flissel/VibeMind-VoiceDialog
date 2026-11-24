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

    // The space asked for while a camera move was running. The scene starts one move at a time;
    // without this a click during a move was lost (measured 2026-11-23: of five switches 0.4 s
    // apart every second one did not arrive). The last wish wins and is carried out on arrival.
    var wanted = null;

    var wantedTimer = null;

    // Looks every 100 ms whether the running move has ended (not every move ends with an arrival
    // event: the zoom into the Desktop screen view does not). Gives up after 6 s.
    function followWanted(triesLeft) {
        clearTimeout(wantedTimer);
        wantedTimer = setTimeout(function() {
            var app = window.multiverseApp;
            if (!wanted) return;
            if (app && app.isNavigating && triesLeft > 0) { followWanted(triesLeft - 1); return; }
            var next = wanted;
            wanted = null;
            if (app && app.isNavigating) { syncSpace(app.currentSpace); return; } // still stuck: tabs back to the truth
            switchSpace(next);
        }, 100);
    }

    async function switchSpace(spaceId) {
        var app = window.multiverseApp;
        if (app && app.isNavigating) {
            wanted = spaceId;
            syncSpace(spaceId);   // the tab answers at once; the scene follows after the running move
            followWanted(60);
            return;
        }
        // The scene knows where the user is; window.currentSpace can lag behind it.
        if (spaceId === (app ? app.currentSpace : window.currentSpace)) {
            syncSpace(spaceId);
            return;
        }

        console.log('[Space] Switching to:', spaceId);

        // Navigate via MultiverseApp (visual navigation with camera animation)
        if (app) {
            // Nothing started (unknown space): the tabs must not claim the new space.
            if (app.navigateToSpace(spaceId) === false) return;
        }
        syncSpace(spaceId);

        // Also notify backend
        try {
            await window.vibemind.navigateToSpace(spaceId);
        } catch(e) {
            console.error('[Space] Navigation failed:', e);
        }
    }

    /**
     * Tabs, indicator, agent badge and panels for the space on screen. Called when a move to a
     * space starts and again when it arrives (multiverse.js _arriveAtSpace), so they are right
     * whatever started the move.
     */
    function syncSpace(spaceId) {
        window.currentSpace = spaceId;

        // Update UI tabs
        document.querySelectorAll('.space-tab').forEach(function(tab) {
            tab.classList.toggle('active', tab.dataset.space === spaceId);
        });

        // Update Nav Panel buttons
        document.querySelectorAll('.nav-space-btn').forEach(function(btn) {
            btn.classList.toggle('active', btn.dataset.space === spaceId);
        });

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

        var mvSpaceInfo = window.multiverseApp ? window.multiverseApp.getSpaceInfo(spaceId) : null;
        // The external spaces (Sales, Marketing, ...) are not in the list above; the scene knows them.
        var info = spaceInfo[spaceId] || (mvSpaceInfo ? { icon: mvSpaceInfo.icon, name: mvSpaceInfo.name } : null);
        if (info) {
            if (spaceIcon) spaceIcon.textContent = info.icon;
            if (spaceName) spaceName.textContent = info.name;
        }
        // Show the indicator when space changes
        if (spaceIndicator) spaceIndicator.classList.remove('hidden');

        // Update agent display based on space
        if (mvSpaceInfo && mvSpaceInfo.agent) {
            updateAgentDisplay(mvSpaceInfo.agent.slug, mvSpaceInfo.agent.name);
        }

        // Hide/show appropriate info panels
        var bubbleInfo = document.getElementById('bubble-info');
        var projectInfo = document.getElementById('project-info');
        if (spaceId === 'projects') {
            if (bubbleInfo) bubbleInfo.classList.add('hidden');
        } else if (spaceId === 'ideas') {
            if (projectInfo) projectInfo.classList.add('hidden');
        }
        // The pages of the spaces (Flowzen diary included) are shown and hidden by multiverse.js
        // on arrival and on leaving; doing it here as well would hide the page just shown.
    }

    /** slug: the agent's key (also its colour class); shownName: what the user reads, e.g. "Aufträge". */
    function updateAgentDisplay(agentName, shownName) {
        window.currentAgent = agentName;
        if (agentNameDisplay) {
            agentNameDisplay.textContent = displayName(agentName, shownName);
        }
        // Update indicator color based on agent
        var indicator = document.querySelector('.agent-indicator');
        if (indicator) {
            indicator.className = 'agent-indicator ' + agentName.toLowerCase();
        }
    }

    /** The name the indicator shows: the space's own name when given, else the key with a capital. */
    function displayName(slug, shownName) {
        if (typeof shownName === 'string' && shownName.trim()) return shownName.trim();
        return slug.charAt(0).toUpperCase() + slug.slice(1);
    }

    // Public API
    window.spaceNavigator = {
        switchSpace: switchSpace,
        syncSpace: syncSpace,
        updateAgentDisplay: updateAgentDisplay,
        displayName: displayName
    };
})();
