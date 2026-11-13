const assert = require('node:assert/strict');
const test = require('node:test');

const {
  NACHFRIST_MS, anfrageEntscheidung, eingesperrtNachNavigation, istEingesperrterRahmen, ketteEingesperrt, neuerStand,
  rahmenGesperrt, rahmenImBaum, rahmenNavigation, rahmenUebernommen, rahmenVerfolgen, rueckhaltAnmelden,
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

test('Rueckhalt-Zustand (R47): eingesperrt auf Lebenszeit, nur der Abbau entlaesst, Ablauf nach 5 s', () => {
  const st = neuerStand();
  rahmenUebernommen(st, { rahmenId: 7, elternId: 1, url: K, jetzt: 1000 });
  assert.deepEqual([...st.confined], [7]);
  for (const url of ['https://example.com/#x', 'about:blank', 'https://www.figma.com/embed', 'app://-/index.html']) {
    rahmenUebernommen(st, { rahmenId: 7, elternId: 1, url, jetzt: 1100 });
    assert.equal(st.confined.has(7), true, url);
  }
  assert.equal(st.kuerzlich.size, 0);
  rahmenUebernommen(st, { rahmenId: 9, elternId: 1, url: `${K}#teil`, jetzt: 1100 });
  rahmenUebernommen(st, { rahmenId: 8, elternId: 7, url: 'about:srcdoc', jetzt: 1150 });
  assert.equal(st.confined.has(9) && st.confined.has(8), true);
  rahmenUebernommen(st, { rahmenId: 12, elternId: 1, url: 'https://www.youtube.com/embed/x', jetzt: 1150 });
  assert.equal(st.confined.has(12), false);
  rahmenImBaum(st, new Set([1, 7, 12]), 2000);
  assert.deepEqual([...st.confined], [7]);
  assert.equal(st.kuerzlich.get(8), 2000);
  assert.equal(st.kuerzlich.get(9), 2000);
  rahmenImBaum(st, new Set([1, 7]), 2000 + NACHFRIST_MS);
  assert.equal(st.kuerzlich.has(8), true);
  rahmenImBaum(st, new Set([1, 7]), 2001 + NACHFRIST_MS);
  assert.equal(st.kuerzlich.size, 0);
  assert.equal(NACHFRIST_MS, 5000);
});

test('Navigationssperre nach Zustand (R47): Rahmen oder Vorfahr eingesperrt -> block', () => {
  const confined = new Set([7]);
  const kuerzlich = new Map([[9, 1000]]);
  assert.equal(ketteEingesperrt([7, 1], confined, kuerzlich, 1000), true);
  assert.equal(ketteEingesperrt([8, 7, 1], confined, kuerzlich, 1000), true);
  assert.equal(ketteEingesperrt([9, 1], confined, kuerzlich, 1000 + NACHFRIST_MS), true);
  assert.equal(ketteEingesperrt([9, 1], confined, kuerzlich, 1001 + NACHFRIST_MS), false);
  assert.equal(ketteEingesperrt([12, 1], confined, kuerzlich, 1000), false);
  assert.equal(rahmenNavigation('about:blank', true), 'block');
  assert.equal(rahmenNavigation('https://example.com/', true), 'block');
  assert.equal(rahmenNavigation('https://www.youtube.com/embed/x', false), 'allow');
});

test('anfrageEntscheidung (R44-R47): jeder Zweig, der Verweiser zaehlt nie', () => {
  const leer = { confined: new Set(), kuerzlich: new Map() };
  const offen = { confined: new Set([7]), kuerzlich: new Map() };
  const kuerzlich = { confined: new Set(), kuerzlich: new Map([[7, 1000]]) };
  const basis = {
    url: 'https://example.com/x', resourceType: 'image', rahmenId: 7, rahmenUrl: K, vorfahrenIds: [1], imBaum: true,
    ketteUnterWissen: true, ...offen, jetzt: 1000,
  };
  for (const url of ['data:,x', 'blob:null/1', 'about:blank', K, `${K}#teil`, `${K}?v=2`]) {
    assert.equal(anfrageEntscheidung({ ...basis, url }), false, url);
  }
  for (const url of ['https://example.com/x', 'app://workspace/knowledge/b.html', 'app://workspace/knowledge/b.png',
    'app://-/index.html', 'devtools://devtools/x', 'chrome-extension://pdf/x.js', 'http://127.0.0.1:8765/', 'kein-schema']) {
    assert.equal(anfrageEntscheidung({ ...basis, url }), true, url);
  }
  assert.equal(anfrageEntscheidung({ ...basis, ketteUnterWissen: false, rahmenUrl: 'about:blank' }), true, 'selbst nach about:blank');
  assert.equal(anfrageEntscheidung({ ...basis, ketteUnterWissen: false, rahmenUrl: 'https://example.com/x', url: 'https://example.com/y' }), true);
  assert.equal(anfrageEntscheidung({ ...basis, ketteUnterWissen: false, rahmenId: 8, rahmenUrl: 'about:srcdoc', vorfahrenIds: [7, 1], url: 'app://-/x.js' }), true);
  assert.equal(anfrageEntscheidung({ ...basis, ketteUnterWissen: false, ...kuerzlich, jetzt: 1000 + NACHFRIST_MS }), true);
  const app = { ...basis, ketteUnterWissen: false, rahmenId: 1, rahmenUrl: 'app://-/index.html', vorfahrenIds: [] };
  for (const url of ['https://api.example.com/v1', 'app://-/x.js', 'chrome-extension://pdf/x.js', 'wss://sync.example/']) {
    assert.equal(anfrageEntscheidung({ ...app, url }), false, url);
  }
  assert.equal(anfrageEntscheidung({ ...app, referrer: K }), false, 'Verweiser zaehlt nicht');
  assert.equal(anfrageEntscheidung({ ...app, rahmenId: 12, vorfahrenIds: [1], rahmenUrl: 'https://www.youtube.com/embed/x' }), false);
  assert.equal(anfrageEntscheidung({ ...basis, ...kuerzlich, ketteUnterWissen: false, jetzt: 1001 + NACHFRIST_MS }), false);
  for (const rahmen of [{ rahmenId: null, rahmenUrl: null, vorfahrenIds: [] }, { rahmenId: 12, rahmenUrl: null, vorfahrenIds: [], imBaum: false }]) {
    const u = { ...basis, ...rahmen, ketteUnterWissen: false };
    const n = JSON.stringify(rahmen);
    assert.equal(anfrageEntscheidung(u), true, n);
    assert.equal(anfrageEntscheidung({ ...u, ...kuerzlich, jetzt: 2000 }), true, n);
    assert.equal(anfrageEntscheidung({ ...u, ...kuerzlich, jetzt: 1001 + NACHFRIST_MS }), false, n);
    assert.equal(anfrageEntscheidung({ ...u, ...leer }), false, n);
    for (const url of ['app://-/x.js', 'devtools://devtools/x', 'data:,x']) assert.equal(anfrageEntscheidung({ ...u, url }), false, url);
    for (const url of ['chrome-extension://pdf/x.js', 'http://localhost:9999/', 'kein-schema']) assert.equal(anfrageEntscheidung({ ...u, url }), true, url);
  }
  assert.equal(anfrageEntscheidung({ ...basis, resourceType: 'mainFrame' }), false);
  assert.equal(anfrageEntscheidung({ ...basis, resourceType: 'mainFrame', rahmenId: null, ketteUnterWissen: false }), false);
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

test('Rueckhalt (R47) verdrahtet: Konzept, Kind, Selbst-Navigation, Schliessen mit Nachfrist, Zerstoeren', () => {
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
  assert.equal(rahmenGesperrt(ansicht, konzept), false, 'erster Ladevorgang eines neuen Rahmens frei');
  ansicht.navigiert(konzept, K);
  const kind = { url: 'about:blank', parent: konzept, frameTreeNodeId: 8, processId: 9, routingId: 8 };
  ansicht.rahmen.push(kind);
  ansicht.navigiert(kind, 'about:srcdoc');
  const youtube = { url: 'https://www.youtube.com/embed/x', parent: haupt, frameTreeNodeId: 10, processId: 9, routingId: 10 };
  ansicht.rahmen.push(youtube);
  ansicht.navigiert(youtube, youtube.url);
  const w = ansicht;

  assert.deepEqual(frage({ url: 'https://example.com/', frame: konzept, resourceType: 'image', webContents: w }), { cancel: true });
  assert.deepEqual(frage({ url: 'app://workspace/knowledge/b.html', frame: konzept, resourceType: 'xhr', webContents: w }), { cancel: true });
  assert.deepEqual(frage({ url: `${K}?neu=1`, frame: konzept, resourceType: 'xhr', webContents: w }), {});
  assert.deepEqual(frage({ url: 'https://example.com/', frame: kind, resourceType: 'subFrame', webContents: w }), { cancel: true });
  assert.deepEqual(frage({ url: 'data:image/png;base64,AA', frame: konzept, resourceType: 'image', webContents: w }), {});
  assert.deepEqual(frage({ url: 'https://example.com/', frame: haupt, resourceType: 'xhr', webContents: w }), {}, 'App selbst');
  assert.deepEqual(frage({ url: 'https://www.youtube.com/y.js', frame: youtube, resourceType: 'script', webContents: w }), {});
  assert.deepEqual(frage({ url: 'https://example.com/?r=1', frame: haupt, resourceType: 'xhr', referrer: K, webContents: w }), {});

  // Konzept schickt sich selbst weg (about:blank, fremde Seite, In-Page): bleibt eingesperrt, Navigation gesperrt
  ansicht.navigiert(konzept, 'about:blank');
  assert.equal(rahmenGesperrt(w, konzept), true);
  assert.equal(rahmenNavigation(konzept.url, rahmenGesperrt(w, konzept)), 'block');
  assert.deepEqual(frage({ url: 'https://example.com/', frame: konzept, resourceType: 'image', webContents: w }), { cancel: true });
  ansicht.navigiert(konzept, 'https://example.com/seite');
  ansicht.imSeiteNavigiert(konzept, 'https://example.com/seite#x');
  assert.deepEqual(frage({ url: 'https://example.com/b.js', frame: konzept, resourceType: 'script', webContents: w }), { cancel: true });
  assert.equal(rahmenGesperrt(w, kind), true, 'Kind ueber den Vorfahren');
  assert.equal(rahmenGesperrt(w, youtube), false);

  // Rahmen verworfen oder ohne Rahmen, Konzept offen -> abbrechen; Hauptrahmen-Laden und app: frei
  const weg = { get frameTreeNodeId() { throw new Error('disposed'); }, url: K, parent: null };
  assert.deepEqual(frage({ url: 'https://example.com/', frame: weg, resourceType: 'image', webContents: w }), { cancel: true });
  assert.deepEqual(frage({ url: 'http://127.0.0.1:8765/flut', resourceType: 'xhr', webContents: w }), { cancel: true });
  assert.deepEqual(frage({ url: 'app://-/x.js', resourceType: 'script', webContents: w }), {});
  assert.deepEqual(frage({ url: 'app://-/index.html', frame: weg, resourceType: 'mainFrame', webContents: w }), {});

  // Konzept geschlossen (neu laden = neuer Rahmen): alter Knoten nicht mehr im Baum -> 5 s weiter abbrechen
  ansicht.rahmen = [haupt, youtube];
  const abgeloest = { url: 'about:blank', parent: null, frameTreeNodeId: 7 };
  assert.deepEqual(frage({ url: 'http://127.0.0.1:8765/flut', frame: abgeloest, resourceType: 'xhr', webContents: w }), { cancel: true });
  assert.deepEqual(frage({ url: 'http://127.0.0.1:8765/flut', resourceType: 'xhr', webContents: w }), { cancel: true });
  assert.deepEqual(frage({ url: 'https://www.youtube.com/z.js', frame: youtube, resourceType: 'script', webContents: w }), {});
  const neu = { url: 'about:blank', parent: haupt, frameTreeNodeId: 13, processId: 9, routingId: 13 };
  ansicht.rahmen.push(neu);
  assert.equal(rahmenGesperrt(w, neu), false, 'neu eingehaengter Rahmen laedt');
  const echtesJetzt = Date.now;
  try {
    Date.now = () => echtesJetzt() + NACHFRIST_MS + 50;
    assert.deepEqual(frage({ url: 'http://127.0.0.1:8765/', resourceType: 'xhr', webContents: w }), {}, 'nach der Nachfrist');
  } finally {
    Date.now = echtesJetzt;
  }

  ansicht.zerstoert();
  assert.deepEqual(frage({ url: 'https://example.com/', resourceType: 'image', webContents: w }), {});
  assert.deepEqual(frage({ url: 'https://example.com/', resourceType: 'image' }), {});
});
