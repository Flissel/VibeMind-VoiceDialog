/**
 * Clicks of the Desktop space, main-process side.
 *
 * The Brain answers two routes only to callers without `Origin` and `Sec-Fetch-Site` (not a page):
 *   GET  /api/desktop/klicks?seit=…   the clicks of the task book, for the marks on the picture
 *   POST /api/desktop/hand-klick      a click a person made on the picture, passed to the desktop
 * The renderer asks through IPC (desktop:klicks, desktop:hand-klick); this file calls the Brain
 * with Node's http, which sends neither header.
 *
 * A hand click carries the sign of the app (X-Vibemind-Eingabe: "<sec>.<hmac>" over
 * "<sec>\nhand-klick <x> <y>", key VIBEMIND_EINGABE_SCHLUESSEL), the same form as for a typed
 * sentence (python/swarm/routing/brain_multihop_bridge.py). The key is read here only, never
 * handed to the renderer and never logged. Without it no click goes out.
 *
 * The sign says "a person clicked". The renderer alone cannot vouch for that (any script in it
 * could ask), so the main process watches the real mouse input of the app window
 * (webContents 'input-event', which a page cannot fake): a click is signed only when a real left
 * mouse press happened at the same place of the window (CLIENT_TOLERANCE) within WITNESS_MS,
 * and each press is used once. The Brain takes each sign only once as well.
 */
const crypto = require('node:crypto');
const http = require('node:http');

const KEY_NAME = 'VIBEMIND_EINGABE_SCHLUESSEL';
const KEY_MIN_LENGTH = 32;
const HEADER = 'X-Vibemind-Eingabe';
const LIMIT = 20000;               // the Brain takes -20000…20000
const CLICK_TIMEOUT_MS = 60000;    // a click waits for its approval in OpenFang
const LIST_TIMEOUT_MS = 4000;
const WITNESS_MS = 1500;           // from the press to the request (the click fires on release)
const CLIENT_TOLERANCE = 4;        // pixels of the window between press and the place asked

function brainPort(env) {
  const text = String(env.BRAIN_PORT || '').trim();
  const port = /^\d+$/.test(text) ? Number(text) : 0;
  return port >= 1 && port <= 65535 ? port : 5000;
}

/** "<sec>.<hmac-sha256 hex>" over "<sec>\nhand-klick <x> <y>". */
function zeichen(key, x, y, sec) {
  const t = Math.floor(sec);
  const mac = crypto.createHmac('sha256', key).update(`${t}\nhand-klick ${x} ${y}`, 'utf8').digest('hex');
  return `${t}.${mac}`;
}

function plainInt(value) {
  return Number.isInteger(value) && value >= -LIMIT && value <= LIMIT;
}

/** One request to the Brain on 127.0.0.1, without Origin and Sec-Fetch-Site; resolves { status, body }. */
function brainRequest({ port, method, path, body, headers = {}, timeoutMs }, request = http.request) {
  return new Promise((resolve) => {
    const data = body === undefined ? null : Buffer.from(JSON.stringify(body), 'utf8');
    const req = request({
      host: '127.0.0.1', port, method, path, timeout: timeoutMs,
      headers: { Accept: 'application/json', ...(data ? { 'Content-Type': 'application/json', 'Content-Length': data.length } : {}), ...headers },
    }, (res) => {
      const chunks = [];
      res.on('data', (c) => chunks.push(c));
      res.on('end', () => {
        let parsed = null;
        try { parsed = JSON.parse(Buffer.concat(chunks).toString('utf8')); } catch (_) { parsed = null; }
        resolve({ status: res.statusCode, body: parsed });
      });
    });
    req.on('timeout', () => { req.destroy(); resolve({ status: 0, body: null, grund: 'keine_antwort' }); });
    req.on('error', () => resolve({ status: 0, body: null, grund: 'gehirn_nicht_erreichbar' }));
    if (data) req.write(data);
    req.end();
  });
}

/**
 * The last real left mouse press in the app window, kept by the main process.
 * record() takes Electron input events; take() hands the press out once, when it is fresh and
 * at the place (window pixels, the renderer's client coordinates times the zoom factor).
 */
function createClickWitness(nowMs = () => Date.now()) {
  let last = null;
  return {
    record(input) {
      if (!input || input.type !== 'mouseDown' || (input.button && input.button !== 'left')) return;
      if (!Number.isFinite(input.x) || !Number.isFinite(input.y)) return;
      last = { x: input.x, y: input.y, at: nowMs(), used: false };
    },
    take(clientX, clientY, zoom = 1) {
      if (!last || last.used || nowMs() - last.at > WITNESS_MS) return false;
      if (!Number.isFinite(clientX) || !Number.isFinite(clientY)) return false;
      const factor = Number.isFinite(zoom) && zoom > 0 ? zoom : 1;
      if (Math.abs(clientX * factor - last.x) > CLIENT_TOLERANCE || Math.abs(clientY * factor - last.y) > CLIENT_TOLERANCE) return false;
      last.used = true;
      return true;
    },
  };
}

function createDesktopKlicks(deps = {}) {
  const env = deps.env || process.env;
  const now = deps.now || (() => Date.now() / 1000);
  const request = deps.request || http.request;
  let busy = false;

  /** The clicks since `seit` (seconds), as the Brain gives them; a failure is an empty list with a reason. */
  async function klicks(seit) {
    const query = typeof seit === 'number' && Number.isFinite(seit) && seit > 0 ? `?seit=${seit}` : '';
    const answer = await brainRequest({ port: brainPort(env), method: 'GET', path: `/api/desktop/klicks${query}`, timeoutMs: LIST_TIMEOUT_MS }, request);
    if (answer.status === 200 && answer.body && Array.isArray(answer.body.klicks)) return answer.body;
    return { success: false, klicks: [], error: (answer.body && (answer.body.error || answer.body.grund)) || answer.grund || `http_${answer.status}` };
  }

  /** Pass a click of the picture to the desktop; the answer of the Brain, or a refusal with its reason. */
  async function handKlick(x, y) {
    if (!plainInt(x) || !plainInt(y)) return { ok: false, x, y, grund: 'eingabe_ungueltig' };
    const key = typeof env[KEY_NAME] === 'string' ? env[KEY_NAME] : '';
    if (key.length < KEY_MIN_LENGTH) return { ok: false, x, y, grund: 'nicht_belegt' };
    if (busy) return { ok: false, x, y, grund: 'klick_laeuft' };   // one at a time
    busy = true;
    try {
      const answer = await brainRequest({
        port: brainPort(env), method: 'POST', path: '/api/desktop/hand-klick', body: { x, y },
        headers: { [HEADER]: zeichen(key, x, y, now()) }, timeoutMs: CLICK_TIMEOUT_MS,
      }, request);
      if (answer.status === 200 && answer.body && typeof answer.body === 'object') return { x, y, ...answer.body };
      const grund = (answer.body && (answer.body.grund || answer.body.error)) || answer.grund || `http_${answer.status}`;
      return { ok: false, x, y, grund: String(grund) };
    } finally {
      busy = false;
    }
  }

  return { klicks, handKlick };
}

/**
 * The two IPC handlers. Only the window of the app (`isOwnSender`) may ask; anything else
 * gets a refusal without a call to the Brain.
 */
function registerDesktopKlicks(ipcMain, isOwnSender, deps = {}) {
  const api = createDesktopKlicks(deps);
  const witness = deps.witness || createClickWitness(deps.nowMs);
  ipcMain.handle('desktop:klicks', (event, seit) => (isOwnSender(event) ? api.klicks(Number(seit)) : { success: false, klicks: [], error: 'fremd' }));
  ipcMain.handle('desktop:hand-klick', (event, args) => {
    if (!isOwnSender(event)) return { ok: false, grund: 'fremd' };
    const x = args && args.x;
    const y = args && args.y;
    const zoom = event.sender && typeof event.sender.getZoomFactor === 'function' ? event.sender.getZoomFactor() : 1;
    // no real press at this place just now: no sign, nothing goes out
    if (!witness.take(args && args.clientX, args && args.clientY, zoom)) return { ok: false, x, y, grund: 'kein_echter_klick' };
    return api.handKlick(x, y);
  });
  /** Watch the real mouse input of the app window (call for each new window). */
  function watch(webContents) {
    webContents.on('input-event', (_event, input) => witness.record(input));
  }
  return { ...api, watch };
}

module.exports = { createDesktopKlicks, createClickWitness, registerDesktopKlicks, zeichen, brainPort, KEY_NAME, HEADER, WITNESS_MS };
