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

  // ── View control ──
  closeVideo: () => ipcRenderer.send('hide-video'),
});
