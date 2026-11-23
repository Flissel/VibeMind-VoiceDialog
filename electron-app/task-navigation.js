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
  if (inner && inner[2].trim()) text = inner[2].replace(/\\n/g, ' ').replace(/\\(['"\\])/g, '$1');
  else text = text.replace(/^(['"])([\s\S]*)\1$/, '$2');
  text = text.replace(/\s+/g, ' ').trim();
  return text.length > RESULT_MAX ? text.slice(0, RESULT_MAX - 1) + '\u2026' : text;
}

/**
 * Turns plan events into messages for the renderer:
 *
 *   task_navigate  once per plan and space, at the first step that starts there. A plan that
 *                  moves on to another space (design, then coding) is followed; a space already
 *                  visited in this plan is not jumped to again, so nothing flips back and forth.
 *   task_status    where the plan stands: { state: 'running' | 'done' | 'failed', space, step,
 *                  done, total, result, error, elapsed_s, plan_id }. `space` is the app key of
 *                  the last step with a place in the app ('' when the plan has none).
 *
 * @param {(message: object) => void} send
 */
function createTaskNavigator(send) {
  let planId = '';
  let total = 0;
  let done = 0;
  let visited = new Set();
  let last = null; // { space, registry_space, step, result, error }

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
      ...extra,
    };
    send(message);
    return message;
  };

  return {
    handle(kind, payload) {
      if (!payload) payload = {};
      if (kind === 'plan_started') {
        planId = typeof payload.plan_id === 'string' ? payload.plan_id : '';
        total = Array.isArray(payload.hops) ? payload.hops.length : 0;
        done = 0;
        visited = new Set();
        last = null;
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
          send(navigation);
        }
        status('running');
        return navigation;
      }
      if (kind === 'hop_completed') {
        done += 1;
        const space = appKeyForSpace(payload.space);
        if (!space) return null;
        last = {
          space,
          registry_space: payload.space,
          step: payload.description || payload.capability || '',
          result: payload.ok === false ? '' : resultText(payload.result_preview),
          error: payload.ok === false ? String(payload.error || 'fehlgeschlagen').slice(0, RESULT_MAX) : '',
          result_ref: text(payload.result_ref),
          ...stageOf(payload),
        };
        return status('running', { step_ok: payload.ok !== false });
      }
      if (kind === 'plan_completed') {
        if (!last) return null; // nothing of this plan had a place in the app
        const seconds = Number(payload.elapsed_s);
        return status(payload.ok === false ? 'failed' : 'done', { elapsed_s: Number.isFinite(seconds) ? seconds : null });
      }
      return null;
    },
  };
}

let _request = null;
let _timer = null;
let _closed = false;

function initTaskNavigation(mainWindow, options = {}) {
  const host = options.host || process.env.BRAIN_HOST || '127.0.0.1';
  const port = parseInt(options.port || process.env.BRAIN_PORT || '5000', 10);
  const log = options.logger || console;
  const navigator = createTaskNavigator((message) => {
    if (mainWindow && !mainWindow.isDestroyed()) mainWindow.webContents.send('python-message', message);
    if (message.type === 'task_navigate') {
      log.log(`[Task-Nav] ${message.registry_space} -> ${message.space} (${message.capability})`);
    } else if (message.state !== 'running') {
      log.log(`[Task-Nav] Plan ${message.state} in ${message.space}`);
    }
  });
  _closed = false;

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
  SPACE_TO_APP, appKeyForSpace, parseSse, resultText, createTaskNavigator, initTaskNavigation, closeTaskNavigation,
};
