/**
 * VibeMind Electron Preload Script
 *
 * Exposes safe IPC methods to the renderer process.
 * This bridges the renderer (Three.js) with the main process (Python backend).
 */

// Sentry renderer initialization (must be before contextBridge)
try {
    const SentryRenderer = require('@sentry/electron/renderer');
    if (process.env.SENTRY_DSN) { SentryRenderer.init(); }
} catch (e) { /* Sentry is optional */ }

const { contextBridge, ipcRenderer } = require('electron');

// Expose protected methods to the renderer
contextBridge.exposeInMainWorld('vibemind', {
    // Window controls
    minimize: () => ipcRenderer.send('window-minimize'),
    maximize: () => ipcRenderer.send('window-maximize'),
    close: () => ipcRenderer.send('window-close'),

    // Bubble interactions
    selectBubble: (bubbleId) => ipcRenderer.send('bubble-selected', bubbleId),
    enterBubble: (bubbleId) => ipcRenderer.send('enter-bubble', bubbleId),
    exitBubble: () => ipcRenderer.send('exit-bubble'),

    // Voice control
    startVoice: () => ipcRenderer.send('start-voice'),
    stopVoice: () => ipcRenderer.send('stop-voice'),

    // Send generic message to Python
    sendToPython: (message) => ipcRenderer.send('to-python', message),

    // Write renderer log to file (for autonomous debugging)
    writeLog: (level, ...args) => ipcRenderer.send('renderer-log', { level, args }),

    // Inline game console chat (renderer → main → Python → process_intent)
    sendChatMessage: (text) =>
        ipcRenderer.invoke('renderer:chat-text-input', { text }),

    // Send tool action from UI toolbar (triggers intent orchestrator directly)
    sendToolAction: (eventType, payload = {}) => ipcRenderer.send('to-python', {
        type: 'tool_action',
        event_type: eventType,
        payload: payload
    }),

    // ===== SPACE NAVIGATION =====
    
    // Navigate to a specific space
    navigateToSpace: (spaceId) => ipcRenderer.invoke('navigate-to-space', spaceId),
    
    // Get current space info
    getCurrentSpace: () => ipcRenderer.invoke('get-current-space'),
    
    // Listen for space changes
    onSpaceChanged: (callback) => {
        ipcRenderer.on('python-message', (event, message) => {
            if (message.type === 'space_changed') {
                callback(message);
            }
        });
    },
    
    // Listen for space suggestions (agent-triggered)
    onSpaceSuggestion: (callback) => {
        ipcRenderer.on('python-message', (event, message) => {
            if (message.type === 'space_suggestion') {
                callback(message);
            }
        });
    },

    // ===== AGENT TRANSFER =====
    
    // Listen for agent switches
    onAgentSwitched: (callback) => {
        ipcRenderer.on('python-message', (event, message) => {
            if (message.type === 'agent_switched') {
                callback(message);
            }
        });
    },
    
    // Get current agent info
    getCurrentAgent: () => ipcRenderer.invoke('get-current-agent'),

    // ===== HAND GESTURES =====
    
    // Send hand gesture data
    sendHandGesture: (gestureData) => ipcRenderer.invoke('hand-gesture', gestureData),
    
    // Listen for hand gesture updates (from MediaPipe)
    onHandGesture: (callback) => {
        ipcRenderer.on('python-message', (event, message) => {
            if (message.type === 'hand_gesture') {
                callback(message);
            }
        });
    },
    
    // Start/stop hand tracking
    startHandTracking: () => ipcRenderer.send('to-python', { type: 'start_hand_tracking' }),
    stopHandTracking: () => ipcRenderer.send('to-python', { type: 'stop_hand_tracking' }),

    // Listen for messages from Python backend
    onPythonMessage: (callback) => {
        ipcRenderer.on('python-message', (event, message) => {
            callback(message);
        });
    },

    // ===== IDEA EXPLORATION (AI-Scientist Tree Search) =====

    // Start exploration with mode (auto/interactive/guided)
    startExploration: (options = {}) => ipcRenderer.send('to-python', {
        type: 'exploration_start',
        ...options
    }),

    // Stop current exploration
    stopExploration: () => ipcRenderer.send('to-python', { type: 'exploration_stop' }),

    // Respond to exploration question
    respondToExplorationQuestion: (questionId, responseType, selectedOption, customText) => {
        ipcRenderer.send('to-python', {
            type: 'exploration_respond',
            question_id: questionId,
            response_type: responseType,
            selected_option: selectedOption,
            custom_text: customText
        });
    },

    // Set exploration direction (guided mode)
    setExplorationDirection: (direction, bubbleId) => ipcRenderer.send('to-python', {
        type: 'exploration_direction',
        direction: direction,
        bubble_id: bubbleId
    }),

    // Listen for exploration events
    onExplorationEvent: (callback) => {
        ipcRenderer.on('python-message', (event, message) => {
            if (message.type && message.type.startsWith('exploration')) {
                callback(message);
            }
        });
    },

    // Listen for connection found (interactive mode question)
    onExplorationQuestion: (callback) => {
        ipcRenderer.on('python-message', (event, message) => {
            if (message.type === 'exploration.connection_found' ||
                message.type === 'exploration.direction_request' ||
                message.type === 'exploration.stage_complete' ||
                message.type === 'exploration.validation_request') {
                callback(message);
            }
        });
    },

    // Listen for node discoveries
    onExplorationNodeDiscovered: (callback) => {
        ipcRenderer.on('python-message', (event, message) => {
            if (message.type === 'exploration_node_discovered') {
                callback(message);
            }
        });
    },

    // Listen for exploration completion
    onExplorationComplete: (callback) => {
        ipcRenderer.on('python-message', (event, message) => {
            if (message.type === 'exploration_complete') {
                callback(message);
            }
        });
    },

    // Listen for exploration voice (when TTS unavailable, shows text)
    onExplorationVoice: (callback) => {
        ipcRenderer.on('python-message', (event, message) => {
            if (message.type === 'exploration_voice') {
                callback(message);
            }
        });
    },

    // Listen for specific events
    onBubbleUpdate: (callback) => {
        ipcRenderer.on('python-message', (event, message) => {
            if (message.type === 'bubble_update' || message.type === 'bubbles_sync') {
                callback(message);
            }
        });
    },

    onVoiceTranscript: (callback) => {
        ipcRenderer.on('python-message', (event, message) => {
            if (message.type === 'user_transcript' || message.type === 'agent_response') {
                callback(message);
            }
        });
    },

    onNavigationCommand: (callback) => {
        ipcRenderer.on('python-message', (event, message) => {
            if (message.type === 'navigate_to_bubble' || message.type === 'enter_bubble' || message.type === 'exit_bubble') {
                callback(message);
            }
        });
    },

    // Request initial state
    requestBubbles: () => ipcRenderer.send('to-python', { type: 'get_bubbles' }),
    requestShuttles: () => ipcRenderer.send('to-python', { type: 'get_shuttles' }),

    // Canvas operations (inside bubble view)
    addCanvasNode: (bubbleId, node) => ipcRenderer.send('to-python', {
        type: 'add_canvas_node',
        bubble_id: bubbleId,
        node: node
    }),

    updateCanvasNode: (bubbleId, nodeId, updates) => ipcRenderer.send('to-python', {
        type: 'update_canvas_node',
        bubble_id: bubbleId,
        node_id: nodeId,
        updates: updates
    }),

    deleteCanvasNode: (bubbleId, nodeId) => ipcRenderer.send('to-python', {
        type: 'delete_canvas_node',
        bubble_id: bubbleId,
        node_id: nodeId
    }),

    // ===== PROJECT LIVE PREVIEW =====
    
    // Start live preview for a project (triggers Coding Engine Sandbox)
    startProjectPreview: (projectId, projectPath) => ipcRenderer.invoke('start-project-preview', { 
        project_id: projectId, 
        project_path: projectPath 
    }),
    
    // Stop running preview
    stopProjectPreview: (projectId) => ipcRenderer.send('to-python', { 
        type: 'stop_project_preview', 
        project_id: projectId 
    }),
    
    // Listen for preview ready events
    onProjectPreviewReady: (callback) => {
        ipcRenderer.on('python-message', (event, message) => {
            if (message.type === 'project_preview_ready') {
                callback(message);
            }
        });
    },
    
    // Listen for preview errors
    onProjectPreviewError: (callback) => {
        ipcRenderer.on('python-message', (event, message) => {
            if (message.type === 'project_preview_error') {
                callback(message);
            }
        });
    },
    
    // Get preview status
    getPreviewStatus: (projectId) => ipcRenderer.invoke('get-preview-status', projectId),

    // ===== CODING ENGINE DASHBOARD =====

    // Dashboard View Control
    showDashboard: () => ipcRenderer.send('show-dashboard'),
    hideDashboard: () => ipcRenderer.send('hide-dashboard'),
    isDashboardVisible: () => ipcRenderer.invoke('is-dashboard-visible'),

    // ===== ROWBOAT (ROARBOOT SPACE) =====

    // Rowboat BrowserView Control
    showRowboat: () => ipcRenderer.send('show-rowboat'),
    hideRowboat: () => ipcRenderer.send('hide-rowboat'),
    isRowboatVisible: () => ipcRenderer.invoke('is-rowboat-visible'),

    // ===== CLAUDE CODE TOKEN =====

    // Get Claude Code OAuth token (for Settings UI auto-detect)
    getClaudeCodeToken: () => ipcRenderer.invoke('get-claude-code-token'),

    // ===== SWE DESIGN (FACTORY SPACE) =====

    // SWE Design BrowserView Control
    showSweDesign: () => ipcRenderer.send('show-swedesign'),
    hideSweDesign: () => ipcRenderer.send('hide-swedesign'),
    isSweDesignVisible: () => ipcRenderer.invoke('is-swedesign-visible'),

    // ===== CLAWPORT DASHBOARD =====

    // ClawPort BrowserView Control
    showClawPort: () => ipcRenderer.send('show-clawport'),
    hideClawPort: () => ipcRenderer.send('hide-clawport'),
    isClawPortVisible: () => ipcRenderer.invoke('is-clawport-visible'),

    // ===== BRAIN DASHBOARD =====

    // Brain BrowserView Control
    showBrain: () => ipcRenderer.send('show-brain'),
    hideBrain: () => ipcRenderer.send('hide-brain'),
    isBrainVisible: () => ipcRenderer.invoke('is-brain-visible'),

    // ===== AGENT FARM =====

    // Agent Farm BrowserView Control
    showAgentFarm: () => ipcRenderer.send('show-agentfarm'),
    showAgentFarmTab: (tab) => ipcRenderer.send('show-agentfarm-tab', tab),
    hideAgentFarm: () => ipcRenderer.send('hide-agentfarm'),
    isAgentFarmVisible: () => ipcRenderer.invoke('is-agentfarm-visible'),

    // MiroFish BrowserView Control
    showMiroFish: () => ipcRenderer.send('show-mirofish'),
    hideMiroFish: () => ipcRenderer.send('hide-mirofish'),
    isMiroFishVisible: () => ipcRenderer.invoke('is-mirofish-visible'),

    // Flowzen Diary (Blue Rose Journal) BrowserView Control
    showFlowzen: () => ipcRenderer.send('show-flowzen'),
    hideFlowzen: () => ipcRenderer.send('hide-flowzen'),
    isFlowzenVisible: () => ipcRenderer.invoke('is-flowzen-visible'),

    // Video Space BrowserView Control
    showVideo: () => ipcRenderer.send('show-video'),
    hideVideo: () => ipcRenderer.send('hide-video'),

    // Docker Management (for Coding Engine containers)
    docker: {
        startEngine: () => ipcRenderer.invoke('docker:start-engine'),
        stopEngine: () => ipcRenderer.invoke('docker:stop-engine'),
        getEngineStatus: () => ipcRenderer.invoke('docker:get-engine-status'),
        startProject: (projectId, outputDir) =>
            ipcRenderer.invoke('docker:start-project', { projectId, outputDir }),
        stopProject: (projectId) =>
            ipcRenderer.invoke('docker:stop-project', projectId),
        getProjectStatus: (projectId) =>
            ipcRenderer.invoke('docker:get-project-status', projectId),
        getProjectLogs: (projectId, tail) =>
            ipcRenderer.invoke('docker:get-project-logs', { projectId, tail }),
    },

    // Port Allocation (VNC and App preview ports)
    ports: {
        getVncPort: (projectId) => ipcRenderer.invoke('ports:get-vnc-port', projectId),
        getAppPort: (projectId) => ipcRenderer.invoke('ports:get-app-port', projectId),
        getAll: () => ipcRenderer.invoke('ports:get-all'),
    },

    // Engine Control (Code Generation)
    engine: {
        startGeneration: (requirementsPath, outputDir) =>
            ipcRenderer.invoke('engine:start-generation', { requirementsPath, outputDir }),
        getApiUrl: () => ipcRenderer.invoke('engine:get-api-url'),
        // Claude Code Runner (persistent Docker container with VNC)
        claudeRunner: {
            start: (repoPath, options) =>
                ipcRenderer.invoke('engine:start-claude-runner', repoPath, options),
            stop: () =>
                ipcRenderer.invoke('engine:stop-claude-runner'),
            getStatus: () =>
                ipcRenderer.invoke('engine:get-claude-runner-status'),
        },
    },

    // File System Operations
    fs: {
        openFolder: (path) => ipcRenderer.invoke('fs:open-folder', path),
        showInExplorer: (path) => ipcRenderer.invoke('fs:show-in-explorer', path),
    },

    // Projects (Orchestrator API)
    projects: {
        getAll: () => ipcRenderer.invoke('projects:get-all'),
        get: (id) => ipcRenderer.invoke('projects:get', id),
        create: (data) => ipcRenderer.invoke('projects:create', data),
        delete: (id) => ipcRenderer.invoke('projects:delete', id),
        getStatus: (id) => ipcRenderer.invoke('projects:get-status', id),
    },
});

console.log('[Preload] VibeMind API exposed to renderer (with Space Navigation + Hand Gestures + Project Preview + Shuttles + Dashboard + Exploration)');
