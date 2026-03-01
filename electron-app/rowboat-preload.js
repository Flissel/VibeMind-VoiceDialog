/**
 * Rowboat Preload Script for VibeMind
 *
 * Exposes window.ipc and window.electronUtils to the Rowboat renderer
 * running inside a BrowserView. This is a non-validating shim — runtime
 * Zod validation happens in the main process IPC handlers (ipc.ts).
 *
 * API surface matches what apps/x/apps/preload/src/preload.ts exposes:
 *   window.ipc.invoke(channel, args)  → Promise<response>
 *   window.ipc.send(channel, args)    → void
 *   window.ipc.on(channel, handler)   → () => void (cleanup)
 *   window.electronUtils.getPathForFile(file) → string
 */

const { contextBridge, ipcRenderer, webUtils } = require('electron');

contextBridge.exposeInMainWorld('ipc', {
  invoke(channel, args) {
    return ipcRenderer.invoke(channel, args);
  },
  send(channel, args) {
    ipcRenderer.send(channel, args);
  },
  on(channel, handler) {
    const listener = (_event, data) => handler(data);
    ipcRenderer.on(channel, listener);
    // Return cleanup function
    return () => ipcRenderer.removeListener(channel, listener);
  },
});

contextBridge.exposeInMainWorld('electronUtils', {
  getPathForFile(file) {
    return webUtils.getPathForFile(file);
  },
});

console.log('[Rowboat Preload] window.ipc and window.electronUtils exposed');
