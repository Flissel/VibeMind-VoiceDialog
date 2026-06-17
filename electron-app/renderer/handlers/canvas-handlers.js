/**
 * Canvas Handlers — entered_bubble, node/edge CRUD, tool messages, summaries, whitepaper.
 * Extracted from index.html message handler.
 *
 * Dependencies: window.spaceCanvas, window.multiverseApp, window.summariesPanel, window.whitepaperPanel
 */
(function() {
    'use strict';
    var H = window._messageHandlers = window._messageHandlers || {};

    H['entered_bubble'] = function(msg) {
        // Hide bubble tooltip
        var ipanel = document.getElementById('info-panel');
        if (ipanel) ipanel.classList.add('hidden');
        if (window.multiverseApp) {
            window.multiverseApp.tooltipPinned = false;
            window.multiverseApp.hoveredBubbleIndex = -1;
        }

        // If enterSpace() already started the transition, store content for later
        if (window.isEnteringBubble) {
            console.log('[Python] entered_bubble - storing content for enterSpace() to load:', msg.content ? msg.content.length : 0, 'nodes');
            if (msg.content) {
                window.pendingBubbleContent = {
                    content: msg.content,
                    edges: msg.edges || []
                };
            }
            return;
        }

        var spaceView = document.getElementById('space-view');
        var canvasContainer = document.getElementById('canvas-container');

        // Phase 11.U.J — Top-level guard. A view-switch into the bubble is
        // ONLY legitimate for a USER-initiated navigation. enterSpace()
        // (bubble-navigation.js, the Enter button / double-click / voice)
        // sets window.isEnteringBubble=true and the early-return at the top
        // of this handler already covers that path (it stores pending
        // content and returns). So if we reach here with space-view HIDDEN
        // and isEnteringBubble FALSE, this `entered_bubble` is an
        // AUTOMATIC re-enter (e.g. a stray refresh()/enterBubble() round
        // trip after a Brain mutation) — exactly the auto-navigation the
        // user wants gone. Do NOT switch views; the bubble's data will be
        // picked up in-place via Supabase-Realtime or on the next genuine
        // enter. Stash content so a later real enter is instant.
        if (spaceView.classList.contains('hidden') && !window.isEnteringBubble) {
            console.log('[Python] entered_bubble at TOP-LEVEL without user intent — NOT navigating (auto re-enter suppressed)');
            if (msg.content) {
                window.pendingBubbleContent = { content: msg.content, edges: msg.edges || [] };
            }
            return;
        }

        // First switch views if not already in space view
        if (spaceView.classList.contains('hidden')) {
            console.log('[Python] entered_bubble - switching to space view');
            var bubbleTitle = msg.bubble_title || 'Space';
            document.getElementById('space-title').textContent = bubbleTitle;
            var tbSpace = document.getElementById('titlebar-space');
            if (tbSpace) tbSpace.textContent = '\u203A ' + bubbleTitle;

            var bubbleIndex = window.multiverseApp ? window.multiverseApp.getBubbleIndexById(msg.bubble_id) : undefined;

            if (window.multiverseApp && bubbleIndex !== undefined && bubbleIndex >= 0) {
                window.multiverseApp.enterBubbleWithAnimation(bubbleIndex, function() {
                    canvasContainer.classList.add('hidden');
                    spaceView.classList.remove('hidden');

                    if (!window.spaceCanvas) {
                        window.spaceCanvas = new UniverseCanvas('space-canvas');
                    }
                    if (msg.content) {
                        window.spaceCanvas.loadNodes(msg.content, msg.edges || []);
                    }

                    setTimeout(function() {
                        var overlay = document.getElementById('transition-overlay');
                        if (overlay) overlay.classList.remove('active');
                    }, 100);
                });
            } else {
                canvasContainer.classList.add('hidden');
                spaceView.classList.remove('hidden');

                if (!window.spaceCanvas) {
                    window.spaceCanvas = new UniverseCanvas('space-canvas');
                }
                if (msg.content) {
                    window.spaceCanvas.loadNodes(msg.content, msg.edges || []);
                }
            }
        } else {
            if (window.spaceCanvas && msg.content) {
                window.spaceCanvas.loadNodes(msg.content, msg.edges || []);
            }
        }
    };

    H['node_added'] = function(msg) {
        // If it's a top-level bubble, add to 3D Multiverse
        if (msg.node && msg.node.node_type === 'bubble' && window.multiverseApp) {
            window.multiverseApp.addBubbleTo3D(msg.node);
        }
        // Also forward to space canvas (for inside-bubble view)
        if (window.spaceCanvas) window.spaceCanvas.onNodeAdded(msg.node);
    };

    H['node_updated'] = function(msg) {
        if (window.spaceCanvas) window.spaceCanvas.onNodeUpdated(msg.node_id, msg.updates);
    };

    H['node_deleted'] = function(msg) {
        if (window.spaceCanvas) window.spaceCanvas.onNodeDeleted(msg.node_id);
    };

    H['edge_added'] = function(msg) {
        if (window.spaceCanvas && msg.edge) {
            window.spaceCanvas.onEdgeAdded(msg.edge);
            window.showTranscript('System', 'Linked ideas together');
        }
    };

    H['exited_bubble'] = function(msg) {
        console.log('[Python] Received exited_bubble message');
        window.bubbleNavigation.exitSpace(true);
    };

    // Tool-initiated messages
    H['agent_switching'] = function(msg) {
        console.log('[Agent] Switching to:', msg.bubble_title);
        window.showTranscript('System', 'Switching to ' + msg.bubble_title + '...');
    };

    H['tool_add_node'] = function(msg) {
        console.log('[Tool] Add node to bubble:', msg.bubble_name || msg.bubble_id);
        if (window.spaceCanvas && msg.node) window.spaceCanvas.onNodeAdded(msg.node);
    };

    H['tool_update_node'] = function(msg) {
        console.log('[Tool] Update node:', msg.node_id);
        if (window.spaceCanvas && msg.updates) window.spaceCanvas.onNodeUpdated(msg.node_id, msg.updates);
    };

    H['tool_delete_node'] = function(msg) {
        console.log('[Tool] Delete node:', msg.node_id);
        if (window.spaceCanvas) window.spaceCanvas.onNodeDeleted(msg.node_id);
    };

    H['node_structured_update'] = function(msg) {
        var structuredContent = msg.content || msg.structured_content;
        console.log('[Tool] Structured content update:', msg.node_id, structuredContent);
        if (window.spaceCanvas && msg.node_id && structuredContent) {
            window.spaceCanvas.onNodeStructuredUpdate(msg.node_id, structuredContent);
        }
    };

    H['bubble_scored'] = function(msg) {
        console.log('[Tool] Bubble scored:', msg.bubble_id, 'Score:', msg.score);
        window.showTranscript('System', 'Scored ' + msg.score + '/100');
    };

    H['bubble_promoted'] = function(msg) {
        console.log('[Tool] Bubble promoted:', msg.bubble_id, '->', msg.project_name);
        window.showTranscript('System', 'Promoted to project: ' + msg.project_name);
    };

    H['bubble_deleted'] = function(msg) {
        console.log('[Tool] Bubble deleted:', msg.bubble_id, 'title:', msg.title);
        if (window.multiverseApp) {
            var removed = window.multiverseApp.removeBubble(msg.bubble_id);
            if (!removed && msg.title) {
                console.log('[Tool] Trying to remove by title:', msg.title);
                removed = window.multiverseApp.removeBubble(msg.title);
            }
            if (!removed) {
                console.warn('[Tool] Could not find bubble to remove:', msg.bubble_id, msg.title);
            }
        }
    };

    H['canvas_refresh'] = function(msg) {
        console.log('[Tool] Canvas refresh requested');
        if (window.spaceCanvas) window.spaceCanvas.refresh();
    };

    H['idea_summarized'] = function(msg) {
        console.log('[Tool] Idea summarized:', msg);
        if (window.summariesPanel) {
            window.summariesPanel.addSummary(
                msg.idea_title || 'Untitled',
                msg.summary || '',
                msg.style || 'concise',
                msg.node_count || 0
            );
        }
    };

    H['white_paper_generated'] = function(msg) {
        console.log('[Tool] White Paper generated:', msg);
        if (window.whitepaperPanel) {
            window.whitepaperPanel.displayWhitePaper(
                msg.title || 'White Paper',
                msg.content || '',
                msg.node_count || 0,
                msg.max_depth_reached || 0
            );
        }
        window.showTranscript('System', 'White Paper "' + msg.title + '" generated with ' + msg.node_count + ' ideas');
    };
})();
