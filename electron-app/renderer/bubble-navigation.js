/**
 * Bubble Navigation — Enter/exit bubble space, enter/back button handlers.
 * Extracted from index.html inline script.
 *
 * Dependencies:
 *   window.multiverseApp (multiverse.js)
 *   window.UniverseCanvas (universe_canvas.js)
 *   window.vibemind.enterBubble / exitBubble (preload IPC)
 *
 * Shared state via window globals:
 *   window.spaceCanvas — UniverseCanvas instance
 *   window.isEnteringBubble — race condition flag
 *   window.pendingBubbleContent — content from entered_bubble arriving during animation
 */
(function() {
    'use strict';

    var enterBtn = document.getElementById('enter-btn');
    var backBtn = document.getElementById('back-btn');
    var spaceView = document.getElementById('space-view');
    var canvasContainer = document.getElementById('canvas-container');

    // Shared state (accessible from message handler in index.html)
    window.spaceCanvas = null;
    window.isEnteringBubble = false;
    window.pendingBubbleContent = null;

    if (enterBtn) {
        enterBtn.onclick = function() {
            // Use tooltip bubble ID (hovered) first, then fall back to selected
            var tooltipId = window.multiverseApp ? window.multiverseApp.getTooltipBubbleId() : null;
            var selectedId = window.multiverseApp ? window.multiverseApp.getSelectedBubbleId() : null;
            var bubbleId = tooltipId || selectedId;
            console.log('[Enter Button] Clicked, tooltipId:', tooltipId, 'selectedId:', selectedId, 'using:', bubbleId);
            if (bubbleId !== null && bubbleId !== undefined) {
                console.log('[Enter Button] Entering bubble:', bubbleId);
                window.vibemind.enterBubble(bubbleId);
                enterSpace(bubbleId);
            } else {
                console.warn('[Enter Button] No bubble in tooltip or selected!');
            }
        };
    }

    if (backBtn) {
        backBtn.onclick = function() { exitSpace(); };
    }

    function enterSpace(bubbleId) {
        try {
            // Set flag to prevent entered_bubble handler from duplicating work
            window.isEnteringBubble = true;
            window.pendingBubbleContent = null;  // Clear any old pending content

            // Hide bubble hover tooltip and reset multiverse state.
            // info-panel, bubble-info, and enter-btn are independently
            // hidden-able — hide all three so no part of the card lingers.
            var infoPanel = document.getElementById('info-panel');
            var bubbleInfo = document.getElementById('bubble-info');
            var enterBtnEl = document.getElementById('enter-btn');
            if (infoPanel) infoPanel.classList.add('hidden');
            if (bubbleInfo) bubbleInfo.classList.add('hidden');
            if (enterBtnEl) enterBtnEl.classList.add('hidden');
            if (window.multiverseApp) {
                window.multiverseApp.tooltipPinned = false;
                window.multiverseApp.hoveredBubbleIndex = -1;
                window.multiverseApp.selectedBubbleIndex = -1;
            }

            var bubble = window.multiverseApp ? window.multiverseApp.getBubbleById(bubbleId) : null;
            var bubbleTitle = (bubble && bubble.userData && (bubble.userData.title || bubble.userData.data && bubble.userData.data.title))
                || (bubble && bubble.title)
                || 'Space';
            document.getElementById('space-title').textContent = bubbleTitle;
            // Show space name in titlebar
            var titlebarSpace = document.getElementById('titlebar-space');
            if (titlebarSpace) titlebarSpace.textContent = '\u203A ' + bubbleTitle;

            // Get bubble index for animation
            var bubbleIndex = window.multiverseApp ? window.multiverseApp.getBubbleIndexById(bubbleId) : undefined;

            // Phase 11.U.L — notify eval-panel which bubble we're entering
            // so the right-edge toggle becomes visible and reflects the
            // cached score for THIS bubble (not the last globally evaluated).
            // We pass BOTH the local int-id and the DB-UUID — the eval cache
            // is keyed by UUID (because that's what mirofish_result emits).
            if (typeof window.onEvalBubbleEnter === 'function') {
                try {
                    var dbId = (bubble && bubble.userData && bubble.userData.db_id) || null;
                    window.onEvalBubbleEnter(dbId || bubbleId, { localId: bubbleId, dbId: dbId });
                } catch (e) { /* non-fatal */ }
            }

            if (window.multiverseApp && bubbleIndex !== undefined && bubbleIndex >= 0) {
                // Use animated entry
                console.log('[Enter] Starting animated entry to bubble:', bubbleId);
                window.multiverseApp.enterBubbleWithAnimation(bubbleIndex, function() {
                    // After animation: switch views
                    canvasContainer.classList.add('hidden');
                    spaceView.classList.remove('hidden');

                    if (!window.spaceCanvas) {
                        window.spaceCanvas = new UniverseCanvas('space-canvas');
                    }

                    // Load pending content if Python sent it during animation
                    if (window.pendingBubbleContent) {
                        console.log('[Enter] Loading pending content:', window.pendingBubbleContent.content ? window.pendingBubbleContent.content.length : 0, 'nodes');
                        window.spaceCanvas.loadNodes(window.pendingBubbleContent.content, window.pendingBubbleContent.edges || []);
                        window.pendingBubbleContent = null;
                    } else {
                        window.spaceCanvas.loadBubble(bubbleId);
                    }

                    // Clear flag after view switch complete
                    window.isEnteringBubble = false;

                    // Hide overlay after view switch
                    setTimeout(function() {
                        var overlay = document.getElementById('transition-overlay');
                        if (overlay) overlay.classList.remove('active');
                    }, 100);
                });
            } else {
                // Fallback: immediate switch (no animation)
                console.log('[Enter] Fallback immediate entry to bubble:', bubbleId);
                canvasContainer.classList.add('hidden');
                spaceView.classList.remove('hidden');

                if (!window.spaceCanvas) {
                    window.spaceCanvas = new UniverseCanvas('space-canvas');
                }

                // Load pending content if available
                if (window.pendingBubbleContent) {
                    window.spaceCanvas.loadNodes(window.pendingBubbleContent.content, window.pendingBubbleContent.edges || []);
                    window.pendingBubbleContent = null;
                } else {
                    window.spaceCanvas.loadBubble(bubbleId);
                }

                // Clear flag
                window.isEnteringBubble = false;
            }
        } catch(e) {
            console.error('[Enter] Error:', e);
            window.isEnteringBubble = false;
        }
    }

    function exitSpace(fromPython) {
        fromPython = fromPython || false;
        try {
            console.log('[Exit] Starting exit from bubble (fromPython=' + fromPython + ')');
            console.trace('[Exit] Call stack:');

            // Phase 11.U.L — hide eval toggle & panel when leaving bubble
            if (typeof window.onEvalBubbleExit === 'function') {
                try { window.onEvalBubbleExit(); } catch (e) { /* non-fatal */ }
            }

            // Clear space name from titlebar
            var titlebarSpace = document.getElementById('titlebar-space');
            if (titlebarSpace) titlebarSpace.textContent = '';

            // Show transition overlay
            var overlay = document.getElementById('transition-overlay');
            if (overlay) overlay.classList.add('active');

            // Clear canvas
            if (window.spaceCanvas) {
                window.spaceCanvas.clear();
            }

            // Switch views
            spaceView.classList.add('hidden');
            canvasContainer.classList.remove('hidden');

            // Notify backend ONLY if exit was initiated from UI (not from Python)
            if (!fromPython) {
                try {
                    if (window.vibemind && window.vibemind.exitBubble) {
                        window.vibemind.exitBubble();
                    }
                } catch(e) { /* ignore IPC errors */ }
            }

            // Trigger resize and animation in next frame (minimal delay)
            requestAnimationFrame(function() {
                window.dispatchEvent(new Event('resize'));
                if (window.multiverseApp) {
                    window.multiverseApp.exitBubbleWithAnimation(function() {
                        console.log('[Exit] Animation complete');
                    });
                } else {
                    // No animation, just hide overlay
                    if (overlay) overlay.classList.remove('active');
                }
            });
        } catch(e) {
            console.error('[Exit] Error:', e);
        }
    }

    // Public API
    window.bubbleNavigation = {
        enterSpace: enterSpace,
        exitSpace: exitSpace
    };
})();
