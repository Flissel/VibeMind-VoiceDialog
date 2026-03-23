/**
 * Shuttle Handlers — shuttle_launched, batch_progress, shuttle_complete, sync, stage updates.
 * Extracted from index.html message handler.
 *
 * Dependencies: window.multiverseApp.shuttleManager
 */
(function() {
    'use strict';
    var H = window._messageHandlers = window._messageHandlers || {};

    H['shuttle_launched'] = function(msg) {
        console.log('[Shuttle] Launched:', msg);
        if (window.multiverseApp && window.multiverseApp.shuttleManager) {
            window.multiverseApp.shuttleManager.createShuttle({
                id: msg.shuttle_id || 'shuttle-' + Date.now(),
                bubbleName: msg.bubble_name,
                bubbleId: msg.bubble_id,
                startPosition: msg.start_position,
                totalRequirements: msg.total_requirements,
                batchCount: msg.batch_count
            });
        }
        window.showTranscript('System', 'Shuttle launched: ' + msg.total_requirements + ' requirements from "' + msg.bubble_name + '"');
    };

    H['batch_progress'] = function(msg) {
        console.log('[Shuttle] Batch progress:', msg);
        if (window.multiverseApp && window.multiverseApp.shuttleManager) {
            window.multiverseApp.shuttleManager.updateBatchProgress(
                msg.shuttle_id,
                msg.batch_index,
                msg.results
            );
        }
    };

    H['shuttle_complete'] = function(msg) {
        console.log('[Shuttle] Complete:', msg);
        if (window.multiverseApp && window.multiverseApp.shuttleManager) {
            window.multiverseApp.shuttleManager.updateShuttleComplete(
                msg.shuttle_id,
                { score: msg.score, passed: msg.passed, failed: msg.failed }
            );
        }
        window.showTranscript('System', 'Shuttle complete: Score ' + (msg.score * 100).toFixed(0) + '% (' + msg.passed + ' passed, ' + msg.failed + ' need work)');
    };

    H['shuttles_sync'] = function(msg) {
        console.log('[Shuttle] Restoring', (msg.shuttles ? msg.shuttles.length : 0), 'shuttles from database');
        if (window.multiverseApp && window.multiverseApp.shuttleManager) {
            (msg.shuttles || []).forEach(function(s) {
                window.multiverseApp.shuttleManager.createShuttle({
                    id: s.shuttle_id,
                    bubbleName: s.bubble_name,
                    bubbleId: s.bubble_id,
                    startPosition: s.start_position,
                    totalRequirements: s.total_count,
                    batchCount: 4,
                    score: s.score,
                    passed: s.passed_count,
                    failed: s.failed_count,
                    status: s.status,
                    currentStage: s.current_stage || 'mining'
                });
            });
        }
    };

    H['shuttle_stage_update'] = function(msg) {
        console.log('[Shuttle] Stage update:', msg.shuttle_id, '->', msg.stage);
        if (window.multiverseApp && window.multiverseApp.shuttleManager) {
            window.multiverseApp.shuttleManager.updateShuttleStage(msg.shuttle_id, msg.stage);
            var stageNames = {
                'mining': '\u26CF\uFE0F Mining',
                'requirements': '\uD83D\uDCC4 Requirements',
                'validation': '\u2713 Validation',
                'knowledge_graph': '\u2733\uFE0F Knowledge Graph',
                'techstack': '\uD83D\uDE80 TechStack'
            };
            var stageName = stageNames[msg.stage] || msg.stage;
            window.showTranscript('System', 'Shuttle: ' + stageName + ' stage');
        }
    };

    H['shuttle_synced'] = function(msg) {
        console.log('[Shuttle] Synced from orchestrator:', msg);
        if (window.multiverseApp && window.multiverseApp.shuttleManager) {
            var existing = window.multiverseApp.shuttleManager.getShuttle(msg.shuttle_id);
            if (existing) {
                window.multiverseApp.shuttleManager.updateShuttleStage(msg.shuttle_id, msg.current_stage);
            } else {
                window.multiverseApp.shuttleManager.createShuttle({
                    id: msg.shuttle_id,
                    bubbleName: msg.bubble_name,
                    bubbleId: msg.bubble_id,
                    totalRequirements: msg.total,
                    batchCount: 4,
                    score: msg.score,
                    passed: msg.passed,
                    failed: msg.failed,
                    status: msg.score >= 0.7 ? 'arrived' : 'in_transit',
                    currentStage: msg.current_stage
                });
            }
        }
        var progressPct = Math.round((msg.progress || 0.2) * 100);
        window.showTranscript('System', 'Shuttle synced: "' + msg.bubble_name + '" at ' + progressPct + '% (' + msg.current_stage + ')');
    };

    H['stage_shuttle_created'] = function(msg) {
        console.log('[Shuttle] Stage shuttle created:', msg.stage_type, 'for', msg.bubble_name);
        if (window.multiverseApp && window.multiverseApp.shuttleManager) {
            window.multiverseApp.shuttleManager.createStageShuttle({
                shuttle_id: msg.shuttle_id,
                bubble_id: msg.bubble_id,
                bubble_name: msg.bubble_name,
                stage_type: msg.stage_type,
                stage_data: msg.stage_data
            });

            var stageIcons = {
                'mining': '\uD83C\uDFED',
                'validation': '\u2696\uFE0F',
                'knowledge_graph': '\uD83D\uDD17',
                'techstack': '\uD83D\uDCC1'
            };
            var stageNames = {
                'mining': 'Mining',
                'validation': 'Validation',
                'knowledge_graph': 'Knowledge Graph',
                'techstack': 'TechStack'
            };
            var icon = stageIcons[msg.stage_type] || '\uD83D\uDE80';
            var stageName = stageNames[msg.stage_type] || msg.stage_type;

            var info = '';
            if (msg.stage_type === 'mining') {
                info = (msg.total || 0) + ' requirements';
            } else if (msg.stage_type === 'validation') {
                info = (msg.passed || 0) + '/' + ((msg.passed || 0) + (msg.failed || 0)) + ' passed';
            } else if (msg.stage_type === 'knowledge_graph') {
                info = (msg.entities || 0) + ' entities';
            } else if (msg.stage_type === 'techstack') {
                info = msg.recommended_stack || 'analyzing...';
            }

            window.showTranscript('System', icon + ' ' + stageName + ' shuttle: ' + msg.bubble_name + ' (' + info + ')');
        }
    };
})();
