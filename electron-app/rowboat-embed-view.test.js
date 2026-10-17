const assert = require('node:assert/strict');
const { EventEmitter } = require('node:events');
const test = require('node:test');

const { APP_PARTITION, APP_SCHEME_PRIVILEGES, attachEmbedIpc, proxyAppRequest, registerAppProtocol } = require('./rowboat-embed-view');

function fakeWebContents() {
  const handlers = new Map();
  const sent = [];
  return {
    handlers, sent, destroyed: false,
    ipc: {
      handle: (ch, fn) => { if (handlers.has(ch)) throw new Error(`doppelt: ${ch}`); handlers.set(ch, fn); },
      removeHandler: (ch) => handlers.delete(ch),
    },
    send(ch, p) { sent.push([ch, p]); },
    isDestroyed() { return this.destroyed; },
  };
}
function fakeClient(connected = true) {
  const c = new EventEmitter();
  c.connected = connected;
  c.info = connected ? { port: 4321, token: 'tok-geheim', pid: 1, preloadPath: 'C:/rb/preload.js' } : null;
  c.calls = [];
  c.invoke = async (ch, args) => { c.calls.push([ch, args]); return { ok: true, ch }; };
  return c;
}

test('jeder Kanal bekommt einen Handler auf genau dieser Ansicht, Aufrufe gehen an den Client', async () => {
  const wc = fakeWebContents();
  const client = fakeClient();
  attachEmbedIpc(wc, client, ['workspace:exists', 'runs:list']);
  assert.deepEqual([...wc.handlers.keys()], ['workspace:exists', 'runs:list']);
  assert.deepEqual(await wc.handlers.get('workspace:exists')({}, { path: 'a' }), { ok: true, ch: 'workspace:exists' });
  assert.deepEqual(client.calls, [['workspace:exists', { path: 'a' }]]);
});

test('Push geht an die Ansicht, nach detach nicht mehr; Handler sind entfernt', () => {
  const wc = fakeWebContents();
  const client = fakeClient();
  const detach = attachEmbedIpc(wc, client, ['workspace:exists']);
  client.emit('push', 'runs:events', { x: 1 });
  detach();
  client.emit('push', 'runs:events', { x: 2 });
  assert.deepEqual(wc.sent, [['runs:events', { x: 1 }]]);
  assert.equal(wc.handlers.size, 0);
  attachEmbedIpc(wc, client, ['workspace:exists']); // erneut anschliessbar ohne „doppelt“
});

test('browser:setVisible {visible:true} meldet den Browser-Bereich, reicht aber trotzdem weiter', async () => {
  const wc = fakeWebContents();
  const client = fakeClient();
  let notes = 0;
  attachEmbedIpc(wc, client, ['browser:setVisible'], { onBrowserPane: () => { notes += 1; } });
  await wc.handlers.get('browser:setVisible')({}, { visible: false });
  await wc.handlers.get('browser:setVisible')({}, { visible: true });
  assert.equal(notes, 1);
  assert.equal(client.calls.length, 2);
});

test('Push an eine zerstoerte Ansicht wird verworfen', () => {
  const wc = fakeWebContents();
  const client = fakeClient();
  attachEmbedIpc(wc, client, []);
  wc.destroyed = true;
  client.emit('push', 'runs:events', { x: 1 });
  assert.deepEqual(wc.sent, []);
});

test('app://-Proxy: Token im Header, nie in der URL; Range geht durch; kodierte Pfade bleiben', async () => {
  const seen = [];
  const fetchImpl = async (url, init) => { seen.push([url, init]); return new Response('ok', { status: 206 }); };
  const client = fakeClient();
  const res = await proxyAppRequest(new Request('app://workspace/Meine%20Notizen/b%C3%A4r.png?x=1', { headers: { range: 'bytes=0-9' } }), client, fetchImpl);
  assert.equal(res.status, 206);
  const [url, init] = seen[0];
  assert.equal(url, 'http://127.0.0.1:4321/app/workspace/Meine%20Notizen/b%C3%A4r.png?x=1');
  assert.ok(!url.includes('tok-geheim'));
  assert.equal(init.headers.authorization, 'Bearer tok-geheim');
  assert.equal(init.headers.range, 'bytes=0-9');
  assert.equal(init.method, 'GET');
});

test('app://-Proxy: Oberflaeche unter app://-/index.html', async () => {
  const seen = [];
  await proxyAppRequest(new Request('app://-/index.html'), fakeClient(), async (url) => { seen.push(url); return new Response(''); });
  assert.deepEqual(seen, ['http://127.0.0.1:4321/app/-/index.html']);
});

test('app://-Proxy ohne Verbindung: 503, kein Abruf', async () => {
  let called = false;
  const res = await proxyAppRequest(new Request('app://-/index.html'), fakeClient(false), async () => { called = true; return new Response(''); });
  assert.equal(res.status, 503);
  assert.equal(called, false);
});

test('registerAppProtocol haengt am Protokoll genau dieser Sitzung; Schema-Rechte wie in Rowboat', async () => {
  const handled = [];
  const ses = { protocol: { handle: (scheme, fn) => handled.push([scheme, fn]) } };
  registerAppProtocol(ses, fakeClient(), async () => new Response('x'));
  assert.equal(handled[0][0], 'app');
  assert.equal(await (await handled[0][1](new Request('app://-/index.html'))).text(), 'x');
  assert.equal(APP_PARTITION, 'persist:rowboat-embed');
  assert.deepEqual(APP_SCHEME_PRIVILEGES, { scheme: 'app', privileges: { standard: true, secure: true, supportFetchAPI: true, corsEnabled: true, stream: true } });
});

test('app://-Proxy: Abbruch am Upstream schlaegt fehl -> 502, ohne Token oder Ziel im Body', async () => {
  const fetchImpl = async () => { throw Object.assign(new Error('fetch failed'), { cause: { code: 'ECONNREFUSED' } }); };
  const res = await proxyAppRequest(new Request('app://-/index.html'), fakeClient(), fetchImpl);
  assert.equal(res.status, 502);
  const body = await res.text();
  assert.equal(body, 'Rowboat nicht erreichbar');
  assert.ok(!body.includes('tok-geheim'));
  assert.ok(!body.includes('127.0.0.1'));
});

test('app://-Proxy leitet den Abbruch des Renderers (request.signal) an den Upstream weiter', async () => {
  const seen = [];
  const controller = new AbortController();
  await proxyAppRequest(new Request('app://-/index.html', { signal: controller.signal }), fakeClient(), async (url, init) => { seen.push(init); return new Response(''); });
  const [init] = seen;
  assert.ok(init.signal, 'signal fehlt im fetch-init');
  assert.equal(init.signal.aborted, false);
  controller.abort();
  assert.equal(init.signal.aborted, true);
});
