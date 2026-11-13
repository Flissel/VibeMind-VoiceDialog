const assert = require('node:assert/strict');
const test = require('node:test');

const {
  NACHFRIST_MS, anfrageEntscheidung, eingesperrtNachNavigation, istEingesperrterRahmen, neuerStand, rahmenImBaum,
  rahmenNavigation, rahmenUebernommen, rahmenVerfolgen, rueckhaltAnmelden,
} = require('./konzept-rahmen');

const K = 'app://workspace/knowledge/a.html';

test('eingesperrte Rahmen (R43): alles unter app://workspace/knowledge/, im Zweifel eingesperrt', () => {
  for (const p of [
    'knowledge/a.html', 'knowledge/a.HTML', 'knowledge/a.html?x=1', 'knowledge/a.html#y', 'knowledge/a%2Ehtml',
    'knowledge/a.html.', 'Knowledge/K/a.htm', '%6Bnowledge/a.html', 'knowledge%2Fa.html', 'knowledge/a.xhtml',
    '/knowledge/a.html', 'knowledge/a.png', 'knowledge/seite', 'knowledge', 'bg-tasks/../knowledge/a.html',
    'bg-tasks/%2e%2e/x', 'bg-tasks/%ZZ',
  ]) {
    assert.equal(istEingesperrterRahmen(`app://workspace/${p}`), true, p);
    assert.equal(rahmenNavigation(`app://workspace/${p}`), 'block', p);
  }
  assert.equal(rahmenNavigation('APP://Workspace/knowledge/a.html'), 'block');
  for (const u of [
    'app://workspace/bg-tasks/x/index.html', 'app://workspace/knowledge.html', 'app://workspacex/knowledge/a.html',
    'app://-/index.html', 'https://www.youtube.com/embed/x', 'about:blank', '', undefined,
  ]) {
    assert.equal(rahmenNavigation(u), 'allow', String(u));
  }
});

test('eingesperrtNachNavigation: knowledge/ oder Kind eines eingesperrten Rahmens', () => {
  assert.equal(eingesperrtNachNavigation(K, false), true);
  assert.equal(eingesperrtNachNavigation('app://workspace/knowledge/seite', false), true);
  assert.equal(eingesperrtNachNavigation('about:srcdoc', true), true);
  assert.equal(eingesperrtNachNavigation('app://workspace/bg-tasks/x/index.html', false), false);
  assert.equal(eingesperrtNachNavigation('https://www.youtube.com/embed/x', false), false);
});

test('Rueckhalt-Zustand (R46): In-Page entlaesst nie, Dokumentwechsel und Abbau entlassen nach kuerzlich, Ablauf', () => {
  const st = neuerStand();
  rahmenUebernommen(st, { rahmenId: 7, elternId: 1, url: K, inPage: false, jetzt: 1000 });
  assert.deepEqual([...st.confined], [7]);
  rahmenUebernommen(st, { rahmenId: 7, elternId: 1, url: 'https://example.com/#x', inPage: true, jetzt: 1100 });
  assert.equal(st.confined.has(7), true, 'In-Page entlaesst nie');
  rahmenUebernommen(st, { rahmenId: 9, elternId: 1, url: `${K}#teil`, inPage: true, jetzt: 1100 });
  assert.equal(st.confined.has(9), true, 'In-Page unter knowledge/ nimmt auf');
  rahmenUebernommen(st, { rahmenId: 8, elternId: 7, url: 'about:srcdoc', inPage: false, jetzt: 1150 });
  assert.equal(st.confined.has(8), true, 'Kind eines eingesperrten Rahmens');
  rahmenUebernommen(st, { rahmenId: 7, elternId: 1, url: 'https://www.figma.com/embed', inPage: false, jetzt: 1200 });
  assert.equal(st.confined.has(7), false);
  assert.equal(st.kuerzlich.get(7), 1200);
  rahmenUebernommen(st, { rahmenId: 7, elternId: 1, url: K, inPage: false, jetzt: 1300 });
  assert.equal(st.confined.has(7), true);
  assert.equal(st.kuerzlich.has(7), false);
  rahmenImBaum(st, new Set([1, 7]), 2000);
  assert.deepEqual([...st.confined], [7]);
  assert.equal(st.kuerzlich.get(8), 2000);
  assert.equal(st.kuerzlich.get(9), 2000);
  rahmenImBaum(st, new Set([1, 7]), 2000 + NACHFRIST_MS);
  assert.equal(st.kuerzlich.has(8), true);
  rahmenImBaum(st, new Set([1, 7]), 2001 + NACHFRIST_MS);
  assert.equal(st.kuerzlich.size, 0);
  assert.equal(NACHFRIST_MS, 5000);
});

test('anfrageEntscheidung (R44-R46): jeder Zweig, der Verweiser zaehlt nie', () => {
  const leer = { confined: new Set(), kuerzlich: new Map() };
  const offen = { confined: new Set([7]), kuerzlich: new Map() };
  const kuerzlich = { confined: new Set(), kuerzlich: new Map([[7, 1000]]) };
  const basis = {
    url: 'https://example.com/x', resourceType: 'image', rahmenId: 7, vorfahrenIds: [1], imBaum: true,
    ketteUnterWissen: false, ...offen, jetzt: 1000,
  };
  assert.equal(anfrageEntscheidung(basis), true);
  assert.equal(anfrageEntscheidung({ ...basis, ...kuerzlich, jetzt: 1000 + NACHFRIST_MS }), true);
  assert.equal(anfrageEntscheidung({ ...basis, ...kuerzlich, jetzt: 1001 + NACHFRIST_MS }), false);
  assert.equal(anfrageEntscheidung({ ...basis, rahmenId: 8, vorfahrenIds: [7, 1] }), true, 'Vorfahr eingesperrt');
  assert.equal(anfrageEntscheidung({ ...basis, rahmenId: 8, vorfahrenIds: [7, 1], ...kuerzlich, jetzt: 1500 }), true);
  assert.equal(anfrageEntscheidung({ ...basis, rahmenId: 1, vorfahrenIds: [] }), false, 'App selbst');
  assert.equal(anfrageEntscheidung({ ...basis, rahmenId: 12, vorfahrenIds: [1] }), false, 'Einbettung');
  assert.equal(anfrageEntscheidung({ ...basis, ...leer, rahmenId: 12, ketteUnterWissen: true }), true);
  assert.equal(anfrageEntscheidung({ ...basis, rahmenId: 1, vorfahrenIds: [], referrer: K, ...leer }), false, 'Verweiser zaehlt nicht');
  for (const rahmen of [{ rahmenId: null }, { rahmenId: 12, imBaum: false }]) {
    const n = JSON.stringify(rahmen);
    assert.equal(anfrageEntscheidung({ ...basis, ...rahmen }), true, n);
    assert.equal(anfrageEntscheidung({ ...basis, ...rahmen, ...kuerzlich, jetzt: 2000 }), true, n);
    assert.equal(anfrageEntscheidung({ ...basis, ...rahmen, ...kuerzlich, jetzt: 1001 + NACHFRIST_MS }), false, n);
    assert.equal(anfrageEntscheidung({ ...basis, ...rahmen, ...leer }), false, n);
  }
  for (const url of ['app://-/x.js', 'app://workspace/knowledge/b.png', 'data:,x', 'blob:null/1', 'about:blank',
    'devtools://devtools/x', 'chrome-extension://pdf/x.js']) {
    assert.equal(anfrageEntscheidung({ ...basis, url, ketteUnterWissen: true }), false, url);
  }
  assert.equal(anfrageEntscheidung({ ...basis, url: 'kein-schema' }), true);
  assert.equal(anfrageEntscheidung({ ...basis, resourceType: 'mainFrame', ketteUnterWissen: true }), false);
  assert.equal(anfrageEntscheidung({ ...basis, resourceType: 'mainFrame', rahmenId: null }), false);
});

function fakeAnsicht(id) {
  const handler = new Map();
  const haupt = { url: 'app://-/index.html', parent: null, frameTreeNodeId: 1, processId: 9, routingId: 1 };
  const ansicht = {
    id,
    rahmen: [haupt],
    haupt,
    on: (ereignis, fn) => handler.set(ereignis, fn),
    mainFrame: { get framesInSubtree() { return ansicht.rahmen; } },
    navigiert(rahmen, url) {
      rahmen.url = url;
      handler.get('did-frame-navigate')({}, url, 200, 'OK', rahmen === haupt, rahmen.processId, rahmen.routingId);
    },
    imSeiteNavigiert(rahmen, url) {
      rahmen.url = url;
      handler.get('did-navigate-in-page')({}, url, rahmen === haupt, rahmen.processId, rahmen.routingId);
    },
    zerstoert() { handler.get('destroyed')(); },
  };
  return ansicht;
}

test('Rueckhalt (R46) verdrahtet: Konzept, Kind, In-Page, Schliessen mit Nachfrist, Zerstoeren', () => {
  let hoerer = null;
  rueckhaltAnmelden({ webRequest: { onBeforeRequest: (fn) => { hoerer = fn; } } });
  const frage = (details) => {
    let antwort;
    hoerer(details, (a) => { antwort = a; });
    return antwort;
  };
  const ansicht = fakeAnsicht(4711);
  rahmenVerfolgen(ansicht);
  const { haupt } = ansicht;
  const konzept = { url: 'about:blank', parent: haupt, frameTreeNodeId: 7, processId: 9, routingId: 7 };
  ansicht.rahmen.push(konzept);
  ansicht.navigiert(konzept, K);
  const kind = { url: 'about:blank', parent: konzept, frameTreeNodeId: 8, processId: 9, routingId: 8 };
  ansicht.rahmen.push(kind);
  ansicht.navigiert(kind, 'about:srcdoc');
  const youtube = { url: 'https://www.youtube.com/embed/x', parent: haupt, frameTreeNodeId: 10, processId: 9, routingId: 10 };
  ansicht.rahmen.push(youtube);
  ansicht.navigiert(youtube, youtube.url);
  const w = ansicht;

  assert.deepEqual(frage({ url: 'https://example.com/', frame: konzept, resourceType: 'image', webContents: w }), { cancel: true });
  assert.deepEqual(frage({ url: 'https://example.com/', frame: kind, resourceType: 'subFrame', webContents: w }), { cancel: true });
  assert.deepEqual(frage({ url: 'data:image/png;base64,AA', frame: konzept, resourceType: 'image', webContents: w }), {});
  assert.deepEqual(frage({ url: 'https://example.com/', frame: haupt, resourceType: 'xhr', webContents: w }), {}, 'App selbst');
  assert.deepEqual(frage({ url: 'https://www.youtube.com/y.js', frame: youtube, resourceType: 'script', webContents: w }), {});
  assert.deepEqual(frage({ url: 'https://example.com/?r=1', frame: haupt, resourceType: 'xhr', referrer: K, webContents: w }), {});

  // In-Page-Navigation zu einer fremden Adresse entlaesst nicht (Befund 1)
  ansicht.imSeiteNavigiert(kind, 'https://example.com/');
  assert.deepEqual(frage({ url: 'https://example.com/', frame: kind, resourceType: 'xhr', webContents: w }), { cancel: true });

  // Rahmen verworfen oder ohne Rahmen, Konzept offen -> abbrechen; Hauptrahmen-Laden und app: frei
  const weg = { get frameTreeNodeId() { throw new Error('disposed'); }, url: K, parent: null };
  assert.deepEqual(frage({ url: 'https://example.com/', frame: weg, resourceType: 'image', webContents: w }), { cancel: true });
  assert.deepEqual(frage({ url: 'http://127.0.0.1:8765/flut', resourceType: 'xhr', webContents: w }), { cancel: true });
  assert.deepEqual(frage({ url: 'app://-/x.js', resourceType: 'script', webContents: w }), {});
  assert.deepEqual(frage({ url: 'app://-/index.html', frame: weg, resourceType: 'mainFrame', webContents: w }), {});

  // Konzept geschlossen: Rahmen haengt nicht mehr im Baum, liest sich aber noch (Befund 2) -> 5 s weiter abbrechen
  ansicht.rahmen = [haupt, youtube];
  const abgeloest = { url: 'about:blank', parent: null, frameTreeNodeId: 7 };
  assert.deepEqual(frage({ url: 'http://127.0.0.1:8765/flut', frame: abgeloest, resourceType: 'xhr', webContents: w }), { cancel: true });
  assert.deepEqual(frage({ url: 'http://127.0.0.1:8765/flut', resourceType: 'xhr', webContents: w }), { cancel: true });
  assert.deepEqual(frage({ url: 'https://www.youtube.com/z.js', frame: youtube, resourceType: 'script', webContents: w }), {});
  const echtesJetzt = Date.now;
  try {
    Date.now = () => echtesJetzt() + NACHFRIST_MS + 50;
    assert.deepEqual(frage({ url: 'http://127.0.0.1:8765/', resourceType: 'xhr', webContents: w }), {}, 'nach der Nachfrist');
  } finally {
    Date.now = echtesJetzt;
  }

  // Ansicht zerstoert: Zustand weg; ohne Ansicht keine Renderer-Anfrage
  ansicht.zerstoert();
  assert.deepEqual(frage({ url: 'https://example.com/', resourceType: 'image', webContents: w }), {});
  assert.deepEqual(frage({ url: 'https://example.com/', resourceType: 'image' }), {});
});
