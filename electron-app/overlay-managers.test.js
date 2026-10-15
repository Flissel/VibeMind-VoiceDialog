const assert = require('node:assert/strict');
const http = require('node:http');
const test = require('node:test');

const ClawPortManager = require('./clawport-manager');
const DashboardManager = require('./dashboard-manager');
const EyeTermManager = require('./eyeterm-manager');
const MiroFishManager = require('./mirofish-manager');
const RowboatManager = require('./rowboat-manager');
const VideoManager = require('./video-manager');
const { CARD_PREFIX } = require('./overlay-status');

const quiet = { log() {}, info() {}, warn() {}, error() {} };

function harness() {
  const views = [];
  class FakeBrowserView {
    constructor(options) {
      this.options = options;
      this.loads = [];
      this.handlers = new Map();
      this.webContents = {
        loadURL: async (url) => { this.loads.push(['url', url]); },
        loadFile: async (file) => { this.loads.push(['file', file]); },
        on: (event, handler) => this.handlers.set(event, handler),
        setWindowOpenHandler: () => {},
        openDevTools: () => {},
        insertCSS: () => {},
        isDestroyed: () => false,
        send: () => {},
        close: () => {},
        destroy: () => {},
        session: { webRequest: { onHeadersReceived() {} }, clearCache: async () => {} },
      };
      views.push(this);
    }
    setBounds() {}
  }
  const mainWindow = {
    on() {}, setBrowserView() {}, addBrowserView() {}, removeBrowserView() {}, getBrowserView: () => null,
    getContentBounds: () => ({ x: 0, y: 0, width: 1200, height: 800 }),
    isDestroyed: () => false, webContents: { send() {} },
  };
  const shell = { openExternal: async () => {} };
  return { views, FakeBrowserView, mainWindow, shell };
}
function card(load) {
  assert.equal(load[0], 'url');
  assert.ok(load[1].startsWith(CARD_PREFIX), load[1]);
  return decodeURIComponent(load[1].slice(CARD_PREFIX.length));
}
function startServer(handler) {
  return new Promise((resolve) => {
    const server = http.createServer(handler);
    server.listen(0, '127.0.0.1', () => resolve({ server, url: `http://127.0.0.1:${server.address().port}/` }));
  });
}
function stop(server) { server.closeAllConnections(); return new Promise((r) => server.close(r)); }
const titled = (title) => (req, res) => { res.writeHead(200, { 'Content-Type': 'text/html' }); res.end(`<title>${title}</title>`); };

test('MiroFish: nicht erreichbare MIROFISH_URL ergibt Statuskarte', async () => {
  const { server, url } = await startServer(titled('x'));
  await stop(server);
  const h = harness();
  const m = new MiroFishManager(h.mainWindow, { BrowserView: h.FakeBrowserView, shell: h.shell, env: { MIROFISH_URL: url }, overlayDeps: { logger: quiet } });
  m.show();
  await m.overlayReady;
  assert.match(card(h.views[0].loads[0]), /MiroFish nicht verfuegbar – nicht erreichbar/);
});

test('MiroFish: HTTP 502 ergibt Statuskarte statt Fehlerseite', async () => {
  const { server, url } = await startServer((req, res) => { res.writeHead(502); res.end('Bad Gateway'); });
  try {
    const h = harness();
    const m = new MiroFishManager(h.mainWindow, { BrowserView: h.FakeBrowserView, shell: h.shell, env: { MIROFISH_URL: url }, overlayDeps: { logger: quiet } });
    m.show();
    await m.overlayReady;
    assert.match(card(h.views[0].loads[0]), /MiroFish nicht verfuegbar – HTTP 502/);
  } finally { await stop(server); }
});

test('MiroFish: fremde App (falscher Titel) ergibt Statuskarte, echte App laedt', async () => {
  const fremd = await startServer(titled('Rowboat'));
  const echt = await startServer(titled('MiroFish Offline - Predict Everything'));
  try {
    const h = harness();
    const a = new MiroFishManager(h.mainWindow, { BrowserView: h.FakeBrowserView, shell: h.shell, env: { MIROFISH_URL: fremd.url }, overlayDeps: { logger: quiet } });
    a.show();
    await a.overlayReady;
    assert.match(card(h.views[0].loads[0]), /fremde App \(Titel „Rowboat“\)/);
    const b = new MiroFishManager(h.mainWindow, { BrowserView: h.FakeBrowserView, shell: h.shell, env: { MIROFISH_URL: echt.url }, overlayDeps: { logger: quiet } });
    b.show();
    await b.overlayReady;
    assert.deepEqual(h.views[1].loads, [['url', echt.url]]);
  } finally { await stop(fremd.server); await stop(echt.server); }
});

test('ClawPort: fehlender Build ergibt Statuskarte, vorhandener Build laedt', async () => {
  const h = harness();
  const fehlt = new ClawPortManager(h.mainWindow, { BrowserView: h.FakeBrowserView, shell: h.shell, env: {}, rendererPath: 'C:\\nirgends\\index.html', overlayDeps: { existsSync: () => false, logger: quiet } });
  fehlt.show();
  await fehlt.overlayReady;
  assert.match(card(h.views[0].loads[0]), /ClawPort nicht verfuegbar – Datei fehlt/);
  const da = new ClawPortManager(h.mainWindow, { BrowserView: h.FakeBrowserView, shell: h.shell, env: {}, rendererPath: 'C:\\da\\index.html', overlayDeps: { existsSync: () => true, logger: quiet } });
  da.show();
  await da.overlayReady;
  assert.deepEqual(h.views[1].loads, [['file', 'C:\\da\\index.html']]);
});

test('Dashboard: ohne DASHBOARD_DEV_URL und ohne Build Statuskarte, kein :5173', async () => {
  const h = harness();
  const d = new DashboardManager(h.mainWindow, { BrowserView: h.FakeBrowserView, env: {}, dashboardPath: 'C:\\nirgends\\index.html', overlayDeps: { existsSync: () => false, logger: quiet } });
  d.show();
  await d.overlayReady;
  assert.equal(h.views[0].loads.length, 1);
  assert.match(card(h.views[0].loads[0]), /Dashboard \(Coding Engine\) nicht verfuegbar – Datei fehlt/);
  assert.doesNotMatch(card(h.views[0].loads[0]), /5173/);
});

test('Dashboard: DASHBOARD_DEV_URL mit fremder App (Rowboat) ergibt Statuskarte', async () => {
  const fremd = await startServer(titled('Rowboat'));
  try {
    const h = harness();
    const d = new DashboardManager(h.mainWindow, { BrowserView: h.FakeBrowserView, env: { DASHBOARD_DEV_URL: fremd.url }, dashboardPath: 'C:\\nirgends\\index.html', overlayDeps: { existsSync: () => false, logger: quiet } });
    d.show();
    await d.overlayReady;
    assert.match(card(h.views[0].loads[0]), /fremde App \(Titel „Rowboat“\); Datei fehlt/);
  } finally { await stop(fremd.server); }
});

test('Rowboat: Platzhalter „kommt mit Teil 2“, Bridge startet nicht', async () => {
  const h = harness();
  const r = new RowboatManager(h.mainWindow, { BrowserView: h.FakeBrowserView, shell: h.shell, placeholderReason: 'kommt mit Teil 2', overlayDeps: { logger: quiet } });
  r.show();
  await r.overlayReady;
  assert.match(card(h.views[0].loads[0]), /Rowboat nicht verfuegbar – kommt mit Teil 2/);
  assert.equal(await r.startBridge(), false);
  assert.equal(r.bridgeProcess, null);
});

test('eyeTerm: Statuskarte „entfernt“', async () => {
  const h = harness();
  const e = new EyeTermManager(h.mainWindow, { BrowserView: h.FakeBrowserView, env: {}, overlayDeps: { logger: quiet } });
  e.show();
  await e.overlayReady;
  assert.match(card(h.views[0].loads[0]), /eyeTerm nicht verfuegbar – entfernt/);
});

test('Video/Laura: fehlender Renderer ergibt Statuskarte statt Absturz', async () => {
  const h = harness();
  const logger = Object.assign(() => {}, quiet);
  const v = new VideoManager(h.mainWindow, {
    BrowserView: h.FakeBrowserView, shell: h.shell, logger,
    resolveRendererPath: () => { throw new Error('Laura renderer missing; run pnpm laura:build (checked C:\\x\\index.html)'); },
  });
  v.show();
  await v.overlayReady;
  const text = card(h.views[0].loads[0]);
  assert.match(text, /Video\/Laura nicht verfuegbar – Renderer fehlt \(pnpm laura:build\)/);
  assert.match(text, /checked C:\\x\\index\.html/);
});
