/**
 * Bubble Handlers — bubble CRUD, listing, transcripts, enter/exit bubble.
 * Extracted from index.html message handler.
 */
(function() {
    'use strict';
    var H = window._messageHandlers = window._messageHandlers || {};

    H['bubble_created'] = function(msg) {
        if (window.multiverseApp && msg.bubble) {
            var b = msg.bubble;
            var angle = Math.random() * Math.PI * 2;
            var radius = 2 + Math.random() * 2;
            var bubbleData = {
                id: b.id,
                db_id: b.id,
                title: b.title,
                color: { r: 0.3 + Math.random() * 0.4, g: 0.5 + Math.random() * 0.3, b: 0.8 + Math.random() * 0.2 },
                position: {
                    x: Math.cos(angle) * radius,
                    y: -0.5 + Math.random() * 1,
                    z: Math.sin(angle) * radius
                },
                radius: 0.6 + Math.random() * 0.3
            };
            window.multiverseApp.addBubble(bubbleData);
            console.log('[UI] Added new bubble:', b.title, 'id:', b.id);
        }
    };

    H['bubble_updated'] = function(msg) {
        if (window.multiverseApp && msg.bubble) {
            var b = msg.bubble;
            window.multiverseApp.updateBubble(b.id, { title: b.title });
            console.log('[UI] Updated bubble:', b.old_title, '->', b.title);
            window.showTranscript('System', 'Space umbenannt: "' + b.old_title + '" -> "' + b.title + '"');

            var spaceTitle = document.getElementById('space-title');
            if (spaceTitle && spaceTitle.textContent === b.old_title) {
                spaceTitle.textContent = b.title;
            }
        }
    };

    H['bubbles_listed'] = function(msg) {
        if (window.multiverseApp && msg.bubbles) {
            console.log('[UI] Bubbles listed with indices:', msg.bubbles.length);
            msg.bubbles.forEach(function(b) {
                window.multiverseApp.updateBubble(b.id, {
                    numbered_title: b.index + '. ' + b.title,
                    voice_index: b.index
                });
            });
            var indexList = msg.bubbles.slice(0, 5).map(function(b) { return b.index + '. ' + b.title; }).join(', ');
            window.showTranscript('System', 'Spaces: ' + indexList + (msg.total > 5 ? '...' : '') + ' - Sag "geh in [Nummer]" zum Navigieren.');
        }
    };

    H['ideas_listed'] = function(msg) {
        if (msg.ideas && msg.bubble_id) {
            console.log('[UI] Ideas listed with indices:', msg.ideas.length, 'in bubble', msg.bubble_id);
            window.currentIdeaIndices = msg.ideas;
            if (window.universeCanvas && window.universeCanvas.updateNodeIndices) {
                window.universeCanvas.updateNodeIndices(msg.ideas);
            }
            var indexList = msg.ideas.slice(0, 5).map(function(i) { return i.index + '. ' + i.title; }).join(', ');
            window.showTranscript('System', 'Ideen: ' + indexList + (msg.total > 5 ? '...' : '') + ' - Nutze Nummern: "verbinde 1 und 2"');
        }
    };

    H['user_transcript'] = function(msg) {
        window.showTranscript('You', msg.text);
    };

    H['agent_response'] = function(msg) {
        window.showTranscript('Agent', msg.text);
    };

    H['navigate_to_bubble'] = function(msg) {
        if (window.multiverseApp) {
            window.multiverseApp.focusBubble(msg.bubble_id);
        }
    };

    H['enter_bubble'] = function(msg) {
        window.bubbleNavigation.enterSpace(msg.bubble_id);
    };

    H['exit_bubble'] = function(msg) {
        console.log('[Python] Received exit_bubble message');
        window.bubbleNavigation.exitSpace();
    };
})();
