const assert = require('node:assert/strict');
const { EventEmitter } = require('node:events');
const http = require('node:http');
const test = require('node:test');

const BrainManager = require('./brain-manager');
const OpenFangManager = require('./openfang-manager');
const { CARD_PREFIX } = require('./overlay-status');
const { createStartupPolicy } = require('./startup-policy');

function recordingLogger() {
  const lines = [];
  const rec = (level) => (...parts) => lines.push(`${level} ${parts.map(String).join(' ')}`);
  return { lines, log: rec('log'), info: rec('info'), warn: rec('warn'), error: rec('error') };
}
function startServer(handler) {
  return new Promise((resolve) => {
    const server = http.createServer(handler);
    server.listen(0, '127.0.0.1', () => resolve({ server, port: server.address().port }));
  });
}
function stop(server) { server.closeAllConnections(); return new Promise((r) => server.close(r)); }
function fakeSpawn(readyLine = 'API server listening on http://127.0.0.1:4200') {
  const calls = [];
  const spawn = (cmd, args) => {
    calls.push([cmd, ...args]);
    const proc = new EventEmitter();
    proc.stdout = new EventEmitter();
    proc.stderr = new EventEmitter();
    proc.pid = 4242;
    proc.kill = () => {};
    setImmediate(() => proc.stdout.emit('data', Buffer.from(readyLine)));
    return proc;
  };
  spawn.calls = calls;
  return spawn;
}
const wait = (ms) => new Promise((r) => setTimeout(r, ms));

// ---------- OpenFang ----------

test('OpenFang fehlt und openfang-spawn aus: kein Start, kein taskkill, Status "fehlt"', async () => {
  const logger = recordingLogger();
  const policy = createStartupPolicy({}, { logger });
  const spawn = fakeSpawn();
  const killCalls = [];
  const m = new OpenFangManager({ policy, spawn, execFileSync: (...a) => killCalls.push(a), probeHealth: async () => false, sleep: async () => {}, logger });
  await m.start();
  m.destroy();
  await m.stop();
  assert.deepEqual(spawn.calls, []);
  assert.deepEqual(killCalls, []);
  assert.equal(m.status.state, 'fehlt');
  assert.match(m.status.reason, /openfang-spawn aus/);
  assert.ok(logger.lines.some((l) => l.includes('openfang-spawn uebersprungen')));
});

test('langsame Health (1,5 s) gilt als laufend – kein zweiter Start, auch wenn openfang-spawn erlaubt ist', async () => {
  const { server, port } = await startServer((req, res) => setTimeout(() => { res.writeHead(200); res.end('ok'); }, 1500));
  try {
    const policy = createStartupPolicy({ VIBEMIND_STARTUP_ALLOW: 'openfang-spawn' }, { logger: recordingLogger() });
    const spawn = fakeSpawn();
    const m = new OpenFangManager({ policy, spawn, healthUrl: `http://127.0.0.1:${port}/api/health`, logger: recordingLogger() });
    await m.start();
    assert.deepEqual(spawn.calls, []);
    assert.equal(m.isReady(), true);
    assert.equal(m.getPort(), port);
    assert.equal(m.status.state, 'uebernommen');
  } finally { await stop(server); }
});

test('uebernommenes OpenFang wird beim Beenden weder heruntergefahren noch getoetet', async () => {
  let shutdowns = 0;
  const { server, port } = await startServer((req, res) => {
    if (req.url === '/api/shutdown') shutdowns += 1;
    res.writeHead(200); res.end('ok');
  });
  try {
    const killCalls = [];
    const m = new OpenFangManager({ policy: createStartupPolicy({}), execFileSync: (...a) => killCalls.push(a), healthUrl: `http://127.0.0.1:${port}/api/health`, logger: recordingLogger() });
    await m.start();
    await m.stop();
    m.destroy();
    assert.equal(shutdowns, 0);
    assert.deepEqual(killCalls, []);
  } finally { await stop(server); }
});

test('openfang-spawn erlaubt und nichts laeuft: genau ein Start', async () => {
  const policy = createStartupPolicy({ VIBEMIND_STARTUP_ALLOW: 'openfang-spawn' }, { logger: recordingLogger() });
  const spawn = fakeSpawn();
  const m = new OpenFangManager({ policy, spawn, probeHealth: async () => false, sleep: async () => {}, logger: recordingLogger() });
  await m.start();
  assert.equal(spawn.calls.length, 1);
  assert.equal(spawn.calls[0][1], 'start');
});

// ---------- Brain ----------

test('parseBrainPort akzeptiert nur 1..65535 und faellt sonst mit Warnung auf 5000 zurueck', () => {
  const logger = recordingLogger();
  assert.equal(BrainManager.parseBrainPort('5001', logger), 5001);
  assert.equal(BrainManager.parseBrainPort(' 5002 ', logger), 5002);
  assert.equal(BrainManager.parseBrainPort(undefined, logger), 5000);
  assert.equal(BrainManager.parseBrainPort('', logger), 5000);
  assert.equal(logger.lines.length, 0);
  for (const bad of ['5000abc', '70000', '0', '-1', '50.5', 'abc']) {
    assert.equal(BrainManager.parseBrainPort(bad, logger), 5000, bad);
  }
  assert.equal(logger.lines.filter((l) => l.startsWith('warn') && l.includes('BRAIN_PORT')).length, 6);
});

function brainHarness({ env, policy, probe }) {
  const views = [];
  class FakeBrowserView {
    constructor(options) {
      this.options = options;
      this.loads = [];
      this.webContents = {
        loadURL: async (url) => { this.loads.push(url); },
        loadFile: async () => {},
        on: () => {}, setWindowOpenHandler: () => {}, isDestroyed: () => false, send: () => {}, close: () => {}, reload: () => {},
      };
      views.push(this);
    }
    setBounds() {}
  }
  const mainWindow = {
    on() {}, setBrowserView() {}, getContentBounds: () => ({ width: 1200, height: 800 }),
    isDestroyed: () => false, webContents: { send() {} },
  };
  const probes = [];
  const spawn = fakeSpawn('Uvicorn running on http://127.0.0.1:5000');
  const logger = recordingLogger();
  const m = new BrainManager(mainWindow, {
    BrowserView: FakeBrowserView, shell: { openExternal: async () => {} },
    env, policy, spawn, logger,
    probeHealth: async (port) => { probes.push(port); return probe; },
    overlayDeps: { logger },
  });
  return { m, views, probes, spawn, logger };
}

test('Brain fehlt, brain-spawn aus: Statuskarte, kein Start, keine Schleife', async () => {
  const h = brainHarness({ env: { BRAIN_PORT: '5000' }, policy: createStartupPolicy({}), probe: false });
  await h.m.startHeadless();
  await h.m.show();
  await h.m.overlayReady;
  await wait(100);
  assert.deepEqual(h.spawn.calls, []);
  assert.deepEqual(h.probes, [5000, 5000]);
  const url = h.views[0].loads[0];
  assert.ok(url.startsWith(CARD_PREFIX));
  assert.match(decodeURIComponent(url.slice(CARD_PREFIX.length)), /Brain nicht verfuegbar – kein Brain auf :5000 \(brain-spawn aus\)/);
});

test('Brain laeuft auf BRAIN_PORT: wird uebernommen und geladen, kein Start', async () => {
  const h = brainHarness({ env: { BRAIN_PORT: '5002', SKIP_BRAIN_SPAWN: '1' }, policy: createStartupPolicy({ VIBEMIND_STARTUP_ALLOW: 'brain-spawn' }), probe: true });
  await h.m.show();
  assert.deepEqual(h.spawn.calls, []);
  assert.deepEqual(h.probes, [5002]);
  assert.deepEqual(h.views[0].loads, ['http://localhost:5002/brain']);
});

test('SKIP_BRAIN_SPAWN schlaegt ein erlaubtes brain-spawn', async () => {
  const h = brainHarness({ env: { SKIP_BRAIN_SPAWN: 'true' }, policy: createStartupPolicy({ VIBEMIND_STARTUP_ALLOW: 'brain-spawn' }), probe: false });
  await h.m.startHeadless();
  assert.deepEqual(h.spawn.calls, []);
});

test('brain-spawn erlaubt und kein SKIP: eigenes Brain wird gestartet', async () => {
  const h = brainHarness({ env: {}, policy: createStartupPolicy({ VIBEMIND_STARTUP_ALLOW: 'brain-spawn' }), probe: false });
  await h.m.startHeadless();
  assert.equal(h.spawn.calls.length, 1);
  assert.deepEqual(h.spawn.calls[0].slice(1), ['-m', 'web.brain_server', '--port', '5000']);
});
