/**
 * Where n8n is and how the Agent Farm signs in.
 *
 * n8n may run on this machine or elsewhere (N8N_API_URL). The Agent Farm shows the n8n
 * editor in a frame and signs in for the user. The address was hardcoded to
 * localhost:15678 in three places and the sign-in always used the account that a
 * freshly started local n8n gets; against any other n8n that was refused six times in
 * a row (401, then 429).
 *
 * Sign-in data come from the environment (N8N_UI_EMAIL, N8N_UI_PASSWORD). The built-in
 * account is only tried against an n8n on this machine.
 */

const LOCAL_URL = 'http://localhost:15678';
// The owner that local-startup.js creates on a fresh local n8n. Not a secret of any real system.
const LOCAL_OWNER = Object.freeze({ email: 'admin@vibemind.local', password: 'Vibemind1' });

function n8nBaseUrl(env = process.env) {
  // N8N_UI_URL wins: the main process sets it to a local forward when n8n runs on another
  // machine over plain http (see forwardTarget). N8N_API_URL stays what the backend uses.
  const ui = typeof env.N8N_UI_URL === 'string' ? env.N8N_UI_URL.trim() : '';
  const raw = ui || (typeof env.N8N_API_URL === 'string' ? env.N8N_API_URL.trim() : '');
  try {
    const url = new URL(raw || LOCAL_URL);
    if (url.protocol !== 'http:' && url.protocol !== 'https:') return LOCAL_URL;
    return url.origin;
  } catch (_) {
    return LOCAL_URL;
  }
}

/**
 * Whether n8n answers: GET <base>/healthz from the main process. The display "n8n online/offline"
 * of the Agent Farm used to come from python spaces.n8n, which is missing from the installation:
 * it said "offline" while the editor beside it showed n8n (2026-11-26). localhost is asked as
 * 127.0.0.1, so a name that resolves to ::1 first does not make a running n8n look offline.
 */
async function n8nHealth(env = process.env, { fetchImpl = globalThis.fetch, timeoutMs = 3000 } = {}) {
  const url = n8nBaseUrl(env);
  const probe = new URL('/healthz', url);
  if (probe.hostname === 'localhost') probe.hostname = '127.0.0.1';
  const controller = typeof AbortController === 'function' ? new AbortController() : null;
  const timer = controller ? setTimeout(() => controller.abort(), timeoutMs) : null;
  try {
    const res = await fetchImpl(probe.href, { method: 'GET', signal: controller ? controller.signal : undefined });
    return res && res.ok ? { online: true, url } : { online: false, url, error: `n8n antwortet mit ${res ? res.status : 'nichts'}` };
  } catch (_) {
    return { online: false, url, error: 'n8n nicht erreichbar' };
  } finally {
    if (timer) clearTimeout(timer);
  }
}

/** An n8n workflow id: letters, digits, _ and -; nothing that could change the path. */
function isWorkflowId(id) {
  return typeof id === 'string' && /^[A-Za-z0-9_-]{1,64}$/.test(id);
}

/**
 * Activate a workflow through the n8n REST interface (POST /api/v1/workflows/<id>/activate), from the
 * main process with N8N_API_KEY. The VibeCoder field calls it only after the person said "Ja" to a
 * proposal (vibecoder-chat.js). The reason of a failure names the variable, never its value.
 */
async function n8nActivateRest(env, workflowId, { fetchImpl = globalThis.fetch, timeoutMs = 10000 } = {}) {
  const key = typeof env.N8N_API_KEY === 'string' ? env.N8N_API_KEY.trim() : '';
  if (!key) return { success: false, error: 'N8N_API_KEY fehlt' };
  if (!isWorkflowId(workflowId)) return { success: false, error: 'keine gueltige Workflow-id' };
  const url = new URL(`/api/v1/workflows/${workflowId}/activate`, n8nBaseUrl(env));
  if (url.hostname === 'localhost') url.hostname = '127.0.0.1';
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetchImpl(url.href, { method: 'POST', headers: { 'X-N8N-API-KEY': key, Accept: 'application/json' }, signal: controller.signal });
    return res && res.ok ? { success: true } : { success: false, error: `n8n antwortet mit ${res ? res.status : 'nichts'}` };
  } catch (_) {
    return { success: false, error: 'n8n nicht erreichbar' };
  } finally {
    clearTimeout(timer);
  }
}

/**
 * Name and state of a workflow as n8n itself has them (GET /api/v1/workflows/<id>), or null.
 * The VibeCoder field shows this name in its question, never the one the agent wrote.
 */
async function n8nWorkflowInfo(env, workflowId, { fetchImpl = globalThis.fetch, timeoutMs = 5000 } = {}) {
  const key = typeof env.N8N_API_KEY === 'string' ? env.N8N_API_KEY.trim() : '';
  if (!key || !isWorkflowId(workflowId)) return null;
  const url = new URL(`/api/v1/workflows/${workflowId}`, n8nBaseUrl(env));
  if (url.hostname === 'localhost') url.hostname = '127.0.0.1';
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetchImpl(url.href, { method: 'GET', headers: { 'X-N8N-API-KEY': key, Accept: 'application/json' }, signal: controller.signal });
    if (!res || !res.ok) return null;
    const body = await res.json();
    if (!body || String(body.id) !== workflowId || typeof body.name !== 'string') return null;
    return { id: workflowId, name: body.name.slice(0, 120), active: body.active === true };
  } catch (_) {
    return null;
  } finally {
    clearTimeout(timer);
  }
}

function isLocal(baseUrl) {
  const host = new URL(baseUrl).hostname;
  return host === 'localhost' || host === '127.0.0.1' || host === '[::1]';
}

/** The account to sign in with, or null when none is known for this n8n. */
function n8nLogin(env = process.env) {
  const email = typeof env.N8N_UI_EMAIL === 'string' ? env.N8N_UI_EMAIL.trim() : '';
  const password = typeof env.N8N_UI_PASSWORD === 'string' ? env.N8N_UI_PASSWORD : '';
  if (email && password) return { email, password, source: 'environment' };
  if (isLocal(n8nBaseUrl(env))) return { ...LOCAL_OWNER, source: 'local default' };
  return null;
}

/**
 * A refused sign-in does not get better by repeating it, and n8n starts locking out
 * (429). Only "not there yet" is worth another try.
 */
function shouldRetryLogin(statusCode) {
  return ![400, 401, 403, 404, 422, 429].includes(statusCode);
}

/** Addresses whose framing headers the Agent Farm removes so they can be shown in a frame. */
function frameHeaderUrls(env = process.env) {
  const urls = new Set(['http://localhost:15678/*', 'http://localhost:4200/*']);
  urls.add(`${n8nBaseUrl(env)}/*`);
  return [...urls];
}

/**
 * Where to forward a local port to, or null when n8n is local or uses TLS.
 *
 * n8n refuses to work in a browser over plain http from another machine ("configured to use a
 * secure cookie"), and the browser will not store its session cookie there either. Reached
 * through a local forward as http://localhost:PORT both are satisfied: localhost counts as a
 * secure context. Nothing on the n8n machine has to change.
 */
function forwardTarget(env = process.env) {
  const raw = typeof env.N8N_API_URL === 'string' ? env.N8N_API_URL.trim() : '';
  let url;
  try {
    url = new URL(raw);
  } catch (_) {
    return null;
  }
  if (url.protocol !== 'http:' || isLocal(url.origin)) return null;
  return { host: url.hostname, port: Number(url.port || 80) };
}

/** "name=value" pairs from the Set-Cookie headers of the sign-in answer. */
function cookiePairs(setCookieHeaders) {
  const pairs = [];
  for (const raw of setCookieHeaders || []) {
    const first = String(raw).split(';')[0].trim();
    if (first.includes('=') && first.split('=')[0]) pairs.push(first);
  }
  return pairs;
}

/**
 * The Cookie header for a request to n8n: what the request already carries, plus the
 * session cookies, each name once (the session value wins).
 *
 * Why not the browser's cookie store: the editor sits in a frame of another site, so the
 * cookie must be `SameSite=None`, which browsers only accept as `Secure`, and a Secure
 * cookie cannot be stored for a plain-http address on another machine. Adding the header
 * in the main process works for every address and keeps the value out of the page.
 */
function mergeCookieHeader(existing, pairs) {
  const merged = new Map();
  for (const part of String(existing || '').split(';')) {
    const text = part.trim();
    if (text.includes('=')) merged.set(text.split('=')[0], text);
  }
  for (const pair of pairs) merged.set(pair.split('=')[0], pair);
  return [...merged.values()].join('; ');
}

/** Requests that get the session cookie: n8n itself, http and websocket. */
function sessionCookieUrls(env = process.env) {
  const base = new URL(n8nBaseUrl(env));
  const ws = base.protocol === 'https:' ? 'wss:' : 'ws:';
  return [`${base.origin}/*`, `${ws}//${base.host}/*`];
}

module.exports = {
  LOCAL_URL, n8nBaseUrl, n8nHealth, n8nActivateRest, n8nWorkflowInfo, isWorkflowId, n8nLogin, shouldRetryLogin, frameHeaderUrls, forwardTarget,
  cookiePairs, mergeCookieHeader, sessionCookieUrls,
};
