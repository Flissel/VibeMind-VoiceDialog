/**
 * VibeMind Electron Main Process
 *
 * Manages the main window, Python backend process,
 * and IPC communication between renderer and Python.
 */

const { app, BrowserWindow, ipcMain, Tray, Menu, globalShortcut, shell } = require('electron');
const { spawn } = require('child_process');

const path = require('path');

// Coding Engine Dashboard Integration
const DockerManager = require('./docker-manager');
const PortAllocator = require('./port-allocator');
const DashboardManager = require('./dashboard-manager');

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

    mainWindow.loadFile('renderer/index.html');

    // Open DevTools for debugging
    mainWindow.webContents.openDevTools();

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

    // Projects (from req-orchestrator API)
    const ORCHESTRATOR_API = process.env.ORCHESTRATOR_API_URL || 'http://localhost:8087';
    const fetch = require('node-fetch');

    ipcMain.handle('projects:get-all', async () => {
        try {
            const response = await fetch(`${ORCHESTRATOR_API}/api/projects`);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            return await response.json();
        } catch (error) {
            console.error('[Projects] Failed to fetch:', error.message);
            return [];
        }
    });

    ipcMain.handle('projects:get', async (event, id) => {
        try {
            const response = await fetch(`${ORCHESTRATOR_API}/api/projects/${id}`);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            return await response.json();
        } catch (error) {
            console.error('[Projects] Failed to fetch:', error.message);
            return null;
        }
    });

    ipcMain.handle('projects:create', async (event, data) => {
        try {
            const response = await fetch(`${ORCHESTRATOR_API}/api/projects`, {
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
            const response = await fetch(`${ORCHESTRATOR_API}/api/projects/${id}`, {
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
            const response = await fetch(`${ORCHESTRATOR_API}/api/projects/${id}/status`);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            return await response.json();
        } catch (error) {
            console.error('[Projects] Failed to get status:', error.message);
            return { status: 'unknown' };
        }
    });

    // Dashboard View Control
    ipcMain.on('show-dashboard', () => {
        if (dashboardManager) {
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

app.whenReady().then(() => {
    // Initialize Coding Engine managers
    dockerManager = new DockerManager();
    portAllocator = new PortAllocator();

    setupIpcHandlers();
    createWindow();

    // Initialize Dashboard Manager after window is created
    dashboardManager = new DashboardManager(mainWindow);

    startPythonBackend();
    // createTray();  // Uncomment when icon is available
    registerShortcuts();

    console.log('[Main] Coding Engine Dashboard integration initialized');

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
    globalShortcut.unregisterAll();
});
