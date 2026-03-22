/**
 * ExplorationDialog - UI component for AI-Scientist style idea exploration.
 *
 * Displays dialogs for human-in-the-loop interaction during exploration:
 * - Connection found: Accept/Reject/Explore deeper
 * - Direction request: Choose exploration direction
 * - Stage complete: Continue/Stop/Show results
 */

class ExplorationDialog {
    constructor() {
        this.currentQuestion = null;
        this.dialogElement = null;
        this.overlayElement = null;
        this.isVisible = false;
        this.explorationState = {
            isRunning: false,
            mode: 'auto',
            stage: null,
            nodesDiscovered: 0,
            bestScore: 0
        };

        this.init();
        this.setupEventListeners();
    }

    init() {
        // Create overlay
        this.overlayElement = document.createElement('div');
        this.overlayElement.id = 'exploration-dialog-overlay';
        this.overlayElement.className = 'exploration-overlay hidden';
        document.body.appendChild(this.overlayElement);

        // Create dialog container
        this.dialogElement = document.createElement('div');
        this.dialogElement.id = 'exploration-dialog';
        this.dialogElement.className = 'exploration-dialog hidden';
        document.body.appendChild(this.dialogElement);

        // Add styles
        this.injectStyles();

        console.log('[ExplorationDialog] Initialized');
    }

    injectStyles() {
        const style = document.createElement('style');
        style.textContent = `
            .exploration-overlay {
                position: fixed;
                top: 0;
                left: 0;
                width: 100vw;
                height: 100vh;
                background: rgba(0, 0, 0, 0.4);
                backdrop-filter: blur(4px);
                z-index: 9998;
                transition: opacity 0.3s ease;
            }

            .exploration-overlay.hidden {
                opacity: 0;
                pointer-events: none;
            }

            .exploration-dialog {
                position: fixed;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                background: linear-gradient(135deg, rgba(30, 30, 50, 0.95), rgba(20, 20, 40, 0.98));
                border: 1px solid rgba(100, 140, 255, 0.3);
                border-radius: 16px;
                padding: 24px;
                min-width: 400px;
                max-width: 600px;
                z-index: 9999;
                box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5),
                            0 0 40px rgba(100, 140, 255, 0.15);
                transition: opacity 0.3s ease, transform 0.3s ease;
            }

            .exploration-dialog.hidden {
                opacity: 0;
                transform: translate(-50%, -50%) scale(0.95);
                pointer-events: none;
            }

            .exploration-dialog-header {
                display: flex;
                align-items: center;
                gap: 12px;
                margin-bottom: 20px;
            }

            .exploration-dialog-icon {
                width: 40px;
                height: 40px;
                border-radius: 50%;
                background: linear-gradient(135deg, #6c8cff, #a855f7);
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 20px;
            }

            .exploration-dialog-title {
                font-size: 18px;
                font-weight: 600;
                color: #fff;
            }

            .exploration-dialog-subtitle {
                font-size: 12px;
                color: rgba(255, 255, 255, 0.6);
            }

            .exploration-dialog-content {
                color: rgba(255, 255, 255, 0.9);
                font-size: 14px;
                line-height: 1.6;
                margin-bottom: 20px;
            }

            .exploration-connection-preview {
                background: rgba(100, 140, 255, 0.1);
                border: 1px solid rgba(100, 140, 255, 0.2);
                border-radius: 12px;
                padding: 16px;
                margin-bottom: 20px;
                display: flex;
                align-items: center;
                gap: 16px;
            }

            .exploration-bubble {
                background: linear-gradient(135deg, rgba(100, 140, 255, 0.3), rgba(168, 85, 247, 0.3));
                padding: 12px 16px;
                border-radius: 20px;
                font-size: 13px;
                color: #fff;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
                max-width: 150px;
            }

            .exploration-edge-label {
                background: rgba(34, 197, 94, 0.2);
                border: 1px solid rgba(34, 197, 94, 0.4);
                padding: 8px 16px;
                border-radius: 16px;
                font-size: 12px;
                color: rgba(34, 197, 94, 1);
                font-weight: 500;
            }

            .exploration-arrow {
                color: rgba(255, 255, 255, 0.4);
                font-size: 20px;
            }

            .exploration-dialog-buttons {
                display: flex;
                gap: 12px;
                flex-wrap: wrap;
            }

            .exploration-btn {
                flex: 1;
                min-width: 120px;
                padding: 12px 20px;
                border: none;
                border-radius: 8px;
                font-size: 14px;
                font-weight: 500;
                cursor: pointer;
                transition: all 0.2s ease;
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 8px;
            }

            .exploration-btn-accept {
                background: linear-gradient(135deg, #22c55e, #16a34a);
                color: white;
            }

            .exploration-btn-accept:hover {
                background: linear-gradient(135deg, #16a34a, #15803d);
                transform: translateY(-1px);
            }

            .exploration-btn-reject {
                background: linear-gradient(135deg, #ef4444, #dc2626);
                color: white;
            }

            .exploration-btn-reject:hover {
                background: linear-gradient(135deg, #dc2626, #b91c1c);
                transform: translateY(-1px);
            }

            .exploration-btn-explore {
                background: linear-gradient(135deg, #6c8cff, #a855f7);
                color: white;
            }

            .exploration-btn-explore:hover {
                background: linear-gradient(135deg, #5a7aef, #9333ea);
                transform: translateY(-1px);
            }

            .exploration-btn-secondary {
                background: rgba(255, 255, 255, 0.1);
                border: 1px solid rgba(255, 255, 255, 0.2);
                color: rgba(255, 255, 255, 0.8);
            }

            .exploration-btn-secondary:hover {
                background: rgba(255, 255, 255, 0.15);
                border-color: rgba(255, 255, 255, 0.3);
            }

            .exploration-score {
                display: inline-flex;
                align-items: center;
                gap: 6px;
                padding: 4px 10px;
                background: rgba(100, 140, 255, 0.15);
                border-radius: 12px;
                font-size: 12px;
                color: rgba(100, 140, 255, 1);
                margin-top: 12px;
            }

            .exploration-progress {
                margin-top: 16px;
                padding-top: 16px;
                border-top: 1px solid rgba(255, 255, 255, 0.1);
            }

            .exploration-progress-bar {
                height: 6px;
                background: rgba(255, 255, 255, 0.1);
                border-radius: 3px;
                overflow: hidden;
                margin-top: 8px;
            }

            .exploration-progress-fill {
                height: 100%;
                background: linear-gradient(90deg, #6c8cff, #a855f7);
                border-radius: 3px;
                transition: width 0.3s ease;
            }

            .exploration-progress-text {
                font-size: 12px;
                color: rgba(255, 255, 255, 0.6);
                display: flex;
                justify-content: space-between;
            }

            /* Status indicator */
            .exploration-status {
                position: fixed;
                bottom: 20px;
                right: 20px;
                background: rgba(30, 30, 50, 0.95);
                border: 1px solid rgba(100, 140, 255, 0.3);
                border-radius: 12px;
                padding: 12px 16px;
                z-index: 9997;
                display: flex;
                align-items: center;
                gap: 10px;
                transition: opacity 0.3s ease, transform 0.3s ease;
            }

            .exploration-status.hidden {
                opacity: 0;
                transform: translateY(20px);
                pointer-events: none;
            }

            .exploration-status-dot {
                width: 10px;
                height: 10px;
                border-radius: 50%;
                background: #22c55e;
                animation: pulse 1.5s infinite;
            }

            @keyframes pulse {
                0%, 100% { opacity: 1; }
                50% { opacity: 0.5; }
            }

            .exploration-status-text {
                color: rgba(255, 255, 255, 0.9);
                font-size: 13px;
            }
        `;
        document.head.appendChild(style);
    }

    setupEventListeners() {
        // Listen for exploration events via preload API
        if (window.vibemind) {
            window.vibemind.onExplorationQuestion((message) => {
                console.log('[ExplorationDialog] Question received:', message);
                this.showQuestion(message);
            });

            window.vibemind.onExplorationNodeDiscovered((message) => {
                this.updateNodeCount(message.node);
            });

            window.vibemind.onExplorationComplete((message) => {
                this.onExplorationComplete(message);
            });

            window.vibemind.onExplorationEvent((message) => {
                console.log('[ExplorationDialog] Event:', message.type);
                this.handleExplorationEvent(message);
            });
        }

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            if (!this.isVisible) return;

            if (e.key === 'Enter' || e.key === 'y') {
                this.respond('accept');
            } else if (e.key === 'Escape' || e.key === 'n') {
                this.respond('reject');
            } else if (e.key === 'd') {
                this.respond('explore_deeper');
            }
        });
    }

    handleExplorationEvent(message) {
        switch (message.type) {
            case 'exploration_node_discovered':
                this.explorationState.nodesDiscovered++;
                if (message.node && message.node.combined_score > this.explorationState.bestScore) {
                    this.explorationState.bestScore = message.node.combined_score;
                }
                this.updateStatusIndicator();
                break;

            case 'exploration_stage_complete':
                this.explorationState.stage = message.stage;
                this.updateStatusIndicator();
                break;

            case 'exploration_complete':
                this.explorationState.isRunning = false;
                this.hideStatusIndicator();
                break;

            case 'exploration_error':
                this.explorationState.isRunning = false;
                this.hideStatusIndicator();
                console.error('[ExplorationDialog] Error:', message.error);
                break;
        }
    }

    showQuestion(message) {
        this.currentQuestion = message;
        this.isVisible = true;

        const questionType = message.type || message.question_type;
        let html = '';

        if (questionType === 'exploration.connection_found' || questionType === 'connection_found') {
            html = this.renderConnectionQuestion(message);
        } else if (questionType === 'exploration.direction_request' || questionType === 'direction_request') {
            html = this.renderDirectionQuestion(message);
        } else if (questionType === 'exploration.stage_complete' || questionType === 'stage_complete') {
            html = this.renderStageCompleteQuestion(message);
        } else {
            html = this.renderGenericQuestion(message);
        }

        this.dialogElement.innerHTML = html;
        this.overlayElement.classList.remove('hidden');
        this.dialogElement.classList.remove('hidden');

        // Setup button handlers
        this.setupButtonHandlers();
    }

    renderConnectionQuestion(message) {
        const node = message.node || {};
        const score = node.combined_score || 0;
        const scorePercent = Math.round(score * 100);

        return `
            <div class="exploration-dialog-header">
                <div class="exploration-dialog-icon">🔗</div>
                <div>
                    <div class="exploration-dialog-title">Connection Found</div>
                    <div class="exploration-dialog-subtitle">Interactive Exploration</div>
                </div>
            </div>

            <div class="exploration-connection-preview">
                <div class="exploration-bubble">${node.source_bubble_title || 'Source'}</div>
                <div class="exploration-arrow">→</div>
                <div class="exploration-edge-label">${node.edge_label || 'connected'}</div>
                <div class="exploration-arrow">→</div>
                <div class="exploration-bubble">${node.target_bubble_title || 'Target'}</div>
            </div>

            <div class="exploration-dialog-content">
                ${node.reasoning || message.question_text || 'Should I keep this connection?'}
            </div>

            <div class="exploration-score">
                <span>Score:</span>
                <strong>${scorePercent}%</strong>
            </div>

            <div class="exploration-dialog-buttons">
                <button class="exploration-btn exploration-btn-accept" data-response="accept">
                    ✓ Keep (Y)
                </button>
                <button class="exploration-btn exploration-btn-reject" data-response="reject">
                    ✗ Reject (N)
                </button>
                <button class="exploration-btn exploration-btn-explore" data-response="explore_deeper">
                    ↓ Deeper (D)
                </button>
            </div>
        `;
    }

    renderDirectionQuestion(message) {
        const options = message.options || message.candidates || [];
        const optionsHtml = options.map((opt, i) => {
            const label = typeof opt === 'string' ? opt : opt.title;
            return `<button class="exploration-btn exploration-btn-secondary" data-response="direction" data-option="${label}">${i + 1}. ${label}</button>`;
        }).join('');

        return `
            <div class="exploration-dialog-header">
                <div class="exploration-dialog-icon">🧭</div>
                <div>
                    <div class="exploration-dialog-title">Choose Direction</div>
                    <div class="exploration-dialog-subtitle">Guided Exploration</div>
                </div>
            </div>

            <div class="exploration-dialog-content">
                ${message.question_text || 'Which area should I explore next?'}
            </div>

            <div class="exploration-dialog-buttons">
                ${optionsHtml}
            </div>
        `;
    }

    renderStageCompleteQuestion(message) {
        const stageName = message.stage || 'Stage';
        const nodesFound = message.nodes_count || message.nodes_found || 0;
        const bestScore = message.best_score || 0;
        const scorePercent = Math.round(bestScore * 100);

        return `
            <div class="exploration-dialog-header">
                <div class="exploration-dialog-icon">🎯</div>
                <div>
                    <div class="exploration-dialog-title">${stageName} completed</div>
                    <div class="exploration-dialog-subtitle">${nodesFound} connections found</div>
                </div>
            </div>

            <div class="exploration-dialog-content">
                Best score: ${scorePercent}%. Should I continue?
            </div>

            <div class="exploration-progress">
                <div class="exploration-progress-text">
                    <span>Progress</span>
                    <span>${this.getStageProgress(stageName)}</span>
                </div>
                <div class="exploration-progress-bar">
                    <div class="exploration-progress-fill" style="width: ${this.getStageProgressPercent(stageName)}%"></div>
                </div>
            </div>

            <div class="exploration-dialog-buttons">
                <button class="exploration-btn exploration-btn-accept" data-response="continue">
                    → Continue
                </button>
                <button class="exploration-btn exploration-btn-secondary" data-response="show_results">
                    👁 Show Results
                </button>
                <button class="exploration-btn exploration-btn-reject" data-response="stop">
                    ⏹ Stop
                </button>
            </div>
        `;
    }

    renderGenericQuestion(message) {
        const options = message.options || [];
        const optionsHtml = options.map((opt, i) => {
            return `<button class="exploration-btn exploration-btn-secondary" data-response="option" data-option="${opt}">${opt}</button>`;
        }).join('');

        return `
            <div class="exploration-dialog-header">
                <div class="exploration-dialog-icon">❓</div>
                <div>
                    <div class="exploration-dialog-title">Question</div>
                </div>
            </div>

            <div class="exploration-dialog-content">
                ${message.question_text || message.question || 'Please choose an option.'}
            </div>

            <div class="exploration-dialog-buttons">
                ${optionsHtml}
            </div>
        `;
    }

    getStageProgress(stageName) {
        const stages = ['DIRECT', 'INDIRECT', 'ABSTRACT', 'CREATIVE'];
        const index = stages.indexOf(stageName.toUpperCase());
        if (index >= 0) {
            return `Stage ${index + 1}/4`;
        }
        return stageName;
    }

    getStageProgressPercent(stageName) {
        const stages = ['DIRECT', 'INDIRECT', 'ABSTRACT', 'CREATIVE'];
        const index = stages.indexOf(stageName.toUpperCase());
        if (index >= 0) {
            return ((index + 1) / 4) * 100;
        }
        return 25;
    }

    setupButtonHandlers() {
        const buttons = this.dialogElement.querySelectorAll('.exploration-btn');
        buttons.forEach(btn => {
            btn.addEventListener('click', () => {
                const response = btn.dataset.response;
                const option = btn.dataset.option;
                this.respond(response, option);
            });
        });
    }

    respond(responseType, selectedOption = null) {
        if (!this.currentQuestion) return;

        const questionId = this.currentQuestion.question_id;

        console.log('[ExplorationDialog] Responding:', responseType, selectedOption);

        // Send response to Python backend
        if (window.vibemind) {
            window.vibemind.respondToExplorationQuestion(
                questionId,
                responseType,
                selectedOption,
                null // custom_text
            );
        }

        // Hide dialog
        this.hide();
    }

    hide() {
        this.isVisible = false;
        this.currentQuestion = null;
        this.overlayElement.classList.add('hidden');
        this.dialogElement.classList.add('hidden');
    }

    updateNodeCount(node) {
        this.explorationState.nodesDiscovered++;
        if (node && node.combined_score > this.explorationState.bestScore) {
            this.explorationState.bestScore = node.combined_score;
        }
        this.updateStatusIndicator();
    }

    onExplorationComplete(message) {
        this.explorationState.isRunning = false;
        this.hideStatusIndicator();

        // Show summary notification
        const summary = message.summary || `Exploration completed. ${message.stats?.total_nodes || 0} connections found.`;
        this.showNotification(summary);
    }

    showStatusIndicator() {
        let indicator = document.getElementById('exploration-status');
        if (!indicator) {
            indicator = document.createElement('div');
            indicator.id = 'exploration-status';
            indicator.className = 'exploration-status';
            document.body.appendChild(indicator);
        }

        indicator.innerHTML = `
            <div class="exploration-status-dot"></div>
            <div class="exploration-status-text">
                Exploration running... ${this.explorationState.nodesDiscovered} connections
            </div>
        `;
        indicator.classList.remove('hidden');
    }

    updateStatusIndicator() {
        const indicator = document.getElementById('exploration-status');
        if (indicator && this.explorationState.isRunning) {
            const statusText = indicator.querySelector('.exploration-status-text');
            if (statusText) {
                statusText.textContent = `${this.explorationState.stage || 'Exploration'}... ${this.explorationState.nodesDiscovered} connections`;
            }
        }
    }

    hideStatusIndicator() {
        const indicator = document.getElementById('exploration-status');
        if (indicator) {
            indicator.classList.add('hidden');
        }
    }

    showNotification(message) {
        // Simple toast notification
        const toast = document.createElement('div');
        toast.className = 'exploration-status';
        toast.style.bottom = '80px';
        toast.innerHTML = `
            <div class="exploration-dialog-icon" style="width: 24px; height: 24px; font-size: 14px;">✓</div>
            <div class="exploration-status-text">${message}</div>
        `;
        document.body.appendChild(toast);

        setTimeout(() => {
            toast.classList.add('hidden');
            setTimeout(() => toast.remove(), 300);
        }, 5000);
    }

    // Start exploration (called from UI or voice)
    startExploration(mode = 'auto', bubbleId = null, depth = 4) {
        this.explorationState = {
            isRunning: true,
            mode: mode,
            stage: 'DIRECT',
            nodesDiscovered: 0,
            bestScore: 0
        };

        if (mode !== 'auto') {
            this.showStatusIndicator();
        }

        if (window.vibemind) {
            window.vibemind.startExploration({
                bubble_id: bubbleId,
                depth: depth,
                mode: mode
            });
        }
    }
}

// Initialize when DOM is ready
let explorationDialog = null;
document.addEventListener('DOMContentLoaded', () => {
    explorationDialog = new ExplorationDialog();
    window.explorationDialog = explorationDialog;
    console.log('[ExplorationDialog] Ready');
});

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ExplorationDialog;
}
