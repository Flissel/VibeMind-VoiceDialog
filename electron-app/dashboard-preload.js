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
    getApiUrl: () => ipcRenderer.invoke('engine:get-api-url'),
  },

  // ===== FILE SYSTEM =====
  fs: {
    openFolder: (path) => ipcRenderer.invoke('fs:open-folder', path),
    showInExplorer: (path) => ipcRenderer.invoke('fs:show-in-explorer', path),
  },

  // ===== PROJECTS (Orchestrator) =====
  projects: {
    getAll: () => ipcRenderer.invoke('projects:get-all'),
    get: (id) => ipcRenderer.invoke('projects:get', id),
    create: (data) => ipcRenderer.invoke('projects:create', data),
    delete: (id) => ipcRenderer.invoke('projects:delete', id),
    getStatus: (id) => ipcRenderer.invoke('projects:get-status', id),
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
    getApiUrl: () => ipcRenderer.invoke('engine:get-api-url'),
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
  },
});

console.log('[Dashboard Preload] VibeMind + ElectronAPI exposed to dashboard');
