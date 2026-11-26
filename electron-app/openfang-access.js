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
 * Why this request may not carry the key, or null when it may. The reason is a short phrase for the log
 * (Lauf 38: the tab asked for a key and nothing said which check had refused it); it names no value.
 * `isAppPage(url)` says whether a document is the Agent Farm page itself (file:// or its dev address).
 * `frameTree()` (optional) lists the frames of the Agent Farm view; it stands in for `details.frame` when
 * Electron gives none (see frameWithoutDetails).
 */
function openFangRefusal(details, origins, isAppPage, { frameTree } = {}) {
  if (!details || !Array.isArray(origins) || !origins.length) return 'keine OpenFang-Adresse';
  // the target: OpenFang only (a redirect to another host is a request to that host: no key)
  if (!origins.includes(originOf(details.url))) return 'Ziel ist nicht OpenFang';
  const headers = details.requestHeaders || {};
  const origin = header(headers, 'origin');
  if (origin && origin !== 'null' && !origins.includes(origin)) return 'fremde Herkunft (Origin)';
  let frame = details.frame;
  if (!frame) {
    const found = frameWithoutDetails(details, origins, typeof frameTree === 'function' ? frameTree : null);
    if (typeof found === 'string') return found;
    frame = found;
  }
  const parent = frame.parent || null;

  if (details.resourceType === 'subFrame') {
    // The navigation of the OpenFang frame: a frame directly in the Agent Farm page, empty or already
    // OpenFang. A frame inside n8n or Rowboat (its parent is not the app page) gets nothing.
    if (!parent) return 'Rahmen ohne Elternseite';
    if (parent.parent) return 'verschachtelter Rahmen';
    if (!isAppPage(parent.url)) return 'Elternseite ist nicht die Agent Farm';
    const now = frame.url || '';
    return now === '' || now === 'about:blank' || origins.includes(originOf(now)) ? null : 'Rahmen zeigt eine fremde Seite';
  }
  if (details.resourceType === 'mainFrame') return 'Hauptrahmen';   // the Agent Farm view itself is never OpenFang

  // Anything else (fetch, xhr, script, websocket, image): from the OpenFang document, same origin.
  const site = header(headers, 'sec-fetch-site');
  if (site && site !== 'same-origin') return `Sec-Fetch-Site ${site.slice(0, 20)}`;
  if (!parent) return 'Rahmen ohne Elternseite';
  if (parent.parent) return 'verschachtelter Rahmen';   // the tab's own frame, not nested
  if (!isAppPage(parent.url)) return 'Elternseite ist nicht die Agent Farm';
  return origins.includes(originOf(frame.url || '')) ? null : 'Rahmen zeigt nicht OpenFang';
}

/**
 * The frame of a request that Electron reported without one (Lauf 39: every request of the OpenFang tab came
 * with `details.frame` empty, "kein Rahmen bekannt", so the key never went). Only a request of an OpenFang
 * document qualifies, and only when the view holds exactly one OpenFang frame:
 *   - not a navigation (subFrame/mainFrame always come with their frame),
 *   - started by a document of the OpenFang origin: `Sec-Fetch-Site: same-origin` or an OpenFang Referer
 *     (the browser sets both; a page cannot), and no foreign Referer,
 *   - in the frame tree of the Agent Farm view exactly one frame shows OpenFang. Two (say one nested in n8n)
 *     leave it open which one asked: no key.
 * Returns that frame, or the reason why none.
 */
function frameWithoutDetails(details, origins, frameTree) {
  if (!frameTree) return 'kein Rahmen bekannt';
  if (details.resourceType === 'subFrame' || details.resourceType === 'mainFrame') return 'kein Rahmen bekannt';
  const headers = details.requestHeaders || {};
  const site = header(headers, 'sec-fetch-site');
  const referer = header(headers, 'referer');
  if (referer && !origins.includes(originOf(referer))) return 'kein Rahmen bekannt, fremder Referer';
  // Both are set by the browser, never by the page. Whether the main process sees Sec-Fetch-Site is not sure,
  // so an OpenFang Referer counts as well; with neither, it stays open who asked.
  if (site && site !== 'same-origin') return 'kein Rahmen bekannt, Anfrage nicht aus OpenFang';
  if (!site && !referer) return 'kein Rahmen bekannt, weder Sec-Fetch-Site noch Referer';
  let frames;
  try {
    frames = frameTree();
  } catch (_) {
    frames = null;
  }
  if (!Array.isArray(frames)) return 'kein Rahmen bekannt, Rahmenbaum nicht lesbar';
  const shown = frames.filter((f) => {
    try { return f && origins.includes(originOf(f.url || '')); } catch (_) { return false; }
  });
  if (shown.length === 0) return 'kein Rahmen bekannt, kein OpenFang-Rahmen in der Ansicht';
  if (shown.length > 1) return 'kein Rahmen bekannt, mehrere OpenFang-Rahmen';
  return shown[0];
}

/** Whether this request may carry the key (see openFangRefusal). */
function fromOpenFangFrame(details, origins, isAppPage) {
  return openFangRefusal(details, origins, isAppPage) === null;
}

/**
 * Whether two file:// addresses name the same file. Electron reports a loaded file with the drive letter
 * upper-cased and its own percent-encoding; pathToFileURL keeps the case the app was started with. On
 * Windows paths are case-insensitive, so the comparison is too.
 */
function sameFileUrl(a, b, { caseInsensitive = process.platform === 'win32' } = {}) {
  const norm = (url) => {
    let text = String(url || '').split('#')[0].split('?')[0];
    try { text = decodeURIComponent(text); } catch (_) { /* keep as is */ }
    text = text.replace(/\\/g, '/');
    return caseInsensitive ? text.toLowerCase() : text;
  };
  return Boolean(a) && Boolean(b) && norm(a) === norm(b);
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

module.exports = {
  DEFAULT_URL, openfangBaseUrl, openfangOrigins, openfangAuth, openFangRefusal, fromOpenFangFrame, sameFileUrl, withKey, matchesPatterns,
};
