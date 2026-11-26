// R3: the OpenFang key goes only to the OpenFang page in its tab of the Agent Farm.
// n8n and Rowboat are embedded in the same session: a foreign page there gets no key (Marketing-Befund 2026-11-25).
const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const {
  openfangBaseUrl, openfangOrigins, openfangAuth, fromOpenFangFrame, withKey, matchesPatterns,
} = require('./openfang-access');
const AgentFarmManager = require('./agentfarm-manager');

const KEY = 'test-schluessel-0000';                       // invented
const ENV = { OPENFANG_API_KEY: KEY };
const APP = 'file:///app/agentfarm/dist/index.html';
const isApp = (url) => url === APP;
const ORIGINS = openfangOrigins(ENV);

const top = { url: APP, parent: null };
const openfangFrame = { url: 'http://localhost:4200/', parent: top };   // the tab's iframe, as OpenFangWorkflow.tsx loads it
const n8nFrame = { url: 'http://localhost:15678/workflow/1', parent: top };
const rowboatFrame = { url: 'http://localhost:3100/projects/x', parent: top };
const nestedInN8n = { url: 'about:blank', parent: n8nFrame };

const req = (fields) => ({ url: 'http://127.0.0.1:4200/api/agents', resourceType: 'xhr', requestHeaders: {}, ...fields });

test('the address: OPENFANG_URL, else 127.0.0.1:4200; loopback counts as 127.0.0.1 and localhost', () => {
  assert.equal(openfangBaseUrl({}), 'http://127.0.0.1:4200');
  assert.equal(openfangBaseUrl({ OPENFANG_URL: 'http://localhost:4200' }), 'http://localhost:4200');
  assert.equal(openfangBaseUrl({ OPENFANG_URL: 'javascript:alert(1)' }), 'http://127.0.0.1:4200');
  assert.deepEqual(openfangOrigins({}), ['http://127.0.0.1:4200', 'http://localhost:4200']);
  assert.deepEqual(openfangOrigins({ OPENFANG_URL: 'https://fang.example.test' }), ['https://fang.example.test']);
});

test('no key: no rule at all; with a key the patterns cover only the OpenFang origins', () => {
  assert.equal(openfangAuth({}), null);
  assert.equal(openfangAuth({ OPENFANG_API_KEY: '   ' }), null);
  const auth = openfangAuth(ENV);
  assert.deepEqual(auth.urls, ['http://127.0.0.1:4200/*', 'ws://127.0.0.1:4200/*', 'http://localhost:4200/*', 'ws://localhost:4200/*']);
  assert.equal(auth.header, 'Bearer ' + KEY);
  assert.equal(auth.name, 'OPENFANG_API_KEY');
  assert.ok(matchesPatterns('http://localhost:4200/api', auth.urls));
  assert.ok(!matchesPatterns('http://localhost:42001/api', auth.urls), 'another port is another origin');
  assert.ok(!matchesPatterns('http://localhost:15678/rest', auth.urls));
});

test('OpenFang frame → key: its own fetch, script, websocket, and the navigation of the frame', () => {
  assert.ok(fromOpenFangFrame(req({ frame: openfangFrame, requestHeaders: { 'Sec-Fetch-Site': 'same-origin' } }), ORIGINS, isApp));
  assert.ok(fromOpenFangFrame(req({ frame: openfangFrame, requestHeaders: { Origin: 'http://localhost:4200', 'Sec-Fetch-Site': 'same-origin' }, url: 'http://localhost:4200/api/x' }), ORIGINS, isApp));
  assert.ok(fromOpenFangFrame(req({ frame: openfangFrame, resourceType: 'script', url: 'http://localhost:4200/app.js' }), ORIGINS, isApp));
  assert.ok(fromOpenFangFrame(req({ frame: openfangFrame, resourceType: 'webSocket', url: 'ws://localhost:4200/ws' }), ORIGINS, isApp));
  // the tab loads the frame: the frame is empty, its parent is the Agent Farm page (cross-site from file://)
  assert.ok(fromOpenFangFrame(req({ resourceType: 'subFrame', url: 'http://localhost:4200/', frame: { url: '', parent: top },
    requestHeaders: { 'Sec-Fetch-Site': 'cross-site', 'Sec-Fetch-Dest': 'iframe' } }), ORIGINS, isApp));
  assert.ok(fromOpenFangFrame(req({ resourceType: 'subFrame', url: 'http://localhost:4200/agents', frame: openfangFrame }), ORIGINS, isApp),
    'a navigation inside the OpenFang frame');
});

test('foreign frame → no key: n8n or Rowboat fetching 127.0.0.1:4200, also without an Origin header', () => {
  for (const frame of [n8nFrame, rowboatFrame]) {
    const origin = new URL(frame.url).origin;
    assert.ok(!fromOpenFangFrame(req({ frame, requestHeaders: { Origin: origin, 'Sec-Fetch-Site': 'cross-site' } }), ORIGINS, isApp));
    assert.ok(!fromOpenFangFrame(req({ frame, requestHeaders: { 'Sec-Fetch-Site': 'same-site' } }), ORIGINS, isApp), 'same-site is not same-origin');
    assert.ok(!fromOpenFangFrame(req({ frame }), ORIGINS, isApp), 'no Origin, no Sec-Fetch-Site: the frame decides');
  }
  // a foreign Origin or cross-site, even if the frame claimed to be OpenFang
  assert.ok(!fromOpenFangFrame(req({ frame: openfangFrame, requestHeaders: { Origin: 'http://localhost:15678' } }), ORIGINS, isApp));
  assert.ok(!fromOpenFangFrame(req({ frame: openfangFrame, requestHeaders: { 'Sec-Fetch-Site': 'cross-site' } }), ORIGINS, isApp));
  // a frame n8n puts inside itself, pointed at OpenFang
  assert.ok(!fromOpenFangFrame(req({ resourceType: 'subFrame', url: 'http://localhost:4200/', frame: nestedInN8n }), ORIGINS, isApp));
  assert.ok(!fromOpenFangFrame(req({ resourceType: 'subFrame', url: 'http://localhost:4200/', frame: { url: '', parent: n8nFrame } }), ORIGINS, isApp));
  // an OpenFang page nested in another frame is not the tab's frame
  assert.ok(!fromOpenFangFrame(req({ frame: { url: 'http://localhost:4200/', parent: n8nFrame } }), ORIGINS, isApp));
  // the top frame turned elsewhere, and a request without a frame: nothing (fails closed)
  assert.ok(!fromOpenFangFrame(req({ frame: { url: 'http://localhost:4200/', parent: { url: 'http://evil.example.test/', parent: null } } }), ORIGINS, isApp));
  assert.ok(!fromOpenFangFrame(req({}), ORIGINS, isApp));
  assert.ok(!fromOpenFangFrame(req({ resourceType: 'mainFrame', frame: top }), ORIGINS, isApp));
});

test('redirect → no key: a request that a redirect sends to another host, or another port', () => {
  for (const url of ['http://evil.example.test/steal', 'http://localhost:15678/rest', 'http://127.0.0.1:4201/']) {
    assert.ok(!fromOpenFangFrame(req({ url, frame: openfangFrame, requestHeaders: { 'Sec-Fetch-Site': 'same-origin' } }), ORIGINS, isApp), url);
    assert.ok(!fromOpenFangFrame(req({ url, resourceType: 'subFrame', frame: { url: '', parent: top } }), ORIGINS, isApp), url);
  }
});

test('withKey replaces an Authorization the page set itself and leaves the rest', () => {
  assert.deepEqual(withKey({ authorization: 'Bearer fremd', Accept: 'x' }, 'Bearer ' + KEY), { Accept: 'x', Authorization: 'Bearer ' + KEY });
});

/** The manager with a stand-in view: the session collects the one onBeforeSendHeaders listener. */
function manager(env) {
  const hooks = [];
  class FakeBrowserView {
    constructor() {
      this.webContents = {
        session: { webRequest: { onHeadersReceived() {}, onBeforeSendHeaders: (filter, handler) => hooks.push({ filter, handler }) }, clearCache: async () => {} },
        on() {}, setWindowOpenHandler() {}, loadURL: async () => {}, loadFile: async () => {}, getURL: () => APP, openDevTools() {},
      };
    }
    setBounds() {} setAutoResize() {}
  }
  const logs = [];
  const write = process.stdout.write;
  process.stdout.write = (chunk, ...rest) => { logs.push(String(chunk)); return true; };
  let m;
  try {
    m = new AgentFarmManager(null, { BrowserView: FakeBrowserView, shell: { openExternal() {} }, env, n8nLogin: false,
      overlayDeps: { existsSync: () => true, logger: { log() {}, warn() {}, error() {}, info() {} } } });
    m._resolveRendererPath = () => path.join(path.sep, 'app', 'agentfarm', 'dist', 'index.html');
    m.createView();
  } finally {
    process.stdout.write = write;
  }
  const send = (details) => new Promise((resolve) => {
    const hook = hooks[hooks.length - 1];
    hook.handler({ requestHeaders: {}, ...details }, (result) => resolve(result.requestHeaders));
  });
  return { m, hooks, logs, send, app: pathToFileURL(m._resolveRendererPath()).href };
}

test('the manager: OpenFang frame → header, foreign frame → none; the log names the variable, never the value', async () => {
  const { hooks, logs, send, app } = manager({ ...ENV });
  assert.equal(hooks.length, 1, 'one listener');
  assert.deepEqual(hooks[0].filter.urls, openfangAuth(ENV).urls);
  const appTop = { url: app, parent: null };
  const own = await send({ url: 'http://localhost:4200/api/agents', resourceType: 'xhr', frame: { url: 'http://localhost:4200/', parent: appTop },
    requestHeaders: { 'Sec-Fetch-Site': 'same-origin' } });
  assert.equal(own.Authorization, 'Bearer ' + KEY);
  const foreign = await send({ url: 'http://127.0.0.1:4200/api/agents', resourceType: 'xhr', frame: { url: 'http://localhost:15678/', parent: appTop },
    requestHeaders: { Origin: 'http://localhost:15678', 'Sec-Fetch-Site': 'cross-site' } });
  assert.equal(foreign.Authorization, undefined);
  const all = logs.join('');
  assert.match(all, /Schluessel aus OPENFANG_API_KEY wird nur an die OpenFang-Seite im Reiter mitgegeben/);
  assert.ok(!all.includes(KEY), 'the value is never in the log');
});

test('the manager without a key: no listener, the log says so', () => {
  const { hooks, logs } = manager({});
  assert.equal(hooks.length, 0);
  assert.match(logs.join(''), /kein OPENFANG_API_KEY/);
});

test('n8n cookie and OpenFang key share the one listener; each applies only to its own address', async () => {
  const { m, hooks, send, app } = manager({ ...ENV });
  m._setSendRule('n8n-cookie', { urls: ['http://localhost:15678/*'], apply: (d, h) => ({ ...h, Cookie: 'n8n-auth=x' }) });
  const hook = hooks[hooks.length - 1];
  assert.ok(hook.filter.urls.includes('http://localhost:15678/*') && hook.filter.urls.includes('http://127.0.0.1:4200/*'), 'both in one filter');
  const n8n = await send({ url: 'http://localhost:15678/rest/me', resourceType: 'xhr', frame: { url: 'http://localhost:15678/', parent: { url: app, parent: null } } });
  assert.equal(n8n.Cookie, 'n8n-auth=x');
  assert.equal(n8n.Authorization, undefined, 'no key to n8n');
  const fang = await send({ url: 'http://localhost:4200/api', resourceType: 'xhr', frame: { url: 'http://localhost:4200/', parent: { url: app, parent: null } } });
  assert.equal(fang.Authorization, 'Bearer ' + KEY);
  assert.equal(fang.Cookie, undefined, 'no n8n cookie to OpenFang');
});

test('the key is read only in the main process: no renderer file and no preload knows it', () => {
  const fs = require('node:fs');
  for (const file of ['agentfarm-preload.js', path.join('agentfarm', 'src', 'features', 'OpenFangWorkflow.tsx')]) {
    assert.doesNotMatch(fs.readFileSync(path.join(__dirname, file), 'utf8'), /OPENFANG_API_KEY/, file);
  }
});
