/**
 * Claude Code Runner — Panel for running Claude Code in Docker with VNC.
 * Extracted from index.html inline script.
 *
 * Dependencies:
 *   window.vncPreview.showVncPreview/hideVncPreview/showVncLoading (vnc-preview.js)
 *   window.showTranscript (index.html inline)
 *   window.vibemind.engine.claudeRunner (preload IPC)
 *   window.vibemind.startProjectPreview (preload IPC)
 *   window.multiverseApp (multiverse.js)
 */
(function() {
    'use strict';

    var crPanel = document.getElementById('claude-runner-panel');
    var crStatus = document.getElementById('claude-runner-status');
    var crDetails = document.getElementById('claude-runner-details');
    var crRepoInput = document.getElementById('claude-runner-repo');
    var crStartBtn = document.getElementById('claude-runner-start-btn');
    var crStopBtn = document.getElementById('claude-runner-stop-btn');
    var crVncBtn = document.getElementById('claude-runner-vnc-btn');
    var crPolling = null;

    if (crStartBtn) {
        crStartBtn.addEventListener('click', async function() {
            var repoPath = crRepoInput ? crRepoInput.value.trim() : '';
            if (!repoPath) { crDetails.textContent = 'Please enter a git repo path'; return; }

            crStartBtn.disabled = true;
            crStartBtn.style.opacity = '0.4';
            crStatus.textContent = 'Starting...';
            crStatus.style.background = 'rgba(255, 200, 0, 0.2)';
            crStatus.style.color = '#ffc800';
            crDetails.textContent = 'Building Docker image & starting container...';

            try {
                var result = await window.vibemind.engine.claudeRunner.start(repoPath);
                if (result.success) {
                    crStopBtn.disabled = false;
                    crStopBtn.style.opacity = '1';
                    crVncBtn.disabled = false;
                    crVncBtn.style.opacity = '1';
                    crVncBtn.dataset.vncPort = result.vncPort;
                    crStatus.textContent = 'Running';
                    crStatus.style.background = 'rgba(0, 255, 136, 0.2)';
                    crStatus.style.color = '#00ff88';
                    crDetails.textContent = 'Container started. VNC: ' + result.vncPort;
                    startCrPolling();
                } else {
                    crStartBtn.disabled = false;
                    crStartBtn.style.opacity = '1';
                    crStatus.textContent = 'Error';
                    crStatus.style.background = 'rgba(255, 68, 68, 0.2)';
                    crStatus.style.color = '#ff4444';
                    crDetails.textContent = result.error;
                }
            } catch (error) {
                crStartBtn.disabled = false;
                crStartBtn.style.opacity = '1';
                crStatus.textContent = 'Error';
                crDetails.textContent = error.message;
            }
        });
    }

    if (crStopBtn) {
        crStopBtn.addEventListener('click', async function() {
            await window.vibemind.engine.claudeRunner.stop();
            stopCrPolling();
            crStartBtn.disabled = false;
            crStartBtn.style.opacity = '1';
            crStopBtn.disabled = true;
            crStopBtn.style.opacity = '0.4';
            crVncBtn.disabled = true;
            crVncBtn.style.opacity = '0.4';
            crStatus.textContent = 'Stopped';
            crStatus.style.background = 'rgba(100, 100, 100, 0.3)';
            crStatus.style.color = '#888';
            crDetails.textContent = 'Not running';
            if (window.vncPreview) window.vncPreview.hideVncPreview();
        });
    }

    if (crVncBtn) {
        crVncBtn.addEventListener('click', function() {
            var vncPort = crVncBtn.dataset.vncPort;
            if (vncPort && window.vncPreview) {
                window.vncPreview.showVncPreview(
                    'http://localhost:' + vncPort + '/vnc.html?autoconnect=true&resize=scale',
                    'Claude Code Runner',
                    'claude-runner'
                );
            }
        });
    }

    function startCrPolling() {
        stopCrPolling();
        crPolling = setInterval(async function() {
            try {
                var s = await window.vibemind.engine.claudeRunner.getStatus();
                if (!s.running) { crStopBtn.click(); return; }
                var icons = { idle: '\uD83D\uDFE2', processing: '\uD83D\uDD35', completed: '\u2705', failed: '\u274C', error: '\uD83D\uDD34', starting: '\uD83D\uDFE1' };
                crDetails.textContent =
                    (icons[s.state] || '\u26AA') + ' ' + (s.message || s.state) +
                    (s.branch ? '\nBranch: ' + s.branch : '') +
                    (s.details ? '\n' + s.details : '');
                crStatus.textContent = s.state || 'Running';
            } catch(e) { /* ignore */ }
        }, 5000);
    }

    function stopCrPolling() {
        if (crPolling) { clearInterval(crPolling); crPolling = null; }
    }

    // Show/hide runner panel with keyboard shortcut (Ctrl+Shift+R)
    document.addEventListener('keydown', function(e) {
        if (e.ctrlKey && e.shiftKey && e.key === 'R') {
            if (crPanel) crPanel.classList.toggle('hidden');
        }
    });

    // Open Project Button Handler
    var openProjectBtn = document.getElementById('open-project-btn');
    if (openProjectBtn) {
        openProjectBtn.addEventListener('click', async function() {
            var projectId = window.multiverseApp ? window.multiverseApp.selectedProjectId : null;
            var projectData = window.multiverseApp ? window.multiverseApp.getProjectById(projectId) : null;

            if (projectId) {
                console.log('[UI] Opening project preview:', projectId);
                if (window.vncPreview) window.vncPreview.showVncLoading(true, projectData ? projectData.title : 'Project');

                try {
                    // Start the preview via IPC - this triggers the Coding Engine sandbox
                    await window.vibemind.startProjectPreview(projectId, projectData ? projectData.path : undefined);
                    if (window.showTranscript) window.showTranscript('System', 'Starting Live Preview for ' + (projectData ? projectData.title : projectId) + '...');
                } catch (error) {
                    console.error('[UI] Failed to start preview:', error);
                    if (window.vncPreview) window.vncPreview.hideVncPreview();
                    if (window.showTranscript) window.showTranscript('System', 'Failed to start preview: ' + error.message);
                }
            }
        });
    }
})();
