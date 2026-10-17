const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const test = require('node:test');
const { WebSocketServer } = require('ws');

const { RowboatEmbedClient, NOT_RUNNING } = require('./rowboat-embed-client');

const TOKEN = 'tok-geheim-123';

function tmpEmbedFile() {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'rb-embed-'));
  return path.join(dir, 'embed.json');
}
function writeInfo(file, port, extra = {}) {
  fs.writeFileSync(file, JSON.stringify({ v: 1, port, token: TOKEN, pid: process.pid, preloadPath: 'C:/rb/preload.js', ...extra }));
}
/** Nachgebauter Rowboat-Zugang: antwortet auf hello mit welcome, auf invoke per handler. */
function fakeRowboat(handler = (m) => ({ type: 'result', id: m.id, ok: true, result: { echo: m.args } })) {
  return new Promise((resolve) => {
    const wss = new WebSocketServer({ host: '127.0.0.1', port: 0 });
    const seen = [];
    const sockets = new Set();
    wss.on('connection', (ws) => {
      sockets.add(ws);
      ws.on('message', (d) => {
        const m = JSON.parse(String(d));
        seen.push(m);
        if (m.type === 'hello') {
          if (m.token !== TOKEN) return ws.close(4401);
          return ws.send(JSON.stringify({ type: 'welcome', v: 1, invokeChannels: ['workspace:exists', 'browser:setVisible'] }));
        }
        if (m.type === 'invoke') {
          const reply = handler(m, ws);
          if (reply) ws.send(JSON.stringify(reply));
        }
      });
    });
    wss.on('listening', () => resolve({
      wss, seen, port: wss.address().port,
      push: (channel, payload) => { for (const s of sockets) s.send(JSON.stringify({ type: 'push', channel, payload })); },
      kill: () => new Promise((r) => { for (const s of sockets) s.terminate(); wss.close(() => r()); }),
    }));
  });
}
function once(emitter, name) { return new Promise((r) => emitter.once(name, (...a) => r(a))); }
function quiet() { const lines = []; const rec = (...a) => lines.push(a.join(' ')); return { lines, info: rec, warn: rec, error: rec, log: rec }; }

test('ohne embed.json: getrennt mit Hinweis auf start_desktop.py --embed, verbindet sich, sobald die Datei da ist', async () => {
  const file = tmpEmbedFile();
  const rb = await fakeRowboat();
  const c = new RowboatEmbedClient({ embedFile: file, backoffMs: [20], logger: quiet() });
  try {
    c.start();
    await new Promise((r) => setTimeout(r, 30));
    assert.equal(c.connected, false);
    assert.equal(c.reason, NOT_RUNNING);
    writeInfo(file, rb.port);
    const [welcome] = await once(c, 'connected');
    assert.deepEqual(welcome, { invokeChannels: ['workspace:exists', 'browser:setVisible'], preloadPath: 'C:/rb/preload.js' });
    assert.equal(c.connected, true);
    assert.deepEqual(rb.seen[0], { type: 'hello', v: 1, token: TOKEN });
  } finally { c.stop(); await rb.kill(); }
});

test('tote PID in embed.json: getrennt, kein Verbindungsversuch', async () => {
  const file = tmpEmbedFile();
  const rb = await fakeRowboat();
  writeInfo(file, rb.port);
  const c = new RowboatEmbedClient({ embedFile: file, backoffMs: [20], isPidAlive: () => false, logger: quiet() });
  try {
    c.start();
    await new Promise((r) => setTimeout(r, 60));
    assert.equal(c.connected, false);
    assert.equal(c.reason, NOT_RUNNING);
    assert.equal(rb.seen.length, 0);
  } finally { c.stop(); await rb.kill(); }
});

test('lebende PID, toter Port: getrennt, versucht es weiter, haengt nicht', async () => {
  const file = tmpEmbedFile();
  const rb = await fakeRowboat();
  const port = rb.port;
  await rb.kill();
  writeInfo(file, port);
  const c = new RowboatEmbedClient({ embedFile: file, backoffMs: [20], logger: quiet() });
  try {
    c.start();
    await new Promise((r) => setTimeout(r, 120));
    assert.equal(c.connected, false);
    await assert.rejects(c.invoke('workspace:exists', { path: 'a' }), /Rowboat nicht verbunden/);
  } finally { c.stop(); }
});

test('invoke: Ergebnis per id, Fehler mit code', async () => {
  const file = tmpEmbedFile();
  const rb = await fakeRowboat((m) => (m.channel === 'browser:setVisible'
    ? { type: 'result', id: m.id, ok: false, error: { code: 'embed_unsupported', message: 'embed_unsupported: nur im Rowboat-Fenster' } }
    : { type: 'result', id: m.id, ok: true, result: { echo: m.args } }));
  writeInfo(file, rb.port);
  const c = new RowboatEmbedClient({ embedFile: file, backoffMs: [20], logger: quiet() });
  try {
    c.start();
    await once(c, 'connected');
    assert.deepEqual(await c.invoke('workspace:exists', { path: 'a.md' }), { echo: { path: 'a.md' } });
    await assert.rejects(c.invoke('browser:setVisible', { visible: true }), (err) => err.code === 'embed_unsupported' && /nur im Rowboat-Fenster/.test(err.message));
  } finally { c.stop(); await rb.kill(); }
});

test('push wird als Ereignis weitergegeben', async () => {
  const file = tmpEmbedFile();
  const rb = await fakeRowboat();
  writeInfo(file, rb.port);
  const c = new RowboatEmbedClient({ embedFile: file, backoffMs: [20], logger: quiet() });
  try {
    c.start();
    await once(c, 'connected');
    const got = once(c, 'push');
    rb.push('runs:events', { x: 1 });
    assert.deepEqual(await got, ['runs:events', { x: 1 }]);
  } finally { c.stop(); await rb.kill(); }
});

test('Abbruch: offener Aufruf wird abgelehnt, disconnected kommt, Neustart auf neuem Port verbindet wieder', async () => {
  const file = tmpEmbedFile();
  const rb = await fakeRowboat(() => null); // antwortet nie
  writeInfo(file, rb.port);
  const c = new RowboatEmbedClient({ embedFile: file, backoffMs: [20], logger: quiet() });
  try {
    c.start();
    await once(c, 'connected');
    const pending = c.invoke('workspace:exists', { path: 'a' });
    const down = once(c, 'disconnected');
    await rb.kill();
    await assert.rejects(pending, /getrennt/);
    await down;
    const rb2 = await fakeRowboat();
    writeInfo(file, rb2.port);
    await once(c, 'connected');
    assert.equal(c.info.port, rb2.port);
    await rb2.kill();
  } finally { c.stop(); }
});

test('showApp schickt show-app nur, wenn verbunden', async () => {
  const file = tmpEmbedFile();
  const rb = await fakeRowboat();
  const c = new RowboatEmbedClient({ embedFile: file, backoffMs: [20], logger: quiet() });
  try {
    assert.equal(c.showApp(), false);
    writeInfo(file, rb.port);
    c.start();
    await once(c, 'connected');
    assert.equal(c.showApp(), true);
    await new Promise((r) => setTimeout(r, 30));
    assert.deepEqual(rb.seen.at(-1), { type: 'show-app' });
  } finally { c.stop(); await rb.kill(); }
});

test('das Token erscheint in keiner Log-Zeile', async () => {
  const file = tmpEmbedFile();
  const rb = await fakeRowboat();
  writeInfo(file, rb.port);
  const logger = quiet();
  const c = new RowboatEmbedClient({ embedFile: file, backoffMs: [20], logger });
  try {
    c.start();
    await once(c, 'connected');
    await rb.kill();
    await once(c, 'disconnected');
  } finally { c.stop(); }
  assert.ok(logger.lines.length > 0);
  assert.ok(logger.lines.every((l) => !l.includes(TOKEN)));
});
