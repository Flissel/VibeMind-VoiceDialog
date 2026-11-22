/**
 * Task navigation: when the Brain starts working on a task, tell the renderer which
 * space the task belongs to, so the app can go there.
 *
 * The Brain publishes plan progress as Server-Sent Events on /api/multihop/stream.
 * Each `hop_started` carries `space` (the id from config/space_agent_registry.yml,
 * set by brain/the_brain/core/step_space.py). This module listens, maps that id to the
 * key of the app's 3D scene and sends one `task_navigate` message per plan: the app
 * should follow the task once, not jump back and forth with every step.
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
  schedule: null,
  research: null,
  minibook: null,
  learning: null,
  'event-management': null,
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

/**
 * Turns plan events into at most one navigation per plan.
 * @param {(message: object) => void} send
 */
function createTaskNavigator(send) {
  let navigated = false;
  return {
    handle(kind, payload) {
      if (kind === 'plan_started') {
        navigated = false;
        return null;
      }
      if (kind !== 'hop_started' || navigated || !payload) return null;
      const space = appKeyForSpace(payload.space);
      if (!space) return null; // a general step, or a space without a place in the app: try the next step
      navigated = true;
      const message = {
        type: 'task_navigate',
        space,
        registry_space: payload.space,
        capability: payload.capability || '',
        description: payload.description || '',
      };
      send(message);
      return message;
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
    log.log(`[Task-Nav] ${message.registry_space} -> ${message.space} (${message.capability})`);
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
  SPACE_TO_APP, appKeyForSpace, parseSse, createTaskNavigator, initTaskNavigation, closeTaskNavigation,
};
