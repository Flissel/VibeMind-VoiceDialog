/**
 * Video Space Preload — exposes IPC bridge for video-ui BrowserView.
 *
 * Same API as agentfarm-preload.js video methods, plus videoList() for gallery.
 */

const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('vibemindVideo', {
  // ── Video tools ──
  videoStatus: () =>
    ipcRenderer.invoke('agentfarm:video-status'),

  videoTeamRun: (step) =>
    ipcRenderer.invoke('agentfarm:video-team-run', { step }),

  videoVision: (params) =>
    ipcRenderer.invoke('agentfarm:video-vision', params || {}),

  videoDemoAnalyze: (inputFile, targetDuration) =>
    ipcRenderer.invoke('agentfarm:video-demo-analyze', {
      input_file: inputFile,
      target_duration: targetDuration,
    }),

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

  // ── Video Projects ──
  createProject: (name, description) =>
    ipcRenderer.invoke('video:project-create', { name, description }),

  addProjectPerson: (projectId, name, role, rawVideoPath) =>
    ipcRenderer.invoke('video:project-add-person', {
      project_id: projectId, name, role, raw_video_path: rawVideoPath,
    }),

  listProjects: () =>
    ipcRenderer.invoke('video:project-list'),

  getProjectPipeline: (projectId) =>
    ipcRenderer.invoke('video:project-pipeline', { project_id: projectId }),

  runPipelineStep: (projectId, personName, stepName) =>
    ipcRenderer.invoke('video:project-run-step', {
      project_id: projectId, person_name: personName, step_name: stepName,
    }),

  getReferencePipeline: () =>
    ipcRenderer.invoke('video:reference-pipeline'),

  publishToRowboat: () =>
    ipcRenderer.invoke('video:publish-rowboat'),

  // ── Video upload ──
  videoUpload: (filePath, personName) =>
    ipcRenderer.invoke('video:upload', { file_path: filePath, person_name: personName }),

  // ── Video delete ──
  videoDelete: (videoId, deleteDisk) =>
    ipcRenderer.invoke('video:delete', { video_id: videoId, delete_disk: !!deleteDisk }),

  // ── Video file URL helper ──
  // Serve via local media server (http://localhost:9877/) for reliable playback
  toVideoURL: (filePath) => {
    if (!filePath) return '';
    const normalized = filePath.replace(/\\/g, '/');
    // Strip the Rowboat Videos base path to get relative path for media server
    const rowboatBase = require('os').homedir().replace(/\\/g, '/') + '/.rowboat/Videos/';
    if (normalized.includes('.rowboat/Videos/')) {
      const relative = normalized.split('.rowboat/Videos/')[1];
      return `http://localhost:9877/${relative}`;
    }
    // Fallback: file:// for paths outside Rowboat
    return `file:///${normalized.replace(/^\/+/, '')}`;
  },

  // ── View control ──
  closeVideo: () => ipcRenderer.send('hide-video'),
});
