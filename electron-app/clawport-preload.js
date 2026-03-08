/**
 * ClawPort Dashboard Preload Script
 *
 * Exposes safe IPC methods to the dashboard BrowserView.
 * Separate from main preload.js to keep API boundaries clean.
 */

const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('vibemindDashboard', {
  // ── Memory ──
  getMemoryOverview: () =>
    ipcRenderer.invoke('clawport:get-memory-overview'),

  searchMemory: (query, category, limit) =>
    ipcRenderer.invoke('clawport:search-memory', { query, category, limit }),

  getRecentMemory: (category, limit) =>
    ipcRenderer.invoke('clawport:get-recent-memory', { category, limit }),

  // ── Schedule ──
  getScheduledTasks: (status, limit) =>
    ipcRenderer.invoke('clawport:get-scheduled-tasks', { status, limit }),

  updateTaskStatus: (taskId, status) =>
    ipcRenderer.invoke('clawport:update-task-status', { taskId, status }),

  // ── Agent Status ──
  getAgentStatus: () =>
    ipcRenderer.invoke('clawport:get-agent-status'),

  // ── Chat ──
  sendChatMessage: (text) =>
    ipcRenderer.invoke('clawport:chat-text-input', { text }),

  getConversationHistory: (limit) =>
    ipcRenderer.invoke('clawport:get-conversation-history', { limit }),

  // ── Python message push events ──
  onPythonMessage: (callback) => {
    ipcRenderer.on('clawport-message', (_event, message) => {
      callback(message);
    });
  },

  // ── Dashboard control ──
  closeDashboard: () => ipcRenderer.send('hide-clawport'),
});
