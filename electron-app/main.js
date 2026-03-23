/**
 * VibeMind Electron Main Process
 *
 * Manages the main window, Python backend process,
 * and IPC communication between renderer and Python.
 */

// Sentry error tracking (lazy-init after app.whenReady)
const sentry = require('./sentry');

const { app, BrowserWindow, ipcMain, Tray, Menu, globalShortcut, shell, protocol, net } = require('electron');
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

// ClawPort Dashboard Integration
const ClawPortManager = require('./clawport-manager');

// Brain Dashboard Integration
const BrainManager = require('./brain-manager');

// Agent Farm Integration
const AgentFarmManager = require('./agentfarm-manager');

// MiroFish Integration
const MiroFishManager = require('./mirofish-manager');

// Flowzen Diary (Blue Rose Journal) Integration
const FlowzenManager = require('./flowzen-manager');

// Video Space Integration
const VideoManager = require('./video-manager');

// eyeTerm Camera Preview Integration
const EyeTermManager = require('./eyeterm-manager');

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

// ClawPort Dashboard manager
let clawportManager = null;

// Brain Dashboard manager
let brainManager = null;

// Agent Farm manager
let agentfarmManager = null;

// MiroFish manager
let mirofishManager = null;

// Flowzen Diary (Blue Rose Journal) manager
let flowzenManager = null;

// Video Space manager
let videoManager = null;

// eyeTerm camera preview manager
let eyetermManager = null;

// Pending Python response handlers (for request-response IPC pattern)
const pendingPythonResponses = new Map();

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
 * Priority: ANTHROPIC_API_KEY > OPENROUTER > OPENAI
 * Note: Claude Code OAuth tokens are NOT valid Anthropic API keys and cannot
 * be used for direct API calls to api.anthropic.com.
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

        // Determine desired config (Priority: ANTHROPIC > OPENROUTER > OPENAI)
        let desiredConfig = null;
        let source = '';

        // 1. Explicit Anthropic API key from .env
        {
            const anthropicKey = process.env.ANTHROPIC_API_KEY;
            if (anthropicKey && !anthropicKey.includes('DEIN_KEY') && !anthropicKey.includes('your_')) {
                desiredConfig = {
                    provider: { flavor: 'anthropic', apiKey: anthropicKey },
                    model: process.env.ROWBOAT_MODEL || 'claude-sonnet-4-20250514',
                };
                source = 'Anthropic';
            }
        }

        // 2. OpenRouter
        if (!desiredConfig && process.env.OPENROUTER_API_KEY) {
            desiredConfig = {
                provider: { flavor: 'openrouter', apiKey: process.env.OPENROUTER_API_KEY },
                model: process.env.ROWBOAT_MODEL || 'anthropic/claude-sonnet-4',
            };
            source = 'OpenRouter';
        }

        // 3. OpenAI (fallback)
        if (!desiredConfig && process.env.OPENAI_API_KEY) {
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
            console.log(`[Main] Rowboat auto-configured with ${source}`);
        } else {
            console.log(`[Main] Rowboat models already match (${source}), skipping`);
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

function killZombiePythonProcesses() {
    // Kill stale Python processes on ports we need (8099=eyeTerm, 8009=AutomationUI)
    if (process.platform !== 'win32') return;
    const { execFileSync } = require('child_process');
    for (const port of [8099, 8009]) {
        try {
            const out = execFileSync('netstat', ['-ano'], { timeout: 3000, encoding: 'utf8' });
            const lines = out.split('\n').filter(l => l.includes(`:${port}`) && l.includes('LISTEN'));
            for (const line of lines) {
                const parts = line.trim().split(/\s+/);
                const pid = parseInt(parts[parts.length - 1], 10);
                if (pid > 0 && pid !== process.pid) {
                    console.log(`[Main] Killing zombie process on port ${port} (PID ${pid})`);
                    try {
                        execFileSync('taskkill', ['/PID', String(pid), '/T', '/F'], { timeout: 3000 });
                    } catch (_) { /* may already be dead */ }
                }
            }
        } catch (_) { /* netstat may fail — ignore */ }
    }
}

function startPythonBackend() {
    // Kill leftover Python processes from previous sessions
    killZombiePythonProcesses();

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
    sentry.setContext('python_backend', { status: 'running', pid: pythonProcess.pid });

    // Handle stdout from Python (JSON messages)
    pythonProcess.stdout.on('data', (data) => {
        const lines = data.toString().split('\n').filter(l => l.trim());
        for (const line of lines) {
            try {
                const message = JSON.parse(line);
                sentry.addBreadcrumb({ category: 'ipc.python', message: `<- ${message.type}`, level: 'info' });

                // Log IPC as structured JSON so CDP Debug Agent can color it
                // Emit in renderer context so CDP Debug Agent sees it
                if (mainWindow?.webContents) {
                    const j = JSON.stringify({__ipc_log: true, dir: '\u2192', type: message.type, preview: JSON.stringify(message).substring(0, 150)});
                    mainWindow.webContents.executeJavaScript(`console.log(${JSON.stringify(j)})`).catch(() => {});
                }
                
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

                // Handle Rowboat update auto-applied
                if (message.type === 'rowboat_update_applied') {
                    rowboatManager?.relayEvent('rowboat:updateApplied', message);
                }

                // Handle structured content updates
                if (message.type === 'node_structured_update') {
                    debugLog('Structured content update:', message.node_id);
                }
                
                // Check for pending ClawPort response handlers
                if (message.type && pendingPythonResponses.has(message.type)) {
                    const handler = pendingPythonResponses.get(message.type);
                    handler(message);
                }

                // Forward ClawPort-relevant messages to dashboard BrowserView
                if (clawportManager && clawportManager.getIsVisible()) {
                    const clawportTypes = ['chat_response', 'agent_status_list', 'scheduled_tasks_list', 'memory_overview', 'memory_search_results'];
                    if (clawportTypes.includes(message.type)) {
                        clawportManager.relayEvent('clawport-message', message);
                    }
                }

                // Forward Flowzen-relevant messages to diary BrowserView
                if (flowzenManager) {
                    if (message.type === 'flowzen_diary_entries_result') {
                        flowzenManager.send('flowzen-diary-data', { entries: message.entries });
                    }
                    if (message.type === 'flowzen_status_result') {
                        flowzenManager.send('flowzen-status', message);
                    }
                    if (message.type === 'flowzen_recommend_result') {
                        flowzenManager.send('flowzen-recommend-result', message);
                    }
                    if (message.type === 'flowzen_rose_state' && message.state === 'diary_new' && message.diary_entry) {
                        flowzenManager.send('flowzen-diary-entry', message.diary_entry);
                    }
                }

                // Forward to renderer
                if (mainWindow && mainWindow.webContents) {
                    mainWindow.webContents.send('python-message', message);
                } else {
                    console.warn('[Main] Cannot forward - mainWindow not ready');
                }
            } catch (e) {
                // Non-JSON output (debug logs from Python)
                console.log('[Python stdout]:', line);
            }
        }
    });

    // Handle stderr from Python (space-colored JSON logs)
    // Python's SpaceJsonFormatter emits one JSON object per line when piped.
    // We parse and render with ANSI colors for terminal + forward to renderer.

    const RST = '\x1b[0m';
    const SPACE_ANSI = {
        bubbles:      '\x1b[96m',  // Bright Cyan
        ideas:        '\x1b[92m',  // Bright Green
        coding:       '\x1b[93m',  // Bright Yellow
        desktop:      '\x1b[95m',  // Bright Magenta
        rowboat:      '\x1b[94m',  // Blue
        research:     '\x1b[91m',  // Red
        minibook:     '\x1b[97m',  // White Bold
        schedule:     '\x1b[36m',  // Cyan
        voice:        '\x1b[33m',  // Dark Yellow
        orchestrator: '\x1b[35m',  // Dark Magenta
        brain:        '\x1b[32m',  // Dark Green
        system:       '\x1b[2m',   // Dim
    };
    const LEVEL_ANSI = {
        DEBUG:    '\x1b[2m',       // Dim
        INFO:     '',              // Default
        WARNING:  '\x1b[93m',     // Yellow
        ERROR:    '\x1b[91m',     // Red
        CRITICAL: '\x1b[91;1m',   // Bold Red
    };
    const SPACE_TAGS = {
        bubbles: '[BUBBLES]', ideas: '[IDEAS]', coding: '[CODING]',
        desktop: '[DESKTOP]', rowboat: '[ROWBOAT]', research: '[RESEARCH]',
        minibook: '[MINIBOOK]', schedule: '[SCHEDULE]', voice: '[VOICE]',
        orchestrator: '[ORCH]', brain: '[BRAIN]', system: '[SYSTEM]',
    };

    let stderrBuffer = '';
    pythonProcess.stderr.on('data', (data) => {
        stderrBuffer += data.toString();
        const lines = stderrBuffer.split('\n');
        stderrBuffer = lines.pop(); // keep incomplete last line in buffer

        for (const line of lines) {
            const trimmed = line.trim();
            if (!trimmed) continue;

            try {
                const log = JSON.parse(trimmed);
                if (log.log) {
                    const tag = (SPACE_TAGS[log.s] || '[SYSTEM]').padEnd(10);
                    const spaceColor = SPACE_ANSI[log.s] || SPACE_ANSI.system;
                    const levelColor = LEVEL_ANSI[log.l] || '';
                    const levelPad = (log.l || '').padEnd(5);
                    const dimTs = '\x1b[2m';

                    const colored = `${spaceColor}${tag}${RST} ${levelColor}${levelPad}${RST} ${dimTs}[${log.t}]${RST} ${log.m}`;

                    if (log.l === 'ERROR' || log.l === 'CRITICAL') {
                        process.stderr.write(colored + '\n');
                    } else {
                        process.stdout.write(colored + '\n');
                    }

                    // Forward to renderer for optional in-app log panel
                    if (mainWindow?.webContents) {
                        mainWindow.webContents.send('python-log', log);
                    }
                    // Emit in renderer context so CDP Debug Agent sees it
                    if (mainWindow?.webContents) {
                        const j = JSON.stringify({__space_log: true, ...log});
                        mainWindow.webContents.executeJavaScript(
                            `console.log(${JSON.stringify(j)})`
                        ).catch(() => {});
                    }
                    continue;
                }
            } catch (e) {
                // Not JSON — fall through
            }
            // Plain text fallback — print to terminal AND emit in renderer
            process.stdout.write(`[Python] ${trimmed}\n`);
            if (mainWindow?.webContents) {
                mainWindow.webContents.executeJavaScript(
                    `console.log('[Python stderr]: ' + ${JSON.stringify(trimmed)})`
                ).catch(() => {});
            }
        }
    });

    pythonProcess.on('close', (code) => {
        // Flush remaining stderr buffer
        if (stderrBuffer.trim()) {
            console.error('[Python stderr]:', stderrBuffer.trim());
        }
        stderrBuffer = '';
        console.log('[Main] Python process exited with code:', code);
        sentry.setContext('python_backend', { status: 'exited', exitCode: code });
        if (code !== 0) { sentry.captureMessage(`Python backend crashed (exit ${code})`, 'error'); }
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
        sentry.addBreadcrumb({ category: 'ipc.python', message: `-> ${message.type}`, level: 'info' });
        // Emit in renderer context so CDP Debug Agent sees it
        if (mainWindow?.webContents) {
            const j = JSON.stringify({__ipc_log: true, dir: '\u2190', type: message.type, preview: json.substring(0, 150)});
            mainWindow.webContents.executeJavaScript(`console.log(${JSON.stringify(j)})`).catch(() => {});
        }
        pythonProcess.stdin.write(json + '\n');
    } else {
        console.error('[Main] Cannot send to Python - process not running');
    }
}

/**
 * Send message to Python and wait for a response with matching type.
 * Used by ClawPort dashboard IPC handlers that need return values.
 */
function sendToPythonAndWait(message, responseType, timeoutMs = 10000) {
    return new Promise((resolve, reject) => {
        const timeout = setTimeout(() => {
            pendingPythonResponses.delete(responseType);
            reject(new Error(`Timeout waiting for ${responseType}`));
        }, timeoutMs);

        pendingPythonResponses.set(responseType, (response) => {
            clearTimeout(timeout);
            pendingPythonResponses.delete(responseType);
            resolve(response);
        });

        sentry.addBreadcrumb({ category: 'ipc.python.rpc', message: `-> ${message.type} (await ${responseType})`, level: 'info' });
        sendToPython(message);
    });
}

// ============================================================================
// MULTIVERSE HANDLERS
// ============================================================================

// Agent to Space mapping for automatic navigation
const AGENT_SPACE_MAP = {
    'rachel': 'ideas',
    'rowboat': 'roarboot',
    'director': 'video',
};

function handleAgentTransfer(message) {
    /**
     * Handle agent transfer completion.
     * Updates current agent and AUTOMATICALLY navigates to the matching space.
     */
    const { from_agent, to_agent, target_agent_id } = message;
    
    console.log(`[Main] Agent Transfer: ${from_agent} → ${to_agent}`);
    currentAgent = to_agent;
    sentry.setTag('agent', to_agent);

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
        sentry.setTag('space', targetSpace);

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
        sentry.setTag('space', currentSpace);

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

    // Fallback 1: Read epics.json if user_stories.json was missing or empty
    if (!userStoriesCount) {
        const epicsPath = path.join(projectDir, 'user_stories', 'epics', 'epics.json');
        if (fs.existsSync(epicsPath)) {
            try {
                const epics = JSON.parse(fs.readFileSync(epicsPath, 'utf-8'));
                if (Array.isArray(epics)) {
                    const allStoryIds = new Set();
                    const allReqIds = new Set();
                    for (const epic of epics) {
                        if (Array.isArray(epic.user_stories)) {
                            for (const sid of epic.user_stories) allStoryIds.add(sid);
                        }
                        if (Array.isArray(epic.parent_requirements)) {
                            for (const rid of epic.parent_requirements) allReqIds.add(rid);
                        }
                    }
                    userStoriesCount = allStoryIds.size;
                    requirementsCount = allReqIds.size || userStoriesCount;
                }
            } catch { /* ignore */ }
        }
    }

    // Fallback 2: Read content_analysis.json if both user_stories.json and epics.json missing
    if (!userStoriesCount) {
        const contentAnalysisPath = path.join(projectDir, 'content_analysis.json');
        if (fs.existsSync(contentAnalysisPath)) {
            try {
                const data = JSON.parse(fs.readFileSync(contentAnalysisPath, 'utf-8'));
                const usSummary = data.artifact_summaries?.user_stories || {};
                userStoriesCount = usSummary.count || 0;
                // Extract unique requirement IDs from items
                const items = usSummary.items || [];
                const reqIds = new Set();
                for (const item of items) {
                    if (item.parent_requirement_id) reqIds.add(item.parent_requirement_id);
                }
                requirementsCount = reqIds.size || userStoriesCount;
            } catch { /* ignore */ }
        }
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

    // Read epics data
    let epicsList = [];
    const epicsPath = path.join(projectDir, 'user_stories', 'epics', 'epics.json');
    if (fs.existsSync(epicsPath)) {
        try {
            const data = JSON.parse(fs.readFileSync(epicsPath, 'utf-8'));
            if (Array.isArray(data)) {
                epicsList = data.map((e) => ({
                    id: e.id || '',
                    title: e.title || '',
                    description: e.description || '',
                    status: e.status || 'draft',
                    priority: e.priority || '',
                    story_points: e.story_points || 0,
                    user_stories: e.user_stories || [],
                    parent_requirements: e.parent_requirements || [],
                    acceptance_criteria: e.acceptance_criteria || [],
                }));
            }
        } catch { /* ignore */ }
    }

    // Read pipeline manifest for progress
    let pipelineStages = [];
    let pipelineSummary = {};
    const pipelinePath = path.join(projectDir, 'pipeline_manifest.json');
    if (fs.existsSync(pipelinePath)) {
        try {
            const data = JSON.parse(fs.readFileSync(pipelinePath, 'utf-8'));
            pipelineSummary = {
                total_stages: (data.stages || []).length,
                completed_stages: (data.stages || []).filter((s) => s.status === 'completed').length,
                total_cost_usd: data.total_cost_usd || 0,
                total_duration_ms: data.total_duration_ms || 0,
                started_at: data.started_at || '',
                completed_at: data.completed_at || '',
            };
            pipelineStages = (data.stages || []).map((s) => ({
                name: s.name || '',
                status: s.status || '',
                duration_ms: s.duration_ms || 0,
                cost_usd: s.cost_usd || 0,
                llm_calls: s.llm_calls || 0,
            }));
        } catch { /* ignore */ }
    }

    return {
        ...summary,
        tech_stack_full: techStackFull,
        tasks_by_feature: tasksByFeature,
        quality_issues_list: qualityIssuesList,
        master_document_excerpt: masterDocExcerpt,
        feature_breakdown: featureBreakdown,
        epics_list: epicsList,
        pipeline_stages: pipelineStages,
        pipeline_summary: pipelineSummary,
    };
}

function setupIpcHandlers() {
    // Forward messages from renderer to Python
    ipcMain.on('to-python', (event, message) => {
        sendToPython(message);
    });

    // Renderer log → file (for autonomous debugging)
    const fs = require('fs');
    const rendererLogPath = require('path').join(__dirname, '..', 'logs', 'renderer.log');
    // Ensure logs dir exists
    try { fs.mkdirSync(require('path').dirname(rendererLogPath), { recursive: true }); } catch(e) {}
    ipcMain.on('renderer-log', (event, { level, args }) => {
        const ts = new Date().toISOString();
        const line = `[${ts}] [${level}] ${args.map(a => typeof a === 'object' ? JSON.stringify(a) : String(a)).join(' ')}\n`;
        fs.appendFileSync(rendererLogPath, line);
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
        const vncPort = await portAllocator.allocate(projectId);
        const appPort = await portAllocator.allocateAppPort(projectId);
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
        if (!dockerManager) return 'http://localhost:8321';
        return dockerManager.getApiUrl();
    });

    ipcMain.handle('engine:start-generation-with-preview', async (event, projectId, requirementsPath, outputDir, forceGenerate = false) => {
        if (!dockerManager || !portAllocator) return { success: false, error: 'Managers not initialized' };
        try {
            const engineRoot = process.env.CODING_ENGINE_PATH || path.join(__dirname, '..', 'python', 'spaces', 'coding', 'Coding_engine');
            const projectRoot = path.join(__dirname, '..');
            let localPath = requirementsPath;
            if (requirementsPath.startsWith('/app/projects/')) {
                const relative = requirementsPath.replace('/app/projects/', '');
                localPath = path.join(engineRoot, 'Data', 'all_services', relative);
            }
            // Docker requires absolute paths for volume mounts on Windows
            if (!path.isAbsolute(localPath)) {
                localPath = path.resolve(projectRoot, localPath);
            }
            const vncPort = await portAllocator.allocate(projectId);
            const appPort = await portAllocator.allocateAppPort(projectId);
            let absOutputDir = outputDir.startsWith('.') ? path.join(engineRoot, outputDir.replace(/^\.\//, '')) : outputDir;
            if (!path.isAbsolute(absOutputDir)) {
                absOutputDir = path.resolve(projectRoot, absOutputDir);
            }
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
            const projectRoot = path.join(__dirname, '..');
            let absProjectPath = path.isAbsolute(projectPath) ? projectPath : path.resolve(projectRoot, projectPath);
            let absOutputDir = outputDir.startsWith('.') ? path.join(engineRoot, outputDir.replace(/^\.\//, '')) : outputDir;
            if (!path.isAbsolute(absOutputDir)) {
                absOutputDir = path.resolve(projectRoot, absOutputDir);
            }
            const vncPort = await portAllocator.allocate(projectId);
            const appPort = await portAllocator.allocateAppPort(projectId);
            return await dockerManager.startGenerationWithPreview(projectId, absProjectPath, absOutputDir, vncPort, appPort, true);
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

    // ========================================
    // CLAUDE CODE RUNNER
    // ========================================

    ipcMain.handle('engine:start-claude-runner', async (event, repoPath, options = {}) => {
        if (!dockerManager || !portAllocator) return { success: false, error: 'Managers not initialized' };
        try {
            const projectRoot = path.join(__dirname, '..');
            const absRepoPath = path.isAbsolute(repoPath) ? repoPath : path.resolve(projectRoot, repoPath);
            const vncPort = await portAllocator.allocate('claude-runner');
            const result = await dockerManager.startClaudeRunner(absRepoPath, vncPort, options);
            if (!result.success) {
                portAllocator.release('claude-runner');
            }
            return result;
        } catch (error) {
            console.error('[ClaudeRunner] Error:', error);
            portAllocator.release('claude-runner');
            return { success: false, error: error.message };
        }
    });

    ipcMain.handle('engine:stop-claude-runner', async () => {
        if (!dockerManager) return { success: false, error: 'Docker manager not initialized' };
        portAllocator?.release('claude-runner');
        return await dockerManager.stopClaudeRunner();
    });

    ipcMain.handle('engine:get-claude-runner-status', async () => {
        if (!dockerManager) return { running: false };
        return dockerManager.getClaudeRunnerStatus();
    });

    ipcMain.handle('engine:start-epic-generation', async (event, projectId, projectPath, outputDir) => {
        if (!dockerManager || !portAllocator) return { success: false, error: 'Managers not initialized' };
        try {
            const engineRoot = process.env.CODING_ENGINE_PATH || path.join(__dirname, '..', 'python', 'spaces', 'coding', 'Coding_engine');
            const absOutputDir = outputDir && outputDir.startsWith('.')
                ? path.join(engineRoot, outputDir.replace(/^\.\//, ''))
                : (outputDir || path.join(engineRoot, 'output'));
            const vncPort = await portAllocator.allocate(projectId);
            const appPort = await portAllocator.allocateAppPort(projectId);
            console.log(`[EpicGen] Starting for ${projectId}, VNC:${vncPort}, App:${appPort}`);

            // Start VNC preview container
            const containerResult = await dockerManager.startProjectContainer(projectId, absOutputDir, vncPort, appPort);
            if (!containerResult.success) {
                portAllocator.release(projectId);
                return { success: false, error: containerResult.error };
            }

            // Kick off epic orchestration via API
            const containerPath = toContainerProjectPath(projectPath);
            try {
                const response = await fetch(`${ENGINE_API}/api/v1/dashboard/start-epic-generation`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ project_path: containerPath, output_dir: absOutputDir, vnc_port: vncPort, app_port: appPort })
                });
                if (!response.ok) {
                    console.warn(`[EpicGen] API returned ${response.status}`);
                } else {
                    console.log(`[EpicGen] Orchestrator started via API`);
                }
            } catch (apiError) {
                console.warn(`[EpicGen] Could not reach API:`, apiError.message);
            }

            return { success: true, vncPort, appPort };
        } catch (error) {
            console.error('[EpicGen] Error:', error);
            return { success: false, error: error.message };
        }
    });

    // Helper: convert host project path to container-internal path for the Coding Engine API
    function toContainerProjectPath(hostPath) {
        const engineRoot = process.env.CODING_ENGINE_PATH || path.join(__dirname, '..', 'python', 'spaces', 'coding', 'Coding_engine');
        const dataDir = path.join(engineRoot, 'Data', 'all_services').replace(/\\/g, '/');
        const normalized = hostPath.replace(/\\/g, '/');
        if (normalized.startsWith(dataDir)) {
            return '/data/projects' + normalized.slice(dataDir.length);
        }
        // Already a container path or /data/projects path
        if (normalized.startsWith('/data/projects')) return normalized;
        return hostPath;
    }

    const ENGINE_API = process.env.CODING_ENGINE_API_URL || 'http://localhost:8321';

    ipcMain.handle('engine:get-epics', async (event, projectPath) => {
        console.log(`[Epic:IPC] get-epics for: ${projectPath}`);
        try {
            const containerPath = toContainerProjectPath(projectPath);
            const url = `${ENGINE_API}/api/v1/dashboard/epics?project_path=${encodeURIComponent(containerPath)}`;
            const response = await fetch(url);
            if (!response.ok) throw new Error(`HTTP ${response.status}: ${await response.text()}`);
            return await response.json();
        } catch (error) {
            console.error('[Epic:IPC] get-epics failed:', error.message);
            return { project_path: projectPath, total_epics: 0, epics: [] };
        }
    });

    ipcMain.handle('engine:get-epic-tasks', async (event, epicId, projectPath) => {
        try {
            const containerPath = toContainerProjectPath(projectPath);
            const response = await fetch(
                `${ENGINE_API}/api/v1/dashboard/epic/${epicId}/tasks?project_path=${encodeURIComponent(containerPath)}`
            );
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            return await response.json();
        } catch (error) {
            console.error(`[Epic:IPC] get-epic-tasks failed for ${epicId}:`, error.message);
            return { epic_id: epicId, tasks: [], total_tasks: 0 };
        }
    });

    ipcMain.handle('engine:run-epic', async (event, epicId, projectPath) => {
        try {
            const containerPath = toContainerProjectPath(projectPath);
            const response = await fetch(`${ENGINE_API}/api/v1/dashboard/epic/${epicId}/run`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ project_path: containerPath })
            });
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            return await response.json();
        } catch (error) {
            console.error(`[Epic:IPC] run-epic failed for ${epicId}:`, error.message);
            return { success: false, error: error.message };
        }
    });

    ipcMain.handle('engine:rerun-epic', async (event, epicId, projectPath) => {
        try {
            const containerPath = toContainerProjectPath(projectPath);
            const response = await fetch(`${ENGINE_API}/api/v1/dashboard/epic/${epicId}/rerun`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ project_path: containerPath })
            });
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            return await response.json();
        } catch (error) {
            console.error(`[Epic:IPC] rerun-epic failed for ${epicId}:`, error.message);
            return { success: false, error: error.message };
        }
    });

    ipcMain.handle('engine:rerun-task', async (event, epicId, taskId, projectPath, fixInstructions) => {
        try {
            const containerPath = toContainerProjectPath(projectPath);
            const response = await fetch(`${ENGINE_API}/api/v1/dashboard/epic/${epicId}/task/${taskId}/rerun`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ project_path: containerPath, fix_instructions: fixInstructions || null })
            });
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            return await response.json();
        } catch (error) {
            console.error(`[Epic:IPC] rerun-task failed for ${epicId}/${taskId}:`, error.message);
            return { success: false, error: error.message };
        }
    });

    ipcMain.handle('engine:generate-task-lists', async (event, projectPath) => {
        try {
            const containerPath = toContainerProjectPath(projectPath);
            const response = await fetch(`${ENGINE_API}/api/v1/dashboard/generate-task-lists`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ project_path: containerPath })
            });
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            return await response.json();
        } catch (error) {
            console.error('[Epic:IPC] generate-task-lists failed:', error.message);
            return { success: false, error: error.message };
        }
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
    // Electron has global fetch built-in (Node 18+)

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
            // Mutual exclusion: hide all other BrowserViews when showing dashboard
            if (rowboatManager && rowboatManager.getIsVisible()) rowboatManager.hide();
            if (sweDesignManager && sweDesignManager.getIsVisible()) sweDesignManager.hide();
            if (clawportManager && clawportManager.getIsVisible()) clawportManager.hide();
            if (brainManager && brainManager.getIsVisible()) brainManager.hide();
            if (agentfarmManager && agentfarmManager.getIsVisible()) agentfarmManager.hide();
            if (mirofishManager && mirofishManager.getIsVisible()) mirofishManager.hide();
            if (flowzenManager && flowzenManager.getIsVisible()) flowzenManager.hide();
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
            // Mutual exclusion: hide all other BrowserViews when showing rowboat
            if (dashboardManager && dashboardManager.getIsVisible()) dashboardManager.hide();
            if (sweDesignManager && sweDesignManager.getIsVisible()) sweDesignManager.hide();
            if (clawportManager && clawportManager.getIsVisible()) clawportManager.hide();
            if (brainManager && brainManager.getIsVisible()) brainManager.hide();
            if (agentfarmManager && agentfarmManager.getIsVisible()) agentfarmManager.hide();
            if (mirofishManager && mirofishManager.getIsVisible()) mirofishManager.hide();
            if (flowzenManager && flowzenManager.getIsVisible()) flowzenManager.hide();
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
    // CLAUDE CODE TOKEN (for Settings UI badge)
    // ========================================

    ipcMain.handle('get-claude-code-token', async () => {
        const token = getClaudeCodeToken();
        if (!token) return { available: false };
        return {
            available: true,
            token,
            subscriptionType: 'max',
        };
    });

    // ========================================
    // SWE DESIGN (FACTORY SPACE) VIEW CONTROL
    // ========================================

    ipcMain.on('show-swedesign', async () => {
        if (sweDesignManager) {
            // Mutual exclusion: hide all other BrowserViews when showing swedesign
            if (dashboardManager && dashboardManager.getIsVisible()) dashboardManager.hide();
            if (rowboatManager && rowboatManager.getIsVisible()) rowboatManager.hide();
            if (clawportManager && clawportManager.getIsVisible()) clawportManager.hide();
            if (brainManager && brainManager.getIsVisible()) brainManager.hide();
            if (agentfarmManager && agentfarmManager.getIsVisible()) agentfarmManager.hide();
            if (mirofishManager && mirofishManager.getIsVisible()) mirofishManager.hide();
            if (flowzenManager && flowzenManager.getIsVisible()) flowzenManager.hide();
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
    // CLAWPORT DASHBOARD VIEW CONTROL
    // ========================================

    ipcMain.on('show-clawport', () => {
        if (clawportManager) {
            // Mutual exclusion: hide all other BrowserViews
            if (dashboardManager && dashboardManager.getIsVisible()) dashboardManager.hide();
            if (rowboatManager && rowboatManager.getIsVisible()) rowboatManager.hide();
            if (sweDesignManager && sweDesignManager.getIsVisible()) sweDesignManager.hide();
            if (brainManager && brainManager.getIsVisible()) brainManager.hide();
            if (agentfarmManager && agentfarmManager.getIsVisible()) agentfarmManager.hide();
            if (mirofishManager && mirofishManager.getIsVisible()) mirofishManager.hide();
            if (flowzenManager && flowzenManager.getIsVisible()) flowzenManager.hide();
            clawportManager.show();
            console.log('[Main] ClawPort shown');
        }
    });

    ipcMain.on('hide-clawport', () => {
        if (clawportManager) {
            clawportManager.hide();
            console.log('[Main] ClawPort hidden');
        }
    });

    ipcMain.handle('is-clawport-visible', () => {
        return clawportManager ? clawportManager.getIsVisible() : false;
    });

    // ========================================
    // BRAIN DASHBOARD VIEW CONTROL
    // ========================================

    ipcMain.on('show-brain', async () => {
        if (brainManager) {
            // Mutual exclusion: hide all other BrowserViews
            if (dashboardManager && dashboardManager.getIsVisible()) dashboardManager.hide();
            if (rowboatManager && rowboatManager.getIsVisible()) rowboatManager.hide();
            if (sweDesignManager && sweDesignManager.getIsVisible()) sweDesignManager.hide();
            if (clawportManager && clawportManager.getIsVisible()) clawportManager.hide();
            if (agentfarmManager && agentfarmManager.getIsVisible()) agentfarmManager.hide();
            if (mirofishManager && mirofishManager.getIsVisible()) mirofishManager.hide();
            if (flowzenManager && flowzenManager.getIsVisible()) flowzenManager.hide();
            await brainManager.show();
            console.log('[Main] Brain Dashboard shown');
        }
    });

    ipcMain.on('hide-brain', () => {
        if (brainManager) {
            brainManager.hide();
            console.log('[Main] Brain Dashboard hidden');
        }
    });

    ipcMain.handle('is-brain-visible', () => {
        return brainManager ? brainManager.getIsVisible() : false;
    });

    // ========================================
    // AGENT FARM VIEW CONTROL
    // ========================================

    ipcMain.on('show-agentfarm', () => {
        if (agentfarmManager) {
            // Mutual exclusion: hide all other BrowserViews
            if (dashboardManager && dashboardManager.getIsVisible()) dashboardManager.hide();
            if (rowboatManager && rowboatManager.getIsVisible()) rowboatManager.hide();
            if (sweDesignManager && sweDesignManager.getIsVisible()) sweDesignManager.hide();
            if (clawportManager && clawportManager.getIsVisible()) clawportManager.hide();
            if (brainManager && brainManager.getIsVisible()) brainManager.hide();
            if (videoManager && videoManager.getIsVisible()) videoManager.hide();
            if (flowzenManager && flowzenManager.getIsVisible()) flowzenManager.hide();
            agentfarmManager.show();
            console.log('[Main] Agent Farm shown');
        }
    });

    ipcMain.on('hide-agentfarm', () => {
        if (agentfarmManager) {
            agentfarmManager.hide();
            console.log('[Main] Agent Farm hidden');
        }
    });

    // ========================================
    // VIDEO SPACE VIEW CONTROL
    // ========================================

    ipcMain.on('show-video', () => {
        if (videoManager) {
            // Mutual exclusion: hide all other BrowserViews
            if (dashboardManager && dashboardManager.getIsVisible()) dashboardManager.hide();
            if (rowboatManager && rowboatManager.getIsVisible()) rowboatManager.hide();
            if (sweDesignManager && sweDesignManager.getIsVisible()) sweDesignManager.hide();
            if (clawportManager && clawportManager.getIsVisible()) clawportManager.hide();
            if (brainManager && brainManager.getIsVisible()) brainManager.hide();
            if (agentfarmManager && agentfarmManager.getIsVisible()) agentfarmManager.hide();
            if (mirofishManager && mirofishManager.getIsVisible()) mirofishManager.hide();
            if (flowzenManager && flowzenManager.getIsVisible()) flowzenManager.hide();
            videoManager.show();
            console.log('[Main] Video shown');
        }
    });

    ipcMain.on('hide-video', () => {
        if (videoManager) {
            videoManager.hide();
            console.log('[Main] Video hidden');
        }
    });

    // ── MiroFish BrowserView ──────────────────────────────

    ipcMain.on('show-mirofish', () => {
        if (mirofishManager) {
            // Mutual exclusion: hide all other BrowserViews
            if (dashboardManager && dashboardManager.getIsVisible()) dashboardManager.hide();
            if (rowboatManager && rowboatManager.getIsVisible()) rowboatManager.hide();
            if (sweDesignManager && sweDesignManager.getIsVisible()) sweDesignManager.hide();
            if (clawportManager && clawportManager.getIsVisible()) clawportManager.hide();
            if (brainManager && brainManager.getIsVisible()) brainManager.hide();
            if (agentfarmManager && agentfarmManager.getIsVisible()) agentfarmManager.hide();
            if (flowzenManager && flowzenManager.getIsVisible()) flowzenManager.hide();
            mirofishManager.show();
            console.log('[Main] MiroFish shown');
        }
    });

    ipcMain.on('hide-mirofish', () => {
        if (mirofishManager) {
            mirofishManager.hide();
            console.log('[Main] MiroFish hidden');
        }
    });

    ipcMain.handle('is-mirofish-visible', () => {
        return mirofishManager ? mirofishManager.getIsVisible() : false;
    });

    // ========================================
    // FLOWZEN DIARY (BLUE ROSE JOURNAL) VIEW CONTROL
    // ========================================

    ipcMain.on('show-flowzen', () => {
        if (flowzenManager) {
            // Mutual exclusion: hide all other BrowserViews
            if (dashboardManager && dashboardManager.getIsVisible()) dashboardManager.hide();
            if (rowboatManager && rowboatManager.getIsVisible()) rowboatManager.hide();
            if (sweDesignManager && sweDesignManager.getIsVisible()) sweDesignManager.hide();
            if (clawportManager && clawportManager.getIsVisible()) clawportManager.hide();
            if (brainManager && brainManager.getIsVisible()) brainManager.hide();
            if (agentfarmManager && agentfarmManager.getIsVisible()) agentfarmManager.hide();
            if (mirofishManager && mirofishManager.getIsVisible()) mirofishManager.hide();
            if (videoManager && videoManager.getIsVisible()) videoManager.hide();
            flowzenManager.show();
            console.log('[Main] Flowzen Diary shown');
        }
    });

    ipcMain.on('hide-flowzen', () => {
        if (flowzenManager) {
            flowzenManager.hide();
            console.log('[Main] Flowzen Diary hidden');
        }
    });

    ipcMain.handle('is-flowzen-visible', () => {
        return flowzenManager ? flowzenManager.getIsVisible() : false;
    });

    ipcMain.on('show-agentfarm-tab', (_event, tab) => {
        if (agentfarmManager) {
            // Mutual exclusion
            if (dashboardManager && dashboardManager.getIsVisible()) dashboardManager.hide();
            if (rowboatManager && rowboatManager.getIsVisible()) rowboatManager.hide();
            if (sweDesignManager && sweDesignManager.getIsVisible()) sweDesignManager.hide();
            if (clawportManager && clawportManager.getIsVisible()) clawportManager.hide();
            if (brainManager && brainManager.getIsVisible()) brainManager.hide();
            if (flowzenManager && flowzenManager.getIsVisible()) flowzenManager.hide();
            agentfarmManager.show();
            // Send tab switch to the AgentFarm BrowserView
            const view = agentfarmManager.agentfarmView;
            if (view && view.webContents) {
                view.webContents.send('agentfarm-switch-tab', { tab });
            }
            console.log(`[Main] Agent Farm shown (tab: ${tab})`);
        }
    });

    ipcMain.handle('is-agentfarm-visible', () => {
        return agentfarmManager ? agentfarmManager.getIsVisible() : false;
    });

    // ── Agent Farm IPC → Python handlers ──

    ipcMain.handle('agentfarm:get-projects', async (_event, { statusFilter, limit }) => {
        try {
            return await sendToPythonAndWait({ type: 'get_projects', status_filter: statusFilter, limit }, 'generated_projects_list');
        } catch (e) {
            return { type: 'generated_projects_list', projects: [], error: e.message };
        }
    });

    ipcMain.handle('agentfarm:get-project-status', async (_event, { projectId, jobId }) => {
        try {
            return await sendToPythonAndWait({ type: 'get_generation_status', project_id: projectId, job_id: jobId }, 'generation_status');
        } catch (e) {
            return { type: 'generation_status', error: e.message };
        }
    });

    ipcMain.handle('agentfarm:n8n-status', async () => {
        try {
            return await sendToPythonAndWait({ type: 'n8n_status' }, 'n8n_status_result');
        } catch (e) {
            return { online: false, error: e.message };
        }
    });

    ipcMain.handle('agentfarm:n8n-list', async () => {
        try {
            return await sendToPythonAndWait({ type: 'n8n_list' }, 'n8n_list_result');
        } catch (e) {
            return { workflows: [], error: e.message };
        }
    });

    ipcMain.handle('agentfarm:n8n-generate', async (_event, { description }) => {
        try {
            return await sendToPythonAndWait({ type: 'n8n_generate', description }, 'n8n_generate_result');
        } catch (e) {
            return { success: false, error: e.message };
        }
    });

    ipcMain.handle('agentfarm:n8n-activate', async (_event, { workflowId }) => {
        try {
            return await sendToPythonAndWait({ type: 'n8n_activate', workflow_id: workflowId }, 'n8n_activate_result');
        } catch (e) {
            return { success: false, error: e.message };
        }
    });

    ipcMain.handle('agentfarm:n8n-deactivate', async (_event, { workflowId }) => {
        try {
            return await sendToPythonAndWait({ type: 'n8n_deactivate', workflow_id: workflowId }, 'n8n_deactivate_result');
        } catch (e) {
            return { success: false, error: e.message };
        }
    });

    ipcMain.handle('agentfarm:n8n-delete', async (_event, { workflowId }) => {
        try {
            return await sendToPythonAndWait({ type: 'n8n_delete', workflow_id: workflowId }, 'n8n_delete_result');
        } catch (e) {
            return { success: false, error: e.message };
        }
    });

    // ── AgentFarm Autogen Handlers ──────────────────────────────
    ipcMain.handle('agentfarm:create-team', async (_, templateId, config) => {
        return await sendToPythonAndWait(
            { type: 'agentfarm_create_team', template_id: templateId, ...config },
            'agentfarm_create_team_result'
        );
    });

    ipcMain.handle('agentfarm:run-team', async (_, teamId, task) => {
        return await sendToPythonAndWait(
            { type: 'agentfarm_run', team_id: teamId, task },
            'agentfarm_run_result'
        );
    });

    ipcMain.handle('agentfarm:farm-status', async () => {
        return await sendToPythonAndWait(
            { type: 'agentfarm_status' },
            'agentfarm_status_result'
        );
    });

    ipcMain.handle('agentfarm:list-teams', async () => {
        return await sendToPythonAndWait(
            { type: 'agentfarm_list_teams' },
            'agentfarm_list_teams_result'
        );
    });

    ipcMain.handle('agentfarm:stop-run', async (_, runId) => {
        return await sendToPythonAndWait(
            { type: 'agentfarm_stop_run', run_id: runId },
            'agentfarm_stop_run_result'
        );
    });

    ipcMain.handle('agentfarm:run-results', async (_, runId) => {
        return await sendToPythonAndWait(
            { type: 'agentfarm_run_results', run_id: runId },
            'agentfarm_run_results_result'
        );
    });

    // ========================================
    // VIDEO PRODUCTION (Agent Farm Video tab)
    // ========================================

    ipcMain.handle('agentfarm:video-status', async () => {
        try {
            return await sendToPythonAndWait({ type: 'video_status' }, 'video_status_result');
        } catch (e) {
            return { success: false, error: e.message };
        }
    });

    ipcMain.handle('agentfarm:video-team-run', async (_event, { step }) => {
        try {
            return await sendToPythonAndWait({ type: 'video_team_run', step }, 'video_team_run_result', 600000);
        } catch (e) {
            return { success: false, error: e.message };
        }
    });

    ipcMain.handle('agentfarm:video-vision', async (_event, params) => {
        try {
            return await sendToPythonAndWait({ type: 'video_vision', ...params }, 'video_vision_result', 600000);
        } catch (e) {
            return { success: false, error: e.message };
        }
    });

    ipcMain.handle('agentfarm:video-demo-analyze', async (_event, { input_file, target_duration }) => {
        try {
            return await sendToPythonAndWait({ type: 'video_demo_analyze', input_file, target_duration }, 'video_demo_analyze_result', 120000);
        } catch (e) {
            return { success: false, error: e.message };
        }
    });

    ipcMain.handle('agentfarm:video-demo-build', async (_event, { config_path }) => {
        try {
            return await sendToPythonAndWait({ type: 'video_demo_build', config_path }, 'video_demo_build_result', 600000);
        } catch (e) {
            return { success: false, error: e.message };
        }
    });

    ipcMain.handle('agentfarm:video-lipsync', async (_event, { person }) => {
        try {
            return await sendToPythonAndWait({ type: 'video_lipsync', person }, 'video_lipsync_result', 600000);
        } catch (e) {
            return { success: false, error: e.message };
        }
    });

    ipcMain.handle('agentfarm:video-lipsync-analyze', async () => {
        try {
            return await sendToPythonAndWait({ type: 'video_lipsync_analyze' }, 'video_lipsync_analyze_result', 120000);
        } catch (e) {
            return { success: false, error: e.message };
        }
    });

    ipcMain.handle('agentfarm:video-voice-clone', async () => {
        try {
            return await sendToPythonAndWait({ type: 'video_voice_clone' }, 'video_voice_clone_result', 120000);
        } catch (e) {
            return { success: false, error: e.message };
        }
    });

    ipcMain.handle('agentfarm:video-voice-tts', async (_event, { person }) => {
        try {
            return await sendToPythonAndWait({ type: 'video_voice_tts', person }, 'video_voice_tts_result', 120000);
        } catch (e) {
            return { success: false, error: e.message };
        }
    });

    ipcMain.handle('agentfarm:video-list', async () => {
        try {
            return await sendToPythonAndWait({ type: 'video_list' }, 'video_list_result', 15000);
        } catch (e) {
            return { success: false, message: e.message, videos: [] };
        }
    });

    // ========================================
    // EYETERM CAMERA PREVIEW CONTROL
    // ========================================

    ipcMain.on('eyeterm:toggle', () => {
        if (eyetermManager) {
            const visible = eyetermManager.toggle();
            console.log('[Main] eyeTerm camera preview:', visible ? 'shown' : 'hidden');
        }
    });

    ipcMain.handle('eyeterm:get-status', () => {
        return eyetermManager ? eyetermManager.getStatus() : { visible: false };
    });

    ipcMain.handle('eyeterm:toggle-cursor', async () => {
        try {
            return await sendToPythonAndWait({ type: 'eyeterm_toggle_cursor' }, 'eyeterm_cursor_status');
        } catch (e) {
            return { success: false, error: e.message };
        }
    });

    ipcMain.handle('eyeterm:calibrate', async () => {
        try {
            return await sendToPythonAndWait({ type: 'eyeterm_calibrate' }, 'eyeterm_calibrate_result');
        } catch (e) {
            return { success: false, error: e.message };
        }
    });

    // ── ClawPort IPC → Python handlers ──

    ipcMain.handle('clawport:get-memory-overview', async () => {
        try {
            return await sendToPythonAndWait({ type: 'get_memory_overview' }, 'memory_overview');
        } catch (e) {
            return { type: 'memory_overview', data: { task_memory: { available: false }, conversation_memory: { available: false }, user_profiles: { available: false } } };
        }
    });

    ipcMain.handle('clawport:search-memory', async (_event, { query, category, limit }) => {
        try {
            return await sendToPythonAndWait({ type: 'search_memory', query, category, limit }, 'memory_search_results');
        } catch (e) {
            return { type: 'memory_search_results', category, results: [] };
        }
    });

    ipcMain.handle('clawport:get-recent-memory', async (_event, { category, limit }) => {
        try {
            return await sendToPythonAndWait({ type: 'get_recent_memory', category, limit }, 'recent_memory');
        } catch (e) {
            return { type: 'recent_memory', category, results: [] };
        }
    });

    ipcMain.handle('clawport:get-scheduled-tasks', async (_event, { status, limit }) => {
        try {
            return await sendToPythonAndWait({ type: 'get_scheduled_tasks', status, limit }, 'scheduled_tasks_list');
        } catch (e) {
            return { type: 'scheduled_tasks_list', tasks: [], total: 0 };
        }
    });

    ipcMain.handle('clawport:update-task-status', async (_event, { taskId, status }) => {
        try {
            return await sendToPythonAndWait({ type: 'update_task_status', task_id: taskId, status }, 'task_status_updated');
        } catch (e) {
            return { type: 'task_status_updated', success: false, task_id: taskId };
        }
    });

    ipcMain.handle('clawport:get-agent-status', async () => {
        try {
            return await sendToPythonAndWait({ type: 'get_agent_status' }, 'agent_status_list');
        } catch (e) {
            return { type: 'agent_status_list', agents: [] };
        }
    });

    ipcMain.handle('clawport:get-projects', async (_event, { statusFilter, limit }) => {
        try {
            return await sendToPythonAndWait(
                { type: 'get_generated_projects', status_filter: statusFilter, limit: limit || 20 },
                'generated_projects_list'
            );
        } catch (e) {
            return { type: 'generated_projects_list', projects: [] };
        }
    });

    ipcMain.handle('clawport:get-generation-status', async (_event, { projectId, jobId }) => {
        try {
            return await sendToPythonAndWait(
                { type: 'get_generation_status', project_id: projectId, job_id: jobId },
                'generation_status'
            );
        } catch (e) {
            return { type: 'generation_status', error: e.message };
        }
    });

    ipcMain.handle('clawport:chat-text-input', async (_event, { text }) => {
        try {
            return await sendToPythonAndWait({ type: 'chat_text_input', text }, 'chat_response', 30000);
        } catch (e) {
            return { type: 'chat_response', success: false, message: `Timeout: ${e.message}` };
        }
    });

    // Game console chat overlay (renderer 3D view → same pipeline as voice)
    ipcMain.handle('renderer:chat-text-input', async (_event, { text }) => {
        try {
            return await sendToPythonAndWait({ type: 'chat_text_input', text }, 'chat_response', 30000);
        } catch (e) {
            return { type: 'chat_response', success: false, message: `Timeout: ${e.message}` };
        }
    });

    ipcMain.handle('clawport:get-conversation-history', async (_event, { limit }) => {
        try {
            return await sendToPythonAndWait({ type: 'get_conversation_history', limit }, 'conversation_history');
        } catch (e) {
            return { type: 'conversation_history', messages: [] };
        }
    });

    // ── Plugin Management ──

    ipcMain.handle('clawport:get-plugins', async () => {
        try {
            return await sendToPythonAndWait({ type: 'get_plugins' }, 'plugin_list');
        } catch (e) {
            return { type: 'plugin_list', plugins: [], total_enabled: 0, total_available: 0 };
        }
    });

    ipcMain.handle('clawport:accept-plugin', async (_event, { pluginId }) => {
        try {
            return await sendToPythonAndWait({ type: 'accept_plugin', plugin_id: pluginId }, 'plugin_action_result');
        } catch (e) {
            return { success: false, error: e.message };
        }
    });

    ipcMain.handle('clawport:reject-plugin', async (_event, { pluginId }) => {
        try {
            return await sendToPythonAndWait({ type: 'reject_plugin', plugin_id: pluginId }, 'plugin_action_result');
        } catch (e) {
            return { success: false, error: e.message };
        }
    });

    ipcMain.handle('clawport:toggle-plugin', async (_event, { pluginId, enabled }) => {
        try {
            return await sendToPythonAndWait({ type: 'toggle_plugin', plugin_id: pluginId, enabled }, 'plugin_action_result');
        } catch (e) {
            return { success: false, error: e.message };
        }
    });

    // ── n8n Workflow Builder ──

    ipcMain.handle('clawport:n8n-status', async () => {
        try {
            return await sendToPythonAndWait({ type: 'n8n_status' }, 'n8n_status_result', 10000);
        } catch (e) {
            return { online: false, error: e.message };
        }
    });

    ipcMain.handle('clawport:n8n-list', async () => {
        try {
            return await sendToPythonAndWait({ type: 'n8n_list' }, 'n8n_list_result', 10000);
        } catch (e) {
            return { workflows: [] };
        }
    });

    ipcMain.handle('clawport:n8n-generate', async (_event, { description }) => {
        try {
            return await sendToPythonAndWait({ type: 'n8n_generate', description }, 'n8n_generate_result', 60000);
        } catch (e) {
            return { success: false, message: `Timeout: ${e.message}` };
        }
    });

    ipcMain.handle('clawport:n8n-activate', async (_event, { workflowId }) => {
        try {
            return await sendToPythonAndWait({ type: 'n8n_activate', workflow_id: workflowId }, 'n8n_activate_result', 10000);
        } catch (e) {
            return { success: false, message: e.message };
        }
    });

    ipcMain.handle('clawport:n8n-deactivate', async (_event, { workflowId }) => {
        try {
            return await sendToPythonAndWait({ type: 'n8n_deactivate', workflow_id: workflowId }, 'n8n_deactivate_result', 10000);
        } catch (e) {
            return { success: false, message: e.message };
        }
    });

    ipcMain.handle('clawport:n8n-delete', async (_event, { workflowId }) => {
        try {
            return await sendToPythonAndWait({ type: 'n8n_delete', workflow_id: workflowId }, 'n8n_delete_result', 10000);
        } catch (e) {
            return { success: false, message: e.message };
        }
    });

    // ── AgentFarm / Autogen ──

    ipcMain.handle('clawport:agentfarm-create-team', async (_event, { templateId, config }) => {
        try {
            return await sendToPythonAndWait(
                { type: 'agentfarm_create_team', template_id: templateId, ...config },
                'agentfarm_create_team_result'
            );
        } catch (e) {
            return { success: false, message: e.message };
        }
    });

    ipcMain.handle('clawport:agentfarm-run-team', async (_event, { teamId, task }) => {
        try {
            return await sendToPythonAndWait(
                { type: 'agentfarm_run', team_id: teamId, task },
                'agentfarm_run_result'
            );
        } catch (e) {
            return { success: false, message: e.message };
        }
    });

    ipcMain.handle('clawport:agentfarm-status', async () => {
        try {
            return await sendToPythonAndWait(
                { type: 'agentfarm_status' },
                'agentfarm_status_result'
            );
        } catch (e) {
            return { success: false, message: e.message };
        }
    });

    ipcMain.handle('clawport:agentfarm-list-teams', async () => {
        try {
            return await sendToPythonAndWait(
                { type: 'agentfarm_list_teams' },
                'agentfarm_list_teams_result'
            );
        } catch (e) {
            return { success: false, message: e.message };
        }
    });

    ipcMain.handle('clawport:agentfarm-stop-run', async (_event, { runId }) => {
        try {
            return await sendToPythonAndWait(
                { type: 'agentfarm_stop_run', run_id: runId },
                'agentfarm_stop_run_result'
            );
        } catch (e) {
            return { success: false, message: e.message };
        }
    });

    ipcMain.handle('clawport:agentfarm-run-results', async (_event, { runId }) => {
        try {
            return await sendToPythonAndWait(
                { type: 'agentfarm_run_results', run_id: runId },
                'agentfarm_run_results_result'
            );
        } catch (e) {
            return { success: false, message: e.message };
        }
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

    // Ctrl+Shift+C: Trigger eyeTerm calibration
    globalShortcut.register('CommandOrControl+Shift+C', () => {
        console.log('[Main] Shortcut: eyeTerm Calibration');
        sendToPython({ type: 'eyeterm_calibrate' });
    });
}

// ============================================================================

app.whenReady().then(async () => {
    // Initialize Sentry error tracking (requires app to be ready)
    sentry.initSentry();

    // Register vibemind-video:// protocol handler for video playback
    protocol.handle('vibemind-video', (request) => {
        const url = new URL(request.url);
        let filePath = decodeURIComponent(url.pathname);
        // Remove leading slash on Windows (e.g., /C:/... -> C:/...)
        if (process.platform === 'win32' && filePath.startsWith('/')) {
            filePath = filePath.slice(1);
        }
        // Security: only allow .mp4 from vibevideo directories
        const normalized = path.resolve(filePath);
        const allowedBase = path.resolve(__dirname, '..', 'python', 'spaces', 'video');
        if (!normalized.startsWith(allowedBase) || !normalized.endsWith('.mp4')) {
            return new Response('Forbidden', { status: 403 });
        }
        return net.fetch(`file:///${normalized.replace(/\\/g, '/')}`);
    });

    // Initialize Coding Engine managers
    dockerManager = new DockerManager();
    portAllocator = new PortAllocator();

    // Clean up stale containers from previous sessions and release their ports
    try {
        await portAllocator.cleanupStaleContainers();
    } catch (e) {
        console.warn('[Main] Container cleanup failed (Docker may not be running):', e.message);
    }

    setupIpcHandlers();
    createWindow();

    // Initialize Dashboard Manager after window is created
    dashboardManager = new DashboardManager(mainWindow);

    // Forward engine log lines and structured progress to the dashboard renderer
    if (dockerManager && dashboardManager) {
        dockerManager.setLogCallback((logLine) => {
            dashboardManager.sendMessage('engine:log', logLine);
        });
        dockerManager.setProgressCallback((progressData) => {
            dashboardManager.sendMessage('engine:progress', progressData);
        });
    }

    // Initialize Rowboat Manager for Roarboot Space
    rowboatManager = new RowboatManager(mainWindow);

    // Initialize SWE Design Manager for Factory Space
    sweDesignManager = new SweDesignManager(mainWindow);

    // Initialize ClawPort Dashboard Manager
    clawportManager = new ClawPortManager(mainWindow);

    // Initialize Brain Dashboard Manager
    brainManager = new BrainManager(mainWindow);

    // Initialize Agent Farm Manager
    agentfarmManager = new AgentFarmManager(mainWindow);

    // Initialize MiroFish Manager
    mirofishManager = new MiroFishManager(mainWindow);

    // Initialize Flowzen Diary (Blue Rose Journal) Manager
    flowzenManager = new FlowzenManager(mainWindow, sendToPython);

    // Initialize Video Space Manager
    videoManager = new VideoManager(mainWindow);

    // Initialize eyeTerm Camera Preview Manager
    eyetermManager = new EyeTermManager(mainWindow);

    // ========================================
    // N8N DOCKER AUTO-START
    // ========================================
    // Start n8n container in background if N8N_ENABLED=true
    if (process.env.N8N_ENABLED === 'true') {
        const n8nCompose = path.join(__dirname, '..', 'docker-compose.n8n.yml');
        if (fs.existsSync(n8nCompose)) {
            console.log('[Main] Starting n8n Docker container...');
            const { exec: execCb } = require('child_process');
            execCb(
                `docker compose -f "${n8nCompose}" up -d`,
                { cwd: path.join(__dirname, '..') },
                (err, stdout, stderr) => {
                    if (err) {
                        console.warn('[Main] n8n Docker start failed:', err.message);
                    } else {
                        console.log('[Main] n8n Docker started successfully');
                        if (stdout.trim()) console.log('[Main] n8n:', stdout.trim());
                    }
                }
            );
        } else {
            console.warn('[Main] docker-compose.n8n.yml not found, skipping n8n auto-start');
        }
    }

    // ========================================
    // MIROFISH DOCKER AUTO-START
    // ========================================
    // Start MiroFish containers in background if MIROFISH_ENABLED=true
    if (process.env.MIROFISH_ENABLED === 'true') {
        const mirofishCompose = path.join(__dirname, '..', 'docker-compose.mirofish.yml');
        if (fs.existsSync(mirofishCompose)) {
            console.log('[Main] Starting MiroFish Docker containers...');
            const { exec: execMf } = require('child_process');
            execMf(
                `docker compose -f "${mirofishCompose}" up -d`,
                { cwd: path.join(__dirname, '..') },
                (err, stdout, stderr) => {
                    if (err) {
                        console.warn('[Main] MiroFish Docker start failed:', err.message);
                    } else {
                        console.log('[Main] MiroFish Docker started successfully');
                        if (stdout.trim()) console.log('[Main] MiroFish:', stdout.trim());
                    }
                }
            );
        } else {
            console.warn('[Main] docker-compose.mirofish.yml not found, skipping MiroFish auto-start');
        }
    }

    // ========================================
    // ROWBOAT @x/core SERVICES INITIALIZATION
    // ========================================
    // Each phase is independent — a failure in one doesn't block the rest.
    // The critical path is: initConfigs → setupIpcHandlers.
    if (rowboatServices) {
        // Call a function only if it exists on the bundle; warn if missing
        const _rb = (name, ...args) => {
            if (typeof rowboatServices[name] !== 'function') {
                console.warn(`[Rowboat] ${name} not exported — rebuild: npm run build:rowboat`);
                return undefined;
            }
            return rowboatServices[name](...args);
        };

        // Phase 1 — Config dirs (~/.rowboat/) + VibeMind model auto-config
        try {
            await _rb('initConfigs');
            await autoConfigureRowboatModels();
            console.log('[Rowboat] Phase 1/4: configs ready');
        } catch (err) {
            console.error('[Rowboat] Phase 1/4 (configs) failed:', err.message);
        }

        // Phase 2 — IPC handlers (critical: renderer can't function without these)
        try {
            _rb('setupIpcHandlers');
            console.log('[Rowboat] Phase 2/4: IPC handlers registered');
        } catch (err) {
            console.error('[Rowboat] Phase 2/4 (IPC handlers) FAILED:', err.message);
        }

        // Phase 3 — File/run/service watchers
        try {
            _rb('startWorkspaceWatcher');
            _rb('startRunsWatcher');
            _rb('startServicesWatcher');
            console.log('[Rowboat] Phase 3/4: watchers started');
        } catch (err) {
            console.error('[Rowboat] Phase 3/4 (watchers) failed:', err.message);
        }

        // Phase 4 — Background services (graph builder + optional syncs)
        try { _rb('initGraphBuilder'); } catch (err) {
            console.warn('[Rowboat] Graph builder failed (non-critical):', err.message);
        }
        for (const svc of ['initGmailSync', 'initCalendarSync', 'initFirefliesSync',
                           'initGranolaSync', 'initPreBuiltRunner', 'initAgentRunner']) {
            try { _rb(svc); } catch { /* optional sync */ }
        }
        console.log('[Rowboat] Phase 4/4: background services started');

        // Push-Event Relay: BrowserView is not a BrowserWindow,
        // so BrowserWindow.getAllWindows() in @x/core won't reach it.
        const { bus, serviceBus, onWorkspaceChange, onOAuthConnect } = rowboatServices;
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
        if (onWorkspaceChange) {
            onWorkspaceChange((event) => {
                rowboatManager?.relayEvent('workspace:didChange', event);
            });
        }
        if (onOAuthConnect) {
            onOAuthConnect((event) => {
                console.log(`[Rowboat] OAuth event: ${event.provider} success=${event.success}`);
                rowboatManager?.relayEvent('oauth:didConnect', event);
            });
        }
        console.log('[Rowboat] Event relay configured');
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
    // Signal Python to shut down gracefully by closing stdin (triggers EOF → cleanup)
    if (pythonProcess && pythonProcess.stdin && !pythonProcess.stdin.destroyed) {
        try {
            pythonProcess.stdin.end();
            console.log('[Main] Closed Python stdin (graceful shutdown signal)');
        } catch (e) {
            console.warn('[Main] stdin.end() error:', e.message);
        }
    }

    // Unregister shortcuts
    globalShortcut.unregisterAll();

    if (process.platform !== 'darwin') {
        app.quit();
    }
});

let dockerCleanupDone = false;
app.on('before-quit', (event) => {
    if (dockerManager && !dockerCleanupDone) {
        event.preventDefault();
        // Docker cleanup with 5s timeout to prevent hanging
        const dockerTimeout = setTimeout(() => {
            console.warn('[Main] Docker cleanup timed out (5s), forcing quit');
            dockerCleanupDone = true;
            app.quit();
        }, 5000);
        dockerManager.stopAllContainers()
            .catch(e => console.warn('[Main] Docker cleanup error:', e.message))
            .finally(() => {
                clearTimeout(dockerTimeout);
                dockerCleanupDone = true;
                app.quit();
            });
        return;
    }
});

app.on('will-quit', () => {
    // Kill Python process tree (main + all child threads/subprocesses)
    if (pythonProcess) {
        const pid = pythonProcess.pid;
        console.log(`[Main] Killing Python process tree (PID ${pid})`);

        // If stdin wasn't closed yet, close it first (graceful signal)
        if (pythonProcess.stdin && !pythonProcess.stdin.destroyed) {
            try { pythonProcess.stdin.end(); } catch (e) { /* ignore */ }
        }

        // taskkill /T kills the entire process tree on Windows
        const { execFileSync } = require('child_process');
        try {
            if (process.platform === 'win32') {
                execFileSync('taskkill', ['/PID', String(pid), '/T', '/F'], { timeout: 5000 });
            } else {
                // POSIX: kill process group
                process.kill(-pid, 'SIGKILL');
            }
            console.log('[Main] Python process tree killed');
        } catch (e) {
            console.warn('[Main] Process tree kill failed:', e.message);
            // Fallback: kill just the main process
            try { pythonProcess.kill('SIGKILL'); } catch (_) { /* ignore */ }
        }
        pythonProcess = null;
    }

    // Stop Rowboat watchers (guard: may never have been started)
    if (rowboatServices) {
        for (const fn of ['stopWorkspaceWatcher', 'stopRunsWatcher', 'stopServicesWatcher']) {
            try { if (typeof rowboatServices[fn] === 'function') rowboatServices[fn](); } catch { /* best-effort */ }
        }
        console.log('[Rowboat] Watchers stopped');
    }

    // Destroy BrowserView managers
    if (rowboatManager) rowboatManager.destroy();
    if (sweDesignManager) sweDesignManager.destroy();
    if (clawportManager) clawportManager.destroy();
    if (brainManager) brainManager.destroy();

    globalShortcut.unregisterAll();
});
