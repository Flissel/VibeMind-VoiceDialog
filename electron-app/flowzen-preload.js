/**
 * Flowzen Diary Preload Script
 *
 * Preload for the Flowzen Journal BrowserView.
 * With contextIsolation:true, preload and page JS live in separate worlds.
 * Solution: expose a registration function and queue messages until registered.
 */

const { contextBridge, ipcRenderer } = require('electron');

// Message queue — filled until page JS registers its handlers
const _queue = [];
let _handlers = null;

function deliver(method, args) {
    if (_handlers && typeof _handlers[method] === 'function') {
        _handlers[method](...args);
    } else {
        _queue.push({ method, args });
    }
}

function flushQueue() {
    while (_queue.length > 0 && _handlers) {
        const { method, args } = _queue.shift();
        if (typeof _handlers[method] === 'function') {
            _handlers[method](...args);
        }
    }
}

// Expose API to page JS
contextBridge.exposeInMainWorld('flowzenDiary', {
    // The old request to Python. The journal no longer uses it: Python's part for it is gone, the
    // button asks window.blueRose.recommend instead.
    recommend: () => ipcRenderer.send('to-python', { type: 'flowzen_recommend' }),

    // Page JS calls this to register its handlers (setEntries, addEntry, etc.)
    register: (handlers) => {
        _handlers = handlers;
        flushQueue();
    },
});

// Blue Rose as the personal space (blue-rose.html): the page asks the main process, which asks the
// brain (blue-rose-data.js). The page gets ready lines; it never talks to the brain itself.
contextBridge.exposeInMainWorld('blueRose', {
    read: (place) => ipcRenderer.invoke('blue-rose:read', place),
    recommend: (place) => ipcRenderer.invoke('blue-rose:recommend', place),
    saveMood: (entry) => ipcRenderer.invoke('blue-rose:mood', entry),
    setAnalysis: (on) => ipcRenderer.invoke('blue-rose:analysis', on),
    remove: (art, id) => ipcRenderer.invoke('blue-rose:remove', art, id),
    // 'bereich' = this page, 'tagebuch' = the journal (flowzen-diary.html)
    page: (name) => ipcRenderer.send('blue-rose:page', name),
});

// Receive from main process → deliver to page JS (or queue)
ipcRenderer.on('flowzen-diary-data', (_event, data) => {
    deliver('setEntries', [data.entries || []]);
});

ipcRenderer.on('flowzen-diary-entry', (_event, entry) => {
    deliver('addEntry', [entry]);
});

ipcRenderer.on('flowzen-status', (_event, data) => {
    deliver('updateStatus', [data]);
});

ipcRenderer.on('flowzen-recommend-result', (_event, data) => {
    deliver('recommendDone', [data]);
});
