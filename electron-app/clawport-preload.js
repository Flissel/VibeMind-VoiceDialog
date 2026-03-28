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

  // ── n8n Workflows ──
  openN8nEditor: (workflowId) =>
    ipcRenderer.invoke('clawport:open-n8n-editor', { workflowId }),
  n8nStatus: () =>
    ipcRenderer.invoke('clawport:n8n-status'),

  n8nList: () =>
    ipcRenderer.invoke('clawport:n8n-list'),

  n8nGenerate: (description) =>
    ipcRenderer.invoke('clawport:n8n-generate', { description }),

  n8nActivate: (workflowId) =>
    ipcRenderer.invoke('clawport:n8n-activate', { workflowId }),

  n8nDeactivate: (workflowId) =>
    ipcRenderer.invoke('clawport:n8n-deactivate', { workflowId }),

  n8nDelete: (workflowId) =>
    ipcRenderer.invoke('clawport:n8n-delete', { workflowId }),

  // ── Projects / Coding Engine ──
  getProjects: (statusFilter, limit) =>
    ipcRenderer.invoke('clawport:get-projects', { statusFilter, limit }),

  getGenerationStatus: (projectId, jobId) =>
    ipcRenderer.invoke('clawport:get-generation-status', { projectId, jobId }),

  // ── Plugins ──
  getPlugins: () =>
    ipcRenderer.invoke('clawport:get-plugins'),

  acceptPlugin: (pluginId) =>
    ipcRenderer.invoke('clawport:accept-plugin', { pluginId }),

  rejectPlugin: (pluginId) =>
    ipcRenderer.invoke('clawport:reject-plugin', { pluginId }),

  togglePlugin: (pluginId, enabled) =>
    ipcRenderer.invoke('clawport:toggle-plugin', { pluginId, enabled }),

  // ── AgentFarm / Autogen ──
  agentfarmCreateTeam: (templateId, config) =>
    ipcRenderer.invoke('clawport:agentfarm-create-team', { templateId, config }),

  agentfarmRunTeam: (teamId, task) =>
    ipcRenderer.invoke('clawport:agentfarm-run-team', { teamId, task }),

  agentfarmStatus: () =>
    ipcRenderer.invoke('clawport:agentfarm-status'),

  agentfarmListTeams: () =>
    ipcRenderer.invoke('clawport:agentfarm-list-teams'),

  agentfarmStopRun: (runId) =>
    ipcRenderer.invoke('clawport:agentfarm-stop-run', { runId }),

  agentfarmRunResults: (runId) =>
    ipcRenderer.invoke('clawport:agentfarm-run-results', { runId }),

  // ── Models Config ──
  getModelsConfig: () =>
    ipcRenderer.invoke('clawport:get-models-config'),

  updateModelRole: (role, provider, model, maxTokens) =>
    ipcRenderer.invoke('clawport:update-model-role', { role, provider, model, maxTokens }),

  testModelConnection: (role) =>
    ipcRenderer.invoke('clawport:test-model-connection', { role }),

  // ── Python message push events ──
  onPythonMessage: (callback) => {
    ipcRenderer.on('clawport-message', (_event, message) => {
      callback(message);
    });
  },

  // ── Dashboard control ──
  closeDashboard: () => ipcRenderer.send('hide-clawport'),
});
