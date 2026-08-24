const { contextBridge, ipcRenderer, webUtils } = require('electron');

const bridge = {
  getServiceInfo: () => ipcRenderer.invoke('laura:service-info'),
  pickMediaFile: () => ipcRenderer.invoke('laura:pick-file'),
  saveTextFile: (defaultName, content) =>
    ipcRenderer.invoke('laura:save-file', defaultName, content),
  pathForFile: (file) => webUtils.getPathForFile(file),
  pickMediaFiles: () => ipcRenderer.invoke('laura:pick-files'),
  pickFolder: () => ipcRenderer.invoke('laura:pick-folder'),
  listMediaInFolder: (folder) => ipcRenderer.invoke('laura:list-media-in-folder', folder),
  openPath: (filePath) => ipcRenderer.invoke('laura:open-path', filePath),
  revealPath: (filePath) => ipcRenderer.invoke('laura:reveal-path', filePath),
};

contextBridge.exposeInMainWorld('laura', bridge);
