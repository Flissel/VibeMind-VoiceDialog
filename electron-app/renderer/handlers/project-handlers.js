/**
 * Project Handlers — bubbles_sync, projects_sync, project CRUD, VNC preview messages.
 * Extracted from index.html message handler.
 */
(function() {
    'use strict';
    var H = window._messageHandlers = window._messageHandlers || {};

    H['bubbles_sync'] = function(msg) {
        if (window.multiverseApp && msg.bubbles) {
            window.multiverseApp.syncBubbles(msg.bubbles);
            console.log('[UI] Bubbles synced, now requesting shuttles...');
            setTimeout(function() {
                window.vibemind.requestShuttles();
            }, 100);
        }
    };

    H['projects_sync'] = function(msg) {
        if (window.multiverseApp && msg.projects) {
            window.multiverseApp.syncProjects(msg.projects);
        }
    };

    H['generated_projects_list'] = function(msg) {
        if (window.multiverseApp && msg.projects) {
            console.log('[UI] Got generated projects:', msg.projects.length);
            window.multiverseApp.syncProjects(msg.projects);
        }
    };

    H['project_created'] = function(msg) {
        console.log('[UI] Project created:', msg.project);
        if (msg.success && msg.project) {
            var projectName = msg.project.name || 'New Project';
            var score = msg.project.score ? ' (score: ' + (msg.project.score * 100).toFixed(0) + '%)' : '';
            window.showTranscript('System', '\u2705 Project created: ' + projectName + score);
            if (window.vibemind && window.vibemind.sendToPython) {
                window.vibemind.sendToPython({ type: 'get_generated_projects' });
            }
        } else if (!msg.success) {
            window.showTranscript('System', '\u274C Failed to create project: ' + (msg.error || 'Unknown error'));
        }
    };

    H['project_updated'] = function(msg) {
        console.log('[UI] Project updated:', msg.project_id);
        if (window.multiverseApp && msg.projects) {
            window.multiverseApp.syncProjects(msg.projects);
        }
    };

    H['project_deleted'] = function(msg) {
        console.log('[UI] Project deleted:', msg.project_id);
        if (window.multiverseApp && msg.projects) {
            window.multiverseApp.syncProjects(msg.projects);
        }
    };

    H['enter_project'] = function(msg) {
        console.log('[UI] Enter project:', msg.project_id);
    };

    H['project_issue_detected'] = function(msg) {
        if (msg.issue) {
            var severity = msg.issue.severity || 'medium';
            var issueIcon = severity === 'critical' ? '\uD83D\uDD34' :
                            severity === 'high' ? '\uD83D\uDFE0' : '\uD83D\uDFE1';
            var issueTitle = msg.issue.title || 'Issue detected';
            var issueCategory = msg.issue.category ? ' [' + msg.issue.category + ']' : '';
            window.showTranscript('Quality', issueIcon + ' ' + issueTitle + issueCategory);
            console.log('[UI] Issue detected:', severity, issueTitle);
        }
    };

    H['project_quality_update'] = function(msg) {
        if (msg.summary) {
            var total = msg.summary.total_issues || 0;
            var bySev = msg.summary.by_severity || {};
            var critical = bySev.critical || 0;
            var high = bySev.high || 0;
            var medium = bySev.medium || 0;
            var low = bySev.low || 0;
            var autoFixed = msg.summary.auto_fixed || 0;
            var qualityMsg = '\uD83D\uDCCA Quality: ' + total + ' issues (' + critical + ' critical, ' + high + ' high, ' + medium + ' medium, ' + low + ' low) \u2014 ' + autoFixed + ' auto-fixed';
            window.showTranscript('Quality', qualityMsg);
            console.log('[UI] Quality update:', msg.summary);
        }
    };

    // VNC Preview messages
    H['project-preview_starting'] = function(msg) {
        console.log('[UI] Project preview starting:', msg.project_id);
        window.vncPreview.showVncLoading(true, msg.project_title || 'Project');
        window.vncPreview.updateVncLoadingDetails('Starting sandbox container...');
    };

    H['project-preview-ready'] = function(msg) {
        console.log('[UI] Project preview ready:', msg.vnc_url);
        window.vncPreview.showVncPreview(msg.vnc_url, msg.project_title, msg.project_id);
        window.showTranscript('System', 'Live Preview ready for ' + (msg.project_title || 'project'));
    };

    H['project-preview-error'] = function(msg) {
        console.error('[UI] Project preview error:', msg.error);
        window.vncPreview.hideVncPreview();
        window.showTranscript('System', 'Preview failed: ' + msg.error);
    };

    H['project-preview-stopped'] = function(msg) {
        console.log('[UI] Project preview stopped:', msg.project_id);
        window.vncPreview.hideVncPreview();
    };

    H['sandbox_cycle_complete'] = function(msg) {
        console.log('[UI] Sandbox cycle:', msg.cycle_number, 'Success:', msg.success);
        if (msg.success) {
            window.vncPreview.updateVncStatus('Running \u2713');
        } else {
            window.vncPreview.updateVncStatus('Error \u2717');
        }
    };
})();
