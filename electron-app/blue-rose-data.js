/**
 * Blue Rose as the personal space, step 1: what the page "Dein Bereich" shows.
 *
 * The main process asks the brain on this machine (/api/blue_rose/*, vibemind-os
 * brain/the_brain/web/routers/blue_rose.py) and turns the answer into ready German lines. The page
 * only draws them. The brain answers these addresses to the main process alone, never to a page.
 *
 * What travels here: counts, one of five mood words, a number 1-10. Never a sentence of the person.
 * Nothing is logged but the kind of a failure.
 */
const crypto = require('node:crypto');
const { brainBase } = require('./orders-data');

const MOODS = Object.freeze({
  energized: 'voller Energie', focused: 'fokussiert', calm: 'ruhig', tired: 'müde', anxious: 'unruhig',
});
const WINDOWS = Object.freeze([
  { id: 'early_morning', from: 5, to: 8, name: 'früh morgens' },
  { id: 'morning', from: 8, to: 12, name: 'vormittags' },
  { id: 'midday', from: 12, to: 14, name: 'mittags' },
  { id: 'afternoon', from: 14, to: 17, name: 'nachmittags' },
  { id: 'evening', from: 17, to: 21, name: 'abends' },
  { id: 'night', from: 21, to: 5, name: 'nachts' },
]);
const SPACES = Object.freeze({
  ideas: 'Ideen', projects: 'Projekte', desktop: 'Desktop', roarboot: 'Rowboat', sales: 'Sales',
  marketing: 'Marketing', learning: 'Lernen', video: 'Video', flowzen: 'Blue Rose', mirofish: 'MiroFish',
  thebrain: 'The Brain', agentfarm: 'Agent Farm', swedesign: 'SWE Design', clawport: 'Dashboard',
  orders: 'Aufträge', events: 'Events', coding: 'Coding', ohne: 'ohne Bereich',
});
const KINDS = Object.freeze([
  { id: 'befinden', name: 'Antworten zum Befinden' },
  { id: 'alt_befinden', name: 'Alte Stimmungs-Einträge (Flowzen, April)' },
  { id: 'alt_aktivitaet', name: 'Alte Befehls-Zählung (Flowzen, April)' },
  { id: 'alt_tagebuch', name: 'Altes Tagebuch (Flowzen)' },
]);
const REASONS = Object.freeze({
  kein_schluessel: 'Dem Gehirn fehlt der Zugang zur eigenen Datenbank für Blue Rose.',
  tabelle_fehlt: 'Die Tabellen für Blue Rose sind noch nicht angelegt.',
  kein_zugriff: 'Die Datenbank lehnt den Zugriff ab.',
  nicht_erreichbar: 'Die Datenbank ist gerade nicht erreichbar.',
  nicht_bestaetigt: 'Das Speichern ließ sich nicht bestätigen.',
  nicht_geloescht: 'Das Löschen hat nicht geklappt.',
  eingabe_ungueltig: 'Diese Eingabe nimmt Blue Rose nicht an.',
  nur_lokal: 'Das Gehirn hat die Anfrage abgewiesen.',
  nicht_belegt: 'Das Gehirn erkennt die App nicht (Schlüssel fehlt oder passt nicht).',
  graph_fehlt: 'Der Entscheidungs-Graph ist nicht geladen.',
  graph_fehler: 'Der Entscheidungs-Graph ließ sich nicht lesen.',
});

const count = (n, one, many) => `${n} ${n === 1 ? one : many}`;
const spaceName = (id) => SPACES[id] || String(id || '').slice(0, 24) || SPACES.ohne;
const reason = (grund) => REASONS[grund] || 'Das hat nicht geklappt.';
const isHour = (h) => Number.isInteger(h) && h >= 0 && h <= 23;
const inWindow = (w, hour) => (w.from < w.to ? hour >= w.from && hour < w.to : hour >= w.from || hour < w.to);

/** Counts per time of day, from counts per UTC hour and the offset of the place in hours. */
function windowCounts(hoursUtc, offsetHours) {
  const shift = Number.isFinite(offsetHours) ? Math.round(offsetHours) : 0;
  const out = WINDOWS.map((w) => ({ ...w, saetze: 0 }));
  (Array.isArray(hoursUtc) ? hoursUtc : []).slice(0, 24).forEach((n, utc) => {
    if (!Number.isInteger(n) || n <= 0) return;
    const local = (((utc + shift) % 24) + 24) % 24;
    out.find((w) => inWindow(w, local)).saetze += n;
  });
  return out;
}

function workCards(z, offsetHours) {
  if (!z || z.ok !== true) return [];
  if (!z.saetze) return [];
  const basis = `Grundlage: ${count(z.saetze, 'Satz', 'Sätze')} an ${count(z.aktive_tage, 'Tag', 'Tagen')} · gezählt`;
  const cards = [];
  const windows = windowCounts(z.stunden_utc, offsetHours).filter((w) => w.saetze / z.saetze >= 0.2)
    .sort((a, b) => b.saetze - a.saetze).slice(0, 2);
  if (windows.length) {
    const parts = windows.map((w) => `${w.name} (${w.from}–${w.to} Uhr)`);
    cards.push({ text: `Du arbeitest meist ${parts.join(' und ')}.`, basis });
  }
  const top = (z.bereiche || []).filter((b) => b.id !== 'ohne').slice(0, 2);
  if (top.length) {
    const parts = top.map((b) => `${spaceName(b.id)} (${Math.round((100 * b.saetze) / z.saetze)} %)`);
    cards.push({ text: `Am häufigsten: ${parts.join(', ')}.`, basis });
  }
  if (z.gesprochen > 0) {
    cards.push({ text: `${count(z.gesprochen, 'Satz', 'Sätze')} gesprochen, ${z.getippt} getippt.`, basis });
  }
  if (Number.isFinite(z.dauer_ms_median)) {
    const s = z.dauer_ms_median / 1000;
    cards.push({ text: `Eine Antwort braucht meist ${s < 10 ? s.toFixed(1).replace('.', ',') : Math.round(s)} Sekunden.`, basis });
  }
  return cards;
}

function frictionCards(z) {
  if (!z || z.ok !== true) return [];
  const basis = `letzte ${z.tage} Tage · gezählt`;
  const cards = [];
  for (const b of z.bereiche || []) {
    if (b.nicht_verstanden > 0) {
      cards.push({ text: `${spaceName(b.id)}: ${b.nicht_verstanden} von ${count(b.saetze, 'Satz', 'Sätzen')} nicht verstanden.`, basis, weight: b.nicht_verstanden });
    }
    if (b.misslungen > 0) {
      cards.push({ text: `${spaceName(b.id)}: ${b.misslungen} von ${count(b.saetze, 'Satz', 'Sätzen')} nicht gelungen.`, basis, weight: b.misslungen });
    }
  }
  return cards.sort((a, b) => b.weight - a.weight).slice(0, 6).map(({ text, basis: g }) => ({ text, basis: g }));
}

function moodPart(befinden, now) {
  const rows = befinden && Array.isArray(befinden.eintraege) ? befinden.eintraege : [];
  const entries = rows.slice(0, 30).map((row) => {
    const at = new Date(row.angelegt);
    const when = Number.isNaN(at.getTime()) ? ''
      : at.toLocaleString('de-DE', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
    return { id: String(row.id), at: at.getTime(), energie: row.energie, text: `${when}: ${MOODS[row.stimmung] || row.stimmung} · Energie ${row.energie}/10` };
  });
  const days = [];
  for (let back = 6; back >= 0; back -= 1) {
    const day = new Date(now); day.setHours(0, 0, 0, 0); day.setDate(day.getDate() - back);
    const end = day.getTime() + 86400000;
    const ofDay = entries.filter((e) => e.at >= day.getTime() && e.at < end).map((e) => e.energie);
    days.push({
      tag: day.toLocaleDateString('de-DE', { weekday: 'short' }).replace('.', ''),
      energie: ofDay.length ? Math.round(ofDay.reduce((a, b) => a + b, 0) / ofDay.length) : null,
    });
  }
  return {
    state: befinden && befinden.ok === true ? 'ok' : 'fehler',
    hinweis: befinden && befinden.ok === true ? '' : reason(befinden && befinden.grund),
    letzter: entries.length ? entries[0].text : 'Noch kein Eintrag.',
    tage: days,
    eintraege: entries.map(({ id, text }) => ({ id, text })),
  };
}

function storedPart(bestand) {
  return KINDS.map((kind) => {
    const n = bestand ? bestand[kind.id] : null;
    return {
      id: kind.id,
      name: kind.name,
      text: Number.isInteger(n) ? (n >= 1000 ? '1000 oder mehr Einträge' : count(n, 'Eintrag', 'Einträge')) : 'nicht lesbar',
      loeschbar: Number.isInteger(n) && n > 0,
    };
  }).filter((line) => line.id === 'befinden' || line.loeschbar || line.text === 'nicht lesbar');
}

/** The whole page as ready lines. `answer` is what the brain said, or null when it did not answer. */
function viewModel(answer, { offsetHours = 0, now = Date.now() } = {}) {
  if (!answer || typeof answer !== 'object') {
    return { state: 'aus', hinweis: 'Das Gehirn antwortet gerade nicht. Blue Rose zeigt deshalb nichts an.' };
  }
  if (answer.ok !== true) return { state: 'fehler', hinweis: reason(answer.grund) };
  const settings = answer.einstellungen || {};
  const z = answer.zahlen || {};
  const analyse = settings.analyse === true;
  let zahlenHinweis = '';
  if (!analyse) {
    zahlenHinweis = settings.ok === false
      ? `${reason(settings.grund)} Solange liest Blue Rose den Entscheidungs-Graphen nicht.`
      : 'Analyse ist aus. Blue Rose liest den Entscheidungs-Graphen nicht.';
  } else if (z.ok !== true) {
    zahlenHinweis = reason(z.grund);
  } else if (!z.saetze) {
    zahlenHinweis = `In den letzten ${z.tage} Tagen steht kein Satz von dir im Entscheidungs-Graphen.`;
  }
  const e = answer.empfehlung || {};
  return {
    state: 'ok',
    analyse,
    analyseSchaltbar: settings.ok === true,
    befinden: moodPart(answer.befinden, now),
    empfehlung: e.ok === true ? `Jetzt passt: ${e.name}.` : 'Trag dein Befinden ein, dann sagt Blue Rose, was jetzt passt.',
    arbeitsweise: workCards(z, offsetHours),
    hakt: frictionCards(z),
    zahlenHinweis,
    haktLeer: analyse && z.ok === true && z.saetze > 0 ? 'Nichts Auffälliges gezählt.' : '',
    bestand: storedPart(answer.bestand),
    stimmungen: Object.entries(MOODS).map(([id, name]) => ({ id, name })),
  };
}

async function defaultFetchJson(url, options = {}) {
  const response = await fetch(url, { ...options, signal: AbortSignal.timeout(20000) });
  if (!response.ok && response.status !== 403) throw new Error(`HTTP ${response.status}`);
  return response.json();
}

const KEY_NAME = 'VIBEMIND_EINGABE_SCHLUESSEL';
const KEY_MIN_LENGTH = 32;

/**
 * The sign of the app for one request (as desktop-klicks.js for a hand click): the brain takes
 * nothing for Blue Rose without it, since a Host header can be made up by anyone who reaches the port.
 * "<sec>.<hmac-sha256>" over "<sec>\nblue-rose <METHOD> <path?query> <sha256 of the body> <once>".
 */
function signHeaders(key, method, pathAndQuery, body, { sec = Date.now() / 1000, once = crypto.randomBytes(12).toString('hex') } = {}) {
  const t = Math.floor(sec);
  const sum = crypto.createHash('sha256').update(body || '', 'utf8').digest('hex');
  const mac = crypto.createHmac('sha256', key).update(`${t}\nblue-rose ${method} ${pathAndQuery} ${sum} ${once}`, 'utf8').digest('hex');
  return { 'X-Blue-Rose-Einmal': once, 'X-Vibemind-Eingabe': `${t}.${mac}` };
}

/** Reads and writes of the page. Never throws; a failure becomes a calm line. */
function createBlueRose({ base = brainBase(), fetchJson = defaultFetchJson, log = () => {}, env = process.env } = {}) {
  const key = String(env[KEY_NAME] || '').trim();
  const signed = (method, pathAndQuery, data) => {
    const body = data === undefined ? undefined : JSON.stringify(data);
    const headers = { ...signHeaders(key, method, pathAndQuery, body), ...(body === undefined ? {} : { 'Content-Type': 'application/json' }) };
    return fetchJson(`${base}${pathAndQuery}`, body === undefined ? { headers } : { method, headers, body });
  };
  const post = (pathAndQuery, data) => signed('POST', pathAndQuery, data);
  if (key.length < KEY_MIN_LENGTH) {
    const text = 'Der App fehlt der Schlüssel, mit dem sie sich beim Gehirn ausweist.';
    const no = async () => ({ ok: false, text });
    return { read: async () => ({ state: 'fehler', hinweis: text }), recommend: no, saveMood: no, setAnalysis: no, remove: no };
  }
  const quiet = async (work, what) => {
    try { return await work(); } catch (error) {
      log(`[BlueRose] ${what}: ${error && error.name ? error.name : 'Fehler'}`);
      return null;
    }
  };
  // A refusal of the brain is logged by its code (a fixed word such as "nicht_belegt"), never by content.
  const result = (answer, what) => {
    if (answer && answer.ok === true) return { ok: true };
    if (answer && what) log(`[BlueRose] ${what}: abgelehnt (${/^[a-z_]{1,40}$/.test(answer.grund) ? answer.grund : 'ohne Grund'})`);
    return { ok: false, text: answer ? reason(answer.grund) : 'Das Gehirn antwortet gerade nicht.' };
  };
  return {
    async read({ stunde, offsetHours } = {}) {
      const hour = isHour(stunde) ? `&stunde=${stunde}` : '';
      const answer = await quiet(() => signed('GET', `/api/blue_rose/uebersicht?tage=14${hour}`), 'lesen');
      return viewModel(answer, { offsetHours });
    },
    /**
     * "Was soll ich als Nächstes tun?": one sentence from the fixed table of the brain (mood of the
     * last hours x time of day), no model. Without a fresh entry it says what to do first; a
     * failure says why. Only the sentence leaves here, never the entries.
     */
    async recommend({ stunde } = {}) {
      const vm = await this.read({ stunde });
      return vm.state === 'ok' ? { ok: true, text: vm.empfehlung } : { ok: false, text: vm.hinweis };
    },
    async saveMood({ stimmung, energie, stunde } = {}) {
      if (!Object.hasOwn(MOODS, stimmung) || !Number.isInteger(energie) || energie < 1 || energie > 10 || !isHour(stunde)) {
        return { ok: false, text: reason('eingabe_ungueltig') };
      }
      return result(await quiet(() => post('/api/blue_rose/befinden', { stimmung, energie, stunde }), 'eintragen'), 'eintragen');
    },
    async setAnalysis(on) {
      if (typeof on !== 'boolean') return { ok: false, text: reason('eingabe_ungueltig') };
      return result(await quiet(() => post('/api/blue_rose/einstellungen', { analyse: on }), 'schalter'), 'schalter');
    },
    /** One kind, everything ('alles'), or one mood entry by its id. No id may arrive as undefined or null. */
    async remove(art, id) {
      const one = id !== undefined && id !== null;
      const known = art === 'alles' || KINDS.some((kind) => kind.id === art);
      if (!known || (one && (art !== 'befinden' || typeof id !== 'string' || !/^[0-9a-zA-Z-]{1,64}$/.test(id)))) {
        log('[BlueRose] loeschen: Eingabe nicht angenommen');
        return { ok: false, text: reason('eingabe_ungueltig') };
      }
      return result(await quiet(() => post('/api/blue_rose/loeschen', one ? { art, id } : { art }), 'loeschen'), 'loeschen');
    },
  };
}

module.exports = { createBlueRose, viewModel, windowCounts, signHeaders, MOODS, KINDS };
