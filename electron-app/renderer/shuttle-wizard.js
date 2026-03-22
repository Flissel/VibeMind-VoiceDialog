/**
 * Shuttle Wizard Controller — Wizard state, agent results, step navigation, button handlers.
 * Extracted from index.html inline script.
 *
 * Dependencies:
 *   window.vibemind.sendToPython (preload IPC)
 *
 * Note: All data rendered here originates from the Python backend
 * (wizard_handler.py) and SQLite, never from untrusted user HTML.
 * Render functions use textContent for text values and build DOM elements safely.
 */
(function() {
    'use strict';

    var wizardState = {
        shuttleId: null,
        bubbleId: null,
        currentStep: 'mining',
        project: {},
        context: {},
        stakeholders: [],
        requirements: [],
        constraints: {},
        _lastGapSuggestions: [],
    };

    // Initialize wizard when entering a shuttle
    function initWizard(shuttleData) {
        wizardState.shuttleId = shuttleData.id;
        wizardState.bubbleId = shuttleData.bubbleId;
        wizardState.currentStep = 'mining';

        // Request wizard state from backend (may have persisted data)
        if (window.vibemind && window.vibemind.sendToPython) {
            window.vibemind.sendToPython({
                type: 'wizard_init_from_bubble',
                shuttle_id: shuttleData.id,
                bubble_id: shuttleData.bubbleId,
            });
        }
    }

    // Handle wizard messages from Python backend
    window.addEventListener('message-from-python', function(e) {
        var msg = e.detail;
        if (!msg) return;

        if (msg.type === 'wizard_initialized') {
            console.log('[Wizard] Initialized:', msg);
            if (msg.project) {
                wizardState.project = msg.project;
                document.getElementById('wizard-project-name').value = msg.project.name || '';
                document.getElementById('wizard-project-desc').value = msg.project.description || '';
                document.getElementById('wizard-domain').value = msg.project.domain || '';
                document.getElementById('wizard-target-users').value = msg.project.target_users || '';
            }
        }

        if (msg.type === 'wizard_state') {
            console.log('[Wizard] State loaded:', msg);
            Object.assign(wizardState, {
                currentStep: msg.current_step || 'mining',
                project: msg.project || {},
                context: msg.context || {},
                stakeholders: msg.stakeholders || [],
                requirements: msg.requirements || [],
                constraints: msg.constraints || {},
            });
            renderWizardRequirements();
            renderWizardStakeholders();
            navigateWizardStep(wizardState.currentStep);
        }

        if (msg.type === 'wizard_agent_result') {
            console.log('[Wizard] Agent result:', msg.team, msg);
            handleAgentTeamResult(msg);
        }

        if (msg.type === 'wizard_step_saved') {
            console.log('[Wizard] Step saved:', msg);
        }

        if (msg.type === 'wizard_finalized') {
            console.log('[Wizard] Finalized:', msg);
            if (msg.success) {
                var statusEl = document.getElementById('techstack-count');
                if (statusEl) statusEl.textContent = 'Finalized!';
            }
        }
    });

    function navigateWizardStep(step) {
        var stepMap = {
            'mining': 'mining',
            'requirements': 'validation',
            'knowledge_graph': 'knowledge_graph',
            'techstack': 'techstack',
        };
        var panelKey = stepMap[step] || step;

        // Update checkpoint tabs
        var checkpointStages = ['mining', 'validation', 'knowledge_graph', 'techstack'];
        document.querySelectorAll('.checkpoint-tab').forEach(function(tab) {
            tab.style.display = '';
            tab.classList.toggle('active', tab.dataset.stage === panelKey);
        });

        // Update panels
        document.querySelectorAll('.checkpoint-panel').forEach(function(p) { p.classList.remove('active'); });
        var panel = document.getElementById('checkpoint-' + panelKey);
        if (panel) panel.classList.add('active');

        // Update tab status icons
        var wizardSteps = ['mining', 'requirements', 'knowledge_graph', 'techstack'];
        var currentIdx = wizardSteps.indexOf(step);
        checkpointStages.forEach(function(s, i) {
            var tabStatus = document.getElementById('tab-status-' + s);
            if (tabStatus) {
                if (i < currentIdx) tabStatus.textContent = '\u2705';
                else if (i === currentIdx) tabStatus.textContent = '\uD83D\uDD04';
                else tabStatus.textContent = '\u23F3';
            }
        });

        // Update summary on finalize step
        if (step === 'techstack') updatePackageSummary();

        // Update validation summary on constraints step
        if (step === 'knowledge_graph') {
            document.getElementById('wizard-val-reqs').textContent = wizardState.requirements.length;
            document.getElementById('wizard-val-stakeholders').textContent = wizardState.stakeholders.length;
            var cCount = Object.values(wizardState.constraints).reduce(
                function(sum, arr) { return sum + (Array.isArray(arr) ? arr.length : 0); }, 0
            );
            document.getElementById('wizard-val-constraints').textContent = cCount;
            document.getElementById('kg-count').textContent = cCount + ' constraints';
        }
    }

    function updatePackageSummary() {
        document.getElementById('wizard-pkg-project').textContent = wizardState.project.name || '-';
        document.getElementById('wizard-pkg-domain').textContent = wizardState.project.domain || '-';
        document.getElementById('wizard-pkg-reqs').textContent = wizardState.requirements.length;
        document.getElementById('wizard-pkg-stakeholders').textContent = wizardState.stakeholders.length;
        var cCount = Object.values(wizardState.constraints).reduce(
            function(sum, arr) { return sum + (Array.isArray(arr) ? arr.length : 0); }, 0
        );
        document.getElementById('wizard-pkg-constraints').textContent = cCount;
    }

    function collectMiningData() {
        return {
            name: document.getElementById('wizard-project-name').value,
            description: document.getElementById('wizard-project-desc').value,
            domain: document.getElementById('wizard-domain').value,
            target_users: document.getElementById('wizard-target-users').value,
        };
    }

    function renderWizardRequirements() {
        var grid = document.getElementById('wizard-requirements-grid');
        if (!grid) return;
        grid.textContent = '';
        var reqs = wizardState.requirements;
        if (reqs.length === 0) {
            var ph = document.createElement('div');
            ph.className = 'wizard-placeholder';
            ph.textContent = 'No requirements yet';
            grid.appendChild(ph);
            return;
        }
        reqs.forEach(function(req, i) {
            var card = document.createElement('div');
            card.className = 'req-card';

            var header = document.createElement('div');
            header.className = 'req-card-header';
            var idSpan = document.createElement('span');
            idSpan.className = 'req-id';
            idSpan.textContent = req.id || 'REQ-' + String(i+1).padStart(3,'0');
            var prioSpan = document.createElement('span');
            prioSpan.className = 'req-priority';
            prioSpan.textContent = req.priority || 'medium';
            header.appendChild(idSpan);
            header.appendChild(prioSpan);

            var text = document.createElement('div');
            text.className = 'req-text';
            text.textContent = req.title || req.text || 'Untitled';

            card.appendChild(header);
            card.appendChild(text);

            if (req.description) {
                var desc = document.createElement('div');
                desc.className = 'req-desc';
                desc.textContent = req.description;
                card.appendChild(desc);
            }

            grid.appendChild(card);
        });
        document.getElementById('validation-count').textContent = reqs.length + ' requirements';
    }

    function renderWizardStakeholders() {
        var grid = document.getElementById('wizard-stakeholders-grid');
        if (!grid) return;
        grid.textContent = '';
        var stakeholders = wizardState.stakeholders;
        if (stakeholders.length === 0) {
            var ph = document.createElement('div');
            ph.className = 'wizard-placeholder';
            ph.textContent = 'No stakeholders generated yet';
            grid.appendChild(ph);
            return;
        }
        stakeholders.forEach(function(s) {
            var card = document.createElement('div');
            card.className = 'stakeholder-card';
            var role = document.createElement('div');
            role.className = 'stakeholder-role';
            role.textContent = s.role || s.name || 'Unknown';
            card.appendChild(role);
            if (s.concerns) {
                var concerns = document.createElement('div');
                concerns.className = 'stakeholder-concerns';
                concerns.textContent = Array.isArray(s.concerns) ? s.concerns.join(', ') : s.concerns;
                card.appendChild(concerns);
            }
            grid.appendChild(card);
        });
    }

    function handleAgentTeamResult(msg) {
        if (msg.team === 'context_enricher' && msg.success) {
            wizardState.context = (msg.suggestions && msg.suggestions[0]) || {};
            var resultDiv = document.getElementById('wizard-context-result');
            var contentDiv = document.getElementById('wizard-context-content');
            if (resultDiv && contentDiv) {
                contentDiv.textContent = '';
                var ctx = wizardState.context;
                ['summary', 'business', 'technical', 'user'].forEach(function(key) {
                    if (ctx[key]) {
                        var p = document.createElement('p');
                        var strong = document.createElement('strong');
                        strong.textContent = key.charAt(0).toUpperCase() + key.slice(1) + ': ';
                        p.appendChild(strong);
                        p.appendChild(document.createTextNode(ctx[key]));
                        contentDiv.appendChild(p);
                    }
                });
                resultDiv.classList.remove('hidden');
            }
        }

        if (msg.team === 'stakeholder' && msg.success) {
            wizardState.stakeholders = msg.suggestions || [];
            renderWizardStakeholders();
        }

        if (msg.team === 'requirement_gap' && msg.success) {
            var suggestions = msg.suggestions || [];
            wizardState._lastGapSuggestions = suggestions;
            var sugDiv = document.getElementById('wizard-suggestions');
            var sugList = document.getElementById('wizard-suggestions-list');
            if (sugDiv && sugList && suggestions.length > 0) {
                sugList.textContent = '';
                suggestions.forEach(function(s, i) {
                    var card = document.createElement('div');
                    card.className = 'suggestion-card';
                    card.dataset.index = i;

                    var header = document.createElement('div');
                    header.className = 'suggestion-header';
                    var typeSpan = document.createElement('span');
                    typeSpan.className = 'suggestion-type';
                    typeSpan.textContent = s.type || 'requirement';
                    var confSpan = document.createElement('span');
                    confSpan.className = 'suggestion-confidence';
                    confSpan.textContent = ((s.confidence || 0) * 100).toFixed(0) + '%';
                    header.appendChild(typeSpan);
                    header.appendChild(confSpan);

                    var text = document.createElement('div');
                    text.className = 'suggestion-text';
                    text.textContent = s.title || s.text || 'Suggested requirement';

                    card.appendChild(header);
                    card.appendChild(text);

                    if (s.gap_area) {
                        var reason = document.createElement('div');
                        reason.className = 'suggestion-reason';
                        reason.textContent = s.gap_area;
                        card.appendChild(reason);
                    }

                    var actions = document.createElement('div');
                    actions.className = 'suggestion-actions';
                    var acceptBtn = document.createElement('button');
                    acceptBtn.className = 'action-btn small';
                    acceptBtn.textContent = 'Accept';
                    acceptBtn.addEventListener('click', function() { window.acceptSuggestion(i); });
                    var dismissBtn = document.createElement('button');
                    dismissBtn.className = 'action-btn small secondary';
                    dismissBtn.textContent = 'Dismiss';
                    dismissBtn.addEventListener('click', function() { window.dismissSuggestion(i); });
                    actions.appendChild(acceptBtn);
                    actions.appendChild(dismissBtn);
                    card.appendChild(actions);

                    sugList.appendChild(card);
                });
                sugDiv.classList.remove('hidden');
            }
        }

        if (msg.team === 'constraint' && msg.success) {
            var newConstraints = msg.suggestions || [];
            newConstraints.forEach(function(c) {
                var cat = c.category || 'technical';
                if (!wizardState.constraints[cat]) wizardState.constraints[cat] = [];
                wizardState.constraints[cat].push(c);
            });
            renderWizardConstraints();
        }
    }

    function renderWizardConstraints() {
        var grid = document.getElementById('wizard-constraints-grid');
        if (!grid) return;
        grid.textContent = '';
        var entries = Object.entries(wizardState.constraints);
        if (entries.length === 0) {
            var ph = document.createElement('div');
            ph.className = 'wizard-placeholder';
            ph.textContent = 'No constraints yet';
            grid.appendChild(ph);
            return;
        }
        var total = 0;
        entries.forEach(function(entry) {
            var cat = entry[0];
            var items = entry[1] || [];
            total += items.length;
            var catDiv = document.createElement('div');
            catDiv.className = 'constraint-category';
            var h6 = document.createElement('h6');
            h6.textContent = cat;
            catDiv.appendChild(h6);
            items.forEach(function(c) {
                var item = document.createElement('div');
                item.className = 'constraint-item';
                var textSpan = document.createElement('span');
                textSpan.textContent = c.constraint || c.text || '';
                var confSpan = document.createElement('span');
                confSpan.className = 'constraint-confidence';
                confSpan.textContent = ((c.confidence || 0) * 100).toFixed(0) + '%';
                item.appendChild(textSpan);
                item.appendChild(confSpan);
                catDiv.appendChild(item);
            });
            grid.appendChild(catDiv);
        });
        document.getElementById('kg-count').textContent = total + ' constraints';
    }

    // Global functions for suggestion buttons
    window.acceptSuggestion = function(index) {
        var suggestions = wizardState._lastGapSuggestions || [];
        if (suggestions[index]) {
            wizardState.requirements.push({
                id: 'REQ-' + String(wizardState.requirements.length + 1).padStart(3, '0'),
                title: suggestions[index].title || suggestions[index].text || '',
                description: suggestions[index].description || '',
                priority: suggestions[index].priority || 'medium',
                status: 'pending',
            });
            renderWizardRequirements();
        }
        var sugList = document.getElementById('wizard-suggestions-list');
        var cards = sugList ? sugList.querySelectorAll('.suggestion-card') : [];
        if (cards[index]) cards[index].remove();
    };

    window.dismissSuggestion = function(index) {
        var sugList = document.getElementById('wizard-suggestions-list');
        var cards = sugList ? sugList.querySelectorAll('.suggestion-card') : [];
        if (cards[index]) cards[index].remove();
    };

    // ---- Wizard Navigation Buttons ----

    var genCtxBtn = document.getElementById('wizard-generate-context');
    if (genCtxBtn) {
        genCtxBtn.addEventListener('click', function() {
            var data = collectMiningData();
            wizardState.project = data;
            if (window.vibemind && window.vibemind.sendToPython) {
                window.vibemind.sendToPython({
                    type: 'wizard_run_agent',
                    shuttle_id: wizardState.shuttleId,
                    team: 'context_enricher',
                    input: data,
                });
            }
        });
    }

    var nextToReqsBtn = document.getElementById('wizard-next-to-requirements');
    if (nextToReqsBtn) {
        nextToReqsBtn.addEventListener('click', function() {
            var data = collectMiningData();
            wizardState.project = data;
            if (window.vibemind && window.vibemind.sendToPython) {
                window.vibemind.sendToPython({
                    type: 'wizard_submit_step',
                    shuttle_id: wizardState.shuttleId,
                    step: 'mining',
                    data: Object.assign({}, data, { context: wizardState.context }),
                });
            }
            navigateWizardStep('requirements');
            renderWizardRequirements();
        });
    }

    var genStakeholdersBtn = document.getElementById('wizard-generate-stakeholders');
    if (genStakeholdersBtn) {
        genStakeholdersBtn.addEventListener('click', function() {
            if (window.vibemind && window.vibemind.sendToPython) {
                window.vibemind.sendToPython({
                    type: 'wizard_run_agent',
                    shuttle_id: wizardState.shuttleId,
                    team: 'stakeholder',
                    input: wizardState.project,
                });
            }
        });
    }

    var addReqBtn = document.getElementById('wizard-add-requirement');
    if (addReqBtn) {
        addReqBtn.addEventListener('click', function() {
            var title = prompt('Requirement title:');
            if (title) {
                wizardState.requirements.push({
                    id: 'REQ-' + String(wizardState.requirements.length + 1).padStart(3, '0'),
                    title: title,
                    description: '',
                    priority: 'medium',
                    status: 'pending',
                });
                renderWizardRequirements();
            }
        });
    }

    var gapAnalysisBtn = document.getElementById('wizard-run-gap-analysis');
    if (gapAnalysisBtn) {
        gapAnalysisBtn.addEventListener('click', function() {
            if (window.vibemind && window.vibemind.sendToPython) {
                window.vibemind.sendToPython({
                    type: 'wizard_run_agent',
                    shuttle_id: wizardState.shuttleId,
                    team: 'requirement_gap',
                    input: {},
                });
            }
        });
    }

    var nextToConstraintsBtn = document.getElementById('wizard-next-to-constraints');
    if (nextToConstraintsBtn) {
        nextToConstraintsBtn.addEventListener('click', function() {
            if (window.vibemind && window.vibemind.sendToPython) {
                window.vibemind.sendToPython({
                    type: 'wizard_submit_step',
                    shuttle_id: wizardState.shuttleId,
                    step: 'requirements',
                    data: {
                        stakeholders: wizardState.stakeholders,
                        requirements: wizardState.requirements,
                    },
                });
            }
            navigateWizardStep('knowledge_graph');
        });
    }

    var extractConstraintsBtn = document.getElementById('wizard-extract-constraints');
    if (extractConstraintsBtn) {
        extractConstraintsBtn.addEventListener('click', function() {
            if (window.vibemind && window.vibemind.sendToPython) {
                window.vibemind.sendToPython({
                    type: 'wizard_run_agent',
                    shuttle_id: wizardState.shuttleId,
                    team: 'constraint',
                    input: {},
                });
            }
        });
    }

    var nextToTechstackBtn = document.getElementById('wizard-next-to-techstack');
    if (nextToTechstackBtn) {
        nextToTechstackBtn.addEventListener('click', function() {
            if (window.vibemind && window.vibemind.sendToPython) {
                window.vibemind.sendToPython({
                    type: 'wizard_submit_step',
                    shuttle_id: wizardState.shuttleId,
                    step: 'knowledge_graph',
                    data: { constraints: wizardState.constraints },
                });
            }
            navigateWizardStep('techstack');
        });
    }

    var finalizeBtn = document.getElementById('wizard-finalize');
    if (finalizeBtn) {
        finalizeBtn.addEventListener('click', function() {
            var workDivision = document.getElementById('wizard-work-division').value;
            if (window.vibemind && window.vibemind.sendToPython) {
                window.vibemind.sendToPython({
                    type: 'wizard_submit_step',
                    shuttle_id: wizardState.shuttleId,
                    step: 'techstack',
                    data: { work_division: workDivision },
                });
                window.vibemind.sendToPython({
                    type: 'wizard_finalize',
                    shuttle_id: wizardState.shuttleId,
                });
            }
        });
    }

    // Back buttons
    var backToMiningBtn = document.getElementById('wizard-back-to-mining');
    if (backToMiningBtn) backToMiningBtn.addEventListener('click', function() { navigateWizardStep('mining'); });
    var backToReqsBtn = document.getElementById('wizard-back-to-requirements');
    if (backToReqsBtn) backToReqsBtn.addEventListener('click', function() { navigateWizardStep('requirements'); });
    var backToConstraintsBtn = document.getElementById('wizard-back-to-constraints');
    if (backToConstraintsBtn) backToConstraintsBtn.addEventListener('click', function() { navigateWizardStep('knowledge_graph'); });

    // Public API
    window.shuttleWizard = {
        initWizard: initWizard,
        navigateWizardStep: navigateWizardStep
    };
})();
