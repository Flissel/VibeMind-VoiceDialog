// Bridge of the local page "Auftraege": one reading call, nothing else.
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('auftraege', {
  lesen: () => ipcRenderer.invoke('orders:read'),
});
