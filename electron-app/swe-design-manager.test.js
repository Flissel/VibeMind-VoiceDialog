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

function harness(spawnImpl, extra = {}) {
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
    BrowserView: FakeBrowserView, shell: {}, projectRoot: root, spawn: spawnImpl, env: {}, ...extra,
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

test('Der Reiter zeigt die Stufenansicht des Space und startet den alten Server nicht', async () => {
  let spawned = 0;
  const asked = [];
  const h = harness(() => { spawned += 1; return fakeProc({ code: 1, stderr: '' })(); }, {
    overlayDeps: { fetchImpl: async (url) => { asked.push(url); return { ok: true, status: 200, body: null }; }, logger: { warn() {} } },
  });
  try {
    await h.m.show();
    assert.equal(spawned, 0);
    assert.deepEqual(asked, ['http://127.0.0.1:8162/'], 'der Dienst nimmt nur 127.0.0.1 an, nie localhost');
    assert.deepEqual(h.views[0].loads, ['http://127.0.0.1:8162/']);
    assert.equal(h.m.getIsVisible(), true);

    h.m.hide();
    await h.m.show();
    assert.equal(h.views.length, 1);
    assert.equal(h.views[0].loads.length, 1, 'erneutes Oeffnen laedt eine geladene Seite nicht neu');
  } finally { h.cleanup(); }
});

test('Dienst der Stufenansicht nicht da: Statuskarte, beim naechsten Oeffnen neuer Versuch', async () => {
  let up = false;
  const h = harness(null, {
    overlayDeps: {
      fetchImpl: async () => {
        if (up) return { ok: true, status: 200, body: null };
        const err = new Error('fetch failed');
        err.cause = { code: 'ECONNREFUSED' };
        throw err;
      },
      logger: { warn() {} },
    },
  });
  try {
    await h.m.show();
    const url = h.views[0].loads[0];
    assert.ok(url.startsWith(CARD_PREFIX), url);
    assert.match(decodeURIComponent(url.slice(CARD_PREFIX.length)), /SWE Design nicht verfuegbar – nicht erreichbar \(ECONNREFUSED\)/);
    assert.equal(h.m.getIsVisible(), true);
    assert.equal(h.sent[0].status, 'error');

    up = true;
    h.m.hide();
    await h.m.show();
    assert.equal(h.views[0].loads[1], 'http://127.0.0.1:8162/');
  } finally { h.cleanup(); }
});

test('Adresse der Stufenansicht: aus SWE_DESIGN_UI_URL, sonst dieser Rechner', () => {
  const { stageViewUrl } = SweDesignManager;
  assert.equal(stageViewUrl({}), 'http://127.0.0.1:8162/');
  assert.equal(stageViewUrl({ SWE_DESIGN_UI_URL: ' http://127.0.0.1:9000/ ' }), 'http://127.0.0.1:9000/');
  assert.equal(stageViewUrl({ SWE_DESIGN_UI_URL: 'file:///etc/passwd' }), 'http://127.0.0.1:8162/');
  assert.equal(stageViewUrl({ SWE_DESIGN_UI_URL: 'kaputt' }), 'http://127.0.0.1:8162/');
});
