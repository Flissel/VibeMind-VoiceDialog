/**
 * Stage Renderers — Renders stage-specific shuttle data (mining, validation, KG, techstack).
 * Extracted from index.html inline script.
 *
 * Note: innerHTML usage is safe — all content originates from the Python backend
 * (not user input). See shuttle-wizard.js for the same pattern.
 */
(function() {
    'use strict';

    /**
     * Render mining stage data (extracted requirements)
     */
    function renderMiningStageData(stageData) {
        const grid = document.getElementById('shuttle-requirements-grid');
        const countEl = document.getElementById('mining-count');
        if (!grid) return;

        const requirements = stageData?.requirements || [];
        if (requirements.length === 0) {
            grid.innerHTML = '<div class="req-loading">No requirements extracted</div>';
            countEl.textContent = '0 requirements';
            return;
        }

        grid.innerHTML = requirements.map(req => `
            <div class="req-card">
                <div class="req-card-header">
                    <span class="req-id">${req.id || 'REQ-???'}</span>
                    <span class="req-source">${req.source_node_type || 'unknown'}</span>
                </div>
                <div class="req-text">${req.text || 'No description'}</div>
            </div>
        `).join('');

        countEl.textContent = `${requirements.length} requirements extracted`;
    }

    /**
     * Render validation stage data (9-criteria scores)
     */
    function renderValidationStageData(stageData) {
        const grid = document.getElementById('shuttle-requirements-grid');
        const countEl = document.getElementById('validation-count');
        if (!grid) return;

        const results = stageData?.results || [];
        if (results.length === 0) {
            grid.innerHTML = '<div class="req-loading">No validation results</div>';
            countEl.textContent = '0 evaluated';
            return;
        }

        // Render requirements with pass/fail status
        grid.innerHTML = results.map(req => `
            <div class="req-card ${req.status === 'passed' ? 'passed' : 'failed'}">
                <div class="req-card-header">
                    <span class="req-id">${req.id || 'REQ-???'}</span>
                    <span class="req-score">${((req.score || 0) * 100).toFixed(0)}%</span>
                </div>
                <div class="req-text">${req.text || 'No description'}</div>
                ${req.criteria && req.criteria.length > 0 ? `
                    <div class="req-criteria">
                        ${req.criteria.map(c => `<span class="criterion">${c.criterion}: ${(c.score * 100).toFixed(0)}%</span>`).join(' ')}
                    </div>
                ` : ''}
            </div>
        `).join('');

        countEl.textContent = `${stageData.passed || 0}/${results.length} passed (${((stageData.average_score || 0) * 100).toFixed(0)}%)`;
    }

    /**
     * Render knowledge graph stage data (entities + relationships)
     */
    function renderKnowledgeGraphStageData(stageData) {
        const preview = document.getElementById('kg-preview');
        const countEl = document.getElementById('kg-count');
        if (!preview) return;

        const entities = stageData?.entities || [];
        const relationships = stageData?.relationships || [];

        if (stageData?.skipped) {
            preview.innerHTML = '<div class="kg-placeholder">Knowledge Graph API disabled (USE_KG_API=false)</div>';
            countEl.textContent = 'Skipped';
            return;
        }

        if (entities.length === 0 && relationships.length === 0) {
            preview.innerHTML = '<div class="kg-placeholder">No knowledge graph data</div>';
            countEl.textContent = '0 nodes, 0 edges';
            return;
        }

        preview.innerHTML = `
            <div class="kg-summary">
                <div class="kg-stat">
                    <span class="stat-value">${entities.length}</span>
                    <span class="stat-label">Entities</span>
                </div>
                <div class="kg-stat">
                    <span class="stat-value">${relationships.length}</span>
                    <span class="stat-label">Relations</span>
                </div>
            </div>
            <div class="kg-entities">
                <h5>Entities</h5>
                <ul class="entity-list">
                    ${entities.slice(0, 10).map(e => `<li>${e.name || e.label || e} (${e.type || 'entity'})</li>`).join('')}
                    ${entities.length > 10 ? `<li class="more">+${entities.length - 10} more...</li>` : ''}
                </ul>
            </div>
            <div class="kg-relationships">
                <h5>Relationships</h5>
                <ul class="relationship-list">
                    ${relationships.slice(0, 8).map(r => `<li>${r.source || r.from} → ${r.relation || r.type} → ${r.target || r.to}</li>`).join('')}
                    ${relationships.length > 8 ? `<li class="more">+${relationships.length - 8} more...</li>` : ''}
                </ul>
            </div>
        `;

        countEl.textContent = `${entities.length} entities, ${relationships.length} relationships`;
    }

    /**
     * Render techstack stage data (recommendations)
     */
    function renderTechStackStageData(stageData) {
        const container = document.getElementById('techstack-content');
        const countEl = document.getElementById('techstack-count');
        if (!container) return;

        if (stageData?.skipped) {
            container.innerHTML = '<div class="tech-placeholder">TechStack API disabled (USE_TECHSTACK_API=false)</div>';
            countEl.textContent = 'Skipped';
            return;
        }

        const stack = stageData?.recommended_stack || 'Unknown';
        const templates = stageData?.templates || [];
        const technologies = stageData?.technologies || [];

        container.innerHTML = `
            <div class="tech-recommendation">
                <h5>Recommended Stack</h5>
                <div class="recommended-stack">${stack}</div>
            </div>
            ${technologies.length > 0 ? `
                <div class="tech-technologies">
                    <h5>Technologies</h5>
                    <div class="tech-tags">
                        ${technologies.map(t => `<span class="tech-tag">${t}</span>`).join('')}
                    </div>
                </div>
            ` : ''}
            ${templates.length > 0 ? `
                <div class="tech-templates">
                    <h5>Available Templates</h5>
                    <ul class="template-list">
                        ${templates.map(t => `<li>${t}</li>`).join('')}
                    </ul>
                </div>
            ` : ''}
        `;

        countEl.textContent = stack;
    }

    // Listen for checkpoint data updates from backend
    window.addEventListener('shuttle-checkpoint-data', function(event) {
        const { stage, data } = event.detail;

        switch (stage) {
            case 'validation':
                // Update validation criteria grid
                if (data.criteria) {
                    Object.entries(data.criteria).forEach(function([criterion, score]) {
                        const scoreEl = document.getElementById('criteria-' + criterion);
                        if (scoreEl) {
                            scoreEl.textContent = (score * 100).toFixed(0) + '%';
                            scoreEl.parentElement.querySelector('.criteria-status').textContent = score >= 0.7 ? '\u2705' : '\u274C';
                        }
                    });
                }
                document.getElementById('validation-count').textContent = (data.evaluated || 0) + ' evaluated';
                break;

            case 'knowledge_graph':
                // Update KG preview
                var kgPreview = document.getElementById('kg-preview');
                if (kgPreview && data.nodes && data.nodes.length > 0) {
                    kgPreview.innerHTML = `
                        <div class="kg-summary">
                            <div class="kg-stat">
                                <span class="stat-value">${data.nodes.length}</span>
                                <span class="stat-label">Nodes</span>
                            </div>
                            <div class="kg-stat">
                                <span class="stat-value">${data.edges?.length || 0}</span>
                                <span class="stat-label">Edges</span>
                            </div>
                        </div>
                        <div class="kg-entities">
                            ${(data.nodes.slice(0, 10) || []).map(n => `
                                <span class="kg-entity">${n.label || n.name || 'Entity'}</span>
                            `).join('')}
                            ${data.nodes.length > 10 ? `<span class="kg-more">+${data.nodes.length - 10} more</span>` : ''}
                        </div>
                    `;
                }
                document.getElementById('kg-count').textContent = (data.nodes?.length || 0) + ' nodes, ' + (data.edges?.length || 0) + ' edges';
                break;

            case 'techstack':
                // Update TechStack preview
                var techPreview = document.getElementById('techstack-preview');
                if (techPreview && data.recommended_stack) {
                    techPreview.innerHTML = `
                        <div class="techstack-recommendation">
                            <div class="tech-stack-name">${data.recommended_stack}</div>
                            ${data.technologies ? `
                                <div class="tech-list">
                                    ${data.technologies.map(t => `<span class="tech-tag">${t}</span>`).join('')}
                                </div>
                            ` : ''}
                            ${data.reasoning ? `<div class="tech-reasoning">${data.reasoning}</div>` : ''}
                        </div>
                    `;
                }
                document.getElementById('techstack-count').textContent = data.recommended_stack || 'Not detected';
                break;
        }
    });

    // Public API
    window.stageRenderers = {
        renderStageShuttleData: function(stageType, stageData) {
            switch (stageType) {
                case 'mining':
                    renderMiningStageData(stageData);
                    break;
                case 'validation':
                    renderValidationStageData(stageData);
                    break;
                case 'knowledge_graph':
                    renderKnowledgeGraphStageData(stageData);
                    break;
                case 'techstack':
                    renderTechStackStageData(stageData);
                    break;
                default:
                    console.warn('[Shuttle] Unknown stage type:', stageType);
            }
        },
        renderMiningStageData: renderMiningStageData,
        renderValidationStageData: renderValidationStageData,
        renderKnowledgeGraphStageData: renderKnowledgeGraphStageData,
        renderTechStackStageData: renderTechStackStageData
    };
})();
