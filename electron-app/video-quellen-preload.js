// The bar of the Video space (video-quellen.html): choose a source, hear which one is shown. Nothing else.
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('videoQuellen', {
  waehlen: (quelle) => ipcRenderer.send('video-quelle', quelle === 'marketing' ? 'marketing' : 'laura'),
  beiStand: (fn) => {
    if (typeof fn !== 'function') return;
    ipcRenderer.on('video-quelle-stand', (_event, stand) => fn({
      quelle: stand && stand.quelle === 'marketing' ? 'marketing' : 'laura',
      marketing: Boolean(stand && stand.marketing),
    }));
  },
});
