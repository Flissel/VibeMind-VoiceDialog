/**
 * Agent Farm Preload Script
 *
 * Exposes safe IPC methods to the Agent Farm BrowserView.
 * Separate from main preload.js to keep API boundaries clean.
 */

const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('vibemindAgentFarm', {
  // ── Projects / Coding Engine (Autogen tab) ──
  getProjects: (statusFilter, limit) =>
    ipcRenderer.invoke('agentfarm:get-projects', { statusFilter, limit }),

  getProjectStatus: (projectId, jobId) =>
    ipcRenderer.invoke('agentfarm:get-project-status', { projectId, jobId }),

  // ── n8n Workflows (n8n tab) ──
  n8nStatus: () =>
    ipcRenderer.invoke('agentfarm:n8n-status'),

  n8nList: () =>
    ipcRenderer.invoke('agentfarm:n8n-list'),

  n8nGenerate: (description) =>
    ipcRenderer.invoke('agentfarm:n8n-generate', { description }),

  n8nActivate: (workflowId) =>
    ipcRenderer.invoke('agentfarm:n8n-activate', { workflowId }),

  n8nDeactivate: (workflowId) =>
    ipcRenderer.invoke('agentfarm:n8n-deactivate', { workflowId }),

  n8nDelete: (workflowId) =>
    ipcRenderer.invoke('agentfarm:n8n-delete', { workflowId }),

  // ── Video Production (Video tab) ──
  videoStatus: () =>
    ipcRenderer.invoke('agentfarm:video-status'),

  videoTeamRun: (step) =>
    ipcRenderer.invoke('agentfarm:video-team-run', { step }),

  videoVision: (params) =>
    ipcRenderer.invoke('agentfarm:video-vision', params || {}),

  videoDemoAnalyze: (inputFile, targetDuration) =>
    ipcRenderer.invoke('agentfarm:video-demo-analyze', { input_file: inputFile, target_duration: targetDuration }),

  videoDemoBuild: (configPath) =>
    ipcRenderer.invoke('agentfarm:video-demo-build', { config_path: configPath }),

  videoLipsync: (person) =>
    ipcRenderer.invoke('agentfarm:video-lipsync', { person }),

  videoLipsyncAnalyze: () =>
    ipcRenderer.invoke('agentfarm:video-lipsync-analyze'),

  videoVoiceClone: () =>
    ipcRenderer.invoke('agentfarm:video-voice-clone'),

  videoVoiceTts: (person) =>
    ipcRenderer.invoke('agentfarm:video-voice-tts', { person }),

  // ── Video Gallery ──
  videoList: () =>
    ipcRenderer.invoke('agentfarm:video-list'),

  // ── Autogen team management ──
  createTeam: (templateId, config) => ipcRenderer.invoke('agentfarm:create-team', templateId, config),
  runTeam: (teamId, task) => ipcRenderer.invoke('agentfarm:run-team', teamId, task),
  getAgentFarmStatus: () => ipcRenderer.invoke('agentfarm:farm-status'),
  listTeams: () => ipcRenderer.invoke('agentfarm:list-teams'),
  stopRun: (runId) => ipcRenderer.invoke('agentfarm:stop-run', runId),
  getRunResults: (runId) => ipcRenderer.invoke('agentfarm:run-results', runId),

  // ── Python message push events ──
  onMessage: (callback) => {
    ipcRenderer.on('agentfarm-message', (_event, message) => {
      callback(message);
    });
  },

  // ── Tab control ──
  switchTab: (tab) => {
    ipcRenderer.on('agentfarm-switch-tab', (_event, data) => {});
    // Also expose for direct calls
    window.dispatchEvent(new CustomEvent('agentfarm-switch-tab', { detail: { tab } }));
  },

  onSwitchTab: (callback) => {
    ipcRenderer.on('agentfarm-switch-tab', (_event, data) => callback(data));
  },

  // ── View control ──
  closeAgentFarm: () => ipcRenderer.send('hide-agentfarm'),
});
