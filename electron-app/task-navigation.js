/**
 * Task navigation: when the Brain starts working on a task, tell the renderer which
 * space the task belongs to, so the app can go there.
 *
 * The Brain publishes plan progress as Server-Sent Events on /api/multihop/stream.
 * Each `hop_started` carries `space` (the id from config/space_agent_registry.yml,
 * set by brain/the_brain/core/step_space.py). This module listens, maps that id to the
 * key of the app's 3D scene and sends `task_navigate` (once per plan and space) and
 * `task_status` (where the plan stands, and its result), see createTaskNavigator.
 *
 * Whether to really switch (the user may be busy) is decided in the renderer.
 */
const http = require('node:http');
const { OWN_PLAN_PREFIX } = require('./orders-data');

/**
 * Registry space id -> key in the app's scene (multiverse.js `this.spaces`).
 * `null` = the space has no place in the app yet; nothing is sent for it.
 */
const SPACE_TO_APP = Object.freeze({
  ideas: 'ideas',
  bubbles: 'ideas',        // bubbles live in the Ideas overview
  coding: 'projects',
  desktop: 'desktop',
  rowboat: 'roarboot',
  agentfarm: 'agentfarm',
  video: 'video',
  flowzen: 'flowzen',
  mirofish: 'mirofish',
  schedule: 'orders',            // no page of their own: the local page "Auftraege"
  research: 'orders',
  minibook: 'orders',
  learning: 'learning',          // external spaces, see external-spaces.js
  'event-management': 'events',
  sales: 'sales',
  marketing: 'marketing',
  // Software design (with requirements engineering) has no entry in the registry yet; these
  // are the ids it may get. An id the Brain never sends costs nothing.
  'swe-design': 'swedesign',
  swe_design: 'swedesign',
  swedesign: 'swedesign',
  'software-design': 'swedesign',
});

function appKeyForSpace(space) {
  if (typeof space !== 'string') return null;
  const key = SPACE_TO_APP[space.trim().toLowerCase()];
  return key || null;
}

/** Splits a text buffer into complete SSE events; the unfinished tail is returned as `rest`. */
function parseSse(buffer) {
  const events = [];
  const blocks = buffer.split(/\r?\n\r?\n/);
  const rest = blocks.pop();
  for (const block of blocks) {
    let kind = 'message';
    const data = [];
    for (const line of block.split(/\r?\n/)) {
      if (line.startsWith(':')) continue; // comment / keepalive
      if (line.startsWith('event:')) kind = line.slice(6).trim();
      else if (line.startsWith('data:')) data.push(line.slice(5).replace(/^ /, ''));
    }
    if (!data.length) continue;
    try {
      events.push({ kind, payload: JSON.parse(data.join('\n')) });
    } catch (_) {
      // a broken event must not stop the stream
    }
  }
  return { events, rest };
}

const RESULT_MAX = 240;

const count = (value) => (Number.isInteger(value) && value > 0 ? value : null);

/** Stage of a pipeline step: id, position and readable name (field names provisional). */
function stageOf(payload) {
  return {
    stage: text(payload.stage),
    stage_nr: count(payload.stage_nr),
    stage_total: count(payload.stage_total),
    stage_label: text(payload.stage_label),
  };
}

const text = (value) => (typeof value === 'string' ? value.trim().slice(0, RESULT_MAX) : '');

/**
 * A short readable text from `result_preview` (a Python repr, cut at 500 characters).
 * A `message`/`result`/`summary` entry inside is preferred over the raw repr.
 */
function resultText(preview) {
  if (typeof preview !== 'string') return '';
  let text = preview.trim();
  if (!text || text === 'None') return '';
  const inner = /['"](?:message|result|summary|text)['"]:\s*(['"])((?:\\.|(?!\1).)*)\1/.exec(text);
  if (inner && inner[2].trim()) text = inner[2];
  else text = text.replace(/^(['"])([\s\S]*)\1$/, '$2');
  // the repr writes a line break as backslash-n and escapes quotes
  text = text.replace(/\\[nrt]/g, ' ').replace(/\\(['"\\])/g, '$1');
  // Identifiers of rows say nothing to the user: "(id=3f2a..., score=0)" and bare UUIDs go.
  text = text.replace(/\(\s*id\s*=[^)]*\)/gi, '').replace(/\bid\s*=\s*[\w-]+,?/gi, '')
    .replace(/\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b/gi, '');
  text = text.replace(/\s+/g, ' ').trim();
  return text.length > RESULT_MAX ? text.slice(0, RESULT_MAX - 1) + '\u2026' : text;
}

/**
 * The reason a step or plan failed, as the user reads it: the Brain's German sentence (`final_text`),
 * else `error`. The raw original (`fehler`) is never shown.
 */
function errorText(payload) {
  return text(payload && payload.final_text) || text(payload && payload.meldung) || plainError(payload && payload.error) || 'fehlgeschlagen';
}

/** A technical error of a tool or service ("ConnectionError: HTTPConnectionPool(host=…)"), not a sentence. */
const RAW_ERROR = /Error\b|Exception|Traceback|HTTPConnectionPool|Max retries|Timeout|timed out|refused|\bHTTP\b|\b[45]\d\d\s+(?:Not Found|Forbidden|Unauthori[sz]ed|Bad Request|Bad Gateway|Internal Server Error|Service Unavailable)\b|\bhost=|\bport=|Errno|https?:\/\/|File "|[{}[\]<>]|\w+\.\w+\(|^\s*[A-Za-z_]+(?:Error|Exception):\s/;

/**
 * An error as a person reads it. A German sentence stays; a raw error of a hop never reaches the
 * status line, it becomes one plain sentence about what happened.
 */
function plainError(value) {
  const said = text(value);
  if (!said || !RAW_ERROR.test(said)) return said;
  if (/timed? ?out|timeout|Zeitüberschreitung/i.test(said)) return 'Der Dienst hat nicht rechtzeitig geantwortet.';
  if (/Connection|connect|refused|unreachable|Name or service|getaddrinfo|resolve|Max retries|Errno 111|Errno 11001/i.test(said)) return 'Der Dienst ist gerade nicht erreichbar.';
  if (/\b(401|403)\b|Unauthori[sz]ed|Forbidden|permission/i.test(said)) return 'Der Dienst hat den Zugriff abgelehnt.';
  if (/\b404\b|Not Found|NotFound/i.test(said)) return 'Der Dienst hat das Gesuchte nicht gefunden.';
  return 'Der Schritt hat nicht geklappt.';
}

/** 'rueckfrage' or 'hinweis' when the Brain asks back or gives a hint (shown calmly, never as failed), else ''. */
function noteOf(payload) {
  if (!payload) return '';
  if (payload.rueckfrage === true || payload.verstanden === false) return 'rueckfrage';
  if (payload.hinweis === true) return 'hinweis';
  return '';
}

/**
 * A step whose work goes on after the plan: the Brain took the order and a model works on it
 * ({ ok: true, pending: true, status: 'angenommen' }). Its result arrives later at the card,
 * through the database. Read from the event itself or from the preview of its result.
 */
function acceptedOf(payload) {
  if (!payload || payload.ok === false) return false;
  // fertig: false (new Brain): the plan gave an order and ended; the result is not there yet.
  if (payload.pending === true || payload.status === 'angenommen' || payload.fertig === false) return true;
  const preview = typeof payload.result_preview === 'string' ? payload.result_preview : '';
  return /['"]pending['"]\s*:\s*(?:True|true)\b/.test(preview) || /['"]status['"]\s*:\s*['"]angenommen['"]/.test(preview);
}

/** Ids of the cards an accepted order works on, when the step names them. */
function targetsOf(payload) {
  const ids = [];
  const add = (value) => { if ((typeof value === 'string' || typeof value === 'number') && String(value).trim()) ids.push(String(value).trim()); };
  if (payload && Array.isArray(payload.targets)) payload.targets.forEach(add);
  if (payload) { add(payload.card_id); add(payload.target_id); }
  const preview = payload && typeof payload.result_preview === 'string' ? payload.result_preview : '';
  const list = /['"]targets['"]\s*:\s*\[([^\]]*)\]/.exec(preview);
  if (list) for (const found of list[1].matchAll(/['"]([^'"]+)['"]/g)) add(found[1]);
  for (const key of ['card_id', 'target_id']) {
    const one = new RegExp(`['"]${key}['"]\\s*:\\s*['"]([^'"]+)['"]`).exec(preview);
    if (one) add(one[1]);
  }
  return [...new Set(ids)];
}

/**
 * Turns plan events into messages for the renderer:
 *
 *   task_navigate  once per plan and space, at the first step that starts there. A plan that
 *                  moves on to another space (design, then coding) is followed; a space already
 *                  visited in this plan is not jumped to again, so nothing flips back and forth.
 *   task_status    where the plan stands: { state: 'running' | 'accepted' | 'done' | 'failed', space,
 *                  step, done, total, result, error, elapsed_s, plan_id }. `space` is the app key of
 *                  the last step with a place in the app ('' when the plan has none).
 *                  'accepted': the plan is over, but a model still works on an order it took;
 *                  `targets` names the cards, when the Brain says which. Never shown as failed.
 *
 * @param {(message: object) => void} send
 */
/** A trace id as the app sends it with a sentence (renderer: crypto.randomUUID); anything else is dropped. */
const TRACE_ID = /^[A-Za-z0-9_.:-]{1,80}$/;
function traceOf(payload) {
  const value = payload && payload.trace_id;
  return typeof value === 'string' && TRACE_ID.test(value) ? value : '';
}

/** A plain id of the Brain (bubble or card); anything else is never passed on. */
const PLAIN_ID = /^[A-Za-z0-9-]{1,64}$/;

/**
 * Where the result of a writing call lies, as the Brain names it: { space, bubble_id, node_id } or
 * null. node_id may be null (a bubble as a whole, e.g. rated or arranged).
 */
function zielOf(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
  const id = (x) => (typeof x === 'number' && Number.isInteger(x) ? String(x) : x);
  const space = value.space;
  const bubble = id(value.bubble_id);
  const node = id(value.node_id);
  if (typeof space !== 'string' || !/^[a-z0-9_]{1,32}$/.test(space)) return null;
  // A bubble only for a result in a bubble of Ideas; a result in Sales, Rowboat, … names its space alone.
  if (bubble == null || bubble === '') return { space, bubble_id: null, node_id: null };
  if (typeof bubble !== 'string' || !PLAIN_ID.test(bubble)) return null;
  return { space, bubble_id: bubble, node_id: typeof node === 'string' && PLAIN_ID.test(node) ? node : null };
}

function createTaskNavigator(send) {
  let planId = '';
  let total = 0;
  let done = 0;
  let visited = new Set();
  let last = null; // { space, registry_space, step, result, error }
  let accepted = null; // { space, registry_space, step, targets } the step whose order a model still works on
  let failedStep = false;
  let note = null; // { kind: 'rueckfrage' | 'hinweis', text } a step that asked back or gave a hint
  // The sentence a plan answers: the Brain gives every event of a run the trace_id the app sent with
  // its sentence. It goes on in every message, so overlapping sentences are told apart without order.
  let trace = '';
  const emit = (message) => send(trace ? { ...message, trace_id: trace } : message);

  const status = (state, extra = {}) => {
    const message = {
      type: 'task_status',
      state,
      plan_id: planId,
      space: last ? last.space : '',
      registry_space: last ? last.registry_space : '',
      step: last ? last.step : '',
      done,
      total,
      result: last ? last.result : '',
      error: last ? last.error : '',
      // Announced by the Brain, names provisional: the stage of a pipeline and a pointer to the result.
      stage: last ? last.stage : '',
      // Position of the stage in its pipeline and its readable name, when the Brain sends them.
      stage_nr: last ? last.stage_nr : null,
      stage_total: last ? last.stage_total : null,
      stage_label: last ? last.stage_label : '',
      result_ref: last ? last.result_ref : '',
      ...(trace ? { trace_id: trace } : {}),
      ...extra,
    };
    send(message);
    return message;
  };

  // Plans the app runs for its own pages (the list of the entry "Auftraege") are no task of the person.
  const ownPlan = (id) => typeof id === 'string' && id.startsWith(OWN_PLAN_PREFIX);
  let ignoring = false;

  return {
    handle(kind, payload) {
      if (!payload) payload = {};
      if (kind === 'plan_started') ignoring = ownPlan(payload.plan_id);
      const id = typeof payload.plan_id === 'string' && payload.plan_id ? payload.plan_id : null;
      if (id ? ownPlan(id) : ignoring) return null;
      const traced = traceOf(payload);
      if (traced) trace = traced;
      else if (kind === 'plan_started') trace = '';
      if (kind === 'plan_started') {
        planId = typeof payload.plan_id === 'string' ? payload.plan_id : '';
        total = Array.isArray(payload.hops) ? payload.hops.length : 0;
        done = 0;
        visited = new Set();
        last = null;
        accepted = null;
        failedStep = false;
        note = null;
        // A new plan: what the plan before ended with is no longer the news.
        const reset = { type: 'task_status', state: 'reset', plan_id: planId };
        emit(reset);
        // The Brain names the space of a plan with its start. Then the app follows at once and does
        // not wait for the first step, which can come seconds later.
        const start = appKeyForSpace(payload.space);
        if (start) {
          last = { space: start, registry_space: payload.space, step: '', result: '', error: '', result_ref: '', ...stageOf(payload) };
          visited.add(start);
          emit({ type: 'task_navigate', space: start, registry_space: payload.space, capability: '', description: text(payload.intent) });
          status('running');
        }
        return null;
      }
      if (kind === 'hop_started') {
        const space = appKeyForSpace(payload.space);
        if (!space) return null; // a general step, or a space without a place in the app
        last = { space, registry_space: payload.space, step: payload.description || payload.capability || '', result: '', error: '', result_ref: '', ...stageOf(payload) };
        let navigation = null;
        if (!visited.has(space)) {
          visited.add(space);
          navigation = {
            type: 'task_navigate',
            space,
            registry_space: payload.space,
            capability: payload.capability || '',
            description: payload.description || '',
          };
          emit(navigation);
        }
        status('running');
        return navigation;
      }
      if (kind === 'hop_completed') {
        done += 1;
        const space = appKeyForSpace(payload.space);
        const taken = acceptedOf(payload);
        // A hint or a question back of the Brain (ok false with hinweis/rueckfrage true) is no failure.
        const calm = noteOf(payload);
        if (calm) note = { kind: calm, text: text(payload.final_text) || text(payload.meldung) };
        if (payload.ok === false && !calm) failedStep = true;
        if (!space) return null;
        last = {
          space,
          registry_space: payload.space,
          step: payload.description || payload.capability || '',
          // An accepted order has no result yet; its preview is the receipt of the Brain, not a sentence.
          result: calm ? note.text : payload.ok === false || taken ? '' : resultText(payload.result_preview),
          error: payload.ok === false && !calm ? errorText(payload) : '',
          result_ref: text(payload.result_ref),
          ...stageOf(payload),
        };
        if (taken) accepted = { space, registry_space: payload.space, step: last.step, targets: targetsOf(payload) };
        return status('running', { step_ok: payload.ok !== false, ...(taken ? { accepted: true, targets: accepted.targets } : {}) });
      }
      if (kind === 'plan_completed') {
        if (!last) return null; // nothing of this plan had a place in the app
        // Where the result of a writing call lies (Brain: ziel): the app goes there and marks the card.
        const ziel = zielOf(payload.ziel);
        const end = (state, extra = {}) => status(state, ziel ? { ...extra, ziel } : extra);
        const seconds = Number(payload.elapsed_s);
        // berichtigt: true (new Brain): a second end of the same plan replaces the first, e.g. a
        // result found unreadable afterwards (ok: false, nicht_lesbar: true). It is judged afresh.
        const corrected = payload.berichtigt === true;
        if (corrected) {
          accepted = null;
          note = null;
          last = { ...last, result: text(payload.final_text) || last.result, error: payload.ok === false ? errorText(payload) : '' };
        }
        const elapsed = { elapsed_s: Number.isFinite(seconds) ? seconds : null, ...(corrected ? { berichtigt: true } : {}) };
        // The plan is over, the order it gave is not: a model still works on it. Not failed, not done.
        // The receipt may also come only with the end of the plan ({ pending: true, status: 'angenommen' }).
        if (!accepted && acceptedOf(payload)) {
          accepted = { space: last.space, registry_space: last.registry_space, step: last.step, targets: targetsOf(payload) };
        }
        if (accepted && !failedStep) {
          last = { ...last, space: accepted.space, registry_space: accepted.registry_space, step: accepted.step, result: '', error: '' };
          // No duration: the time it took to accept the order is not the time of its result.
          return end('accepted', { elapsed_s: null, targets: accepted.targets, ...(corrected ? { berichtigt: true } : {}) });
        }
        // A hint or a question back ends the plan calmly: neither ✓ nor ✕.
        const calm = noteOf(payload);
        if (!failedStep && (calm || note)) {
          const kind = calm || note.kind;
          const said = text(payload.final_text) || (note && note.text) || '';
          last = { ...last, result: said, error: '' };
          return end('note', { ...elapsed, note: kind });
        }
        // A step without a usable answer (ok: false) gets no ✓, even when the plan as a whole says ok.
        if (payload.ok === false || failedStep) {
          if (payload.ok === false && !last.error) last = { ...last, error: errorText(payload) };
          return end('failed', elapsed);
        }
        return end('done', elapsed);
      }
      return null;
    },
  };
}

/** The states of an order the Brain names at GET /api/agent-auftraege/{id}/stand. */
const ORDER_STANDS = Object.freeze(['laeuft', 'fertig', 'vorschlag', 'abgebrochen', 'verworfen', 'uebernommen', 'ungeprueft', 'wartet', 'fehler', 'unbekannt']);
/** An order id as the Brain gives it; anything else is never put into a path. */
const ORDER_ID = /^[A-Za-z0-9-]{4,64}$/;

/**
 * The answer of /stand as the app uses it: { stand, meldung, ok, dauer_s, hinweis, saetze } or null.
 * Only these fields pass; meldung is a sentence of the Brain, a raw error becomes a plain one.
 */
function standOf(body) {
  if (!body || typeof body !== 'object') return null;
  // A state the app does not know yet still passes when the Brain says something about it: the
  // renderer then shows that sentence and ends. Without a sentence it says nothing to the app.
  const named = typeof body.stand === 'string' && /^[a-z_]{1,32}$/.test(body.stand) ? body.stand : null;
  const stand = named && (ORDER_STANDS.includes(named) || text(body.meldung)) ? named : null;
  if (!stand) return null;
  const seconds = Number(body.dauer_s);
  const saetze = Array.isArray(body.saetze)
    ? body.saetze.filter((x) => typeof x === 'string' && x.trim()).map((x) => x.trim().slice(0, 80)).slice(0, 4) : [];
  return {
    stand,
    meldung: plainError(body.meldung),
    ok: body.ok !== false,
    dauer_s: body.dauer_s != null && Number.isFinite(seconds) && seconds >= 0 ? seconds : null,
    hinweis: body.hinweis === true,
    saetze,
    // where the result of the order lies, once the Brain names it at /stand
    ...(zielOf(body.ziel) ? { ziel: zielOf(body.ziel) } : {}),
  };
}

/** Read the stand of one order from the Brain (only reading). Resolves null on any trouble. */
function readOrderStand(id, { host = '127.0.0.1', port = 5000, timeoutMs = 4000 } = {}) {
  return new Promise((resolve) => {
    if (typeof id !== 'string' || !ORDER_ID.test(id)) { resolve(null); return; }
    const request = http.get({ host, port, path: '/api/agent-auftraege/' + encodeURIComponent(id) + '/stand',
      headers: { Accept: 'application/json' }, timeout: timeoutMs }, (res) => {
      let raw = '';
      res.setEncoding('utf8');
      res.on('data', (chunk) => { if (raw.length < 65536) raw += chunk; });
      res.on('end', () => {
        if (res.statusCode !== 200) { resolve(null); return; }
        try { resolve(standOf(JSON.parse(raw))); } catch { resolve(null); }
      });
      res.on('error', () => resolve(null));
    });
    request.on('timeout', () => request.destroy());
    request.on('error', () => resolve(null));
  });
}

let _request = null;
let _timer = null;
let _closed = false;
let _standHandled = false;

function initTaskNavigation(mainWindow, options = {}) {
  const host = options.host || process.env.BRAIN_HOST || '127.0.0.1';
  const port = parseInt(options.port || process.env.BRAIN_PORT || '5000', 10);
  const log = options.logger || console;
  const navigator = createTaskNavigator((message) => {
    if (mainWindow && !mainWindow.isDestroyed()) mainWindow.webContents.send('python-message', message);
    if (message.type === 'task_navigate') {
      log.log(`[Task-Nav] ${message.registry_space} -> ${message.space} (${message.capability})`);
    } else if (message.state === 'done' || message.state === 'failed') {
      log.log(`[Task-Nav] Plan ${message.state} in ${message.space}`);
    }
  });
  _closed = false;
  // The stand of an accepted order (renderer: every 5 s while the line says "arbeitet").
  if (options.ipcMain && !_standHandled) {
    _standHandled = true;
    options.ipcMain.handle('task:order-stand', (_event, id) => readOrderStand(id, { host, port }));
  }

  const reconnect = (ms) => {
    if (_closed || _timer) return;
    _timer = setTimeout(() => { _timer = null; connect(); }, ms);
  };

  function connect() {
    if (_closed) return;
    let buffer = '';
    _request = http.get({ host, port, path: '/api/multihop/stream', headers: { Accept: 'text/event-stream' } }, (res) => {
      if (res.statusCode !== 200) {
        res.resume();
        reconnect(5000);
        return;
      }
      log.log('[Task-Nav] Connected — following plan steps');
      res.setEncoding('utf8');
      res.on('data', (chunk) => {
        const parsed = parseSse(buffer + chunk);
        buffer = parsed.rest;
        for (const event of parsed.events) navigator.handle(event.kind, event.payload);
      });
      res.on('end', () => reconnect(2000));
      res.on('error', () => reconnect(3000));
    });
    _request.on('error', () => reconnect(5000));
  }

  connect();
}

function closeTaskNavigation() {
  _closed = true;
  if (_timer) { clearTimeout(_timer); _timer = null; }
  if (_request) { _request.destroy(); _request = null; }
}

module.exports = {
  plainError, standOf, readOrderStand, ORDER_STANDS,
  traceOf, zielOf, SPACE_TO_APP, appKeyForSpace, parseSse, resultText, acceptedOf, targetsOf, noteOf, createTaskNavigator, initTaskNavigation, closeTaskNavigation,
};
