/**
 * Shuttle Interior — Info panel, interior view, checkpoint tabs, orchestrator panel.
 * Extracted from index.html inline script.
 *
 * Dependencies:
 *   window.stageRenderers.renderStageShuttleData (stage-renderers.js)
 *   window.shuttleWizard.initWizard (shuttle-wizard.js, runtime-only)
 *   window.vibemind.sendToPython (preload IPC)
 *   window.multiverseApp (multiverse.js)
 *   THREE (three.js)
 *
 * Note: innerHTML usage is safe — all content originates from the Python backend.
 */
(function() {
    'use strict';

    // ========================================
    // SHUTTLE INFO PANEL
    // ========================================

    var shuttlePanel = document.getElementById('shuttle-info-panel');
    var shuttleCloseBtn = document.getElementById('shuttle-close');
    var shuttleNavigateBtn = document.getElementById('shuttle-navigate-btn');
    var shuttleEnterBtn = document.getElementById('shuttle-enter-btn');
    var infoPanelShuttleId = null;

    // Listen for shuttle clicks from ShuttleManager
    window.addEventListener('shuttle-clicked', function(event) {
        var data = event.detail;
        console.log('[Shuttle Panel] Showing info for:', data);

        // Store shuttle ID for Enter button
        infoPanelShuttleId = data.id;

        // Update panel content
        document.getElementById('shuttle-bubble-name').textContent = data.bubbleName || '-';
        document.getElementById('shuttle-req-count').textContent = (data.totalRequirements || 0) + ' requirements';
        document.getElementById('shuttle-source').textContent = 'from: ' + (data.bubbleName || '-');
        document.getElementById('shuttle-passed').textContent = (data.passed || 0) + ' passed';
        document.getElementById('shuttle-failed').textContent = (data.failed || 0) + ' need work';

        var score = (data.score || 0) * 100;
        document.getElementById('shuttle-score-fill').style.width = score + '%';
        document.getElementById('shuttle-score-text').textContent = 'Score: ' + score.toFixed(0) + '%';

        // Show panel
        if (shuttlePanel) shuttlePanel.classList.remove('hidden');
    });

    // Close shuttle panel
    if (shuttleCloseBtn) {
        shuttleCloseBtn.addEventListener('click', function() {
            if (shuttlePanel) shuttlePanel.classList.add('hidden');
        });
    }

    // Navigate shuttle
    if (shuttleNavigateBtn) {
        shuttleNavigateBtn.addEventListener('click', function() {
            console.log('[Shuttle] Navigate clicked');
            if (window.vibemind && window.vibemind.sendToPython) {
                window.vibemind.sendToPython({
                    type: 'shuttle_navigate',
                    action: 'navigate'
                });
            }
            if (shuttlePanel) shuttlePanel.classList.add('hidden');
        });
    }

    // Enter Shuttle button - zoom into shuttle space
    if (shuttleEnterBtn) {
        shuttleEnterBtn.addEventListener('click', function() {
            console.log('[Shuttle] Enter Shuttle clicked, id:', infoPanelShuttleId);
            if (infoPanelShuttleId && window.enterShuttleFromClick) {
                if (shuttlePanel) shuttlePanel.classList.add('hidden');
                window.enterShuttleFromClick(infoPanelShuttleId);
            }
        });
    }

    // ========================================
    // SHUTTLE INTERIOR VIEW (zoomed-in space)
    // ========================================

    var shuttleInteriorView = document.getElementById('shuttle-interior-view');
    var shuttleExitBtn = document.getElementById('shuttle-exit-btn');
    var shuttleOpenOrchestrator = document.getElementById('shuttle-open-orchestrator');
    var shuttleContinueToProject = document.getElementById('shuttle-continue-to-project');
    var currentShuttleData = null;

    // Store camera position before entering shuttle
    var savedCameraPosition = null;
    var savedCameraTarget = null;

    // Listen for shuttle-entered event (from ShuttleManager zoom animation)
    window.addEventListener('shuttle-entered', function(event) {
        currentShuttleData = event.detail;
        console.log('[Shuttle Interior] Entered:', currentShuttleData);

        // Initialize wizard for this shuttle (runtime dependency on shuttle-wizard.js)
        if (window.shuttleWizard && window.shuttleWizard.initWizard) {
            window.shuttleWizard.initWizard(currentShuttleData);
        }

        // Update interior view with shuttle data
        document.getElementById('shuttle-interior-name').textContent = currentShuttleData.bubbleName || 'Requirement Shuttle';

        // Update stage badge
        var stageBadge = document.getElementById('shuttle-current-stage');
        var stageLabels = {
            'mining': 'Mining',
            'requirements': 'Requirements',
            'validation': 'Validation',
            'knowledge_graph': 'Knowledge Graph',
            'techstack': 'TechStack',
            'complete': 'Complete'
        };
        stageBadge.textContent = stageLabels[currentShuttleData.currentStage] || 'Mining';

        // Update pipeline visualization
        var stages = ['mining', 'requirements', 'validation', 'knowledge_graph', 'techstack'];
        var currentStageIndex = stages.indexOf(currentShuttleData.currentStage || 'mining');
        document.querySelectorAll('.pipeline-stage').forEach(function(el, i) {
            el.classList.remove('active', 'complete');
            if (i < currentStageIndex) {
                el.classList.add('complete');
            } else if (i === currentStageIndex) {
                el.classList.add('active');
            }
        });
        document.querySelectorAll('.pipeline-connector').forEach(function(el, i) {
            el.classList.toggle('active', i < currentStageIndex);
        });

        // Update score circle
        var score = (currentShuttleData.score || 0) * 100;
        var scoreCircle = document.getElementById('shuttle-interior-score');
        scoreCircle.style.background = 'conic-gradient(#66aaff ' + score + '%, rgba(100, 100, 100, 0.3) ' + score + '%)';
        scoreCircle.querySelector('.score-value').textContent = score.toFixed(0) + '%';

        // Update stats
        document.getElementById('shuttle-interior-passed').textContent = currentShuttleData.passed || 0;
        document.getElementById('shuttle-interior-failed').textContent = currentShuttleData.failed || 0;
        document.getElementById('shuttle-interior-total').textContent = currentShuttleData.totalRequirements || 0;

        // PHASE 13: Check if this is a stage-specific shuttle with embedded data
        if (currentShuttleData.isStageShuttle && currentShuttleData.stageData) {
            // Stage shuttle: render data directly (no backend request needed)
            console.log('[Shuttle Interior] Stage shuttle with embedded data:', currentShuttleData.stageType);
            if (window.stageRenderers) {
                window.stageRenderers.renderStageShuttleData(currentShuttleData.stageType, currentShuttleData.stageData);
            }
        } else {
            // Legacy shuttle: request requirements from backend
            if (window.vibemind && window.vibemind.sendToPython) {
                window.vibemind.sendToPython({
                    type: 'get_shuttle_requirements',
                    shuttle_id: currentShuttleData.id
                });
            }
        }

        // Update checkpoint tab status indicators
        var currentStage = currentShuttleData.stageType || currentShuttleData.currentStage || 'mining';
        updateCheckpointTabStatus(currentStage);

        // Show only the tab for the current stage (hide tabs for other checkpoints)
        var checkpointStages = ['mining', 'validation', 'knowledge_graph', 'techstack'];
        var activeStageIdx = checkpointStages.indexOf(currentStage);

        document.querySelectorAll('.checkpoint-tab').forEach(function(tab) {
            var tabStage = tab.dataset.stage;
            var tabIdx = checkpointStages.indexOf(tabStage);

            // Show only the current stage's tab
            var shouldShow = tabIdx === activeStageIdx;
            tab.style.display = shouldShow ? '' : 'none';

            // Activate the current stage tab
            tab.classList.toggle('active', shouldShow);
        });

        // Show the corresponding panel
        document.querySelectorAll('.checkpoint-panel').forEach(function(panel) {
            panel.classList.remove('active');
        });
        var activePanel = document.getElementById('checkpoint-' + currentStage);
        if (activePanel) activePanel.classList.add('active');

        // Show interior view
        if (shuttleInteriorView) shuttleInteriorView.classList.remove('hidden');
        if (shuttlePanel) shuttlePanel.classList.add('hidden');

        console.log('[Shuttle Interior] View opened, stage:', currentStage);
    });

    // Listen for shuttle-exited event
    window.addEventListener('shuttle-exited', function() {
        currentShuttleData = null;
        if (shuttleInteriorView) shuttleInteriorView.classList.add('hidden');

        // Reset all tabs to visible for next shuttle
        document.querySelectorAll('.checkpoint-tab').forEach(function(tab) {
            tab.style.display = '';
        });

        console.log('[Shuttle Interior] View closed');
    });

    // Exit shuttle button
    if (shuttleExitBtn) {
        shuttleExitBtn.addEventListener('click', function() {
            console.log('[Shuttle Interior] Exit clicked');
            if (window.multiverseApp && window.multiverseApp.shuttleManager) {
                var returnPos = savedCameraPosition || new THREE.Vector3(0, 3, 12);
                var returnTarget = savedCameraTarget || new THREE.Vector3(0, 0, 0);
                window.multiverseApp.shuttleManager.exitShuttleWithAnimation(
                    window.multiverseApp.camera,
                    window.multiverseApp.controls,
                    returnPos,
                    returnTarget,
                    function() {
                        if (shuttleInteriorView) shuttleInteriorView.classList.add('hidden');
                    }
                );
            } else {
                // Fallback: just hide the panel
                if (shuttleInteriorView) shuttleInteriorView.classList.add('hidden');
            }
        });
    }

    // Open orchestrator button
    if (shuttleOpenOrchestrator) {
        shuttleOpenOrchestrator.addEventListener('click', function() {
            console.log('[Shuttle Interior] Open orchestrator clicked');
            if (window.toggleOrchestratorPanel) window.toggleOrchestratorPanel();
        });
    }

    // Continue to projects button
    if (shuttleContinueToProject) {
        shuttleContinueToProject.addEventListener('click', function() {
            console.log('[Shuttle Interior] Continue to projects clicked');
            if (currentShuttleData && window.vibemind && window.vibemind.sendToPython) {
                window.vibemind.sendToPython({
                    type: 'create_project_from_shuttle',
                    shuttle_id: currentShuttleData.id,
                    bubble_name: currentShuttleData.bubbleName
                });
            }
            if (shuttleInteriorView) shuttleInteriorView.classList.add('hidden');

            // Navigate to Projects space
            if (window.multiverseApp) {
                window.multiverseApp.navigateToSpace('projects');
            }
        });
    }

    // Handle requirements loaded from backend
    window.addEventListener('shuttle-requirements-loaded', function(event) {
        var requirements = event.detail.requirements;
        var grid = document.getElementById('shuttle-requirements-grid');
        if (!grid) return;

        if (!requirements || requirements.length === 0) {
            grid.innerHTML = '<div class="req-loading">No requirements found</div>';
            return;
        }

        grid.innerHTML = requirements.map(function(req) {
            return '<div class="req-card ' + (req.verdict === 'pass' ? 'passed' : 'failed') + '">' +
                '<div class="req-card-header">' +
                    '<span class="req-id">' + req.id + '</span>' +
                    '<span class="req-score">' + ((req.score || 0) * 100).toFixed(0) + '%</span>' +
                '</div>' +
                '<div class="req-text">' + (req.text || 'No description') + '</div>' +
            '</div>';
        }).join('');

        // Update mining count
        document.getElementById('mining-count').textContent = requirements.length + ' requirements extracted';
    });

    // ========================================
    // CHECKPOINT TABS
    // ========================================

    // Tab switching logic
    document.querySelectorAll('.checkpoint-tab').forEach(function(tab) {
        tab.addEventListener('click', function() {
            var stage = tab.dataset.stage;

            // Update tab states
            document.querySelectorAll('.checkpoint-tab').forEach(function(t) { t.classList.remove('active'); });
            tab.classList.add('active');

            // Update panel visibility
            document.querySelectorAll('.checkpoint-panel').forEach(function(panel) {
                panel.classList.remove('active');
            });
            var targetPanel = document.getElementById('checkpoint-' + stage);
            if (targetPanel) targetPanel.classList.add('active');
        });
    });

    // Update checkpoint tab status based on shuttle stage (4 tabs)
    function updateCheckpointTabStatus(currentStage) {
        // Only the 4 tabs that exist in the HTML (no 'requirements' tab)
        var tabStages = ['mining', 'validation', 'knowledge_graph', 'techstack'];
        var currentIndex = tabStages.indexOf(currentStage);

        tabStages.forEach(function(s, i) {
            var tabStatus = document.getElementById('tab-status-' + s);
            if (tabStatus) {
                if (i < currentIndex) {
                    tabStatus.textContent = '\u2705';  // Completed
                } else if (i === currentIndex) {
                    tabStatus.textContent = '\uD83D\uDD04';  // Active/current
                } else {
                    tabStatus.textContent = '\u23F3';  // Pending
                }
            }
        });
    }

    // ========================================
    // ENTER SHUTTLE FROM CLICK
    // ========================================

    window.enterShuttleFromClick = function(shuttleId) {
        if (!window.multiverseApp || !window.multiverseApp.shuttleManager) return;

        // Save current camera position for return
        savedCameraPosition = window.multiverseApp.camera.position.clone();
        savedCameraTarget = window.multiverseApp.controls.target.clone();

        // Enter the shuttle
        window.multiverseApp.shuttleManager.enterShuttleWithAnimation(
            shuttleId,
            window.multiverseApp.camera,
            window.multiverseApp.controls,
            function() {
                console.log('[Shuttle] Zoom animation complete');
            }
        );
    };

    // ========================================
    // ORCHESTRATOR PANEL
    // ========================================

    var orchestratorPanel = document.getElementById('orchestrator-panel');
    var orchestratorCloseBtn = document.getElementById('orchestrator-close');
    var orchestratorFrame = document.getElementById('orchestrator-frame');
    var ORCHESTRATOR_URL = 'http://localhost:8087';

    function toggleOrchestratorPanel() {
        var isHidden = orchestratorPanel ? orchestratorPanel.classList.toggle('hidden') : true;
        if (!isHidden && orchestratorFrame && !orchestratorFrame.src) {
            orchestratorFrame.src = ORCHESTRATOR_URL;
        }
    }

    if (orchestratorCloseBtn) {
        orchestratorCloseBtn.addEventListener('click', function() {
            if (orchestratorPanel) orchestratorPanel.classList.add('hidden');
        });
    }

    // Expose for voice commands
    window.toggleOrchestratorPanel = toggleOrchestratorPanel;

    // Public API
    window.shuttleInterior = {
        updateCheckpointTabStatus: updateCheckpointTabStatus
    };
})();
