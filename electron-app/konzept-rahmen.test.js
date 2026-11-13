const assert = require('node:assert/strict');
const test = require('node:test');

const {
  NACHFRIST_MS, anfrageEntscheidung, anfrageSperren, eingesperrtNachNavigation, istEingesperrterRahmen, konzeptInAnsicht,
  rahmenNavigation, rahmenVerfolgen, rueckhaltAnmelden,
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

test('Anfragen aus einem eingesperrten Rahmen: nur Dokument-Schemata und die eigene Adresse', () => {
  for (const u of ['https://example.com/?d=1', 'http://127.0.0.1:8765/', 'wss://x/', 'app://workspace/knowledge/b.html', 'mailto:a@b', 'kein-schema']) {
    assert.equal(anfrageSperren(K, u), true, u);
  }
  for (const u of ['data:image/png;base64,AA', 'blob:null/1', 'about:srcdoc', 'chrome-extension://pdf/index.html', K, `${K}#teil`]) {
    assert.equal(anfrageSperren(K, u), false, u);
  }
  for (const f of ['app://workspace/bg-tasks/x/index.html', 'https://www.figma.com/embed', 'app://-/index.html', '']) {
    assert.equal(anfrageSperren(f, 'https://example.com/'), false, f);
  }
});

test('eingesperrtNachNavigation und konzeptInAnsicht (R45)', () => {
  assert.equal(eingesperrtNachNavigation(K, false), true);
  assert.equal(eingesperrtNachNavigation('about:srcdoc', true), true);
  assert.equal(eingesperrtNachNavigation('app://workspace/bg-tasks/x/index.html', false), false);
  assert.equal(eingesperrtNachNavigation('https://www.youtube.com/embed/x', false), false);
  assert.equal(konzeptInAnsicht(1, null, 1000), true);
  assert.equal(konzeptInAnsicht(0, null, 1000), false);
  assert.equal(konzeptInAnsicht(0, 1000, 1000 + NACHFRIST_MS), true);
  assert.equal(konzeptInAnsicht(0, 1000, 1001 + NACHFRIST_MS), false);
  assert.equal(konzeptInAnsicht(0, 5000, 1000), false);
  assert.equal(NACHFRIST_MS, 5000);
});

test('anfrageEntscheidung (R44/R45): jeder Zweig, Verweiser zaehlt nie', () => {
  const basis = { url: 'https://example.com/x', resourceType: 'image', konzeptOffen: false };
  const eingesperrt = { bekannt: true, url: K, eingesperrt: true };
  assert.equal(anfrageEntscheidung({ ...basis, rahmen: eingesperrt }), true);
  assert.equal(anfrageEntscheidung({ ...basis, rahmen: { bekannt: true, url: 'about:srcdoc', eingesperrt: true } }), true);
  for (const url of ['data:,x', 'blob:null/1', 'about:blank', 'chrome-extension://pdf/x.js', K]) {
    assert.equal(anfrageEntscheidung({ ...basis, url, rahmen: eingesperrt }), false, url);
  }
  assert.equal(anfrageEntscheidung({ ...basis, rahmen: { bekannt: true, url: 'app://-/index.html', eingesperrt: false }, konzeptOffen: true }), false);
  assert.equal(anfrageEntscheidung({ ...basis, rahmen: { bekannt: false }, konzeptOffen: true }), true);
  assert.equal(anfrageEntscheidung({ ...basis, rahmen: { bekannt: false }, konzeptOffen: false }), false);
  assert.equal(anfrageEntscheidung({ ...basis, rahmen: { bekannt: false }, referrer: K, konzeptOffen: false }), false, 'Verweiser zaehlt nicht');
  for (const url of ['app://-/x.js', 'devtools://devtools/x', 'data:,x', 'blob:app://-/1', 'about:blank']) {
    assert.equal(anfrageEntscheidung({ ...basis, url, rahmen: { bekannt: false }, konzeptOffen: true }), false, url);
  }
  assert.equal(anfrageEntscheidung({ ...basis, resourceType: 'mainFrame', rahmen: eingesperrt }), false);
  assert.equal(anfrageEntscheidung({ ...basis, resourceType: 'mainFrame', rahmen: { bekannt: false }, konzeptOffen: true }), false);
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
    zerstoert() { handler.get('destroyed')(); },
  };
  return ansicht;
}

test('Rueckhalt (R45): eingesperrte Rahmen beim Navigieren festhalten, Nachfrist beim Schliessen', () => {
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

  // Rahmen bekannt
  assert.deepEqual(frage({ url: 'https://example.com/', frame: konzept, resourceType: 'image', webContents: ansicht }), { cancel: true });
  assert.deepEqual(frage({ url: 'https://example.com/', frame: kind, resourceType: 'subFrame', webContents: ansicht }), { cancel: true });
  assert.deepEqual(frage({ url: 'data:image/png;base64,AA', frame: konzept, resourceType: 'image', webContents: ansicht }), {});
  assert.deepEqual(frage({ url: 'https://example.com/', frame: haupt, resourceType: 'xhr', webContents: ansicht }), {}, 'App-eigene Anfragen');
  const youtube = { url: 'https://www.youtube.com/embed/x', parent: haupt, frameTreeNodeId: 9 };
  assert.deepEqual(frage({ url: 'https://www.youtube.com/y.js', frame: youtube, resourceType: 'script', webContents: ansicht }), {});
  const bericht = { url: 'app://workspace/bg-tasks/x/index.html', parent: haupt, frameTreeNodeId: 10 };
  assert.deepEqual(frage({ url: 'https://cdn.example.com/chart.js', frame: bericht, resourceType: 'script', webContents: ansicht }), {});
  assert.deepEqual(frage({ url: 'https://example.com/?r=1', frame: haupt, resourceType: 'xhr', referrer: K, webContents: ansicht }), {}, 'Verweiser zaehlt nicht');

  // Rahmen verworfen, Konzept noch offen -> abbrechen; Hauptrahmen-Laden und App-Adressen frei
  const weg = { get url() { throw new Error('disposed'); }, parent: null };
  assert.deepEqual(frage({ url: 'https://example.com/', frame: weg, resourceType: 'image', webContents: ansicht }), { cancel: true });
  assert.deepEqual(frage({ url: 'http://127.0.0.1:8765/flut', resourceType: 'xhr', webContents: ansicht }), { cancel: true });
  assert.deepEqual(frage({ url: 'app://-/x.js', resourceType: 'script', webContents: ansicht }), {});
  assert.deepEqual(frage({ url: 'app://-/index.html', frame: weg, resourceType: 'mainFrame', webContents: ansicht }), {});

  // Konzept geschlossen (Rahmen aus dem Baum): Nachfrist 5 s, danach frei
  ansicht.rahmen = [haupt];
  assert.deepEqual(frage({ url: 'http://127.0.0.1:8765/flut', resourceType: 'xhr', webContents: ansicht }), { cancel: true }, 'Nachfrist');
  const echtesJetzt = Date.now;
  try {
    Date.now = () => echtesJetzt() + NACHFRIST_MS + 50;
    assert.deepEqual(frage({ url: 'http://127.0.0.1:8765/', resourceType: 'xhr', webContents: ansicht }), {}, 'nach der Nachfrist');
  } finally {
    Date.now = echtesJetzt;
  }

  // Rahmen navigiert erlaubt anderswohin (Einbettung): faellt aus der Menge
  const zweiter = { url: 'about:blank', parent: haupt, frameTreeNodeId: 11, processId: 9, routingId: 11 };
  ansicht.rahmen.push(zweiter);
  ansicht.navigiert(zweiter, K);
  assert.deepEqual(frage({ url: 'https://example.com/', resourceType: 'image', webContents: ansicht }), { cancel: true });
  ansicht.navigiert(zweiter, 'https://www.figma.com/embed');
  assert.deepEqual(frage({ url: 'https://www.figma.com/x.js', frame: zweiter, resourceType: 'script', webContents: ansicht }), {});

  // Ansicht zerstoert: Menge weg; ohne Ansicht keine Renderer-Anfrage
  ansicht.zerstoert();
  assert.deepEqual(frage({ url: 'https://example.com/', resourceType: 'image', webContents: ansicht }), {});
  assert.deepEqual(frage({ url: 'https://example.com/', resourceType: 'image' }), {});
});
