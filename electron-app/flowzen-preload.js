/**
 * Flowzen Diary Preload Script
 *
 * Preload for the Flowzen Journal BrowserView.
 * Exposes IPC bridge for communication with VibeMind main process.
 */

const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('flowzenDiary', {
    recommend: () => ipcRenderer.send('to-python', { type: 'flowzen_recommend' }),
});

// Receive diary data from main process
ipcRenderer.on('flowzen-diary-data', (_event, data) => {
    if (window._flowzenDiary) window._flowzenDiary.setEntries(data.entries || []);
});

ipcRenderer.on('flowzen-diary-entry', (_event, entry) => {
    if (window._flowzenDiary) window._flowzenDiary.addEntry(entry);
});

ipcRenderer.on('flowzen-status', (_event, data) => {
    if (window._flowzenDiary) window._flowzenDiary.updateStatus(data);
});

ipcRenderer.on('flowzen-recommend-result', (_event, data) => {
    if (window._flowzenDiary) window._flowzenDiary.recommendDone(data);
});
