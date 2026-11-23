/**
 * Gemeinsame Pruefung vor jedem Overlay-loadURL/loadFile (Spec 2026-10-15 Abschnitt 3).
 * Datei vorhanden bzw. URL erreichbar (Timeout 2 s, optional erwarteter <title>);
 * sonst Statuskarte "<Space> nicht verfuegbar – <Grund>" mit dem geprueften Ziel.
 */
const fs = require('node:fs');

const DEFAULT_TIMEOUT_MS = 2000;
const CARD_PREFIX = 'data:text/html;charset=utf-8,';

function resolveElectronParts(dependencies, names) {
  const missing = names.filter((name) => !dependencies[name]);
  const electron = missing.length > 0 ? require('electron') : {};
  return Object.fromEntries(names.map((name) => [name, dependencies[name] || electron[name]]));
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[c]));
}

/**
 * What the card says, in German, without error codes: what is missing and what the person can do.
 * `reason` is the technical reason of the first target checked (several are joined by "; ");
 * `hint`, given by the space, says how its service is started. The technical reason stays in
 * the log and, folded, on the card.
 */
function cardText({ space, reason, hint }) {
  const first = String(reason || '').split('; ')[0];
  const name = String(space || 'Dieser Bereich');
  const own = typeof hint === 'string' && hint.trim() ? hint.trim() : '';
  if (/abgeschaltet|entfernt|deaktiviert/i.test(first)) {
    return { headline: `${name} ist auf Wunsch abgeschaltet.`, todo: own };
  }
  if (/^Datei fehlt/.test(first)) {
    return { headline: `Die Seite von ${name} ist auf diesem Rechner nicht gebaut.`, todo: own || 'Die Seite muss einmal gebaut werden; danach den Reiter erneut öffnen.' };
  }
  if (/^nicht erreichbar|^keine Antwort/.test(first)) {
    return { headline: `Der Dienst von ${name} läuft nicht.`, todo: own || 'Den Dienst starten und den Reiter danach erneut öffnen.' };
  }
  if (/^HTTP /.test(first)) {
    return { headline: `Der Dienst von ${name} läuft, meldet aber einen Fehler.`, todo: 'In ein paar Sekunden den Reiter erneut öffnen. Bleibt es so, das Protokoll des Dienstes ansehen.' };
  }
  if (/^fremde App/.test(first)) {
    return { headline: `Unter der Adresse von ${name} antwortet eine andere Anwendung.`, todo: own || 'Die eingetragene Adresse prüfen.' };
  }
  if (/^ungueltige URL|^kein Ziel/.test(first)) {
    return { headline: `Für ${name} ist keine gültige Adresse eingetragen.`, todo: own || 'Die Adresse in der .env eintragen und die App neu starten.' };
  }
  return { headline: `${name} ist gerade nicht verfügbar.`, todo: own || 'Den Reiter später erneut öffnen.' };
}

function statusCardHtml({ space, reason, target, hint }) {
  const text = cardText({ space, reason, hint });
  return '<!doctype html><html lang="de"><head><meta charset="utf-8">'
    + `<title>${escapeHtml(space)} nicht verfügbar</title>`
    + '<style>html,body{margin:0;height:100%;background:#050510;color:#e6e6f0;font-family:system-ui,sans-serif}'
    + 'main{display:flex;flex-direction:column;align-items:center;justify-content:center;height:100%;gap:14px;padding:24px;box-sizing:border-box;text-align:center}'
    + 'h1{font-size:20px;margin:0;font-weight:600}p{margin:0;color:#c4c8dc;max-width:560px;line-height:1.5}'
    + 'details{color:#80849c;font-size:12px;max-width:560px}summary{cursor:pointer}code{color:#7fd4ff;word-break:break-all}</style></head>'
    + `<body><main><h1 data-status-card="1">${escapeHtml(text.headline)}</h1>`
    + (text.todo ? `<p data-status-todo="1">${escapeHtml(text.todo)}</p>` : '')
    // folded: the technical line as it goes to the log, for whoever looks for the cause
    + `<details><summary>Technische Angaben</summary><p data-status-detail="1">${escapeHtml(space)} nicht verfuegbar – ${escapeHtml(reason || '–')}<br>`
    + `Geprueftes Ziel: <code>${escapeHtml(target || '–')}</code></p></details>`
    + '</main></body></html>';
}

function statusCardUrl(card) {
  return `${CARD_PREFIX}${encodeURIComponent(statusCardHtml(card))}`;
}

function extractTitle(html) {
  const match = /<title[^>]*>([^<]*)<\/title>/i.exec(String(html));
  return match ? match[1].trim() : '';
}

async function cancelBody(response) {
  try { await response.body?.cancel(); } catch { /* egal */ }
}

async function checkOverlayTarget(target, deps = {}) {
  const existsSync = deps.existsSync || fs.existsSync;
  const fetchImpl = deps.fetchImpl || globalThis.fetch;
  if (!target || target.kind === 'unavailable') {
    return { ok: false, reason: (target && target.reason) || 'kein Ziel konfiguriert', target: (target && target.target) || '' };
  }
  if (target.kind === 'file') {
    return existsSync(target.path)
      ? { ok: true, target: target.path }
      : { ok: false, reason: 'Datei fehlt', target: target.path };
  }
  if (target.kind !== 'url') throw new TypeError(`Unbekannte Zielart: ${target.kind}`);

  let parsed;
  try {
    parsed = new URL(target.url);
  } catch {
    return { ok: false, reason: 'ungueltige URL', target: String(target.url) };
  }
  if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
    return { ok: false, reason: 'ungueltige URL', target: target.url };
  }

  const timeoutMs = target.timeoutMs || DEFAULT_TIMEOUT_MS;
  let response;
  try {
    // target.headers: what the page itself will send (an access cookie), so the check sees what the page will see
    const options = { signal: AbortSignal.timeout(timeoutMs), redirect: 'follow' };
    if (target.headers) options.headers = target.headers;
    response = await fetchImpl(target.url, options);
  } catch (err) {
    if (err && (err.name === 'TimeoutError' || err.name === 'AbortError')) {
      return { ok: false, reason: `keine Antwort in ${timeoutMs} ms`, target: target.url };
    }
    const code = (err && err.cause && err.cause.code) || (err && err.message) || String(err);
    return { ok: false, reason: `nicht erreichbar (${code})`, target: target.url };
  }
  if (!response.ok) {
    await cancelBody(response);
    return { ok: false, reason: `HTTP ${response.status}`, target: target.url };
  }
  if (target.expectTitle) {
    let body;
    try {
      body = await response.text();
    } catch (err) {
      return { ok: false, reason: `Antwort unvollstaendig (${err && err.name === 'TimeoutError' ? `keine Antwort in ${timeoutMs} ms` : err.message})`, target: target.url };
    }
    const title = extractTitle(body);
    if (!target.expectTitle.test(title)) {
      return { ok: false, reason: `fremde App (Titel „${title || 'ohne Titel'}“)`, target: target.url };
    }
  } else {
    await cancelBody(response);
  }
  return { ok: true, target: target.url };
}

async function loadOverlay(webContents, { space, targets, hint }, deps = {}) {
  const logger = deps.logger || console;
  const failures = [];
  let chosen = null;
  for (const target of targets) {
    const result = await checkOverlayTarget(target, deps);
    if (result.ok) {
      chosen = { target, result };
      break;
    }
    failures.push(result);
  }
  if (webContents.isDestroyed && webContents.isDestroyed()) {
    return chosen ? chosen.result : { ok: false, reason: 'Ansicht geschlossen', target: '' };
  }
  if (deps.onResult) {
    deps.onResult(chosen ? chosen.result : {
      ok: false,
      reason: failures.map((x) => x.reason).join('; '),
      target: failures.map((x) => x.target).filter(Boolean).join(' | '),
    });
  }
  try {
    if (chosen) {
      if (chosen.target.kind === 'file') await webContents.loadFile(chosen.target.path);
      else await webContents.loadURL(chosen.target.url);
      return chosen.result;
    }
    const reason = failures.map((f) => f.reason).join('; ');
    const target = failures.map((f) => f.target).filter(Boolean).join(' | ');
    logger.warn(`[Overlay] ${space} nicht verfuegbar – ${reason} (${target})`);
    await webContents.loadURL(statusCardUrl({ space, reason, target, hint }));
    return { ok: false, reason, target };
  } catch (err) {
    logger.warn(`[Overlay] ${space}: Laden fehlgeschlagen – ${err.message}`);
    return chosen ? chosen.result : { ok: false, reason: err.message, target: '' };
  }
}

/** Statusfeld fuer die *_view_status-Meldung: Karte ist nicht "ready". */
function loadStatus(result) {
  return result && !result.ok
    ? { status: 'unavailable', message: result.reason }
    : { status: 'ready' };
}

module.exports = {
  CARD_PREFIX,
  DEFAULT_TIMEOUT_MS,
  cardText,
  checkOverlayTarget,
  extractTitle,
  loadOverlay,
  loadStatus,
  resolveElectronParts,
  statusCardHtml,
  statusCardUrl,
};
