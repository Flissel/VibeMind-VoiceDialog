/**
 * Dashboard Preload Script for VibeMind
 *
 * Exposes the vibemind API to the Coding Engine Dashboard BrowserView.
 * This bridges the dashboard React app with VibeMind's main process.
 */

const { contextBridge, ipcRenderer } = require('electron');

// Expose vibemind API that the dashboard can use
contextBridge.exposeInMainWorld('vibemind', {
  // ===== DOCKER MANAGEMENT =====
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

  // ===== PORT ALLOCATION =====
  ports: {
    getVncPort: (projectId) => ipcRenderer.invoke('ports:get-vnc-port', projectId),
    getAppPort: (projectId) => ipcRenderer.invoke('ports:get-app-port', projectId),
    getAll: () => ipcRenderer.invoke('ports:get-all'),
  },

  // ===== ENGINE CONTROL =====
  engine: {
    startGeneration: (requirementsPath, outputDir) =>
      ipcRenderer.invoke('engine:start-generation', { requirementsPath, outputDir }),
    startGenerationWithPreview: (projectId, requirementsPath, outputDir, forceGenerate = false) =>
      ipcRenderer.invoke('engine:start-generation-with-preview', projectId, requirementsPath, outputDir, forceGenerate),
    startOrchestratorGenerationWithPreview: (projectId, projectPath, outputDir) =>
      ipcRenderer.invoke('engine:start-orchestrator-generation-with-preview', projectId, projectPath, outputDir),
    stopGeneration: (projectId) =>
      ipcRenderer.invoke('engine:stop-generation', projectId),
    getApiUrl: () => ipcRenderer.invoke('engine:get-api-url'),
    startEpicGeneration: (projectId, projectPath, outputDir) =>
      ipcRenderer.invoke('engine:start-epic-generation', projectId, projectPath, outputDir),
    getEpics: (projectPath) =>
      ipcRenderer.invoke('engine:get-epics', projectPath),
    getEpicTasks: (epicId, projectPath) =>
      ipcRenderer.invoke('engine:get-epic-tasks', epicId, projectPath),
    runEpic: (epicId, projectPath) =>
      ipcRenderer.invoke('engine:run-epic', epicId, projectPath),
    rerunEpic: (epicId, projectPath) =>
      ipcRenderer.invoke('engine:rerun-epic', epicId, projectPath),
    rerunTask: (epicId, taskId, projectPath, fixInstructions) =>
      ipcRenderer.invoke('engine:rerun-task', epicId, taskId, projectPath, fixInstructions),
    generateTaskLists: (projectPath) =>
      ipcRenderer.invoke('engine:generate-task-lists', projectPath),
  },

  // ===== FILE SYSTEM =====
  fs: {
    openFolder: (path) => ipcRenderer.invoke('fs:open-folder', path),
    showInExplorer: (path) => ipcRenderer.invoke('fs:show-in-explorer', path),
  },

  // ===== PROJECTS (Orchestrator + Local RE) =====
  projects: {
    getAll: () => ipcRenderer.invoke('projects:get-all'),
    get: (id) => ipcRenderer.invoke('projects:get', id),
    create: (data) => ipcRenderer.invoke('projects:create', data),
    delete: (id) => ipcRenderer.invoke('projects:delete', id),
    getStatus: (id) => ipcRenderer.invoke('projects:get-status', id),
    sendToEngine: (projectIds) => ipcRenderer.invoke('projects:send-to-engine', projectIds),
    scanLocalDirs: (paths) => ipcRenderer.invoke('projects:scan-local-dirs', paths),
    getREDetail: (projectPath) => ipcRenderer.invoke('projects:get-re-detail', projectPath),
  },

  // ===== VIBEMIND COMMUNICATION =====

  // Listen for messages from Python backend
  onPythonMessage: (callback) => {
    ipcRenderer.on('python-message', (event, message) => {
      callback(message);
    });
  },

  // Send message to Python backend
  sendToPython: (message) => ipcRenderer.send('to-python', message),

  // ===== ENGINE LOG STREAM =====

  // Listen for real-time engine log lines forwarded by main process
  onEngineLog: (callback) => {
    ipcRenderer.on('engine:log', (_, logLine) => {
      callback(logLine);
    });
    return () => ipcRenderer.removeAllListeners('engine:log');
  },

  // ===== ENGINE PROGRESS STREAM =====

  // Listen for structured progress data from run_engine.py (via docker-manager.js)
  onEngineProgress: (callback) => {
    ipcRenderer.on('engine:progress', (_, progressData) => {
      callback(progressData);
    });
    return () => ipcRenderer.removeAllListeners('engine:progress');
  },

  // ===== DASHBOARD CONTROL =====

  // Request to close/minimize dashboard
  closeDashboard: () => ipcRenderer.send('hide-dashboard'),

  // Check if in embedded mode
  isEmbedded: true,
});

// Also expose as electronAPI for dashboard compatibility
contextBridge.exposeInMainWorld('electronAPI', {
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
  ports: {
    getVncPort: (projectId) => ipcRenderer.invoke('ports:get-vnc-port', projectId),
    getAppPort: (projectId) => ipcRenderer.invoke('ports:get-app-port', projectId),
    getAll: () => ipcRenderer.invoke('ports:get-all'),
  },
  engine: {
    startGeneration: (requirementsPath, outputDir) =>
      ipcRenderer.invoke('engine:start-generation', { requirementsPath, outputDir }),
    startGenerationWithPreview: (projectId, requirementsPath, outputDir, forceGenerate = false) =>
      ipcRenderer.invoke('engine:start-generation-with-preview', projectId, requirementsPath, outputDir, forceGenerate),
    startOrchestratorGenerationWithPreview: (projectId, projectPath, outputDir) =>
      ipcRenderer.invoke('engine:start-orchestrator-generation-with-preview', projectId, projectPath, outputDir),
    stopGeneration: (projectId) =>
      ipcRenderer.invoke('engine:stop-generation', projectId),
    getApiUrl: () => ipcRenderer.invoke('engine:get-api-url'),
    startEpicGeneration: (projectId, projectPath, outputDir) =>
      ipcRenderer.invoke('engine:start-epic-generation', projectId, projectPath, outputDir),
    getEpics: (projectPath) =>
      ipcRenderer.invoke('engine:get-epics', projectPath),
    getEpicTasks: (epicId, projectPath) =>
      ipcRenderer.invoke('engine:get-epic-tasks', epicId, projectPath),
    runEpic: (epicId, projectPath) =>
      ipcRenderer.invoke('engine:run-epic', epicId, projectPath),
    rerunEpic: (epicId, projectPath) =>
      ipcRenderer.invoke('engine:rerun-epic', epicId, projectPath),
    rerunTask: (epicId, taskId, projectPath, fixInstructions) =>
      ipcRenderer.invoke('engine:rerun-task', epicId, taskId, projectPath, fixInstructions),
    generateTaskLists: (projectPath) =>
      ipcRenderer.invoke('engine:generate-task-lists', projectPath),
  },
  fs: {
    openFolder: (path) => ipcRenderer.invoke('fs:open-folder', path),
    showInExplorer: (path) => ipcRenderer.invoke('fs:show-in-explorer', path),
  },
  projects: {
    getAll: () => ipcRenderer.invoke('projects:get-all'),
    get: (id) => ipcRenderer.invoke('projects:get', id),
    create: (data) => ipcRenderer.invoke('projects:create', data),
    delete: (id) => ipcRenderer.invoke('projects:delete', id),
    getStatus: (id) => ipcRenderer.invoke('projects:get-status', id),
    sendToEngine: (projectIds) => ipcRenderer.invoke('projects:send-to-engine', projectIds),
    scanLocalDirs: (paths) => ipcRenderer.invoke('projects:scan-local-dirs', paths),
    getREDetail: (projectPath) => ipcRenderer.invoke('projects:get-re-detail', projectPath),
  },

  // ===== SERVICES (stub — prevents crash when no IPC handler is wired) =====
  services: {
    onStatusUpdate: (_callback) => {
      // No-op: service status currently falls back to REST polling
    },
  },

  // ===== DEBUG (stubs) =====
  debug: {
    getBrowserErrors: () => Promise.resolve([]),
    getDockerLogs: (_id) => Promise.resolve(''),
    captureScreenshot: () => Promise.resolve(null),
  },
});

console.log('[Dashboard Preload] VibeMind + ElectronAPI exposed to dashboard');
