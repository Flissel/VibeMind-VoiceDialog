const test = require('node:test');
const assert = require('node:assert/strict');
const Module = require('node:module');

test('Laura preload exposes only the typed bridge and delegates to Electron', async () => {
  const exposed = [];
  const invocations = [];
  const file = { name: 'clip.mp4' };
  const electron = {
    contextBridge: {
      exposeInMainWorld: (name, bridge) => exposed.push({ bridge, name }),
    },
    ipcRenderer: {
      invoke: async (channel, ...args) => {
        invocations.push({ args, channel });
        return channel;
      },
    },
    webUtils: {
      getPathForFile: (candidate) => {
        assert.equal(candidate, file);
        return 'C:\\media\\clip.mp4';
      },
    },
  };
  const originalLoad = Module._load;
  Module._load = function load(request, parent, isMain) {
    if (request === 'electron') return electron;
    return originalLoad.call(this, request, parent, isMain);
  };

  try {
    delete require.cache[require.resolve('./laura-preload')];
    require('./laura-preload');
  } finally {
    Module._load = originalLoad;
  }

  assert.equal(exposed.length, 1);
  assert.equal(exposed[0].name, 'laura');
  const bridge = exposed[0].bridge;
  assert.deepEqual(Object.keys(bridge).sort(), [
    'getServiceInfo',
    'listMediaInFolder',
    'openPath',
    'pathForFile',
    'pickFolder',
    'pickMediaFile',
    'pickMediaFiles',
    'revealPath',
    'saveTextFile',
  ]);
  assert.equal(Object.hasOwn(bridge, 'ipcRenderer'), false);
  assert.equal(Object.hasOwn(bridge, 'fs'), false);
  assert.equal(bridge.pathForFile(file), 'C:\\media\\clip.mp4');

  await bridge.getServiceInfo();
  await bridge.pickMediaFile();
  await bridge.saveTextFile('notes.txt', 'hello');
  await bridge.pickMediaFiles();
  await bridge.pickFolder();
  await bridge.listMediaInFolder('C:\\media');
  await bridge.openPath('C:\\workspace\\output.mp4');
  await bridge.revealPath('C:\\workspace\\output.mp4');

  assert.deepEqual(invocations, [
    { args: [], channel: 'laura:service-info' },
    { args: [], channel: 'laura:pick-file' },
    { args: ['notes.txt', 'hello'], channel: 'laura:save-file' },
    { args: [], channel: 'laura:pick-files' },
    { args: [], channel: 'laura:pick-folder' },
    { args: ['C:\\media'], channel: 'laura:list-media-in-folder' },
    { args: ['C:\\workspace\\output.mp4'], channel: 'laura:open-path' },
    { args: ['C:\\workspace\\output.mp4'], channel: 'laura:reveal-path' },
  ]);
});
