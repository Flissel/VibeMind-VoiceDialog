const assert = require('node:assert/strict');
const { EventEmitter } = require('node:events');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');

const SweDesignManager = require('./swe-design-manager');
const { CARD_PREFIX } = require('./overlay-status');

const { resolvePythonPath, exitReason } = SweDesignManager;
const swePy = path.join('C:\\re', '.venv', 'Scripts', 'python.exe');
const vPy = path.join('C:\\voice', '.venv312', 'Scripts', 'python.exe');

test('Python: bevorzugt die eigene .venv des Space', () => {
  const exists = (p) => p === swePy || p === vPy;
  assert.equal(resolvePythonPath('C:\\voice', 'C:\\re', exists), swePy);
});

test('Python: ohne Space-venv Rueckfall auf voice/.venv312', () => {
  assert.equal(resolvePythonPath('C:\\voice', 'C:\\re', (p) => p === vPy), vPy);
});

test('Python: ohne jede venv Rueckfall auf python', () => {
  assert.equal(resolvePythonPath('C:\\voice', 'C:\\re', () => false), 'python');
});

test('exitReason: erste Zeile, gekuerzt; bei Traceback die Exception-Zeile am Ende', () => {
  assert.equal(exitReason(2, 'boom\nzweite'), 'Server beendet (Exit 2): boom');
  assert.equal(exitReason(1, ''), 'Server beendet (Exit 1)');
  assert.equal(
    exitReason(1, 'Traceback (most recent call last):\n  File "x.py"\nModuleNotFoundError: No module named \'dataclasses_json\'\n'),
    "Server beendet (Exit 1): ModuleNotFoundError: No module named 'dataclasses_json'",
  );
  const long = exitReason(1, 'x'.repeat(500));
  assert.ok(long.length < 220, long);
  assert.ok(long.endsWith('…'));
});

function harness(spawnImpl) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'swe-mgr-'));
  const re = path.join(root, 'python', 'spaces', 'shuttles', 'swe_desgine');
  fs.mkdirSync(re, { recursive: true });
  fs.writeFileSync(path.join(re, 'start_dashboard.py'), 'print(1)');
  const views = [];
  class FakeBrowserView {
    constructor() {
      this.loads = [];
      this.webContents = {
        loadURL: async (url) => { this.loads.push(url); },
        on() {}, setWindowOpenHandler() {}, isDestroyed: () => false,
        session: { clearCache: async () => {} },
      };
      views.push(this);
    }
    setBounds() {}
  }
  const sent = [];
  const mainWindow = {
    on() {}, setBrowserView() {}, isDestroyed: () => false,
    getContentBounds: () => ({ width: 1200, height: 800 }),
    webContents: { send: (_c, msg) => sent.push(msg) },
  };
  const m = new SweDesignManager(mainWindow, {
    BrowserView: FakeBrowserView, shell: {}, projectRoot: root, spawn: spawnImpl,
  });
  return { m, views, sent, cleanup: () => fs.rmSync(root, { recursive: true, force: true }) };
}

function fakeProc({ code, stderr }) {
  return () => {
    const proc = new EventEmitter();
    proc.stdout = new EventEmitter();
    proc.stderr = new EventEmitter();
    proc.kill = () => {};
    setImmediate(() => {
      proc.stderr.emit('data', Buffer.from(stderr));
      proc.emit('exit', code);
    });
    return proc;
  };
}

test('Server beendet sich mit Exit 1: Statuskarte mit Grund statt leerer Ansicht', async () => {
  const h = harness(fakeProc({ code: 1, stderr: "Traceback (most recent call last):\nModuleNotFoundError: No module named 'dataclasses_json'\n" }));
  try {
    await h.m.show();
    assert.equal(h.views.length, 1);
    const url = h.views[0].loads[0];
    assert.ok(url.startsWith(CARD_PREFIX), url);
    const html = decodeURIComponent(url.slice(CARD_PREFIX.length));
    assert.match(html, /SWE Design nicht verfuegbar – Server beendet \(Exit 1\): ModuleNotFoundError/);
    assert.equal(h.m.getIsVisible(), true);
    assert.equal(h.sent[0].status, 'error');
  } finally { h.cleanup(); }
});
