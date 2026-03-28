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
    // Page JS calls this to send recommend request to Python
    recommend: () => ipcRenderer.send('to-python', { type: 'flowzen_recommend' }),

    // Page JS calls this to register its handlers (setEntries, addEntry, etc.)
    register: (handlers) => {
        _handlers = handlers;
        flushQueue();
    },
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
