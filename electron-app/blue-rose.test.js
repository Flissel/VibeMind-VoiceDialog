// Blue Rose as the personal space, step 1. Invented data only.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const { createBlueRose, viewModel, windowCounts, signHeaders } = require('./blue-rose-data');

const KEY = 'erfundener-testschluessel-0123456789abcdef';   // no real value
// Computed with the brain's own code for KEY, POST /api/blue_rose/loeschen, body {"art":"alles"}:
const VECTOR = '1800000000.2b32ba91da3595ef1577f32e2b910ae608b5deba33f62d4f75e330fed75802ed';

const NOW = new Date(2026, 0, 15, 10, 0, 0).getTime();
const iso = (daysBack, hour) => new Date(2026, 0, 15 - daysBack, hour, 0, 0).toISOString();

function answer(more = {}) {
  const hours = new Array(24).fill(0);
  hours[8] = 30; hours[19] = 15; hours[2] = 5;       // UTC
  return {
    ok: true,
    einstellungen: { ok: true, analyse: true },
    befinden: { ok: true, eintraege: [
      { id: 'id-2', stimmung: 'focused', energie: 7, angelegt: iso(0, 9) },
      { id: 'id-1', stimmung: 'tired', energie: 3, angelegt: iso(2, 20) },
    ] },
    bestand: { befinden: 2, alt_befinden: 1, alt_aktivitaet: 70, alt_tagebuch: 0 },
    zahlen: { ok: true, tage: 14, saetze: 50, aktive_tage: 6, nicht_verstanden: 6, misslungen: 3, gesprochen: 4, getippt: 46,
      stunden_utc: hours, dauer_ms_median: 1400,
      bereiche: [
        { id: 'ideas', saetze: 30, nicht_verstanden: 0, misslungen: 0, dauer_ms_median: 900 },
        { id: 'sales', saetze: 19, nicht_verstanden: 6, misslungen: 3, dauer_ms_median: 2000 },
        { id: 'ohne', saetze: 1, nicht_verstanden: 0, misslungen: 0, dauer_ms_median: null },
      ] },
    empfehlung: { ok: true, kategorie: 'deep_work', name: 'Konzentrierte Arbeit', tageszeit: 'morning' },
    ...more,
  };
}

test('counts per UTC hour become times of day at the place', () => {
  const hours = new Array(24).fill(0); hours[8] = 4; hours[23] = 2;
  const at = (id, offset) => windowCounts(hours, offset).find((w) => w.id === id).saetze;
  assert.equal(at('morning', 1), 4);      // 08 UTC = 09 local
  assert.equal(at('night', 1), 2);        // 23 UTC = 00 local
  assert.equal(at('morning', 0), 4);
  assert.equal(at('afternoon', 8), 4);    // 16 local
  assert.equal(windowCounts(null, 1).reduce((sum, w) => sum + w.saetze, 0), 0);
});

test('the page says in plain lines what was counted, with its basis', () => {
  const vm = viewModel(answer(), { offsetHours: 1, now: NOW });
  assert.equal(vm.state, 'ok');
  assert.equal(vm.analyse, true);
  assert.equal(vm.arbeitsweise[0].text, 'Du arbeitest meist vormittags (8–12 Uhr) und abends (17–21 Uhr).');
  assert.equal(vm.arbeitsweise[0].basis, 'Grundlage: 50 Sätze an 6 Tagen · gezählt');
  assert.equal(vm.arbeitsweise[1].text, 'Am häufigsten: Ideen (60 %), Sales (38 %).');
  assert.equal(vm.arbeitsweise[2].text, '4 Sätze gesprochen, 46 getippt.');
  assert.equal(vm.arbeitsweise[3].text, 'Eine Antwort braucht meist 1,4 Sekunden.');
  assert.deepEqual(vm.hakt.map((card) => card.text), [
    'Sales: 6 von 19 Sätzen nicht verstanden.', 'Sales: 3 von 19 Sätzen nicht gelungen.']);
  assert.equal(vm.empfehlung, 'Jetzt passt: Konzentrierte Arbeit.');
});

test('mood: the last entry, seven days of energy, each entry with its id', () => {
  const vm = viewModel(answer(), { offsetHours: 1, now: NOW });
  assert.match(vm.befinden.letzter, /fokussiert · Energie 7\/10$/);
  assert.equal(vm.befinden.tage.length, 7);
  assert.equal(vm.befinden.tage[6].energie, 7);
  assert.equal(vm.befinden.tage[4].energie, 3);
  assert.equal(vm.befinden.tage[5].energie, null);
  assert.deepEqual(vm.befinden.eintraege.map((e) => e.id), ['id-2', 'id-1']);
  assert.equal(vm.stimmungen.length, 5);
});

test('what is stored: counts per kind; empty old kinds are left out', () => {
  const vm = viewModel(answer(), { now: NOW });
  assert.deepEqual(vm.bestand.map((line) => [line.id, line.text, line.loeschbar]), [
    ['befinden', '2 Einträge', true], ['alt_befinden', '1 Eintrag', true], ['alt_aktivitaet', '70 Einträge', true]]);
});

test('analysis off, missing tables, a silent brain: the page says so and shows no numbers', () => {
  const off = viewModel(answer({ einstellungen: { ok: true, analyse: false }, zahlen: { ok: false, grund: 'analyse_aus' } }), { now: NOW });
  assert.equal(off.analyse, false);
  assert.deepEqual(off.arbeitsweise, []);
  assert.equal(off.zahlenHinweis, 'Analyse ist aus. Blue Rose liest den Entscheidungs-Graphen nicht.');

  const missing = viewModel(answer({
    einstellungen: { ok: false, grund: 'tabelle_fehlt', analyse: false },
    befinden: { ok: false, grund: 'tabelle_fehlt', eintraege: [] },
    zahlen: { ok: false, grund: 'analyse_aus' },
  }), { now: NOW });
  assert.equal(missing.analyseSchaltbar, false);
  assert.match(missing.zahlenHinweis, /noch nicht angelegt/);
  assert.match(missing.befinden.hinweis, /noch nicht angelegt/);

  assert.equal(viewModel(null).state, 'aus');
  assert.equal(viewModel({ ok: false, grund: 'kein_schluessel' }).state, 'fehler');
});

test('the main process asks the brain on this machine and takes only known values', async () => {
  const calls = [];
  const signs = [];
  const rose = createBlueRose({
    base: 'http://127.0.0.1:5000',
    env: { VIBEMIND_EINGABE_SCHLUESSEL: KEY },
    fetchJson: async (url, options = {}) => {
      calls.push([url, options.body ? JSON.parse(options.body) : null]);
      signs.push([options.method || 'GET', url.replace('http://127.0.0.1:5000', ''), options.body, options.headers]);
      return { ok: true };
    },
  });
  assert.equal((await rose.read({ stunde: 9, offsetHours: 1 })).state, 'ok');
  assert.deepEqual(await rose.saveMood({ stimmung: 'calm', energie: 6, stunde: 9 }), { ok: true });
  assert.deepEqual(await rose.setAnalysis(false), { ok: true });
  assert.deepEqual(await rose.remove('befinden', 'id-1'), { ok: true });
  assert.deepEqual(await rose.remove('alles'), { ok: true });
  assert.deepEqual(calls, [
    ['http://127.0.0.1:5000/api/blue_rose/uebersicht?tage=14&stunde=9', null],
    ['http://127.0.0.1:5000/api/blue_rose/befinden', { stimmung: 'calm', energie: 6, stunde: 9 }],
    ['http://127.0.0.1:5000/api/blue_rose/einstellungen', { analyse: false }],
    ['http://127.0.0.1:5000/api/blue_rose/loeschen', { art: 'befinden', id: 'id-1' }],
    ['http://127.0.0.1:5000/api/blue_rose/loeschen', { art: 'alles' }],
  ]);
  // every request carries the sign of the app over exactly itself, each with a value of its own
  for (const [method, pathAndQuery, body, headers] of signs) {
    const [sec] = headers['X-Vibemind-Eingabe'].split('.');
    assert.deepEqual(signHeaders(KEY, method, pathAndQuery, body, { sec: Number(sec), once: headers['X-Blue-Rose-Einmal'] }),
      { 'X-Blue-Rose-Einmal': headers['X-Blue-Rose-Einmal'], 'X-Vibemind-Eingabe': headers['X-Vibemind-Eingabe'] });
    assert.match(headers['X-Blue-Rose-Einmal'], /^[0-9a-f]{24}$/);
  }
  assert.equal(new Set(signs.map((s) => s[3]['X-Blue-Rose-Einmal'])).size, signs.length);
  calls.length = 0;
  for (const bad of [{ stimmung: 'gluecklich', energie: 5, stunde: 9 }, { stimmung: 'calm', energie: 11, stunde: 9 },
    { stimmung: 'calm', energie: 5.5, stunde: 9 }, { stimmung: 'toString', energie: 5, stunde: 9 }, { stimmung: 'calm', energie: 5 }]) {
    assert.equal((await rose.saveMood(bad)).ok, false);
  }
  assert.equal((await rose.setAnalysis('ja')).ok, false);
  assert.equal((await rose.remove('ideas')).ok, false);
  assert.equal((await rose.remove('befinden', 'x,or=(id.not.is.null)')).ok, false);
  assert.equal((await rose.remove('alt_aktivitaet', 'a')).ok, false);
  assert.deepEqual(calls, [], 'nothing unknown reaches the brain');
});

test('a brain that does not answer gives a calm line, and the log names only the kind of failure', async () => {
  const lines = [];
  const rose = createBlueRose({ env: { VIBEMIND_EINGABE_SCHLUESSEL: KEY }, fetchJson: async () => { throw new TypeError('erfundener Inhalt'); }, log: (line) => lines.push(line) });
  assert.equal((await rose.read({})).state, 'aus');
  assert.deepEqual(await rose.saveMood({ stimmung: 'calm', energie: 6, stunde: 9 }), { ok: false, text: 'Das Gehirn antwortet gerade nicht.' });
  assert.deepEqual(lines, ['[BlueRose] lesen: TypeError', '[BlueRose] eintragen: TypeError']);
});

test('the sign is the one the brain checks (vector from core/blue_rose.beleg_satz + eingabe_zeichen)', () => {
  assert.deepEqual(signHeaders(KEY, 'POST', '/api/blue_rose/loeschen', '{"art":"alles"}', { sec: 1800000000, once: 'abcdef0123456789abcdef01' }), {
    'X-Blue-Rose-Einmal': 'abcdef0123456789abcdef01',
    'X-Vibemind-Eingabe': VECTOR,
  });
});

test('without the key of the app nothing is asked, and the page says why', async () => {
  let asked = 0;
  const rose = createBlueRose({ env: { VIBEMIND_EINGABE_SCHLUESSEL: 'zukurz' }, fetchJson: async () => { asked += 1; return { ok: true }; } });
  assert.equal((await rose.read({})).state, 'fehler');
  assert.equal((await rose.remove('alles')).ok, false);
  assert.equal((await rose.saveMood({ stimmung: 'calm', energie: 5, stunde: 9 })).ok, false);
  assert.equal(asked, 0);
});

// Lauf 43: "Was soll ich als Nächstes tun?" called a part of Python that is gone; nothing happened
// on screen, and each click reached Python twice.
test('the recommendation is one sentence from the brain, or the reason why there is none', async () => {
  const urls = [];
  const make = (answerOf) => createBlueRose({ env: { VIBEMIND_EINGABE_SCHLUESSEL: KEY },
    fetchJson: async (url) => { urls.push(url); return answerOf(); } });
  assert.deepEqual(await make(() => answer()).recommend({ stunde: 9 }), { ok: true, text: 'Jetzt passt: Konzentrierte Arbeit.' });
  assert.equal(urls.length, 1, 'one request');
  assert.match(urls[0], /\/api\/blue_rose\/uebersicht\?tage=14&stunde=9$/);
  assert.deepEqual(await make(() => answer({ empfehlung: { ok: false, grund: 'befinden_fehlt' } })).recommend({ stunde: 9 }),
    { ok: true, text: 'Trag dein Befinden ein, dann sagt Blue Rose, was jetzt passt.' });
  assert.deepEqual(await make(() => ({ ok: false, grund: 'nicht_belegt' })).recommend({}),
    { ok: false, text: 'Das Gehirn erkennt die App nicht (Schlüssel fehlt oder passt nicht).' });
  assert.deepEqual(await make(() => { throw new Error('x'); }).recommend({}),
    { ok: false, text: 'Das Gehirn antwortet gerade nicht. Blue Rose zeigt deshalb nichts an.' });
});

test('the panel button: one click is one request, the answer or the reason is shown, nothing goes to Python', async () => {
  const vmod = require('node:vm');
  const els = {};
  const document = { getElementById: (id) => (els[id] = els[id] || { id, textContent: '', className: '', classList: { add() {}, remove() {} }, addEventListener() {} }) };
  let settle; let asked = 0; const toPython = [];
  const window = { vibemind: {
    sendToPython: (message) => toPython.push(message.type),
    blueRoseRecommend: () => { asked += 1; return new Promise((resolve, reject) => { settle = { resolve, reject }; }); },
  } };
  vmod.runInNewContext(fs.readFileSync(path.join(__dirname, 'renderer', 'flowzen-panel.js'), 'utf8'), { window, document });
  const panel = window.flowzenPanel;
  panel.requestFlowzenRecommend();
  panel.requestFlowzenRecommend();            // a second click while the first is under way
  assert.equal(asked, 1);
  assert.equal(els['fz-recommend-btn'].textContent, 'Denke nach …');
  settle.resolve({ ok: true, text: 'Jetzt passt: Pause.' });
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(els['fz-recommend-answer'].textContent, 'Jetzt passt: Pause.');
  assert.equal(els['fz-recommend-btn'].textContent, 'Was soll ich als Nächstes tun?');
  panel.requestFlowzenRecommend();
  assert.equal(asked, 2);
  settle.reject(new Error('x'));
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(els['fz-recommend-answer'].textContent, 'Das hat nicht geklappt.');
  assert.deepEqual(toPython, []);
  // the old answer of Python, should it ever come: its reason is shown
  panel.showRecommendAnswer('Fehler: Beispielgrund');
  assert.equal(els['fz-recommend-answer'].textContent, 'Fehler: Beispielgrund');

  delete window.vibemind.blueRoseRecommend;
  panel.requestFlowzenRecommend();
  assert.equal(els['fz-recommend-answer'].textContent, 'Die Empfehlung ist hier nicht verfügbar.');
});

test('one receiver for to-python: the journal view adds none, and its button asks the main process', () => {
  const read = (...p) => fs.readFileSync(path.join(__dirname, ...p), 'utf8');
  const main = read('main.js');
  assert.equal(main.match(/ipcMain\.on\('to-python'/g).length, 1);
  assert.doesNotMatch(read('flowzen-manager.js'), /ipcMain\.on\(/);
  const FlowzenManager = require('./flowzen-manager');
  const listened = [];
  const contents = { on() {}, setWindowOpenHandler() {}, isDestroyed: () => false, insertCSS: async () => {}, loadFile: async () => {}, loadURL: async () => {}, send() {} };
  class FakeBrowserView { constructor() { this.webContents = contents; } setBounds() {} setAutoResize() {} }
  const write = process.stdout.write; process.stdout.write = () => true;
  try {
    new FlowzenManager(null, () => {}, { BrowserView: FakeBrowserView, shell: { openExternal() {} },
      ipcMain: { on: (channel) => listened.push(channel) }, overlayDeps: { existsSync: () => true, logger: { log() {}, warn() {}, error() {} } } }).createView();
  } finally { process.stdout.write = write; }
  assert.deepEqual(listened, []);

  const diary = read('flowzen-diary.html');
  assert.match(diary, /window\.blueRose\.recommend\(/);
  assert.doesNotMatch(diary, /flowzenDiary\.recommend\(/);
  assert.match(diary, /id="recommend-answer"/);
  assert.match(read('renderer', 'index.html'), /id="fz-recommend-answer"/);
  assert.match(main, /'blue-rose:recommend', \(event, place\) => \(fromApp\(event\)/);
  for (const file of [['renderer', 'index.html'], ['renderer', 'handlers', 'dashboard-handlers.js']]) {
    assert.match(read(...file), /success === false && window\.flowzenPanel\.showRecommendAnswer/, file.join('/'));
  }
});

test('the tab opens with the personal space; the journal is one page of the same view', () => {
  const FlowzenManager = require('./flowzen-manager');
  const loaded = [];
  const sent = [];
  const contents = { on() {}, setWindowOpenHandler() {}, isDestroyed: () => false, insertCSS: async () => {},
    loadFile: async (file) => { loaded.push(path.basename(file)); }, loadURL: async () => {}, send() {} };
  class FakeBrowserView { constructor() { this.webContents = contents; } setBounds() {} setAutoResize() {} }
  const quiet = { log() {}, warn() {}, error() {} };
  const write = process.stdout.write; process.stdout.write = () => true;
  let m;
  try {
    m = new FlowzenManager(null, (message) => sent.push(message.type), { BrowserView: FakeBrowserView, shell: { openExternal() {} },
      ipcMain: { on() {} }, overlayDeps: { existsSync: () => true, logger: quiet } });
    m.createView();
    m.showPage('tagebuch');
    m.showPage('irgendwas');
    m._requestDiaryData();
    m.showPage('bereich');
    m._requestDiaryData();
  } finally { process.stdout.write = write; }
  assert.equal(m.page, 'bereich');
  assert.deepEqual(sent, ['flowzen_status', 'flowzen_diary_entries'], 'only the journal asks Python');
  assert.equal(m.ownsPage(contents), true);
  assert.equal(m.ownsPage({}), false);
  assert.equal(m.ownsPage(null), false);
});

test('the page draws ready lines only: no address of the brain, no innerHTML, German words', () => {
  const page = fs.readFileSync(path.join(__dirname, 'blue-rose.html'), 'utf8');
  assert.doesNotMatch(page, /innerHTML|insertAdjacentHTML|document\.write|fetch\(|127\.0\.0\.1|localhost/);
  assert.match(page, /default-src 'none'/);
  for (const german of ['Blue Rose — Dein Bereich', 'Befinden', 'Arbeitsweise', 'Was an der Software hakt', 'Was gespeichert ist',
    'Nie gespeichert', 'Alles löschen', 'Wirklich löschen?', 'Analyse', 'Tagebuch']) {
    assert.ok(page.includes(german), german);
  }
  const preload = fs.readFileSync(path.join(__dirname, 'flowzen-preload.js'), 'utf8');
  for (const channel of ['blue-rose:read', 'blue-rose:mood', 'blue-rose:analysis', 'blue-rose:remove', 'blue-rose:page']) {
    assert.ok(preload.includes(channel), channel);
  }
  const main = fs.readFileSync(path.join(__dirname, 'main.js'), 'utf8');
  for (const channel of ['blue-rose:read', 'blue-rose:mood', 'blue-rose:analysis', 'blue-rose:remove', 'blue-rose:page']) {
    assert.match(main, new RegExp(`'${channel}', \\(event[^\\n]*fromBlueRose\\(event\\)`), `${channel} checks its sender`);
  }
});
