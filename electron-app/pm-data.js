/**
 * The project manager (pm-claw) in the entry "Auftraege", main-process side.
 *
 * Overview: two reading tools of the role `anzeige` at pm-mcp (digest, vorgaenge_lesen),
 *   PM_MCP_URL and PM_TOKEN_ANZEIGE. One POST per call, JSON-RPC tools/call; the answer is an
 *   event stream with one `data:` line whose result.content[0].text is JSON again.
 * Chat: one message of the person to the gateway of the bot (POST /v1/chat/completions) with the
 *   session key of the bot's own conversation; PM_CLAW_GATEWAY_URL, PM_CLAW_GATEWAY_TOKEN,
 *   PM_CLAW_SITZUNG. Exactly one `user` message with the typed text: no history, no system
 *   message, no tools. The app builds no commands and sends nothing by itself; a release of a
 *   mail stays with the words the agent asks for.
 *
 * Keys and addresses stay here: they never go to the page and never into the log. The page gets
 * sections and plain text; it shows the answers of the agent as text, never as HTML.
 */
const OVERVIEW_TIMEOUT_MS = 10000;
const CHAT_TIMEOUT_MS = 5 * 60 * 1000;
const CHAT_MAX_INPUT = 4000;
const CHAT_MAX_ANSWER = 20000;
const RECENT_MAILS = 8;

const NOT_REACHABLE = 'Projektmanager nicht erreichbar.';
const NOT_SET_UP = 'Projektmanager nicht eingerichtet.';
const CHAT_NOT_SET_UP = 'Chat nicht eingerichtet.';

function cleanUrl(value) {
  const text = typeof value === 'string' ? value.trim() : '';
  if (!text) return '';
  try {
    const url = new URL(text);
    return url.protocol === 'http:' || url.protocol === 'https:' ? url.href : '';
  } catch (_) {
    return '';
  }
}

function secret(value) {
  return typeof value === 'string' ? value.trim() : '';
}

/** What is set up; the values stay in the main process. */
function pmConfig(env = process.env) {
  const overview = { url: cleanUrl(env.PM_MCP_URL), token: secret(env.PM_TOKEN_ANZEIGE) };
  const gateway = cleanUrl(env.PM_CLAW_GATEWAY_URL);
  const chat = {
    url: gateway ? new URL('v1/chat/completions', gateway.endsWith('/') ? gateway : `${gateway}/`).href : '',
    token: secret(env.PM_CLAW_GATEWAY_TOKEN),
    session: secret(env.PM_CLAW_SITZUNG),
  };
  return {
    overview,
    overviewReady: Boolean(overview.url && overview.token),
    chat,
    chatReady: Boolean(chat.url && chat.token && chat.session),
  };
}

function text(value, max = 200) {
  return typeof value === 'string' ? value.trim().slice(0, max) : '';
}

function count(value) {
  return Number.isInteger(value) && value > 0 ? value : 0;
}

/** The JSON inside the answer of pm-mcp: an event stream (`data: {…}`) or plain JSON. */
function rpcPayload(body) {
  const raw = typeof body === 'string' ? body : '';
  const lines = raw.split(/\r?\n/).filter((line) => line.startsWith('data:')).map((line) => line.slice(5).trim());
  for (const candidate of lines.length ? lines : [raw.trim()]) {
    try { return JSON.parse(candidate); } catch (_) { /* next */ }
  }
  return null;
}

/** result.content[0].text parsed; null when the answer is not readable. */
function toolResult(payload) {
  const content = payload && payload.result && Array.isArray(payload.result.content) ? payload.result.content : [];
  const first = content[0];
  if (!first || typeof first.text !== 'string') return null;
  try {
    const value = JSON.parse(first.text);
    return value && typeof value === 'object' ? value : null;
  } catch (_) {
    return null;
  }
}

async function defaultPost(url, { headers, body, timeoutMs }) {
  const response = await fetch(url, { method: 'POST', headers, body, signal: AbortSignal.timeout(timeoutMs) });
  return { status: response.status, headers: { 'retry-after': response.headers.get('retry-after') }, text: await response.text() };
}

/**
 * One tool of the role `anzeige`. Resolves { ok, value } or { ok: false, kind } where kind is
 * 'nicht_erreichbar', 'schluessel' (401) or 'fehler' (with the short text of the service).
 */
async function callTool(config, name, args, post = defaultPost) {
  let answer;
  try {
    answer = await post(config.url, {
      headers: {
        Authorization: `Bearer ${config.token}`,
        'Content-Type': 'application/json',
        Accept: 'application/json, text/event-stream',
      },
      body: JSON.stringify({ jsonrpc: '2.0', id: 1, method: 'tools/call', params: { name, arguments: args || {} } }),
      timeoutMs: OVERVIEW_TIMEOUT_MS,
    });
  } catch (_) {
    return { ok: false, kind: 'nicht_erreichbar' };
  }
  if (answer.status === 401) return { ok: false, kind: 'schluessel' };
  if (answer.status !== 200) return { ok: false, kind: 'nicht_erreichbar' };
  const value = toolResult(rpcPayload(answer.text));
  if (!value) return { ok: false, kind: 'nicht_erreichbar' };   // not readable: never show the raw text
  if (typeof value.fehler === 'string') {
    return /datenbank nicht erreichbar/i.test(value.fehler)
      ? { ok: false, kind: 'nicht_erreichbar' }
      : { ok: false, kind: 'fehler', text: text(value.fehler) };
  }
  return { ok: true, value };
}

function projectItem(project) {
  const parts = [`Phase ${text(project.phase, 40) || 'unbekannt'}`];
  const open = count(project.p1_offen);
  const drafts = count(project.entwuerfe_offen);
  const warnings = count(project.warnungen_offen);
  if (open) parts.push(`${open} Pflichtfeld${open === 1 ? '' : 'er'} offen`);
  if (drafts) parts.push(`${drafts} Entwurf${drafts === 1 ? '' : 'e'} wartet${drafts === 1 ? '' : 'n'}`);
  if (warnings) parts.push(`${warnings} Warnung${warnings === 1 ? '' : 'en'}`);
  if (text(project.phase_vorschlag, 40)) parts.push(`Vorschlag: ${text(project.phase_vorschlag, 40)}`);
  return { title: text(project.slug, 80) || 'Projekt', detail: parts.join(' · ') };
}

function draftItem(draft) {
  const kind = [text(draft.art, 40), text(draft.kanal, 40)].filter(Boolean).join(', ');
  return { title: `${text(draft.id_kurz, 16)} · ${text(draft.slug, 80)}`, detail: kind ? `${kind} · zum Freigeben im Chat: schick ${text(draft.id_kurz, 16)}` : '', zeit: text(draft.seit, 40) };
}

function warningItem(warning) {
  const field = text(warning.feld_id, 60);
  return { title: `${text(warning.typ, 40) || 'Warnung'} · ${text(warning.slug, 80)}`, detail: field ? `Feld ${field}` : '', zeit: text(warning.seit, 40) };
}

function mailItem(mail) {
  const way = mail.richtung === 'ein' ? 'Eingang' : 'Ausgang';
  return { title: `${way} · ${text(mail.slug, 80) || 'ohne Projekt'}`, detail: text(mail.art, 40), zeit: text(mail.zeit, 40) };
}

function errorText(kind, fallback) {
  if (kind === 'schluessel') return 'Schlüssel passt nicht.';
  if (kind === 'fehler') return fallback || NOT_REACHABLE;
  return NOT_REACHABLE;
}

/** The section of the overview from the two answers (callTool results). */
function pmSection(digest, vorgaenge) {
  const base = { id: 'pm', title: 'Projektmanager', items: [], groups: [] };
  if (!digest.ok) return { ...base, state: digest.kind === 'nicht_erreichbar' ? 'aus' : 'fehler', text: errorText(digest.kind, digest.text) };
  const projects = Array.isArray(digest.value.projekte) ? digest.value.projekte.slice(0, 50) : [];
  const groups = [{ title: 'Projekte', items: projects.map(projectItem) }];
  if (vorgaenge.ok) {
    const v = vorgaenge.value;
    const drafts = Array.isArray(v.entwuerfe_wartend) ? v.entwuerfe_wartend.slice(0, 20) : [];
    const warnings = Array.isArray(v.warnungen) ? v.warnungen.slice(0, 20) : [];
    const mails = Array.isArray(v.mails) ? v.mails.slice(0, RECENT_MAILS) : [];
    if (drafts.length) groups.push({ title: 'Wartende Entwürfe', items: drafts.map(draftItem) });
    if (warnings.length) groups.push({ title: 'Warnungen', items: warnings.map(warningItem) });
    const unassigned = count(v.mails_unzugeordnet);
    if (mails.length || unassigned) {
      groups.push({ title: 'Letzte Vorgänge', items: mails.map(mailItem), text: unassigned ? `${unassigned} Mail${unassigned === 1 ? '' : 's'} ohne Projekt.` : '' });
    }
  }
  const summary = projects.length ? `${projects.length} aktive${projects.length === 1 ? 's Projekt' : ' Projekte'}.` : 'Keine aktiven Projekte.';
  const note = vorgaenge.ok ? '' : ` Vorgänge: ${errorText(vorgaenge.kind, vorgaenge.text)}`;
  return { ...base, state: projects.length ? 'ok' : 'leer', text: summary + note, groups };
}

/**
 * The overview reader. Keeps the last good section: when the service is not reachable the page
 * shows the last data with its time (`stand`) and the calm sentence.
 */
function createPmOverview({ env = process.env, post = defaultPost, now = () => new Date() } = {}) {
  let lastGood = null;
  return async function readPm() {
    const config = pmConfig(env);
    if (!config.overviewReady) return { id: 'pm', title: 'Projektmanager', state: 'aus', text: NOT_SET_UP, items: [], groups: [] };
    const [digest, vorgaenge] = await Promise.all([
      callTool(config.overview, 'digest', {}, post),
      callTool(config.overview, 'vorgaenge_lesen', { limit: 20 }, post),
    ]);
    const section = pmSection(digest, vorgaenge);
    if (digest.ok) {
      lastGood = { ...section, stand: now().toISOString() };
      return lastGood;
    }
    if (digest.kind === 'nicht_erreichbar' && lastGood) {
      return { ...lastGood, state: 'aus', text: `${NOT_REACHABLE} Letzter Stand bleibt stehen.` };
    }
    return section;
  };
}

/**
 * The chat. One message at a time; the answer comes in the same request.
 * send(text) resolves { ok: true, antwort } or { ok: false, text } (a sentence for the page).
 */
function createPmChat({ env = process.env, post = defaultPost, nowMs = () => Date.now(), log = () => {} } = {}) {
  let busy = false;
  let waitUntil = 0;

  function state() {
    const ready = pmConfig(env).chatReady;
    return { aktiv: ready, text: ready ? '' : CHAT_NOT_SET_UP };
  }

  async function send(input) {
    const config = pmConfig(env);
    if (!config.chatReady) return { ok: false, text: CHAT_NOT_SET_UP };
    const message = typeof input === 'string' ? input.trim() : '';
    if (!message) return { ok: false, text: 'Bitte zuerst etwas schreiben.' };
    if (message.length > CHAT_MAX_INPUT) return { ok: false, text: `Höchstens ${CHAT_MAX_INPUT} Zeichen.` };
    if (busy) return { ok: false, text: 'Die letzte Nachricht läuft noch.' };
    if (nowMs() < waitUntil) return { ok: false, text: `Zu viele Versuche. Bitte in ${Math.ceil((waitUntil - nowMs()) / 1000)} s wieder.` };
    busy = true;
    try {
      let answer;
      try {
        answer = await post(config.chat.url, {
          headers: {
            Authorization: `Bearer ${config.chat.token}`,
            'x-openclaw-session-key': config.chat.session,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ model: 'openclaw/default', messages: [{ role: 'user', content: message }] }),
          timeoutMs: CHAT_TIMEOUT_MS,
        });
      } catch (_) {
        return { ok: false, text: NOT_REACHABLE };
      }
      if (answer.status === 401) return { ok: false, text: 'Schlüssel passt nicht.' };
      if (answer.status === 404 || answer.status === 405) return { ok: false, text: 'Chat ist auf dem Server ausgeschaltet.' };
      if (answer.status === 429) {
        const seconds = parseInt(answer.headers && answer.headers['retry-after'], 10);
        waitUntil = nowMs() + (Number.isInteger(seconds) && seconds > 0 ? Math.min(seconds, 3600) : 60) * 1000;
        return { ok: false, text: `Zu viele Versuche. Bitte in ${Math.ceil((waitUntil - nowMs()) / 1000)} s wieder.` };
      }
      let body = null;
      try { body = JSON.parse(answer.text); } catch (_) { body = null; }
      if (answer.status === 400) {
        const reason = body && body.error && typeof body.error.message === 'string' ? body.error.message.slice(0, 200) : '';
        log(`[PM-Chat] Anfrage abgelehnt (400)${reason ? `: ${reason}` : ''}`);
        return { ok: false, text: 'Die Anfrage wurde abgelehnt.' };
      }
      if (answer.status !== 200) return { ok: false, text: NOT_REACHABLE };
      const content = body && Array.isArray(body.choices) && body.choices[0] && body.choices[0].message
        ? body.choices[0].message.content : undefined;
      if (typeof content !== 'string') return { ok: false, text: NOT_REACHABLE };   // not readable: no raw text
      return { ok: true, antwort: content.slice(0, CHAT_MAX_ANSWER) };
    } finally {
      busy = false;
    }
  }

  return { state, send };
}

module.exports = {
  pmConfig, rpcPayload, toolResult, callTool, pmSection, createPmOverview, createPmChat,
  NOT_REACHABLE, NOT_SET_UP, CHAT_NOT_SET_UP, CHAT_TIMEOUT_MS, OVERVIEW_TIMEOUT_MS,
};
