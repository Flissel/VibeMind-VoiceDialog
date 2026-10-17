const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const CONFIG = { url: 'http://example.test:54321', anonKey: 'anon-key-xyz' };

// Sandbox-like require: only 'electron' is resolvable, relative paths throw
// exactly like Electron's sandboxed preload ("module not found").
function runInSandbox(file, electron) {
  const code = fs.readFileSync(path.join(__dirname, file), 'utf8');
  const sandboxRequire = (request) => {
    if (request === 'electron') return electron;
    throw new Error(`module not found: ${request}`);
  };
  const context = vm.createContext({
    require: sandboxRequire,
    process: { env: {} },
    module: { exports: {} },
    console,
  });
  vm.runInContext(code, context, { filename: file });
}

function fakeElectron(exposed, sent) {
  return {
    contextBridge: { exposeInMainWorld: (name, api) => exposed.push({ name, api }) },
    ipcRenderer: {
      send: () => {},
      on: () => {},
      invoke: async () => undefined,
      sendSync: (channel) => {
        sent.push(channel);
        return channel === 'vibemind:supabase-config' ? CONFIG : undefined;
      },
    },
  };
}

test('preload.js loads in a sandbox without local requires and exposes vibemind', () => {
  const exposed = [];
  const sent = [];
  assert.doesNotThrow(() => runInSandbox('preload.js', fakeElectron(exposed, sent)));
  assert.equal(exposed.length, 1);
  assert.equal(exposed[0].name, 'vibemind');
  assert.deepEqual(sent, ['vibemind:supabase-config']);
  assert.equal(exposed[0].api.supabase.url, CONFIG.url);
  assert.equal(exposed[0].api.supabase.anonKey, CONFIG.anonKey);
});

test('main-side handler returns the config shape synchronously', () => {
  const { registerSupabaseConfigHandler } = require('./supabase-config-ipc');
  const handlers = {};
  const ipcMain = { on: (ch, fn) => { handlers[ch] = fn; } };
  registerSupabaseConfigHandler(ipcMain, { SUPABASE_URL: 'u', SUPABASE_ANON_KEY: 'k' });
  const event = {};
  handlers['vibemind:supabase-config'](event);
  assert.deepEqual(event.returnValue, { url: 'u', anonKey: 'k' });
});
