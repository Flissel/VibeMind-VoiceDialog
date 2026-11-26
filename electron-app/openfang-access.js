/**
 * R3: the key of OpenFang for its tab in the Agent Farm.
 *
 * Since OpenFang 0.6.9 its dashboard may ask for a key. The key stays in the main process: it is read
 * from OPENFANG_API_KEY and added as `Authorization: Bearer …` to a request only when
 *   - the request goes to the OpenFang address (OPENFANG_URL, default 127.0.0.1:4200), and
 *   - it comes from the OpenFang page itself in its tab (or is the navigation of that tab's frame).
 *
 * n8n and Rowboat run as embedded pages in the same session of the Agent Farm. A foreign page there
 * that fetches 127.0.0.1:4200 must not get the user's access for free (Marketing-Befund 2026-11-25):
 * a foreign Origin, `Sec-Fetch-Site: cross-site`/`same-site`, a frame of another origin, a nested
 * frame or a redirect to another host never gets the header. Without a frame to check, nothing is
 * added (fails closed). The value is never in the renderer, a URL, the log or localStorage.
 */
const DEFAULT_URL = 'http://127.0.0.1:4200';
const LOOPBACK = ['127.0.0.1', 'localhost'];

/** The OpenFang address from the environment, else the default. */
function openfangBaseUrl(env = process.env) {
  const raw = typeof env.OPENFANG_URL === 'string' ? env.OPENFANG_URL.trim() : '';
  try {
    const url = new URL(raw || DEFAULT_URL);
    if (url.protocol !== 'http:' && url.protocol !== 'https:') return DEFAULT_URL;
    return url.origin;
  } catch (_) {
    return DEFAULT_URL;
  }
}

/** Origins of OpenFang (loopback: as 127.0.0.1 and as localhost, the tab loads either). */
function openfangOrigins(env = process.env) {
  const base = new URL(openfangBaseUrl(env));
  const port = base.port ? `:${base.port}` : '';
  const hosts = LOOPBACK.includes(base.hostname) ? LOOPBACK : [base.hostname];
  return hosts.map((host) => `${base.protocol}//${host}${port}`);
}

/**
 * URL patterns, origins and header for the key, or null when there is no key.
 * `name` is what the log may say; the value itself never leaves this object.
 */
function openfangAuth(env = process.env) {
  const key = typeof env.OPENFANG_API_KEY === 'string' ? env.OPENFANG_API_KEY.trim() : '';
  if (!key) return null;
  const origins = openfangOrigins(env);
  const urls = origins.flatMap((origin) => {
    const ws = origin.startsWith('https:') ? origin.replace(/^https:/, 'wss:') : origin.replace(/^http:/, 'ws:');
    return [`${origin}/*`, `${ws}/*`];
  });
  return { urls, origins, header: `Bearer ${key}`, name: 'OPENFANG_API_KEY' };
}

function originOf(url) {
  try {
    const parsed = new URL(url);
    // ws(s) counts as its http(s) origin
    const protocol = parsed.protocol === 'ws:' ? 'http:' : parsed.protocol === 'wss:' ? 'https:' : parsed.protocol;
    return parsed.host ? `${protocol}//${parsed.host}` : '';
  } catch (_) {
    return '';
  }
}

function header(headers, name) {
  const key = Object.keys(headers || {}).find((k) => k.toLowerCase() === name);
  return key ? String(headers[key]) : '';
}

/**
 * Whether this request may carry the key.
 * `isAppPage(url)` says whether a document is the Agent Farm page itself (file:// or its dev address).
 */
function fromOpenFangFrame(details, origins, isAppPage) {
  if (!details || !Array.isArray(origins) || !origins.length) return false;
  // the target: OpenFang only (a redirect to another host is a request to that host: no key)
  if (!origins.includes(originOf(details.url))) return false;
  const headers = details.requestHeaders || {};
  const origin = header(headers, 'origin');
  if (origin && origin !== 'null' && !origins.includes(origin)) return false;
  const frame = details.frame;
  if (!frame) return false;
  const parent = frame.parent || null;

  if (details.resourceType === 'subFrame') {
    // The navigation of the OpenFang frame: a frame directly in the Agent Farm page, empty or already
    // OpenFang. A frame inside n8n or Rowboat (its parent is not the app page) gets nothing.
    if (!parent || parent.parent || !isAppPage(parent.url)) return false;
    const now = frame.url || '';
    return now === '' || now === 'about:blank' || origins.includes(originOf(now));
  }
  if (details.resourceType === 'mainFrame') return false;   // the Agent Farm view itself is never OpenFang

  // Anything else (fetch, xhr, script, websocket, image): from the OpenFang document, same origin.
  const site = header(headers, 'sec-fetch-site');
  if (site && site !== 'same-origin') return false;
  if (!parent || parent.parent || !isAppPage(parent.url)) return false;   // the tab's own frame, not nested
  return origins.includes(originOf(frame.url || ''));
}

/** The headers with the key added (an Authorization the page set itself is replaced). */
function withKey(requestHeaders, value) {
  const headers = { ...(requestHeaders || {}) };
  for (const name of Object.keys(headers)) if (name.toLowerCase() === 'authorization') delete headers[name];
  headers.Authorization = value;
  return headers;
}

/** A URL matches one of the session filter patterns ("http://host:port/*"). */
function matchesPatterns(url, patterns) {
  return patterns.some((pattern) => String(url).startsWith(pattern.replace(/\*$/, '')));
}

module.exports = { DEFAULT_URL, openfangBaseUrl, openfangOrigins, openfangAuth, fromOpenFangFrame, withKey, matchesPatterns };
