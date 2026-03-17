/**
 * eyeTerm Camera Preview Preload Script
 *
 * Exposes safe IPC methods to the eyeTerm BrowserView panel.
 */

const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('vibemindEyeterm', {
  // Toggle camera preview panel visibility
  toggle: () => ipcRenderer.send('eyeterm:toggle'),

  // Get eyeTerm status
  getStatus: () => ipcRenderer.invoke('eyeterm:get-status'),

  // Control eyeTerm features
  toggleCursor: () => ipcRenderer.invoke('eyeterm:toggle-cursor'),
  calibrate: () => ipcRenderer.invoke('eyeterm:calibrate'),
});
