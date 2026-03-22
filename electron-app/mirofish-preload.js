/**
 * MiroFish Preload Script
 *
 * Minimal preload for the MiroFish BrowserView.
 * Exposes IPC bridge for communication with VibeMind main process.
 */

const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('vibemindMirofish', {
  // Send simulation request to Python backend
  startSimulation: (config) => ipcRenderer.invoke('mirofish:start-simulation', config),
  getStatus: () => ipcRenderer.invoke('mirofish:get-status'),

  // Listen for events from main process
  onEvent: (callback) => {
    ipcRenderer.on('mirofish-event', (_event, data) => callback(data));
  },
});
