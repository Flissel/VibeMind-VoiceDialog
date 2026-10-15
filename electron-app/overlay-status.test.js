const assert = require('node:assert/strict');
const http = require('node:http');
const test = require('node:test');

const { checkOverlayTarget, extractTitle, loadOverlay, statusCardHtml } = require('./overlay-status');

const quiet = { log() {}, info() {}, warn() {}, error() {} };

function startServer(handler) {
  return new Promise((resolve) => {
    const server = http.createServer(handler);
    server.listen(0, '127.0.0.1', () => resolve({ server, url: `http://127.0.0.1:${server.address().port}/` }));
  });
}
function stop(server) {
  server.closeAllConnections();
  return new Promise((resolve) => server.close(resolve));
}
function html(title) {
  return (req, res) => { res.writeHead(200, { 'Content-Type': 'text/html' }); res.end(`<html><head><title>${title}</title></head></html>`); };
}
function fakeWebContents({ destroyed = false } = {}) {
  const calls = [];
  return {
    calls,
    isDestroyed: () => destroyed,
    loadURL: async (url) => { calls.push(['url', url]); },
    loadFile: async (file) => { calls.push(['file', file]); },
  };
}
function cardOf(call) {
  assert.equal(call[0], 'url');
  const prefix = 'data:text/html;charset=utf-8,';
  assert.ok(call[1].startsWith(prefix), call[1]);
  return decodeURIComponent(call[1].slice(prefix.length));
}

test('vorhandene Datei wird geladen, fehlende Datei ergibt Statuskarte', async () => {
  const wc = fakeWebContents();
  const ok = await loadOverlay(wc, { space: 'ClawPort', targets: [{ kind: 'file', path: 'C:\\da\\index.html' }] },
    { existsSync: () => true, logger: quiet });
  assert.equal(ok.ok, true);
  assert.deepEqual(wc.calls, [['file', 'C:\\da\\index.html']]);

  const wc2 = fakeWebContents();
  const fehlt = await loadOverlay(wc2, { space: 'ClawPort', targets: [{ kind: 'file', path: 'C:\\weg\\index.html' }] },
    { existsSync: () => false, logger: quiet });
  assert.equal(fehlt.ok, false);
  const card = cardOf(wc2.calls[0]);
  assert.match(card, /ClawPort nicht verfuegbar – Datei fehlt/);
  assert.match(card, /C:\\weg\\index\.html/);
});

test('nicht erreichbare URL ergibt Statuskarte mit Grund', async () => {
  const { server, url } = await startServer(html('x'));
  await stop(server);
  const result = await checkOverlayTarget({ kind: 'url', url }, { logger: quiet });
  assert.equal(result.ok, false);
  assert.match(result.reason, /^nicht erreichbar \(ECONNREFUSED\)$/);
  assert.equal(result.target, url);
});

test('langsame URL: Statuskarte nach dem Timeout', async () => {
  const { server, url } = await startServer((req, res) => setTimeout(() => res.end('spaet'), 500));
  try {
    const result = await checkOverlayTarget({ kind: 'url', url, timeoutMs: 100 });
    assert.deepEqual(result, { ok: false, reason: 'keine Antwort in 100 ms', target: url });
  } finally {
    await stop(server);
  }
});

test('HTTP-Fehlerseite ergibt Statuskarte', async () => {
  const { server, url } = await startServer((req, res) => { res.writeHead(502); res.end('Bad Gateway'); });
  try {
    assert.deepEqual(await checkOverlayTarget({ kind: 'url', url }), { ok: false, reason: 'HTTP 502', target: url });
  } finally {
    await stop(server);
  }
});

test('fremde App (falscher Titel) ergibt Statuskarte, richtige App laedt', async () => {
  const fremd = await startServer(html('Rowboat'));
  const echt = await startServer(html('MiroFish Offline - Predict Everything'));
  try {
    const a = await checkOverlayTarget({ kind: 'url', url: fremd.url, expectTitle: /MiroFish/i });
    assert.deepEqual(a, { ok: false, reason: 'fremde App (Titel „Rowboat“)', target: fremd.url });
    const wc = fakeWebContents();
    const b = await loadOverlay(wc, { space: 'MiroFish', targets: [{ kind: 'url', url: echt.url, expectTitle: /MiroFish/i }] }, { logger: quiet });
    assert.equal(b.ok, true);
    assert.deepEqual(wc.calls, [['url', echt.url]]);
  } finally {
    await stop(fremd.server);
    await stop(echt.server);
  }
});

test('erstes verfuegbares Ziel gewinnt; sonst alle Gruende auf der Karte', async () => {
  const { server, url } = await startServer(html('x'));
  await stop(server);
  const wc = fakeWebContents();
  await loadOverlay(wc, { space: 'Dashboard', targets: [{ kind: 'url', url }, { kind: 'file', path: 'C:\\d\\index.html' }] },
    { existsSync: () => true, logger: quiet });
  assert.deepEqual(wc.calls, [['file', 'C:\\d\\index.html']]);

  const wc2 = fakeWebContents();
  const result = await loadOverlay(wc2, { space: 'Dashboard', targets: [{ kind: 'url', url }, { kind: 'file', path: 'C:\\d\\index.html' }] },
    { existsSync: () => false, logger: quiet });
  assert.equal(result.reason, 'nicht erreichbar (ECONNREFUSED); Datei fehlt');
  assert.equal(result.target, `${url} | C:\\d\\index.html`);
  assert.match(cardOf(wc2.calls[0]), /Dashboard nicht verfuegbar – nicht erreichbar \(ECONNREFUSED\); Datei fehlt/);
});

test('ungueltige und nicht-HTTP-URLs werden nicht geladen', async () => {
  assert.equal((await checkOverlayTarget({ kind: 'url', url: 'kein-url' })).reason, 'ungueltige URL');
  assert.equal((await checkOverlayTarget({ kind: 'url', url: 'file:///C:/x.html' })).reason, 'ungueltige URL');
  assert.equal((await checkOverlayTarget({ kind: 'url', url: '' })).reason, 'ungueltige URL');
});

test('unavailable-Ziel zeigt die Karte mit festem Grund', async () => {
  const wc = fakeWebContents();
  await loadOverlay(wc, { space: 'eyeTerm', targets: [{ kind: 'unavailable', reason: 'entfernt', target: 'http://127.0.0.1:8099' }] }, { logger: quiet });
  const card = cardOf(wc.calls[0]);
  assert.match(card, /eyeTerm nicht verfuegbar – entfernt/);
  assert.match(card, /http:\/\/127\.0\.0\.1:8099/);
});

test('zerstoerte webContents werden nach dem Check nicht mehr geladen', async () => {
  const wc = fakeWebContents({ destroyed: true });
  await loadOverlay(wc, { space: 'ClawPort', targets: [{ kind: 'file', path: 'C:\\x' }] }, { existsSync: () => true, logger: quiet });
  assert.deepEqual(wc.calls, []);
});

test('Statuskarte escaped HTML', () => {
  const out = statusCardHtml({ space: '<b>X</b>', reason: '"a" & b', target: '<script>' });
  assert.doesNotMatch(out, /<b>X<\/b>|<script>/);
  assert.match(out, /&lt;b&gt;X&lt;\/b&gt; nicht verfuegbar – &quot;a&quot; &amp; b/);
  assert.equal(extractTitle('<TITLE> Hallo </TITLE>'), 'Hallo');
});

test('onResult wird vor dem Laden mit dem Ergebnis aufgerufen', async () => {
  const order = [];
  const wc = fakeWebContents();
  wc.loadURL = async () => { order.push('load'); };
  await loadOverlay(wc, { space: 'X', targets: [{ kind: 'unavailable', reason: 'weg', target: 't' }] },
    { logger: quiet, onResult: (r) => order.push(`result:${r.ok}`) });
  assert.deepEqual(order, ['result:false', 'load']);
});
