const assert = require('node:assert/strict');
const test = require('node:test');

const { anfrageEntscheidung, anfrageSperren, istEingesperrterRahmen, rahmenNavigation, rueckhaltAnmelden } = require('./konzept-rahmen');

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

test('anfrageEntscheidung (R44): Rahmen bekannt, unbekannt, Hauptrahmen', () => {
  const basis = { url: 'https://example.com/x', resourceType: 'image', referrer: '', konzeptOffen: false };
  assert.equal(anfrageEntscheidung({ ...basis, rahmen: [K, 'app://-/index.html'] }), true);
  assert.equal(anfrageEntscheidung({ ...basis, rahmen: ['app://-/index.html'], konzeptOffen: true }), false);
  assert.equal(anfrageEntscheidung({ ...basis, rahmen: null, konzeptOffen: true }), true);
  assert.equal(anfrageEntscheidung({ ...basis, rahmen: null, konzeptOffen: false }), false);
  assert.equal(anfrageEntscheidung({ ...basis, rahmen: null, referrer: K }), true);
  assert.equal(anfrageEntscheidung({ ...basis, url: 'app://-/x.js', rahmen: null, konzeptOffen: true }), false);
  assert.equal(anfrageEntscheidung({ ...basis, resourceType: 'mainFrame', rahmen: null, konzeptOffen: true }), false);
});

test('Rueckhalt: bricht Anfragen aus dem Rahmen (oder seinem Kind) ab, laesst andere Rahmen in Ruhe', () => {
  let hoerer = null;
  rueckhaltAnmelden({ webRequest: { onBeforeRequest: (fn) => { hoerer = fn; } } });
  const frage = (details) => {
    let antwort;
    hoerer(details, (a) => { antwort = a; });
    return antwort;
  };
  const haupt = { url: 'app://-/index.html', parent: null };
  const konzept = { url: K, parent: haupt };
  const kind = { url: 'about:srcdoc', parent: konzept };
  assert.deepEqual(frage({ url: 'https://example.com/', frame: konzept, resourceType: 'image' }), { cancel: true });
  assert.deepEqual(frage({ url: 'https://example.com/', frame: kind, resourceType: 'subFrame' }), { cancel: true });
  assert.deepEqual(frage({ url: 'data:image/png;base64,AA', frame: konzept, resourceType: 'image' }), {});
  assert.deepEqual(frage({ url: 'https://example.com/', frame: haupt, resourceType: 'xhr' }), {});
  const youtube = { url: 'https://www.youtube.com/embed/x', parent: haupt };
  assert.deepEqual(frage({ url: 'https://www.youtube.com/y.js', frame: youtube, resourceType: 'script' }), {});
  const bericht = { url: 'app://workspace/bg-tasks/x/index.html', parent: haupt };
  assert.deepEqual(frage({ url: 'https://cdn.example.com/chart.js', frame: bericht, resourceType: 'script' }), {});
  // ohne Rahmen: nach der Ansicht entscheiden
  const ansicht = (urls) => ({ mainFrame: { framesInSubtree: urls.map((url) => ({ url })) } });
  assert.deepEqual(frage({ url: 'https://example.com/', resourceType: 'image', webContents: ansicht(['app://-/index.html']) }), {});
  assert.deepEqual(frage({ url: 'https://example.com/', resourceType: 'image', webContents: ansicht(['app://-/index.html', K]) }), { cancel: true });
  assert.deepEqual(frage({ url: 'https://example.com/', resourceType: 'image' }), {}, 'ohne Ansicht: keine Renderer-Anfrage');
  const weg = { get url() { throw new Error('disposed'); }, parent: null };
  assert.deepEqual(frage({ url: 'https://example.com/', frame: weg, resourceType: 'image', webContents: ansicht([K]) }), { cancel: true });
  assert.deepEqual(frage({ url: 'app://-/index.html', frame: weg, resourceType: 'mainFrame', webContents: ansicht([K]) }), {});
});
