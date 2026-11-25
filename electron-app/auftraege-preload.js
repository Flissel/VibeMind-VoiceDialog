// Bridge of the local page "Auftraege": reading the sections, and the chat with the project
// manager (state and one message). No keys, no addresses: those stay in the main process.
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('auftraege', {
  lesen: (teil) => ipcRenderer.invoke('orders:read', teil === 'pm' ? 'pm' : undefined),
  pmChatStand: () => ipcRenderer.invoke('orders:pm-chat-state'),
  pmChatSenden: (text) => ipcRenderer.invoke('orders:pm-chat-send', String(text)),
});
