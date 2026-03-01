/**
 * VibeMind Electron Main Process
 *
 * Manages the main window, Python backend process,
 * and IPC communication between renderer and Python.
 */

const { app, BrowserWindow, ipcMain, Tray, Menu, globalShortcut, shell } = require('electron');
const { spawn } = require('child_process');

const path = require('path');
const fs = require('fs');

// Load root .env so all config lives in one place
require('dotenv').config({ path: path.join(__dirname, '..', '.env') });

// Coding Engine Dashboard Integration
const DockerManager = require('./docker-manager');
const PortAllocator = require('./port-allocator');
const DashboardManager = require('./dashboard-manager');

// Rowboat (Roarboot Space) Integration
const RowboatManager = require('./rowboat-manager');

// SWE Design (Factory Space) Integration
const SweDesignManager = require('./swe-design-manager');

// Enable remote debugging port for CDP (Chrome DevTools Protocol)
// This allows external tools to connect and manipulate the renderer
// Safety check: only set if app is available (not running as Node)
if (app && app.commandLine) {
    app.commandLine.appendSwitch('remote-debugging-port', '9223');
}

// Note: GPU flags are now passed via command line when starting electron:
// electron . --disable-gpu --enable-unsafe-swiftshader --enable-webgl --ignore-gpu-blocklist

let mainWindow = null;
let pythonProcess = null;
let tray = null;

// Coding Engine Dashboard managers
let dockerManager = null;
let portAllocator = null;
let dashboardManager = null;

// Rowboat (Roarboot Space) manager
let rowboatManager = null;

// SWE Design (Factory Space) manager
let sweDesignManager = null;

// Rowboat @x/core services (esbuild CJS bundle)
let rowboatServices = null;
try {
    rowboatServices = require('./rowboat-services.cjs');
    console.log('[Main] Rowboat services loaded successfully');
} catch (e) {
    console.warn('[Main] Rowboat services not found — run: npm run build:rowboat');
    console.warn('[Main] Error:', e.message);
}

/**
 * Auto-configure Rowboat's ~/.rowboat/config/models.json from VibeMind .env
 * Only writes if no apiKey is configured yet (first-time setup).
 */
async function autoConfigureRowboatModels() {
    const os = require('os');
    const modelsPath = path.join(os.homedir(), '.rowboat', 'config', 'models.json');
    try {
        let currentConfig = null;
        try {
            const raw = await fs.promises.readFile(modelsPath, 'utf8');
            currentConfig = JSON.parse(raw);
        } catch { /* file doesn't exist yet — will create */ }

        // Determine desired config from .env (Priority: ANTHROPIC > OPENROUTER > OPENAI)
        let desiredConfig = null;
        let source = '';

        const anthropicKey = process.env.ANTHROPIC_API_KEY;
        if (anthropicKey && !anthropicKey.includes('DEIN_KEY') && !anthropicKey.includes('your_')) {
            desiredConfig = {
                provider: { flavor: 'anthropic', apiKey: anthropicKey },
                model: process.env.ROWBOAT_MODEL || 'claude-sonnet-4-20250514',
            };
            source = 'Anthropic';
        } else if (process.env.OPENROUTER_API_KEY) {
            desiredConfig = {
                provider: { flavor: 'openrouter', apiKey: process.env.OPENROUTER_API_KEY },
                model: process.env.ROWBOAT_MODEL || 'anthropic/claude-sonnet-4',
            };
            source = 'OpenRouter';
        } else if (process.env.OPENAI_API_KEY) {
            desiredConfig = {
                provider: { flavor: 'openai', apiKey: process.env.OPENAI_API_KEY },
                model: process.env.ROWBOAT_MODEL || 'gpt-4.1',
            };
            source = 'OpenAI';
        }

        if (!desiredConfig) {
            console.log('[Main] No LLM API key found in .env — configure in Roarboot Settings');
            return;
        }

        // Always write if: no config yet, different provider flavor, or different apiKey
        const needsUpdate = !currentConfig
            || !currentConfig.provider
            || currentConfig.provider.flavor !== desiredConfig.provider.flavor
            || currentConfig.provider.apiKey !== desiredConfig.provider.apiKey;

        if (needsUpdate) {
            await fs.promises.writeFile(modelsPath, JSON.stringify(desiredConfig, null, 2));
            console.log(`[Main] Rowboat auto-configured with ${source} from .env`);
        } else {
            console.log(`[Main] Rowboat models already match .env (${source}), skipping`);
        }
    } catch (e) {
        console.warn('[Main] Could not auto-configure Rowboat models:', e.message);
    }
}

// Current space tracking
let currentSpace = 'ideas';  // 'ideas', 'desktop', or 'projects'
let currentAgent = 'rachel';  // Active agent slug

// Debug flag - set to true for verbose logging
const DEBUG = true;

function debugLog(...args) {
    if (DEBUG) {
        console.log('[DEBUG]', new Date().toISOString(), ...args);
    }
}

// ============================================================================

function createWindow() {
    debugLog('Creating main window...');
    mainWindow = new BrowserWindow({
        width: 1400,
        height: 900,
        minWidth: 800,
        minHeight: 600,
        frame: false,           // Frameless for custom titlebar
        transparent: false,     // Disable for reliable WebGL rendering
        backgroundColor: '#050510',
        webPreferences: {
            preload: path.join(__dirname, 'preload.js'),
            contextIsolation: true,
            nodeIntegration: false,
        },
        icon: path.join(__dirname, 'build', 'icon.png'),
    });

    // Grant microphone permission for Vapi voice dashboard (iframe at localhost:8007)
    mainWindow.webContents.session.setPermissionRequestHandler((webContents, permission, callback) => {
        const allowedPermissions = ['media', 'microphone', 'audioCapture'];
        if (allowedPermissions.includes(permission)) {
            callback(true);
        } else {
            callback(false);
        }
    });

    mainWindow.loadFile('renderer/index.html');

    // Open DevTools in detached window so BrowserView overlays (Coding Engine,
    // Rowboat, SWE Design) don't cover it — BrowserView renders above docked DevTools
    mainWindow.webContents.openDevTools({ mode: 'detach' });

    mainWindow.on('closed', () => {
        mainWindow = null;
    });

    // Handle window controls from renderer
    ipcMain.on('window-minimize', () => mainWindow && mainWindow.minimize());
    ipcMain.on('window-maximize', () => {
        if (mainWindow) {
            if (mainWindow.isMaximized()) {
                mainWindow.unmaximize();
            } else {
                mainWindow.maximize();
            }
        }
    });
    ipcMain.on('window-close', () => mainWindow && mainWindow.close());
}

// ============================================================================

function startPythonBackend() {
    // Use venv Python 3.12 to ensure MediaPipe and all dependencies are available
    const pythonPath = process.platform === 'win32'
        ? path.join(__dirname, '..', '.venv312', 'Scripts', 'python.exe')
        : path.join(__dirname, '..', '.venv312', 'bin', 'python');
    const backendPath = path.join(__dirname, '..', 'python', 'electron_backend.py');

    console.log('[Main] ================================================');
    console.log('[Main] Starting Python backend');
    console.log('[Main] Python path:', pythonPath);
    console.log('[Main] Backend path:', backendPath);
    console.log('[Main] CWD:', path.join(__dirname, '..', 'python'));
    console.log('[Main] ================================================');
    
    // Check if Python exists
    const fs = require('fs');
    if (!fs.existsSync(pythonPath)) {
        console.error('[Main] ERROR: Python not found at:', pythonPath);
        console.error('[Main] Make sure .venv312 is created: py -3.12 -m venv .venv312');
        return;
    }
    
    if (!fs.existsSync(backendPath)) {
        console.error('[Main] ERROR: Backend not found at:', backendPath);
        return;
    }

    pythonProcess = spawn(pythonPath, [backendPath], {
        stdio: ['pipe', 'pipe', 'pipe'],
        cwd: path.join(__dirname, '..', 'python'),
    });
    
    console.log('[Main] Python process started with PID:', pythonProcess.pid);

    // Handle stdout from Python (JSON messages)
    pythonProcess.stdout.on('data', (data) => {
        const lines = data.toString().split('\n').filter(l => l.trim());
        for (const line of lines) {
            try {
                const message = JSON.parse(line);
                
                // Log all Python messages for debugging
                console.log('[Python→Electron]:', JSON.stringify(message).substring(0, 200));
                
                // Log errors specifically
                if (message.type === 'voice_error' || message.error) {
                    console.error('[Python ERROR]:', message.error || JSON.stringify(message));
                }
                
                // Handle agent transfer messages
                if (message.type === 'agent_transfer_complete') {
                    handleAgentTransfer(message);
                }
                
                // Handle space navigation
                if (message.type === 'navigate_to_space') {
                    handleSpaceNavigation(message);
                }

                // Handle Rowboat update available — relay to BrowserView
                if (message.type === 'rowboat_update_available') {
                    rowboatManager?.relayEvent('rowboat:updateAvailable', message);
                }

                // Handle structured content updates
                if (message.type === 'node_structured_update') {
                    debugLog('Structured content update:', message.node_id);
                }
                
                // Forward to renderer
                if (mainWindow && mainWindow.webContents) {
                    mainWindow.webContents.send('python-message', message);
                    debugLog('Forwarded to renderer:', message.type);
                } else {
                    console.warn('[Main] Cannot forward - mainWindow not ready');
                }
            } catch (e) {
                // Non-JSON output (debug logs from Python)
                console.log('[Python stdout]:', line);
            }
        }
    });

    // Handle stderr from Python (errors/logs)
    pythonProcess.stderr.on('data', (data) => {
        const output = data.toString().trim();
        if (output) {
            console.error('[Python stderr]:', output);
        }
    });

    pythonProcess.on('close', (code) => {
        console.log('[Main] Python process exited with code:', code);
        if (code !== 0) {
            console.error('[Main] Python crashed! Check the errors above.');
        }
        pythonProcess = null;
    });

    pythonProcess.on('error', (err) => {
        console.error('[Main] Failed to start Python:', err);
    });
}

function sendToPython(message) {
    if (pythonProcess && pythonProcess.stdin) {
        const json = JSON.stringify(message);
        console.log('[Electron→Python]:', json.substring(0, 200));
        pythonProcess.stdin.write(json + '\n');
    } else {
        console.error('[Main] Cannot send to Python - process not running');
    }
}

// ============================================================================
// MULTIVERSE HANDLERS
// ============================================================================

// Agent to Space mapping for automatic navigation
const AGENT_SPACE_MAP = {
    'rachel': 'ideas',
    'alice': 'ideas',      // Alice is the hub, stays in ideas
    'adam': 'desktop',
    'antoni': 'projects',
    'multiverse': 'ideas',
    'sofia': 'projects',   // Sofia is the project manager
    'rowboat': 'roarboot', // Rowboat agent → Roarboot space
};

function handleAgentTransfer(message) {
    /**
     * Handle agent transfer completion.
     * Updates current agent and AUTOMATICALLY navigates to the matching space.
     */
    const { from_agent, to_agent, target_agent_id } = message;
    
    console.log(`[Main] Agent Transfer: ${from_agent} → ${to_agent}`);
    currentAgent = to_agent;
    
    // Determine target space for the new agent
    const targetSpace = AGENT_SPACE_MAP[to_agent.toLowerCase()] || 'ideas';
    const shouldNavigate = targetSpace !== currentSpace;
    
    console.log(`[Main] Agent ${to_agent} belongs to space: ${targetSpace}, current: ${currentSpace}`);
    
    // Send visual feedback to renderer with navigation info
    if (mainWindow && mainWindow.webContents) {
        mainWindow.webContents.send('python-message', {
            type: 'agent_switched',
            from_agent: from_agent,
            to_agent: to_agent,
            current_agent: currentAgent,
            target_space: targetSpace,
            auto_navigate: shouldNavigate,  // Flag for automatic navigation
        });
    }
    
    // AUTOMATIC NAVIGATION - if agent is in a different space, navigate there
    if (shouldNavigate) {
        console.log(`[Main] Auto-navigating to ${targetSpace} for agent ${to_agent}`);
        currentSpace = targetSpace;
        
        // Send space_changed to trigger animated navigation
        if (mainWindow && mainWindow.webContents) {
            mainWindow.webContents.send('python-message', {
                type: 'space_changed',
                space: targetSpace,
                reason: `Agent ${to_agent} works in ${targetSpace} space`,
            });
        }
        
        // Also notify Python backend
        sendToPython({ type: 'navigate_to_space', space: targetSpace });
    }
}

function handleSpaceNavigation(message) {
    /**
     * Handle space navigation from Python (voice command).
     */
    const { target_space } = message;
    
    if (target_space && target_space !== currentSpace) {
        console.log(`[Main] Navigating to space: ${target_space}`);
        currentSpace = target_space;
        
        // Send space change to renderer
        if (mainWindow && mainWindow.webContents) {
            mainWindow.webContents.send('python-message', {
                type: 'space_changed',
                space: currentSpace,
            });
        }
    }
}

// ============================================================================

// RE Project Helpers (ported from Coding_engine/dashboard-app/out/main/main.js)
function readREProjectSummary(projectDir, folderName) {
    let projectName = folderName;
    const techStackTags = [];
    let architecturePattern = '';
    let requirementsCount = 0;
    let userStoriesCount = 0;
    let tasksCount = 0;
    let diagramCount = 0;
    let qualityIssues = { critical: 0, high: 0, medium: 0 };
    let hasApiSpec = false;
    let hasMasterDocument = false;

    const techStackPath = path.join(projectDir, 'tech_stack', 'tech_stack.json');
    if (fs.existsSync(techStackPath)) {
        try {
            const data = JSON.parse(fs.readFileSync(techStackPath, 'utf-8'));
            const rawName = data.project_name || '';
            projectName = rawName && rawName !== 'unnamed_project' ? rawName : folderName;
            architecturePattern = data.architecture_pattern || '';
            if (data.frontend_framework) techStackTags.push(data.frontend_framework);
            if (data.backend_framework) techStackTags.push(data.backend_framework);
            if (data.primary_database) techStackTags.push(data.primary_database);
            if (data.cache_layer && data.cache_layer !== 'none') techStackTags.push(data.cache_layer);
        } catch { /* ignore */ }
    }

    const userStoriesPaths = [
        path.join(projectDir, 'user_stories', 'user_stories.json'),
        path.join(projectDir, 'user_stories.json'),
    ];
    const userStoriesJsonPath = userStoriesPaths.find((p) => fs.existsSync(p)) || '';
    if (userStoriesJsonPath) {
        try {
            const data = JSON.parse(fs.readFileSync(userStoriesJsonPath, 'utf-8'));
            if (Array.isArray(data)) {
                userStoriesCount = data.length;
                const reqIds = new Set();
                for (const story of data) {
                    if (story.linked_requirement) reqIds.add(story.linked_requirement);
                }
                requirementsCount = reqIds.size || userStoriesCount;
            }
        } catch { /* ignore */ }
    }

    const taskListPath = path.join(projectDir, 'tasks', 'task_list.json');
    if (fs.existsSync(taskListPath)) {
        try {
            const data = JSON.parse(fs.readFileSync(taskListPath, 'utf-8'));
            tasksCount = data.total_tasks || 0;
            if (!tasksCount && data.features) {
                for (const tasks of Object.values(data.features)) {
                    if (Array.isArray(tasks)) tasksCount += tasks.length;
                }
            }
        } catch { /* ignore */ }
    }

    const diagramsDir = path.join(projectDir, 'diagrams');
    if (fs.existsSync(diagramsDir)) {
        try {
            const files = fs.readdirSync(diagramsDir);
            diagramCount = files.filter((f) => f.endsWith('.mmd') || f.endsWith('.md')).length;
        } catch { /* ignore */ }
    }

    const qualityPath = path.join(projectDir, 'quality', 'self_critique_report.json');
    if (fs.existsSync(qualityPath)) {
        try {
            const data = JSON.parse(fs.readFileSync(qualityPath, 'utf-8'));
            const bySeverity = data.summary?.by_severity || {};
            qualityIssues = {
                critical: bySeverity.critical || 0,
                high: bySeverity.high || 0,
                medium: bySeverity.medium || 0,
            };
        } catch { /* ignore */ }
    }

    hasApiSpec = fs.existsSync(path.join(projectDir, 'api', 'openapi_spec.yaml'))
        || fs.existsSync(path.join(projectDir, 'api', 'api_documentation.md'));
    hasMasterDocument = fs.existsSync(path.join(projectDir, 'MASTER_DOCUMENT.md'));

    return {
        project_id: folderName,
        project_name: projectName,
        project_path: projectDir,
        source: 'local_re',
        tech_stack_tags: techStackTags,
        architecture_pattern: architecturePattern,
        requirements_count: requirementsCount,
        user_stories_count: userStoriesCount,
        tasks_count: tasksCount,
        diagram_count: diagramCount,
        quality_issues: qualityIssues,
        has_api_spec: hasApiSpec,
        has_master_document: hasMasterDocument,
    };
}

function readREProjectDetail(projectDir) {
    const folderName = path.basename(projectDir);
    const summary = readREProjectSummary(projectDir, folderName);

    const tasksByFeature = {};
    const taskListPath = path.join(projectDir, 'tasks', 'task_list.json');
    if (fs.existsSync(taskListPath)) {
        try {
            const data = JSON.parse(fs.readFileSync(taskListPath, 'utf-8'));
            for (const [featureId, tasks] of Object.entries(data.features || {})) {
                if (Array.isArray(tasks)) {
                    tasksByFeature[featureId] = tasks.map((t) => ({
                        id: t.id || '',
                        title: t.title || '',
                        task_type: t.task_type || '',
                        complexity: t.complexity || 'medium',
                        estimated_hours: t.estimated_hours || 0,
                    }));
                }
            }
        } catch { /* ignore */ }
    }

    let qualityIssuesList = [];
    const qualityPath = path.join(projectDir, 'quality', 'self_critique_report.json');
    if (fs.existsSync(qualityPath)) {
        try {
            const data = JSON.parse(fs.readFileSync(qualityPath, 'utf-8'));
            qualityIssuesList = (data.issues || []).map((i) => ({
                id: i.id || '',
                category: i.category || '',
                severity: i.severity || 'medium',
                title: i.title || '',
            }));
        } catch { /* ignore */ }
    }

    let masterDocExcerpt = '';
    const masterDocPath = path.join(projectDir, 'MASTER_DOCUMENT.md');
    if (fs.existsSync(masterDocPath)) {
        try {
            const content = fs.readFileSync(masterDocPath, 'utf-8');
            masterDocExcerpt = content.slice(0, 2000);
        } catch { /* ignore */ }
    }

    let featureBreakdown = [];
    const fbPath = path.join(projectDir, 'work_breakdown', 'feature_breakdown.json');
    if (fs.existsSync(fbPath)) {
        try {
            const data = JSON.parse(fs.readFileSync(fbPath, 'utf-8'));
            for (const [featId, feat] of Object.entries(data.features || {})) {
                featureBreakdown.push({
                    feature_id: feat.feature_id || featId,
                    feature_name: feat.feature_name || '',
                    requirements: feat.requirements || [],
                });
            }
        } catch { /* ignore */ }
    }

    let techStackFull = {};
    const techStackPath = path.join(projectDir, 'tech_stack', 'tech_stack.json');
    if (fs.existsSync(techStackPath)) {
        try {
            const data = JSON.parse(fs.readFileSync(techStackPath, 'utf-8'));
            for (const [key, val] of Object.entries(data)) {
                if (typeof val === 'string') techStackFull[key] = val;
            }
        } catch { /* ignore */ }
    }

    return {
        ...summary,
        tech_stack_full: techStackFull,
        tasks_by_feature: tasksByFeature,
        quality_issues_list: qualityIssuesList,
        master_document_excerpt: masterDocExcerpt,
        feature_breakdown: featureBreakdown,
    };
}

function setupIpcHandlers() {
    // Forward messages from renderer to Python
    ipcMain.on('to-python', (event, message) => {
        sendToPython(message);
    });

    // Handle specific actions
    ipcMain.on('bubble-selected', (event, bubbleId) => {
        sendToPython({ type: 'bubble_selected', bubble_id: bubbleId });
    });

    ipcMain.on('enter-bubble', (event, bubbleId) => {
        sendToPython({ type: 'enter_bubble', bubble_id: bubbleId });
    });

    ipcMain.on('exit-bubble', (event) => {
        sendToPython({ type: 'exit_bubble' });
    });

    ipcMain.on('start-voice', (event) => {
        sendToPython({ type: 'start_voice' });
    });

    ipcMain.on('stop-voice', (event) => {
        sendToPython({ type: 'stop_voice' });
    });

    // Canvas operations (inside bubble view)
    ipcMain.on('add_canvas_node', (event, data) => {
        sendToPython({
            type: 'add_canvas_node',
            bubble_id: data.bubble_id,
            node: data.node
        });
    });

    ipcMain.on('update_canvas_node', (event, data) => {
        sendToPython({
            type: 'update_canvas_node',
            bubble_id: data.bubble_id,
            node_id: data.node_id,
            updates: data.updates
        });
    });

    ipcMain.on('delete_canvas_node', (event, data) => {
        sendToPython({
            type: 'delete_canvas_node',
            bubble_id: data.bubble_id,
            node_id: data.node_id
        });
    });
    
    // ========================================
    // MULTIVERSE NAVIGATION
    // ========================================
    
    ipcMain.handle('navigate-to-space', (event, spaceName) => {
        console.log('[Main] IPC: navigate-to-space:', spaceName);
        currentSpace = spaceName;
        sendToPython({ type: 'navigate_to_space', space: spaceName });
        
        // Send space_changed notification to renderer
        if (mainWindow && mainWindow.webContents) {
            mainWindow.webContents.send('python-message', {
                type: 'space_changed',
                space: currentSpace,
            });
        }
        return { success: true, space: currentSpace };
    });
    
    ipcMain.handle('get-current-space', (event) => {
        return { space: currentSpace };
    });
    
    ipcMain.handle('get-current-agent', (event) => {
        return { agent: currentAgent };
    });
    
    // ========================================
    // HAND MOTION DATA (from Python)
    // ========================================
    
    ipcMain.handle('hand-gesture', (event, gestureData) => {
        // Forward hand gesture to renderer for visualization
        if (mainWindow && mainWindow.webContents) {
            mainWindow.webContents.send('python-message', {
                type: 'hand_gesture',
                ...gestureData,
            });
        }
        return { success: true };
    });
    
    // ========================================
    // SPACE-SPECIFIC ACTIONS
    // ========================================
    
    ipcMain.on('desktop-action', (event, action) => {
        // Forward desktop automation actions to Python
        sendToPython({
            type: 'desktop_action',
            action: action,
        });
    });
    
    // ========================================
    // PROJECT LIVE PREVIEW (Coding Engine Integration)
    // ========================================
    
    // Track active project previews
    const activeProjectPreviews = new Map();
    
    ipcMain.handle('start-project-preview', async (event, data) => {
        /**
         * Start a live preview sandbox for a project.
         * Sends request to Python backend which manages Docker containers.
         */
        const { projectId, projectPath } = data;
        
        console.log(`[Main] Starting project preview: ${projectId}`);
        console.log(`[Main] Project path: ${projectPath}`);
        
        // Check if preview is already running
        if (activeProjectPreviews.has(projectId)) {
            const existing = activeProjectPreviews.get(projectId);
            if (existing.status === 'running') {
                console.log(`[Main] Preview already running for ${projectId}`);
                return {
                    success: true,
                    status: 'already_running',
                    vncUrl: existing.vncUrl,
                };
            }
        }
        
        // Mark as starting
        activeProjectPreviews.set(projectId, {
            status: 'starting',
            startTime: Date.now(),
        });
        
        // Send to Python backend for Docker/VNC setup
        sendToPython({
            type: 'start_project_preview',
            project_id: projectId,
            project_path: projectPath,
            enable_vnc: true,
            vnc_resolution: '1280x720',
        });
        
        // Notify renderer that preview is starting
        if (mainWindow && mainWindow.webContents) {
            mainWindow.webContents.send('python-message', {
                type: 'project_preview_starting',
                projectId: projectId,
            });
        }
        
        return {
            success: true,
            status: 'starting',
            projectId: projectId,
        };
    });
    
    ipcMain.handle('stop-project-preview', async (event, projectId) => {
        /**
         * Stop a running project preview.
         */
        console.log(`[Main] Stopping project preview: ${projectId}`);
        
        if (!activeProjectPreviews.has(projectId)) {
            return { success: false, error: 'Preview not found' };
        }
        
        // Send stop request to Python
        sendToPython({
            type: 'stop_project_preview',
            project_id: projectId,
        });
        
        // Update tracking
        activeProjectPreviews.delete(projectId);
        
        // Notify renderer
        if (mainWindow && mainWindow.webContents) {
            mainWindow.webContents.send('python-message', {
                type: 'project_preview_stopped',
                projectId: projectId,
            });
        }
        
        return { success: true };
    });
    
    ipcMain.handle('get-preview-status', async (event, projectId) => {
        /**
         * Get the status of a project preview.
         */
        if (!activeProjectPreviews.has(projectId)) {
            return { status: 'not_running' };
        }
        return activeProjectPreviews.get(projectId);
    });
    
    // Handle preview ready events from Python
    ipcMain.on('project-preview-update', (event, data) => {
        /**
         * Update from Python about preview status.
         * Called when Docker container is ready with VNC.
         */
        const { projectId, status, vncUrl, error } = data;

        if (status === 'ready') {
            activeProjectPreviews.set(projectId, {
                status: 'running',
                vncUrl: vncUrl,
                startTime: Date.now(),
            });

            // Forward to renderer
            if (mainWindow && mainWindow.webContents) {
                mainWindow.webContents.send('python-message', {
                    type: 'project_preview_ready',
                    projectId: projectId,
                    vncUrl: vncUrl,
                });
            }
        } else if (status === 'error') {
            activeProjectPreviews.set(projectId, {
                status: 'error',
                error: error,
            });

            if (mainWindow && mainWindow.webContents) {
                mainWindow.webContents.send('python-message', {
                    type: 'project_preview_error',
                    projectId: projectId,
                    error: error,
                });
            }
        }
    });

    // ========================================
    // CODING ENGINE DASHBOARD INTEGRATION
    // ========================================

    // Docker Management
    ipcMain.handle('docker:start-engine', async () => {
        if (!dockerManager) return { success: false, error: 'Docker manager not initialized' };
        return await dockerManager.startEngine();
    });

    ipcMain.handle('docker:stop-engine', async () => {
        if (!dockerManager) return { success: false, error: 'Docker manager not initialized' };
        return await dockerManager.stopEngine();
    });

    ipcMain.handle('docker:get-engine-status', async () => {
        if (!dockerManager) return { running: false, services: [] };
        return await dockerManager.getEngineStatus();
    });

    ipcMain.handle('docker:start-project', async (event, data) => {
        if (!dockerManager || !portAllocator) {
            return { success: false, error: 'Managers not initialized' };
        }
        const { projectId, outputDir } = data;
        const vncPort = portAllocator.allocate(projectId);
        const appPort = portAllocator.allocateAppPort(projectId);
        return await dockerManager.startProjectContainer(projectId, outputDir, vncPort, appPort);
    });

    ipcMain.handle('docker:stop-project', async (event, projectId) => {
        if (!dockerManager || !portAllocator) {
            return { success: false, error: 'Managers not initialized' };
        }
        portAllocator.release(projectId);
        return await dockerManager.stopProjectContainer(projectId);
    });

    ipcMain.handle('docker:get-project-status', async (event, projectId) => {
        if (!dockerManager) return { running: false };
        return await dockerManager.getProjectStatus(projectId);
    });

    ipcMain.handle('docker:get-project-logs', async (event, data) => {
        if (!dockerManager) return '';
        const { projectId, tail } = data;
        return await dockerManager.getProjectLogs(projectId, tail || 100);
    });

    // Port Allocation
    ipcMain.handle('ports:get-vnc-port', async (event, projectId) => {
        if (!portAllocator) return null;
        return portAllocator.getVncPort(projectId);
    });

    ipcMain.handle('ports:get-app-port', async (event, projectId) => {
        if (!portAllocator) return null;
        return portAllocator.getAppPort(projectId);
    });

    ipcMain.handle('ports:get-all', async () => {
        if (!portAllocator) return {};
        return portAllocator.getAllAllocations();
    });

    // Engine Control
    ipcMain.handle('engine:start-generation', async (event, data) => {
        if (!dockerManager) return { success: false, error: 'Docker manager not initialized' };
        const { requirementsPath, outputDir } = data;
        return await dockerManager.startGeneration(requirementsPath, outputDir);
    });

    ipcMain.handle('engine:get-api-url', async () => {
        if (!dockerManager) return 'http://localhost:8000';
        return dockerManager.getApiUrl();
    });

    ipcMain.handle('engine:start-generation-with-preview', async (event, projectId, requirementsPath, outputDir, forceGenerate = false) => {
        if (!dockerManager || !portAllocator) return { success: false, error: 'Managers not initialized' };
        try {
            const engineRoot = process.env.CODING_ENGINE_PATH || path.join(__dirname, '..', 'python', 'spaces', 'coding', 'Coding_engine');
            let localPath = requirementsPath;
            if (requirementsPath.startsWith('/app/projects/')) {
                const relative = requirementsPath.replace('/app/projects/', '');
                localPath = path.join(engineRoot, 'Data', 'all_services', relative);
            }
            const vncPort = portAllocator.allocate(projectId);
            const appPort = portAllocator.allocateAppPort(projectId);
            const absOutputDir = outputDir.startsWith('.') ? path.join(engineRoot, outputDir.replace(/^\.\//, '')) : outputDir;
            return await dockerManager.startGenerationWithPreview(projectId, localPath, absOutputDir, vncPort, appPort, forceGenerate);
        } catch (error) {
            console.error('[Generation] Error:', error);
            return { success: false, error: error.message };
        }
    });

    ipcMain.handle('engine:start-orchestrator-generation-with-preview', async (event, projectId, projectPath, outputDir) => {
        if (!dockerManager || !portAllocator) return { success: false, error: 'Managers not initialized' };
        try {
            const engineRoot = process.env.CODING_ENGINE_PATH || path.join(__dirname, '..', 'python', 'spaces', 'coding', 'Coding_engine');
            const absOutputDir = outputDir.startsWith('.') ? path.join(engineRoot, outputDir.replace(/^\.\//, '')) : outputDir;
            const vncPort = portAllocator.allocate(projectId);
            const appPort = portAllocator.allocateAppPort(projectId);
            return await dockerManager.startGenerationWithPreview(projectId, projectPath, absOutputDir, vncPort, appPort, true);
        } catch (error) {
            console.error('[Orchestrator Generation] Error:', error);
            return { success: false, error: error.message };
        }
    });

    ipcMain.handle('engine:stop-generation', async (event, projectId) => {
        if (!dockerManager || !portAllocator) return { success: false, error: 'Managers not initialized' };
        portAllocator.release(projectId);
        return await dockerManager.stopGeneration(projectId);
    });

    ipcMain.handle('engine:start-epic-generation', async (event, projectId, projectPath, outputDir) => {
        if (!dockerManager || !portAllocator) return { success: false, error: 'Managers not initialized' };
        try {
            const vncPort = portAllocator.allocate(projectId);
            const appPort = portAllocator.allocateAppPort(projectId);
            return await dockerManager.startEpicGeneration(projectId, projectPath, outputDir, vncPort, appPort);
        } catch (error) {
            console.error('[EpicGeneration] Error:', error);
            return { success: false, error: error.message };
        }
    });

    ipcMain.handle('engine:get-epics', async (event, projectPath) => {
        if (!dockerManager) return { success: false, error: 'Docker manager not initialized' };
        return await dockerManager.getEpics(projectPath);
    });

    ipcMain.handle('engine:get-epic-tasks', async (event, epicId, projectPath) => {
        if (!dockerManager) return { success: false, error: 'Docker manager not initialized' };
        return await dockerManager.getEpicTasks(epicId, projectPath);
    });

    ipcMain.handle('engine:run-epic', async (event, epicId, projectPath) => {
        if (!dockerManager) return { success: false, error: 'Docker manager not initialized' };
        return await dockerManager.runEpic(epicId, projectPath);
    });

    ipcMain.handle('engine:rerun-epic', async (event, epicId, projectPath) => {
        if (!dockerManager) return { success: false, error: 'Docker manager not initialized' };
        return await dockerManager.rerunEpic(epicId, projectPath);
    });

    ipcMain.handle('engine:rerun-task', async (event, epicId, taskId, projectPath, fixInstructions) => {
        if (!dockerManager) return { success: false, error: 'Docker manager not initialized' };
        return await dockerManager.rerunTask(epicId, taskId, projectPath, fixInstructions);
    });

    ipcMain.handle('engine:generate-task-lists', async (event, projectPath) => {
        if (!dockerManager) return { success: false, error: 'Docker manager not initialized' };
        return await dockerManager.generateTaskLists(projectPath);
    });

    // File System
    ipcMain.handle('fs:open-folder', async (event, folderPath) => {
        try {
            await shell.openPath(folderPath);
            return { success: true };
        } catch (error) {
            return { success: false, error: error.message };
        }
    });

    ipcMain.handle('fs:show-in-explorer', async (event, filePath) => {
        try {
            shell.showItemInFolder(filePath);
            return { success: true };
        } catch (error) {
            return { success: false, error: error.message };
        }
    });

    // Projects (from req-orchestrator API - matches Coding Engine standalone endpoints)
    const ORCHESTRATOR_API = process.env.ORCHESTRATOR_API_URL || 'http://localhost:8087';
    const TECHSTACK_API = `${ORCHESTRATOR_API}/api/v1/techstack`;
    const fetch = require('node-fetch');

    ipcMain.handle('projects:get-all', async () => {
        try {
            const response = await fetch(`${TECHSTACK_API}/projects`);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const data = await response.json();
            console.log(`[Projects] Loaded ${data.total || data.projects?.length || 0} projects from orchestrator`);
            return data.projects || [];
        } catch (error) {
            console.error('[Projects] Failed to fetch:', error.message);
            return [];
        }
    });

    ipcMain.handle('projects:get', async (event, id) => {
        try {
            const response = await fetch(`${TECHSTACK_API}/projects/${id}`);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            return await response.json();
        } catch (error) {
            console.error('[Projects] Failed to fetch:', error.message);
            return null;
        }
    });

    ipcMain.handle('projects:create', async (event, data) => {
        try {
            const response = await fetch(`${TECHSTACK_API}/projects`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data),
            });
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            return await response.json();
        } catch (error) {
            console.error('[Projects] Failed to create:', error.message);
            return { success: false, error: error.message };
        }
    });

    ipcMain.handle('projects:delete', async (event, id) => {
        try {
            const response = await fetch(`${TECHSTACK_API}/projects/${id}`, {
                method: 'DELETE',
            });
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            return { success: true };
        } catch (error) {
            console.error('[Projects] Failed to delete:', error.message);
            return { success: false, error: error.message };
        }
    });

    ipcMain.handle('projects:get-status', async (event, id) => {
        try {
            const response = await fetch(`${TECHSTACK_API}/projects/${id}/status`);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            return await response.json();
        } catch (error) {
            console.error('[Projects] Failed to get status:', error.message);
            return { status: 'unknown' };
        }
    });

    ipcMain.handle('projects:send-to-engine', async (event, projectIds) => {
        try {
            const response = await fetch(`${TECHSTACK_API}/send-to-engine`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ project_ids: projectIds }),
            });
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || `HTTP ${response.status}`);
            }
            return await response.json();
        } catch (error) {
            console.error('[Projects] Failed to send to engine:', error.message);
            return { success: false, error: error.message };
        }
    });

    // Local RE Project Scanning (filesystem-based, no orchestrator needed)
    ipcMain.handle('projects:scan-local-dirs', async (event, scanPaths) => {
        const engineRoot = process.env.CODING_ENGINE_PATH || path.join(__dirname, '..', 'python', 'spaces', 'coding', 'Coding_engine');
        const defaultScanDir = path.join(engineRoot, 'Data', 'all_services');
        const dirsToScan = (scanPaths && scanPaths.length > 0) ? scanPaths : [defaultScanDir];
        const results = [];
        for (const scanDir of dirsToScan) {
            if (!fs.existsSync(scanDir)) {
                console.log(`[RE] Scan directory not found: ${scanDir}`);
                continue;
            }
            let entries;
            try {
                entries = fs.readdirSync(scanDir, { withFileTypes: true });
            } catch (err) {
                console.error(`[RE] Failed to read directory ${scanDir}:`, err.message);
                continue;
            }
            for (const entry of entries) {
                if (!entry.isDirectory()) continue;
                const projectDir = path.join(scanDir, entry.name);
                const indicators = [
                    path.join(projectDir, 'MASTER_DOCUMENT.md'),
                    path.join(projectDir, 'tech_stack', 'tech_stack.json'),
                    path.join(projectDir, 'user_stories', 'user_stories.md'),
                    path.join(projectDir, 'content_analysis.json'),
                ];
                const isREProject = indicators.some((p) => fs.existsSync(p));
                if (!isREProject) continue;
                try {
                    const summary = readREProjectSummary(projectDir, entry.name);
                    results.push(summary);
                    console.log(`[RE] Found project: ${summary.project_name} (${summary.requirements_count} reqs, ${summary.tasks_count} tasks)`);
                } catch (err) {
                    console.warn(`[RE] Failed to read project ${entry.name}:`, err.message);
                }
            }
        }
        console.log(`[RE] Scan complete: ${results.length} RE projects found`);
        return results;
    });

    ipcMain.handle('projects:get-re-detail', async (event, projectPath) => {
        try {
            return readREProjectDetail(projectPath);
        } catch (err) {
            console.error('[RE] Failed to read project detail:', err.message);
            return null;
        }
    });

    // Dashboard View Control
    ipcMain.on('show-dashboard', () => {
        if (dashboardManager) {
            // Mutual exclusion: hide rowboat + swedesign when showing dashboard
            if (rowboatManager && rowboatManager.getIsVisible()) {
                rowboatManager.hide();
            }
            if (sweDesignManager && sweDesignManager.getIsVisible()) {
                sweDesignManager.hide();
            }
            dashboardManager.show();
            console.log('[Main] Dashboard shown');
        }
    });

    ipcMain.on('hide-dashboard', () => {
        if (dashboardManager) {
            dashboardManager.hide();
            console.log('[Main] Dashboard hidden');
        }
    });

    ipcMain.handle('is-dashboard-visible', () => {
        return dashboardManager ? dashboardManager.getIsVisible() : false;
    });

    // ========================================
    // ROWBOAT (ROARBOOT SPACE) VIEW CONTROL
    // ========================================

    ipcMain.on('show-rowboat', () => {
        if (rowboatManager) {
            // Mutual exclusion: hide dashboard + swedesign when showing rowboat
            if (dashboardManager && dashboardManager.getIsVisible()) {
                dashboardManager.hide();
            }
            if (sweDesignManager && sweDesignManager.getIsVisible()) {
                sweDesignManager.hide();
            }
            rowboatManager.show();
            console.log('[Main] Rowboat shown');
        }
    });

    ipcMain.on('hide-rowboat', () => {
        if (rowboatManager) {
            rowboatManager.hide();
            console.log('[Main] Rowboat hidden');
        }
    });

    ipcMain.handle('is-rowboat-visible', () => {
        return rowboatManager ? rowboatManager.getIsVisible() : false;
    });

    // ========================================
    // SWE DESIGN (FACTORY SPACE) VIEW CONTROL
    // ========================================

    ipcMain.on('show-swedesign', async () => {
        if (sweDesignManager) {
            // Mutual exclusion: hide dashboard + rowboat when showing swedesign
            if (dashboardManager && dashboardManager.getIsVisible()) {
                dashboardManager.hide();
            }
            if (rowboatManager && rowboatManager.getIsVisible()) {
                rowboatManager.hide();
            }
            await sweDesignManager.show();
            console.log('[Main] SWE Design shown');
        }
    });

    ipcMain.on('hide-swedesign', () => {
        if (sweDesignManager) {
            sweDesignManager.hide();
            console.log('[Main] SWE Design hidden');
        }
    });

    ipcMain.handle('is-swedesign-visible', () => {
        return sweDesignManager ? sweDesignManager.getIsVisible() : false;
    });

    // ========================================
    // ROWBOAT AUTO-UPDATE
    // ========================================

    ipcMain.handle('rowboat:triggerUpdate', async (event, { version }) => {
        const { exec } = require('child_process');
        const { promisify } = require('util');
        const execAsync = promisify(exec);
        const submodulePath = path.join(__dirname, '..', 'python', 'spaces', 'rowboat', 'rowboat');

        try {
            // Notify BrowserView: fetching
            rowboatManager?.relayEvent('rowboat:updateProgress', { stage: 'fetching', version });

            await execAsync(`git fetch --tags origin`, { cwd: submodulePath, timeout: 60000 });
            await execAsync(`git checkout tags/${version} --force`, { cwd: submodulePath, timeout: 30000 });

            // Notify BrowserView: building
            rowboatManager?.relayEvent('rowboat:updateProgress', { stage: 'building', version });

            await execAsync(`bash scripts/build-rowboat.sh`, { cwd: __dirname, timeout: 300000 });

            // Notify BrowserView: complete
            rowboatManager?.relayEvent('rowboat:updateProgress', { stage: 'complete', version });

            console.log(`[Main] Rowboat updated to ${version}`);
            return { success: true, version };
        } catch (err) {
            console.error('[Main] Rowboat update failed:', err.message);
            rowboatManager?.relayEvent('rowboat:updateProgress', {
                stage: 'error',
                version,
                error: err.message,
            });
            return { success: false, error: err.message };
        }
    });

    ipcMain.on('app:restart', () => {
        console.log('[Main] App restart requested');
        app.relaunch();
        app.exit(0);
    });
}

// ============================================================================

function createTray() {
    const iconPath = path.join(__dirname, 'build', 'icon.png');
    tray = new Tray(iconPath);

    const contextMenu = Menu.buildFromTemplate([
        { label: 'Show VibeMind', click: () => mainWindow && mainWindow.show() },
        { label: 'Start Voice', click: () => sendToPython({ type: 'start_voice' }) },
        { type: 'separator' },
        { label: 'Ideas Space', click: () => {
            currentSpace = 'ideas';
            sendToPython({ type: 'navigate_to_space', space: 'ideas' });
        }},
        { label: 'Desktop Space', click: () => {
            currentSpace = 'desktop';
            sendToPython({ type: 'navigate_to_space', space: 'desktop' });
        }},
        { type: 'separator' },
        { label: 'Quit', click: () => app.quit() }
    ]);

    tray.setToolTip('VibeMind');
    tray.setContextMenu(contextMenu);

    tray.on('click', () => {
        if (mainWindow) {
            if (mainWindow.isVisible()) {
                mainWindow.hide();
            } else {
                mainWindow.show();
            }
        }
    });
}

// ============================================================================

function registerShortcuts() {
    // Ctrl+Shift+V: Show/hide VibeMind
    globalShortcut.register('CommandOrControl+Shift+V', () => {
        if (mainWindow) {
            if (mainWindow.isVisible()) {
                mainWindow.hide();
            } else {
                mainWindow.show();
                mainWindow.focus();
            }
        }
    });

    // Ctrl+Shift+Space: Toggle voice
    globalShortcut.register('CommandOrControl+Shift+Space', () => {
        sendToPython({ type: 'toggle_voice' });
    });
    
    // Ctrl+1: Switch to Ideas Space
    globalShortcut.register('CommandOrControl+1', () => {
        console.log('[Main] Shortcut: Ideas Space');
        currentSpace = 'ideas';
        if (mainWindow && mainWindow.webContents) {
            mainWindow.webContents.send('python-message', {
                type: 'space_changed',
                space: 'ideas',
            });
        }
        sendToPython({ type: 'navigate_to_space', space: 'ideas' });
    });
    
    // Ctrl+2: Switch to Desktop Space
    globalShortcut.register('CommandOrControl+2', () => {
        console.log('[Main] Shortcut: Desktop Space');
        currentSpace = 'desktop';
        if (mainWindow && mainWindow.webContents) {
            mainWindow.webContents.send('python-message', {
                type: 'space_changed',
                space: 'desktop',
            });
        }
        sendToPython({ type: 'navigate_to_space', space: 'desktop' });
    });
}

// ============================================================================

app.whenReady().then(async () => {
    // Initialize Coding Engine managers
    dockerManager = new DockerManager();
    portAllocator = new PortAllocator();

    setupIpcHandlers();
    createWindow();

    // Initialize Dashboard Manager after window is created
    dashboardManager = new DashboardManager(mainWindow);

    // Initialize Rowboat Manager for Roarboot Space
    rowboatManager = new RowboatManager(mainWindow);

    // Initialize SWE Design Manager for Factory Space
    sweDesignManager = new SweDesignManager(mainWindow);

    // ========================================
    // ROWBOAT @x/core SERVICES INITIALIZATION
    // ========================================
    if (rowboatServices) {
        try {
            // Create ~/.rowboat/ directories + default config files
            await rowboatServices.initConfigs();
            console.log('[Main] Rowboat configs initialized');

            // Auto-configure Rowboat LLM from VibeMind .env if not yet configured
            await autoConfigureRowboatModels();

            // Register all 40+ IPC handlers (workspace:*, runs:*, models:*, etc.)
            rowboatServices.setupIpcHandlers();
            console.log('[Main] Rowboat IPC handlers registered');

            // Start file/run/service watchers
            rowboatServices.startWorkspaceWatcher();
            rowboatServices.startRunsWatcher();
            rowboatServices.startServicesWatcher();
            console.log('[Main] Rowboat watchers started');

            // Start background services
            rowboatServices.initGraphBuilder();
            console.log('[Main] Rowboat graph builder started');

            // Optional sync services — start in background, fail silently
            try { rowboatServices.initGmailSync(); } catch (e) { /* Gmail sync optional */ }
            try { rowboatServices.initCalendarSync(); } catch (e) { /* Calendar sync optional */ }
            try { rowboatServices.initFirefliesSync(); } catch (e) { /* Fireflies sync optional */ }
            try { rowboatServices.initGranolaSync(); } catch (e) { /* Granola sync optional */ }
            try { rowboatServices.initPreBuiltRunner(); } catch (e) { /* Pre-built runner optional */ }
            try { rowboatServices.initAgentRunner(); } catch (e) { /* Agent scheduler optional */ }
            console.log('[Main] Rowboat optional sync services initialized');

            // Push-Event Relay: BrowserView is not a BrowserWindow,
            // so BrowserWindow.getAllWindows() in @x/core won't reach it.
            // We subscribe to event buses and relay to the BrowserView directly.
            const { bus, serviceBus } = rowboatServices;
            if (bus) {
                bus.subscribe('*', (event) => {
                    rowboatManager?.relayEvent('runs:events', event);
                });
            }
            if (serviceBus) {
                serviceBus.subscribe((event) => {
                    rowboatManager?.relayEvent('services:events', event);
                });
            }
            console.log('[Main] Rowboat push-event relay configured');
        } catch (err) {
            console.error('[Main] Rowboat services init failed:', err.message);
        }
    }

    startPythonBackend();
    // createTray();  // Uncomment when icon is available
    registerShortcuts();

    console.log('[Main] Coding Engine Dashboard + Rowboat integration initialized');

    app.on('activate', () => {
        if (BrowserWindow.getAllWindows().length === 0) {
            createWindow();
        }
    });
});

app.on('window-all-closed', () => {
    // Kill Python process
    if (pythonProcess) {
        pythonProcess.kill();
    }

    // Unregister shortcuts
    globalShortcut.unregisterAll();

    if (process.platform !== 'darwin') {
        app.quit();
    }
});

app.on('will-quit', () => {
    if (pythonProcess) {
        pythonProcess.kill();
    }

    // Stop Rowboat watchers
    if (rowboatServices) {
        try {
            rowboatServices.stopWorkspaceWatcher();
            rowboatServices.stopRunsWatcher();
            rowboatServices.stopServicesWatcher();
            console.log('[Main] Rowboat watchers stopped');
        } catch (e) {
            console.warn('[Main] Error stopping Rowboat watchers:', e.message);
        }
    }

    // Destroy Rowboat BrowserView
    if (rowboatManager) {
        rowboatManager.destroy();
    }

    // Destroy SWE Design BrowserView
    if (sweDesignManager) {
        sweDesignManager.destroy();
    }

    globalShortcut.unregisterAll();
});
