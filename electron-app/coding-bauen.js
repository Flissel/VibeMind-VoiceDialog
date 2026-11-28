/**
 * K8: "Ja, bauen" of the coding way, signed by the main process like a hand click.
 *
 * On "Bau mir …" the Brain asks back (rueckfrage, weg "coding") with a frage_id (32 hex characters,
 * valid 300 s, only for itself). Python passes only that id on (`coding_frage` in the chat answer);
 * it is kept here and never shown to the page.
 *
 * When the person then sends "Ja, bauen" in a chat field of the window, this process sends the
 * sentence itself to the Brain (POST /api/multihop/execute, Node http: no Origin, no Sec-Fetch-Site),
 * with context { space: "projects", frage_id } and the sign
 *   X-Vibemind-Eingabe: "<unix-sec>.<hmac-sha256 hex>" over "<sec>\ncoding-bauen <frage_id>"
 * made with VIBEMIND_EINGABE_SCHLUESSEL (read here only, never logged, never in the page).
 *
 * The sign is made only
 *   - after a real input of the person in the window (Enter or a left press, seen by this process
 *     through 'input-event', which a page cannot fake) within WITNESS_MS, each input once,
 *   - while the window is visible and in front,
 *   - and never while the remote-control port is open (K9: CDP input looks real).
 * Otherwise nothing goes out and the chat gets a clear sentence. The question is used once.
 */
'use strict';

const crypto = require('node:crypto');
const http = require('node:http');

const KEY_NAME = 'VIBEMIND_EINGABE_SCHLUESSEL';
const KEY_MIN_LENGTH = 32;
const HEADER = 'X-Vibemind-Eingabe';
const QUESTION_MS = 300000;   // the Brain keeps the question 300 s
const WITNESS_MS = 1500;      // from the input of the person to the request
const ANSWER_MS = 60000;
const FRAGE_ID = /^[0-9a-f]{32}$/;

const TEXT = Object.freeze({
  nichtBelegt: 'Das Bauen wurde nicht gestartet: Die App konnte deine Bestätigung nicht belegen. Bitte „Bau mir …" noch einmal sagen.',
  keineEingabe: 'Das Bauen wurde nicht gestartet: „Ja, bauen" zählt nur, wenn du es selbst im sichtbaren Fenster abschickst.',
  pruefmodus: 'Das Bauen wurde nicht gestartet: Im Prüfmodus (Fernsteuerung offen) bestätigt die App kein Bauen.',
  keinSchluessel: 'Das Bauen wurde nicht gestartet: Der App fehlt der Schlüssel für Bestätigungen.',
  keineAntwort: 'Das Gehirn hat auf „Ja, bauen" nicht geantwortet. Bitte noch einmal versuchen.',
  gestartet: 'Bauen gestartet.',
});

function brainPort(env) {
  const text = String(env.BRAIN_PORT || '').trim();
  const port = /^\d+$/.test(text) ? Number(text) : 0;
  return port >= 1 && port <= 65535 ? port : 5000;
}

/** "<sec>.<hmac-sha256 hex>" over "<sec>\ncoding-bauen <frage_id>". */
function zeichen(key, frageId, sec) {
  const t = Math.floor(sec);
  const mac = crypto.createHmac('sha256', key).update(`${t}\ncoding-bauen ${frageId}`, 'utf8').digest('hex');
  return `${t}.${mac}`;
}

// The confirmations the Brain takes (core/coding_auftrag.py, _JA): "Ja, bauen", "Ja bau", "Ja, baue es",
// "Ja bitte bauen", "Ja, starte den Bau", also inside quotes and with closing punctuation. The same set here,
// so every sentence the Brain would count as "Ja, bauen" is signed by this process and none goes unsigned.
const EDGE_FRONT = '^[\\s"\'„“”‚‘’«»]*';
const EDGE_BACK = '[\\s.!?…"\'„“”‚‘’«»]*$';
const BUILD_YES = new RegExp(`${EDGE_FRONT}ja\\s*[,!.]?\\s*(?:bitte\\s+)?(?:bau(?:e|en)?(?:\\s+es)?|starte?\\s+den\\s+bau)${EDGE_BACK}`, 'i');

/** "Ja, bauen" in every form the Brain takes as the confirmation of a build. */
function isBuildYes(text) {
  return typeof text === 'string' && BUILD_YES.test(text);
}

/** The last real input of the person in the window: Enter or a left mouse press, used once. */
function createInputWitness(nowMs = () => Date.now()) {
  let last = null;
  return {
    record(input) {
      if (!input) return;
      const enter = input.type === 'keyDown' && input.key === 'Enter';
      const press = input.type === 'mouseDown' && (!input.button || input.button === 'left');
      if (enter || press) last = { at: nowMs(), used: false };
    },
    take() {
      if (!last || last.used || nowMs() - last.at > WITNESS_MS) return false;
      last.used = true;
      return true;
    },
  };
}

/** One POST to the Brain on 127.0.0.1 without Origin and Sec-Fetch-Site; resolves { status, body }. */
function brainPost(port, path, body, headers, request = http.request) {
  return new Promise((resolve) => {
    const data = Buffer.from(JSON.stringify(body), 'utf8');
    const req = request({
      host: '127.0.0.1', port, method: 'POST', path, timeout: ANSWER_MS,
      headers: { Accept: 'application/json', 'Content-Type': 'application/json', 'Content-Length': data.length, ...headers },
    }, (res) => {
      const chunks = [];
      res.on('data', (c) => chunks.push(c));
      res.on('end', () => {
        let parsed = null;
        try { parsed = JSON.parse(Buffer.concat(chunks).toString('utf8')); } catch (_) { parsed = null; }
        resolve({ status: res.statusCode, body: parsed });
      });
    });
    req.on('timeout', () => { req.destroy(); resolve({ status: 0, body: null }); });
    req.on('error', () => resolve({ status: 0, body: null }));
    req.write(data);
    req.end();
  });
}

function answer(success, message, extra = {}) {
  return { type: 'chat_response', success, message, ...extra };
}

function createCodingConfirm(deps = {}) {
  const env = deps.env || process.env;
  const nowMs = deps.nowMs || (() => Date.now());
  const request = deps.request || http.request;
  const witness = deps.witness || createInputWitness(nowMs);
  const isVisible = typeof deps.isVisible === 'function' ? deps.isVisible : () => false;
  const remoteOpen = typeof deps.remoteOpen === 'function' ? deps.remoteOpen : () => false;
  let pending = null;   // { id, at }

  /** Keep the coding question of a chat answer; the page gets the answer without its id. */
  function remember(reply) {
    if (!reply || typeof reply !== 'object' || !('coding_frage' in reply)) return reply;
    const { coding_frage: id, ...rest } = reply;
    if (typeof id === 'string' && FRAGE_ID.test(id)) pending = { id, at: nowMs() };
    return rest;
  }

  function open() {
    if (pending && nowMs() - pending.at > QUESTION_MS) pending = null;
    return pending;
  }

  /** Whether this sentence is the answer to an open coding question (then confirm() handles it). */
  function handles(text, typed) {
    return typed === true && isBuildYes(text) && !!open();
  }

  async function confirm(text) {
    const question = open();
    if (!question) return null;
    pending = null;   // the question is used once, whatever happens below
    if (remoteOpen()) return answer(false, TEXT.pruefmodus);
    if (!isVisible() || !witness.take()) return answer(false, TEXT.keineEingabe);
    // trimmed like the Brain reads it (core/geheimnis.py) and like blue-rose-data.js
    const key = typeof env[KEY_NAME] === 'string' ? env[KEY_NAME].trim() : '';
    if (key.length < KEY_MIN_LENGTH) return answer(false, TEXT.keinSchluessel);
    const body = { intent: text.trim(), context: { space: 'projects', frage_id: question.id } };
    const sign = zeichen(key, question.id, nowMs() / 1000);
    const res = await brainPost(brainPort(env), '/api/multihop/execute', body, { [HEADER]: sign }, request);
    const data = res.body && typeof res.body === 'object' ? res.body : null;
    if (!data) return answer(false, TEXT.keineAntwort);
    if (data.ok === false && data.grund === 'nicht_belegt') return answer(false, TEXT.nichtBelegt);
    const said = typeof data.final_text === 'string' && data.final_text.trim() ? data.final_text.trim() : '';
    if (data.ok === false) return answer(false, said || TEXT.keineAntwort);
    return answer(true, said || TEXT.gestartet, data.plan_id ? { plan_id: String(data.plan_id) } : {});
  }

  /** Watch the real input of the app window (call for each new window). */
  function watch(webContents) {
    webContents.on('input-event', (_event, input) => witness.record(input));
  }

  return { remember, handles, confirm, watch };
}

module.exports = { createCodingConfirm, createInputWitness, zeichen, isBuildYes, KEY_NAME, HEADER, QUESTION_MS, WITNESS_MS, TEXT };
