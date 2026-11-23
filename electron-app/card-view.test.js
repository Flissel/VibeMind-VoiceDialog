// Kartenansicht in der Huelle: dieselben Beispiele wie spaces/ideas/tests/test_kartenansicht.py
// (erfundene Beispiele in den Formen des Bestands). Regel: nichts Technisches in dem, was ein Mensch liest.
const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const cv = require(path.join(__dirname, 'renderer', 'card-view.js'));

const ALTES_SCHEMA = { type: 'object', required: ['type', 'pros', 'cons'],
    properties: { type: { const: 'pros_cons_table' }, pros: { type: 'array' } } };

const PRO_CONTRA = {
    id: 'a1b2c3d4', title: 'Karte_1_App', content: 'Karte_1_App', node_type: 'note',
    metadata: { width: 200.0, height: 120.0 }, format_schema: ALTES_SCHEMA,
    content_json: {
        type: 'pros_cons_table',
        pros: [{ point: 'Benutzerfreundliche Oberfläche', weight: 3, evidence: 'schnell' },
            { point: 'Effizienter Query-Builder', weight: 2 }],
        cons: [{ point: 'Hohe Lernkurve für fortgeschrittene Features', weight: 1 }],
    },
};
const VORLAGE = {
    id: 'b1b2c3d4', title: 'Karte_2', content: 'Karte_2', node_type: 'note',
    metadata: {}, format_schema: { type: 'object' },
    content_json: { type: 'technical_specs', title: 'Technische Spezifikation', component: 'Betroffene Komponente',
        specifications: [{ category: 'Performance', priority: 'must_have', requirement: 'Konkrete Anforderung' }] },
};
const SPECS = {
    id: 'c1b2c3d4', title: 'Karte_3_Spec', content: 'Karte_3_Spec', node_type: 'note', metadata: {},
    content_json: { type: 'technical_specs', specifications: [
        { category: 'Security', priority: 'must_have', requirement: 'PSD2-konforme Zahlungsfreigabe',
            acceptance_criteria: 'SCA bei jeder Zahlung' },
        { category: 'Performance', requirement: 'Zahlung in unter 2 Sekunden' }] },
};
const NOTIZ = {
    id: 'd1b2c3d4', title: 'Karte_4_API', node_type: 'note', metadata: {}, content_json: null,
    content: 'Beispiel REST-API integration.\n\nEndpoints:\n- /api/v1/orte (Suche)\n'
        + '- /api/v1/fahrten (Plan)\n\nAuth: OAuth2 client_credentials flow.',
};
const NUR_TITEL = { id: 'e1b2c3d4', title: 'Karte 5', content: 'Karte 5', node_type: 'note',
    metadata: {}, content_json: null };
const RECHERCHE = {
    id: '00000000-0000-4000-8000-00000000000c', title: 'Research: Bubble A 2026-09-17 15:13:39',
    node_type: 'research', content_json: null, format_schema: null,
    metadata: { width: 320.0, height: 220.0, artifact_ref: 'artifact_v1_01ABC', citation_count: 41 },
    content: '# Wettbewerbsanalyse: Bubble A\n\n**Auftraggeber:** Bubble A (B2C Mobile App)\n'
        + '**Sprache:** Deutsch\n\n---\n\n## 0. Executive Summary\n\nBubble A tritt in einen Markt mit '
        + '**zwei** Wettbewerbsringen ein.\n\nDas ergibt ein echtes Blue-Ocean-Feld.\n\n'
        + '## 1. Wettbewerbsprofile\n\n| App | Land |\n|---|---|\n| App X | US |\n\n## 2. Quellen\n\n- Quelle A\n',
};
const SWOT = {
    id: 'f1b2c3d4', title: 'Karte_6', content: 'Karte_6', node_type: 'note', metadata: {},
    content_json: { type: 'swot', subject: 'Was analysiert wird',
        strengths: [{ point: 'Starke Marktposition', impact: 'high' }],
        weaknesses: [{ point: 'Mangelnde Ressourcen' }], opportunities: [], threats: [] },
};
const NEU_FORMATIERT = {
    id: 'a2b2c3d4', title: 'Preise', content: 'A kostet 1\nB kostet 2', node_type: 'note', metadata: {},
    format_schema: { type: 'table' }, content_json: { type: 'table', title: 'Preise', text: 'A kostet 1\nB kostet 2' },
};
const VORSCHLAG = { id: 'a3b2c3d4', title: 'Karte 8', content: 'Eine Kombination aus NFC und Offline-Routing.',
    node_type: 'note', content_json: null, metadata: { ai_generated: true, source_title: 'Karte_7_Quelle' } };

const ALLE = [PRO_CONTRA, VORLAGE, SPECS, NOTIZ, NUR_TITEL, RECHERCHE, SWOT, NEU_FORMATIERT, VORSCHLAG];
const FELDNAMEN = /[{}[\]]|\b[a-z]+_[a-z_]+\b|must_have|pros_cons|content_json|artifact_ref/;

function* lesbareTexte(ansicht) {
    if (Array.isArray(ansicht)) for (const v of ansicht) yield* lesbareTexte(v);
    else if (ansicht && typeof ansicht === 'object') {
        for (const [key, value] of Object.entries(ansicht)) if (key !== 'id') yield* lesbareTexte(value);
    } else if (typeof ansicht === 'string') yield ansicht;
}

test('Format steht im strukturierten Inhalt, nicht im Schema-Typ', () => {
    assert.equal(cv.cardFormat(PRO_CONTRA), 'pros_cons');
    assert.equal(cv.cardFormat(VORLAGE), 'technical_specs');
    assert.equal(cv.cardFormat({ format_schema: ALTES_SCHEMA }), 'pros_cons');
    assert.equal(cv.cardFormat({ format_schema: { type: 'kanban' } }), 'kanban');
    assert.equal(cv.cardFormat({ format_schema: { type: 'object' } }), 'note');
    assert.equal(cv.cardFormat(RECHERCHE), 'research');
    assert.equal(cv.cardFormat(NOTIZ), 'note');
});

test('Pro und Contra zeigt Punkte mit Seite und Anzahl', () => {
    assert.deepEqual(cv.cardShort(PRO_CONTRA), {
        titel: 'Karte 1 App', art: 'Pro und Contra',
        zeilen: ['Pro: Benutzerfreundliche Oberfläche', 'Pro: Effizienter Query-Builder',
            'Contra: Hohe Lernkurve für fortgeschrittene Features'],
        umfang: '2 Pro · 1 Contra', quelle: null, leer: false,
    });
});

test('Vorlagentext gilt als leer', () => {
    const k = cv.cardShort(VORLAGE);
    assert.deepEqual([k.art, k.zeilen, k.umfang, k.leer], ['Anforderungen', [], null, true]);
});

test('Anforderungen zeigen die Anforderung', () => {
    const k = cv.cardShort(SPECS);
    assert.deepEqual(k.zeilen, ['PSD2-konforme Zahlungsfreigabe', 'Zahlung in unter 2 Sekunden']);
    assert.equal(k.umfang, '2 Anforderungen');
});

test('Text, der nur den Titel wiederholt, zeigt nichts doppelt', () => {
    const k = cv.cardShort(NUR_TITEL);
    assert.deepEqual([k.titel, k.zeilen, k.leer], ['Karte 5', [], true]);
});

test('Notiz zeigt die ersten Zeilen ohne Aufzaehlungszeichen', () => {
    const k = cv.cardShort(NOTIZ);
    assert.equal(k.art, 'Notiz');
    assert.deepEqual(k.zeilen, ['Beispiel REST-API integration.', 'Endpoints:', '/api/v1/orte (Suche)']);
});

test('Recherche zeigt die Zusammenfassung, Datum und Quellen', () => {
    const k = cv.cardShort(RECHERCHE);
    assert.equal(k.titel, 'Recherche: Bubble A');
    assert.equal(k.art, 'Recherche');
    assert.deepEqual(k.zeilen, ['Bubble A tritt in einen Markt mit zwei Wettbewerbsringen ein.', 'Das ergibt ein echtes Blue-Ocean-Feld.']);
    assert.equal(k.quelle, 'Recherche vom 17.09.2026 · 41 Quellen');
    assert.equal(k.umfang, '4 Abschnitte');
});

test('SWOT ohne Vorlagentext', () => {
    const k = cv.cardShort(SWOT);
    assert.deepEqual(k.zeilen, ['Stärken: Starke Marktposition', 'Schwächen: Mangelnde Ressourcen']);
    assert.equal(k.umfang, '1 Stärke · 1 Schwäche');
});

test('neu formatierte Karte zeigt ihren Text unter dem neuen Format', () => {
    const k = cv.cardShort(NEU_FORMATIERT);
    assert.deepEqual([k.art, k.zeilen], ['Tabelle', ['A kostet 1', 'B kostet 2']]);
});

test('Vorschlag nennt seine Herkunft', () => {
    assert.equal(cv.cardShort(VORSCHLAG).quelle, 'Vorschlag aus „Karte 7 Quelle“');
});

test('lange Zeilen werden gekuerzt', () => {
    const k = cv.cardShort({ ...NOTIZ, content: 'Wort '.repeat(100) });
    assert.ok(Array.from(k.zeilen[0]).length <= cv.CARD_LINE_CHARS);
    assert.ok(k.zeilen[0].endsWith('…'));
});

test('weitere Formate', () => {
    const faelle = [
        [{ type: 'action_list', items: [{ task: 'Angebot schicken', status: 'completed' }, { task: 'Anrufen' }] },
            ['Angebot schicken (erledigt)', 'Anrufen'], '1 von 2 erledigt', 'Aufgabenliste'],
        [{ type: 'kanban', columns: [{ name: 'Offen', cards: [{ title: 'Logo' }] }, { name: 'Fertig', cards: [] }] },
            ['Offen (1): Logo'], '1 Karte in 2 Spalten', 'Kanban'],
        [{ type: 'table', headers: ['Posten', 'Preis'], rows: [['Stand', '900'], ['Druck', '120']] },
            ['Stand · 900', 'Druck · 120'], '2 Zeilen', 'Tabelle'],
        [{ type: 'hierarchy', levels: [{ items: [{ name: 'Fragen', children: [{ name: 'Wer?' }] }] }] },
            ['Wer?'], '1 Punkt', 'Gliederung'],
        [{ type: 'user_story', stories: [{ role: 'Als Kunde', want: 'möchte ich teilen', benefit: 'x' }] },
            ['Als Kunde möchte ich teilen'], '1 Geschichte', 'Nutzergeschichten'],
        [{ type: 'flowchart', nodes: [{ id: 's', type: 'start', label: 'Start' }, { id: 'p', type: 'process', label: 'Antrag prüfen' }] },
            ['Antrag prüfen'], '1 Schritt', 'Ablauf'],
        [{ type: 'mindmap', center: { label: 'Messe' }, branches: [{ label: 'Stand', children: [{ label: 'Licht' }] }] },
            ['Messe', 'Licht'], '1 Zweig', 'Mindmap'],
    ];
    for (const [inhalt, zeilen, umfang, art] of faelle) {
        const k = cv.cardShort({ id: 'a1b2c3d4', title: 'X', content: 'X', content_json: inhalt });
        assert.deepEqual([k.zeilen, k.umfang, k.art], [zeilen, umfang, art], inhalt.type);
    }
});

test('nichts Technisches auf keiner Karte', () => {
    for (const zeile of ALLE) {
        for (const text of lesbareTexte(cv.cardShort(zeile))) {
            if (text.includes('/api/')) continue; // Pfade, die ein Mensch selbst notiert hat, bleiben
            assert.doesNotMatch(text, FELDNAMEN, `${zeile.title}: ${text}`);
        }
    }
});

test('kaputte Formen brechen nichts', () => {
    for (const inhalt of [{ type: 'pros_cons', pros: 'x' }, { type: 'swot', strengths: [null, 3] },
        { type: 'kanban', columns: [{ cards: 'x' }] }, { type: 5 }, 'kein dict']) {
        const k = cv.cardShort({ id: 'a1b2c3d4', title: null, content: null, content_json: inhalt });
        assert.equal(k.titel, 'Ohne Titel');
        assert.equal(k.leer, true);
    }
});

test('aufgeklappt: alles lesbar, Verbindungen nach Titel, geloeschte Ziele fallen weg', () => {
    const kanten = [{ from_node_id: 'a1b2c3d4', to_node_id: 'c1b2c3d4', edge_type: 'related' },
        { from_node_id: 'd1b2c3d4', to_node_id: 'a1b2c3d4', edge_type: 'expanded_from' },
        { from_node_id: 'a1b2c3d4', to_node_id: 'e1b2c3d4', edge_type: 'parent_child' },
        { from_node_id: 'a1b2c3d4', to_node_id: 'geloescht', edge_type: 'related' }];
    const titel = new Map([['c1b2c3d4', 'Karte 3 Spec'], ['d1b2c3d4', 'Karte 4 API'], ['e1b2c3d4', 'Karte 5']]);
    const ansicht = cv.cardRead(PRO_CONTRA, kanten, titel);
    assert.deepEqual(ansicht.abschnitte, [
        { ueberschrift: 'Pro', zeilen: ['Benutzerfreundliche Oberfläche', 'Effizienter Query-Builder'] },
        { ueberschrift: 'Contra', zeilen: ['Hohe Lernkurve für fortgeschrittene Features'] },
    ]);
    assert.deepEqual(ansicht.verbindungen, [
        { id: 'c1b2c3d4', titel: 'Karte 3 Spec', art: 'verwandt' },
        { id: 'd1b2c3d4', titel: 'Karte 4 API', art: 'Ausgangspunkt' },
        { id: 'e1b2c3d4', titel: 'Karte 5', art: 'Unterpunkt' },
    ]);
    assert.equal(ansicht.text, null);
    for (const text of lesbareTexte(ansicht)) assert.doesNotMatch(text, FELDNAMEN, text);
    // Kanten, wie der Canvas sie laedt (type statt edge_type), und von der anderen Seite gelesen
    const von = cv.cardRead(SPECS, [{ from_node_id: 'a1b2c3d4', to_node_id: 'c1b2c3d4', type: 'parent_child' }],
        new Map([['a1b2c3d4', 'Karte 1 App']]));
    assert.deepEqual(von.verbindungen, [{ id: 'a1b2c3d4', titel: 'Karte 1 App', art: 'Oberpunkt' }]);
});

test('Recherche aufgeklappt hat Gliederung und den vollen Text', () => {
    const ansicht = cv.cardRead(RECHERCHE, [], new Map());
    assert.deepEqual(ansicht.abschnitte.map((a) => a.ueberschrift),
        ['Wettbewerbsanalyse: Bubble A', '0. Executive Summary', '1. Wettbewerbsprofile', '2. Quellen']);
    assert.deepEqual(ansicht.abschnitte[2].zeilen, ['App · Land', 'App X · US']);
    assert.equal(ansicht.text, RECHERCHE.content);
    assert.equal(ansicht.leer, false);
});

test('Zeilen, wie der Canvas sie bekommt (Titel und Text unter content), lesen sich gleich', () => {
    const geladen = { id: PRO_CONTRA.id, type: 'note', position: { x: 1, y: 2 },
        content: { title: PRO_CONTRA.title, text: PRO_CONTRA.content }, content_json: PRO_CONTRA.content_json };
    assert.deepEqual(cv.cardShort(geladen), cv.cardShort(PRO_CONTRA));
    const alsText = { ...NOTIZ, content_json: JSON.stringify({ type: 'technical_specs', specifications: [{ requirement: 'Schnell' }] }) };
    assert.deepEqual(cv.cardShort(alsText).zeilen, ['Schnell']);
});

test('Markdown wird gelesen, nie ausgefuehrt', () => {
    const md = cv.renderMarkdown(RECHERCHE.content
        + '\n<script>alert(1)</script>\n[Quelle](https://example.org/a?b="c") und <img src=x onerror=alert(1)>\n1. eins\n2. zwei');
    assert.doesNotMatch(md.html, /<script|<img|onerror=alert\(1\)>|href=/);
    assert.match(md.html, /&lt;script&gt;/);
    assert.match(md.html, /<h2 id="kv-h-0">Wettbewerbsanalyse: Bubble A<\/h2>/);
    assert.match(md.html, /<table><thead><tr><th>App<\/th><th>Land<\/th><\/tr><\/thead><tbody><tr><td>App X<\/td><td>US<\/td><\/tr><\/tbody><\/table>/);
    assert.match(md.html, /<strong>zwei<\/strong>/);
    assert.match(md.html, /<ul>\n<li>Quelle A<\/li>\n<\/ul>/);
    assert.match(md.html, /<ol>\n<li>eins<\/li>\n<li>zwei<\/li>\n<\/ol>/);
    assert.match(md.html, /<span class="kv-link" role="link" tabindex="0" data-url="https:\/\/example.org\/a\?b=%22c%22"[^>]*>Quelle<\/span>/);
    assert.deepEqual(md.headings.map((h) => h.text),
        ['Wettbewerbsanalyse: Bubble A', '0. Executive Summary', '1. Wettbewerbsprofile', '2. Quellen']);
});

// ---- Einbindung: Canvas zeigt die Karten als Raster, Abfrage laeuft weiter, Ansicht umschaltbar ----
const fs = require('node:fs');
const vm = require('node:vm');

function canvasWorld() {
    const boards = [];
    const listeners = [];
    const container = { innerHTML: '', appendChild() {} };
    const store = new Map();
    const window = {
        localStorage: { getItem: (k) => (store.has(k) ? store.get(k) : null), setItem: (k, v) => store.set(k, String(v)) },
        dispatchEvent: () => true,
        CardView: {
            board(doc, options) {
                const b = { element: { parentNode: null }, updates: [], opened: [], closed: 0, options,
                    mount(c) { this.element.parentNode = c; }, update(n, e) { this.updates.push([n.length, e.length]); },
                    open(id) { this.opened.push(id); return true; }, close() { this.closed += 1; }, setQuery() {}, roots: [], setRoot(id) { this.roots.push(id); } };
                boards.push(b);
                return b;
            },
        },
        renderMermaidIntoContainer: async () => true,
        mermaid: {},
    };
    let polls = 0;
    const context = {
        window, console: { log() {}, warn() {}, error() {} },
        document: { getElementById: () => null, querySelector: () => null, createElement: () => ({ addEventListener() {} }),
            addEventListener: (...a) => listeners.push(a) },
        setInterval: () => { polls += 1; return polls; }, clearInterval() {}, setTimeout: () => 0, clearTimeout() {},
        CustomEvent: class { constructor(type, init) { this.type = type; this.detail = init && init.detail; } },
    };
    vm.runInNewContext(fs.readFileSync(path.join(__dirname, 'renderer', 'universe_canvas.js'), 'utf8'), context);
    const canvas = Object.create(window.UniverseCanvas.prototype);
    canvas.container = container;
    canvas.nodes = new Map();
    canvas.edges = [];
    canvas._showBanner = () => {};
    return { canvas, boards, window, store, polls: () => polls };
}

test('der Canvas zeigt die Karten als Raster und laedt sie weiter alle 5 s', () => {
    const w = canvasWorld();
    w.canvas.loadNodes([PRO_CONTRA, SPECS], [{ from_node_id: 'a1b2c3d4', to_node_id: 'c1b2c3d4', type: 'related' }]);
    assert.equal(w.boards.length, 1);
    assert.equal(w.boards[0].element.parentNode, w.canvas.container);
    assert.deepEqual(w.boards[0].updates, [[2, 1]]);
    assert.equal(w.canvas._mermaidMode, true, 'Aenderungen laden neu wie beim Verbindungsbild');
    assert.equal(w.polls(), 1);
    w.canvas.loadNodes([PRO_CONTRA, SPECS, NOTIZ], []);
    assert.equal(w.boards.length, 1, 'ein Raster, das bleibt: Suche, Groesse und offene Karte gehen nicht verloren');
    assert.deepEqual(w.boards[0].updates, [[2, 1], [3, 0]]);
    assert.equal(w.canvas.showCard('c1b2c3d4'), true);
    assert.deepEqual(w.boards[0].opened, ['c1b2c3d4']);
});

test('Umschalten aufs Verbindungsbild und zurueck, gemerkt fuer den naechsten Start', () => {
    const w = canvasWorld();
    w.canvas.loadNodes([PRO_CONTRA], []);
    w.boards[0].options.onGraph();
    assert.equal(w.store.get('vibemind.canvas.ansicht'), 'graph');
    assert.equal(w.canvas.showCard('a1b2c3d4'), false, 'im Verbindungsbild oeffnet der Chat keine Karte im Raster');
    w.canvas.showView('karten');
    assert.equal(w.store.get('vibemind.canvas.ansicht'), 'karten');
    assert.equal(w.boards[0].updates.length, 2);
});

test('eine andere Bubble: die offene Karte der letzten schliesst', () => {
    const w = canvasWorld();
    w.canvas.loadNodes([PRO_CONTRA], []);
    w.canvas.setBubble('0000000b');
    assert.equal(w.boards[0].closed, 1);
    w.canvas.setBubble('0000000b');
    assert.equal(w.boards[0].closed, 1);
});

test('Quellen sind Links: nur http/https, Satzzeichen bleiben Text', () => {
    const md = cv.renderMarkdown([
        '## Quellen',
        '1. Beispiel, A. (2026). Titel. Abgerufen am 1.1.2026 von https://example.org/bericht?x=1&y=2.',
        '2. <https://example.com/seite_(2)>',
        '3. (siehe https://example.net/a__b__c), weiter',
        '4. javascript:alert(1) und file:///C:/geheim und [boese](javascript:alert(1))',
        '5. Quelle:https://example.org/z',
    ].join('\n'));
    const urls = [...md.html.matchAll(/data-url="([^"]*)"/g)].map((m) => m[1].replace(/&amp;/g, '&'));
    assert.deepEqual(urls, [
        'https://example.org/bericht?x=1&y=2',
        'https://example.com/seite_(2)',
        'https://example.net/a__b__c',
        'https://example.org/z',
    ]);
    assert.match(md.html, /y=2<\/span>\./, 'der Punkt am Satzende gehoert nicht zur Adresse');
    assert.doesNotMatch(md.html, /<strong>/, 'Unterstriche in Adressen werden nicht fett');
    assert.doesNotMatch(md.html, /data-url="(javascript|file)/);
    assert.equal(cv.safeUrl('javascript:alert(1)'), null);
    assert.equal(cv.safeUrl('https://user:pw@example.org/'), null);
    assert.equal(cv.safeUrl('https://example.org/a b'), null);
    assert.equal(cv.safeUrl('http://example.org'), 'http://example.org/');
});

test('ein Klick auf einen Link oeffnet ihn im Browser des Systems, nie in der App', () => {
    const external = require('./external-link');
    const opened = [];
    const shell = { openExternal: async (url) => { opened.push(url); } };
    return Promise.all([
        external.openExternal(shell, 'https://example.org/x'),
        external.openExternal(shell, 'javascript:alert(1)'),
        external.openExternal(shell, 'file:///C:/Windows'),
        external.openExternal(shell, 42),
    ]).then((results) => {
        assert.deepEqual(results.map((r) => r.success), [true, false, false, false]);
        assert.deepEqual(opened, ['https://example.org/x']);
        const main = fs.readFileSync(path.join(__dirname, 'main.js'), 'utf8');
        assert.match(main, /ipcMain\.handle\('app:open-external', \(_event, url\) => require\('\.\/external-link'\)\.openExternal\(shell, url\)\)/);
        const preload = fs.readFileSync(path.join(__dirname, 'preload.js'), 'utf8');
        assert.match(preload, /openExternal: \(url\) => ipcRenderer\.invoke\('app:open-external', url\)/);
    });
});

test('Wiki-Ueberschriften "== Titel ==" werden Ueberschriften', () => {
    assert.deepEqual(cv.headingOf('== Abschnitt 1 =='), { level: 1, text: 'Abschnitt 1' });
    assert.deepEqual(cv.headingOf('=== Teil ==='), { level: 2, text: 'Teil' });
    assert.equal(cv.headingOf('== offen'), null);
    assert.equal(cv.headingOf('a == b'), null);
    const md = cv.renderMarkdown('Vorab\n== Abschnitt 1 ==\nText\n=== Teil ===\nmehr');
    assert.match(md.html, /<h2 id="kv-h-0">Abschnitt 1<\/h2>/);
    assert.match(md.html, /<h3 id="kv-h-1">Teil<\/h3>/);
    assert.doesNotMatch(md.html, /==/);
    assert.equal(cv.plain('== Abschnitt 1 =='), 'Abschnitt 1', 'auf der kleinen Karte ohne Gleichheitszeichen');
});

test('eine leere Bubble zeigt das Raster mit "Noch keine Notizen", nicht die alte Werkzeugleiste', () => {
    const w = canvasWorld();
    let reinit = 0;
    w.canvas.init = () => { reinit += 1; };
    w.canvas.loadNodes([], []);
    assert.equal(w.boards.length, 1);
    assert.equal(w.boards[0].element.parentNode, w.canvas.container);
    assert.deepEqual(w.boards[0].updates, [[0, 0]]);
    assert.equal(w.polls(), 1, 'Karten, die Agenten in die leere Bubble schreiben, erscheinen');
    w.canvas.loadNodes([PRO_CONTRA], []);
    w.canvas.loadNodes(null);
    assert.deepEqual(w.boards[0].updates, [[0, 0], [1, 0], [0, 0]], 'dasselbe Raster, nur leer');
    assert.equal(reinit, 0, 'der alte DOM-Canvas mit seiner Werkzeugleiste wird nicht aufgebaut');
});

test('das Raster sagt in einer leeren Bubble "Noch keine Notizen"', () => {
    const made = [];
    const fake = (tag) => {
        const node = { tag, children: [], className: '', textContent: '', value: '', hidden: false, dataset: {}, style: { setProperty() {} },
            append(...c) { node.children.push(...c); }, replaceChildren(...c) { node.children = c; },
            setAttribute() {}, addEventListener() {}, remove() {}, focus() {}, querySelector: () => null, querySelectorAll: () => [] };
        made.push(node);
        return node;
    };
    const doc = { createElement: fake, addEventListener() {}, removeEventListener() {}, defaultView: null };
    const board = cv.board(doc, {});
    board.mount({ appendChild() {}, append() {} });
    board.update([], []);
    const none = made.find((n) => n.className === 'kv-none');
    assert.equal(none.hidden, false);
    assert.match(none.textContent, /^Noch keine Notizen/);
    board.update([PRO_CONTRA], []);
    assert.equal(none.hidden, true);
});

test('Zoom der Karten: ohne gespeicherte Groesse die mittlere Stufe, Grenzen fuer die Leiste der Bubble', () => {
    const fake = (tag) => {
        const node = { tag, children: [], className: '', textContent: '', value: '', hidden: false, disabled: false, dataset: {}, style: { setProperty() {} },
            append(...c) { node.children.push(...c); }, replaceChildren(...c) { node.children = c; },
            setAttribute() {}, addEventListener() {}, remove() {}, focus() {}, querySelector: () => null, querySelectorAll: () => [] };
        return node;
    };
    const stored = {};
    const store = { getItem: (k) => (k in stored ? stored[k] : null), setItem: (k, v) => { stored[k] = v; } };
    const doc = { createElement: fake, addEventListener() {}, removeEventListener() {}, defaultView: { localStorage: store } };
    const board = cv.board(doc, {});
    board.update([PRO_CONTRA], []);
    assert.deepEqual(board.state, { count: 1, shown: 1, query: '', smaller: true, bigger: true }, 'nicht die kleinste Stufe');
    assert.equal(board.zoom(1), true);
    assert.equal(board.zoom(1), true);
    assert.equal(board.zoom(1), false, 'groesste Stufe');
    assert.equal(board.state.bigger, false);
    assert.equal(stored['vibemind.karten.groesse'], '4');
    board.setQuery('nichts davon');
    assert.equal(board.state.shown, 0);
    assert.equal(cv.board(doc, {}).state.bigger, false, 'die gespeicherte Groesse gilt beim naechsten Oeffnen');
});

test('kein technischer Hinweis ("loadNodes: 98 nodes, 82 edges") auf dem Bildschirm', () => {
    const source = fs.readFileSync(path.join(__dirname, 'renderer', 'universe_canvas.js'), 'utf8');
    assert.doesNotMatch(source, /cy-debug-banner/);
    assert.doesNotMatch(source, /loadNodes: \$\{/);
    const body = /_showBanner\(msg[^)]*\) \{([\s\S]*?)\n    \}/.exec(source)[1];
    assert.doesNotMatch(body, /document|createElement/, 'nur ins Protokoll');
});

test('Esc schliesst nur die Karte, die App verlaesst die Bubble dabei nicht', () => {
    const source = fs.readFileSync(path.join(__dirname, 'renderer', 'card-view.js'), 'utf8');
    assert.match(source, /doc\.addEventListener\('keydown', onKey, true\)/, 'vor dem Fenster (multiverse.js: Esc verlaesst die Bubble)');
    assert.match(source, /e\.stopImmediatePropagation\(\);\s*close\(\);/);
    assert.match(source, /search\.addEventListener\('keydown', \(e\) => \{[\s\S]*?e\.stopPropagation\(\);/, 'Tippen in der Suche wechselt keinen Space');
    const html = fs.readFileSync(path.join(__dirname, 'renderer', 'index.html'), 'utf8');
    assert.ok(html.indexOf('src="card-view.js"') > 0 && html.indexOf('src="card-view.js"') < html.indexOf('src="universe_canvas.js"'));
    const css = fs.readFileSync(path.join(__dirname, 'renderer', 'styles.css'), 'utf8');
    assert.match(css, /styles\/card-view\.css/);
    const chat = fs.readFileSync(path.join(__dirname, 'renderer', 'ideas-chat.js'), 'utf8');
    assert.match(chat, /'Chat einklappen'/);
    assert.match(chat, /canvas\.showCard\(id\)/);
});

test('Suche nach Titel ohne Gross/klein, Umlaute und Unterstriche', () => {
    assert.ok(cv.matches('Karte_1_App', 'karte 1 app'));
    assert.ok(cv.matches('Zahlungsübersicht', 'uebersicht'));
    assert.ok(cv.matches('irgendwas', '  '));
    assert.ok(!cv.matches('Karte 5', 'import'));
});

// Lauf 3 der Pruefung: Kanban "Noch ohne Inhalt", Wurzel unsichtbar, Verweise nur Text.
test('Kanban liest beide Formen und den Inhalt von vor dem Formatieren', () => {
    const spalten = { id: 'k1', title: 'Karte 1', content: 'Karte 1', metadata: {},
        content_json: { type: 'kanban', columns: [{ title: 'Offen', items: ['Logo'] }, { name: 'Fertig', cards: [{ text: 'Flyer' }] }] } };
    assert.deepEqual(cv.cardShort(spalten).zeilen, ['Offen (1): Logo', 'Fertig (1): Flyer']);
    const todo = { id: 'k2', title: 'Karte 2', content: 'Karte 2', metadata: {},
        content_json: { type: 'kanban', todo: [{ title: 'Logo' }], doing: [{ text: 'Flyer' }], done: [] } };
    assert.deepEqual(cv.cardShort(todo).zeilen, ['Offen (1): Logo', 'In Arbeit (1): Flyer']);
    assert.equal(cv.cardShort(todo).leer, false);

    // das Gehirn formatiert: content_json traegt nur den Titel, der Inhalt stand im content_json davor
    const formatiert = { id: 'k3', title: 'Karte 3', content: 'Karte 3', metadata: {},
        format_schema: { type: 'kanban' },
        content_json: { type: 'kanban', title: 'Karte 3', text: 'Karte 3' },
        previous_content_json: JSON.stringify({ type: 'action_list', items: [{ task: 'Angebot schicken', status: 'completed' }, { task: 'Anrufen' }] }) };
    const kurz = cv.cardShort(formatiert);
    assert.equal(kurz.leer, false, 'nicht "Noch ohne Inhalt"');
    assert.equal(kurz.art, 'Kanban');
    assert.deepEqual(kurz.zeilen, ['Aufgaben: Angebot schicken (erledigt)', 'Aufgaben: Anrufen']);
    assert.equal(cv.cardRead(formatiert).leer, false);

    // Text steht im content, das Format traegt einen leeren Text
    const leererText = { id: 'k4', title: 'Karte 4', content: 'Offen: Logo\nIn Arbeit: Flyer', metadata: {},
        content_json: { type: 'kanban', title: 'Karte 4', text: '' } };
    assert.equal(cv.cardShort(leererText).leer, false);
    assert.match(cv.cardRead(leererText).text, /Offen: Logo/);

    // wirklich leer bleibt leer
    const leer = { id: 'k5', title: 'Karte 5', content: 'Karte 5', metadata: {}, content_json: { type: 'kanban', title: 'Karte 5', text: 'Karte 5' } };
    assert.equal(cv.cardShort(leer).leer, true);
});

test('eine Zusammenfassung nennt ihre Karten als Spruenge, nie als Kennung', () => {
    const titles = new Map([['00000000-0000-4000-8000-00000000000a', 'Karte 1'], ['00000000-0000-4000-8000-00000000000b', 'Karte 2'], ['z1', 'Zusammenfassung A']]);
    const summary = { id: 'z1', title: 'Zusammenfassung A', node_type: 'dokument',
        content: '## Kern\n\nAus „Karte 1“ folgt der Plan, „Karte 9“ gibt es nicht.',
        metadata: { art: 'zusammenfassung', quellen: ['00000000-0000-4000-8000-00000000000a', '00000000-0000-4000-8000-00000000000b', 'weg', '00000000-0000-4000-8000-00000000000a'] } };
    const view = cv.cardRead(summary, [], titles);
    assert.deepEqual(view.quellen, [{ id: '00000000-0000-4000-8000-00000000000a', titel: 'Karte 1' }, { id: '00000000-0000-4000-8000-00000000000b', titel: 'Karte 2' }],
        'bekannte Karten, jede einmal, eine geloeschte faellt weg');
    const html = cv.linkMentions(cv.renderMarkdown(view.text).html, titles, 'z1');
    assert.match(html, /„<span class="kv-jump" role="link" tabindex="0" data-card-id="00000000-0000-4000-8000-00000000000a" title="Karte öffnen">Karte 1<\/span>“/);
    assert.match(html, /„Karte 9“/, 'ein unbekannter Titel bleibt Text');
    assert.equal(cv.linkMentions('<p>„Zusammenfassung A“</p>', titles, 'z1'), '<p>„Zusammenfassung A“</p>', 'nie ein Sprung auf sich selbst');
    assert.equal(cv.linkMentions('<p>„<b>x</b>“</p>', titles, 'z1'), '<p>„<b>x</b>“</p>');
    const source = fs.readFileSync(path.join(__dirname, 'renderer', 'card-view.js'), 'utf8');
    assert.match(source, /closest\('\.kv-jump\[data-card-id\]'\)/, 'der Klick oeffnet die Karte im selben Leser');
});

test('die gesetzte Wurzel traegt an ihrer Karte das Zeichen "Wurzel"', () => {
    const made = [];
    const fake = (tag) => {
        const node = { tag, children: [], className: '', textContent: '', value: '', hidden: false, disabled: false, dataset: {}, style: { setProperty() {} },
            append(...c) { node.children.push(...c); }, replaceChildren(...c) { node.children = c; },
            setAttribute() {}, addEventListener() {}, remove() {}, focus() {}, querySelector: () => null, querySelectorAll: () => [] };
        made.push(node);
        return node;
    };
    const doc = { createElement: fake, addEventListener() {}, removeEventListener() {}, defaultView: null };
    const board = cv.board(doc, {});
    const a = { id: '00000000-0000-4000-8000-00000000000a', title: 'Karte 1', content: 'Text eins', metadata: {} };
    const b = { id: '00000000-0000-4000-8000-00000000000b', title: 'Karte 2', content: 'Text zwei', metadata: {} };
    board.update([a, b], []);
    const marks = () => made.filter((n) => n.className === 'kv-wurzel');
    assert.equal(marks().length, 0);
    assert.equal(board.setRoot('00000000-0000-4000-8000-00000000000b'), true);
    const grid = made.find((n) => n.className === 'kv-grid');
    const marked = grid.children.filter((card) => card.children.some((part) => part.className === 'kv-top'
        && part.children.some((c) => c.className === 'kv-wurzel' && c.textContent === 'Wurzel')));
    assert.deepEqual(marked.map((card) => card.dataset.cardId), ['00000000-0000-4000-8000-00000000000b']);
    assert.equal(board.setRoot('00000000-0000-4000-8000-00000000000b'), false, 'gleich: kein neues Zeichnen');
    board.setRoot(null);
    assert.equal(board.rootId, null);

    const canvas = fs.readFileSync(path.join(__dirname, 'renderer', 'universe_canvas.js'), 'utf8');
    assert.match(canvas, /row\.metadata\.wurzel/, 'aus der Zeile der Bubble (bubble_wurzel)');
    assert.match(canvas, /this\._board\.setRoot\(this\._wurzel\)/);
    assert.match(canvas, /this\._board\.setRoot\(null\)/, 'eine andere Bubble: die alte Wurzel gilt nicht');
});

test('eine Dokument-Karte heisst nach ihrer Art und sagt, aus wie vielen Karten sie ist', () => {
    const doc = { id: 'z2', title: 'Zusammenfassung B', node_type: 'dokument', content: 'Kurz gesagt: alles gut.',
        metadata: { art: 'zusammenfassung', quellen: ['a', 'b', 'c'] } };
    assert.equal(cv.cardShort(doc).art, 'Zusammenfassung');
    assert.equal(cv.cardShort(doc).quelle, 'aus 3 Karten');
    assert.equal(cv.cardShort({ ...doc, metadata: { art: 'white_paper', quellen: ['a'] } }).art, 'White Paper');
    assert.equal(cv.cardShort({ ...doc, metadata: { art: 'zusammenfassung' } }).quelle, null);
});

// Gruppieren nach Thema legt Ueberschrift-Karten an (metadata.gruppen_kopf), je eine ueber ihrer Spalte.
test('Gruppieren: die Ueberschrift-Karte steht als Kopf ueber den Karten ihrer Spalte, nicht als Karte', () => {
    const karte = (id, title, x, y, kopf = false) => ({ id, title, content: kopf ? '' : 'Text ' + title, node_type: 'note',
        position: { x, y }, metadata: kopf ? { gruppen_kopf: true } : {} });
    const knoten = [
        karte('00000000-0000-4000-8000-0000000000b1', 'Technik', 0, 0, true),
        karte('00000000-0000-4000-8000-0000000000b2', 'Geld', 240, 0, true),
        karte('00000000-0000-4000-8000-000000000a02', 'Karte 2', 0, 280),
        karte('00000000-0000-4000-8000-000000000a01', 'Karte 1', 0, 140),
        karte('00000000-0000-4000-8000-000000000a03', 'Karte 3', 240, 140),
        karte('00000000-0000-4000-8000-000000000a04', 'Karte 4', 900, 900),
    ];
    const gruppen = cv.grouped(knoten.map(cv.rowOf));
    assert.deepEqual(gruppen.map((g) => [g.head ? g.head.title : null, g.cards.map((c) => c.title)]),
        [['Technik', ['Karte 1', 'Karte 2']], ['Geld', ['Karte 3']], [null, ['Karte 4']]]);
    assert.deepEqual(cv.grouped([karte('00000000-0000-4000-8000-000000000a05', 'Karte 5', 0, 0)].map(cv.rowOf)).length, 1, 'ohne Ueberschriften wie bisher');

    const fake = (tag) => {
        const node = { tag, children: [], className: '', textContent: '', value: '', hidden: false, dataset: {}, style: { setProperty() {} },
            append(...c) { node.children.push(...c); }, replaceChildren(...c) { node.children = c; },
            setAttribute() {}, addEventListener() {}, remove() {}, focus() {}, querySelector: () => null, querySelectorAll: () => [] };
        return node;
    };
    const madeBy = (cls) => (n) => n.className === cls;
    const made = [];
    const doc = { createElement: (t) => { const n = fake(t); made.push(n); return n; }, addEventListener() {}, removeEventListener() {}, defaultView: null };
    const board = cv.board(doc, {});
    board.update(knoten, []);
    const grid = made.find(madeBy('kv-grid'));
    const reihe = grid.children.map((n) => n.className === 'kv-gruppe' ? '# ' + n.children[0].textContent
        : n.className.startsWith('kv-gruppe') ? '# ' + n.textContent : n.children[1].textContent);
    assert.deepEqual(reihe, ['# Technik', 'Karte 1', 'Karte 2', '# Geld', 'Karte 3', '# Ohne Gruppe', 'Karte 4']);
    assert.equal(board.state.count, 6, 'rows of the board; the line counts only cards');
    const zahl = made.find((n) => /^\d+ Karten$/.test(n.textContent) && n.className !== 'kv-gruppe-zahl');
    assert.equal(zahl.textContent, '4 Karten', 'Ueberschriften zaehlen nicht als Karten');
    const css = fs.readFileSync(path.join(__dirname, 'renderer', 'styles', 'card-view.css'), 'utf8');
    assert.match(css, /\.kv-gruppe \{\s*grid-column: 1 \/ -1;/);
    const canvas = fs.readFileSync(path.join(__dirname, 'renderer', 'universe_canvas.js'), 'utf8');
    assert.match(canvas, /if \(data\.metadata && data\.metadata\.gruppen_kopf === true\) el\.classList\.add\('canvas-node--kopf'\);/);
});

// Lauf 10: "6 Karten in 6 Spalten" (Offen, In Arbeit, Fertig, Offen, In Arbeit, Erledigt), columns in
// card width with the text upright. The form is the one of the window log (entered_bubble): the Ideas
// server sends columns (with a colour) AND todo/doing/done for one board. Titles invented.
test('Kanban in der Form des Gehirns: nur die Spalten, auf der Karte kurz, in der Leseansicht lesbar breit', () => {
    const KANBAN = { id: 'k6', title: 'Karte 6', content: 'Karte 6', metadata: { width: 200, height: 100 },
        format_schema: { type: 'kanban' }, format_type: 'kanban',
        content_json: { type: 'kanban', title: 'Karte 6',
            todo: [{ title: 'Punkt 1' }], doing: [{ title: 'Punkt 2' }], done: [{ title: 'Punkt 3' }],
            columns: [{ name: 'Offen', cards: [{ id: 'k3', title: 'Punkt 1' }, { id: 'k4', title: 'Punkt 4' }], color: '#6c757d' },
                { name: 'In Arbeit', cards: [{ id: 'k1', title: 'Punkt 2' }], color: '#0d6efd' },
                { name: 'Fertig', cards: [{ id: 'k2', title: 'Punkt 3' }], color: '#198754' }] } };
    const kurz = cv.cardShort(KANBAN);
    assert.equal(kurz.umfang, '4 Karten in 3 Spalten', 'columns only, todo/doing/done not a second time');
    assert.deepEqual(kurz.zeilen, ['Offen (2): Punkt 1', 'In Arbeit (1): Punkt 2', 'Fertig (1): Punkt 3'], 'one line per column');
    assert.equal(kurz.spalten, undefined, 'no columns side by side in card width');
    const read = cv.cardRead(KANBAN);
    assert.deepEqual(read.abschnitte.map((a) => a.ueberschrift), ['Offen', 'In Arbeit', 'Fertig'], 'the reading view: each column once');

    const css = require('node:fs').readFileSync(require('node:path').join(__dirname, 'renderer', 'styles', 'card-view.css'), 'utf8');
    assert.match(css, /\.kv-read-content\.kv-kanban \{[^}]*grid-auto-columns: minmax\(180px, 1fr\);[^}]*overflow-x: auto;/);
    assert.doesNotMatch(css, /\.kv-spalten/);
    assert.match(require('node:fs').readFileSync(require('node:path').join(__dirname, 'renderer', 'card-view.js'), 'utf8'),
        /if \(cardFormat\(row\) === 'kanban'\) content\.classList\.add\('kv-kanban'\);/);
});

// Lauf 13: a board made from one note; its card reads "<title of the note> – <text>" (window log,
// node_updated). On the small card the title stands above already: the line drops it. Titles invented.
test('Kanban aus einer Notiz: die Zeile traegt den Titel der Karte nicht noch einmal', () => {
    const NOTE = { id: 'k7', title: 'Karte 7', content: 'Karte 7 – ein Satz zur Karte', metadata: { width: 200, height: 100 },
        format_schema: { type: 'kanban' }, format_type: 'kanban',
        content_json: { type: 'kanban', title: 'Karte 7', text: 'Karte 7 – ein Satz zur Karte',
            todo: [{ title: 'Karte 7 – ein Satz zur Karte' }], doing: [], done: [],
            columns: [{ name: 'Offen', cards: [{ id: 'k1', title: 'Karte 7 – ein Satz zur Karte' }], color: '#6c757d' },
                { name: 'In Arbeit', cards: [], color: '#0d6efd' }, { name: 'Erledigt', cards: [], color: '#198754' }] } };
    const kurz = cv.cardShort(NOTE);
    assert.deepEqual(kurz.zeilen, ['Offen (1): ein Satz zur Karte']);
    assert.equal(kurz.umfang, '1 Karte in 3 Spalten');
    const read = cv.cardRead(NOTE);
    assert.ok(!JSON.stringify(read.abschnitte).includes('Karte 7 –'), 'the reading view drops it too');
    // a card that only starts like the title stays whole
    const other = { ...NOTE, content_json: { ...NOTE.content_json, columns: [{ name: 'Offen', cards: [{ title: 'Karte 70 bleibt' }] }] } };
    assert.deepEqual(cv.cardShort(other).zeilen, ['Offen (1): Karte 70 bleibt']);
});

// Lauf 15: "Offen (1): Offen: <text>". The note said "Offen: <text>"; its board put that card into the
// column "Offen" (window log, node_updated: "<title> – Offen: <text>"). The status word once. Titles invented.
test('Kanban: beginnt der Kartentext mit dem Namen seiner Spalte und Doppelpunkt, steht das Wort nur einmal', () => {
    const NOTE = { id: 'k8', title: 'Karte 8', content: 'Karte 8 – Offen: Teile bestellen', metadata: { width: 200, height: 100 },
        format_schema: { type: 'kanban' }, format_type: 'kanban',
        content_json: { type: 'kanban', title: 'Karte 8', text: 'Karte 8 – Offen: Teile bestellen',
            todo: [{ title: 'Karte 8 – Offen: Teile bestellen' }], doing: [], done: [],
            columns: [{ name: 'Offen', cards: [{ id: 'k3', title: 'Karte 8 – Offen: Teile bestellen' }], color: '#6c757d' },
                { name: 'In Arbeit', cards: [{ id: 'k4', title: 'Offen: noch zu klaeren' }], color: '#0d6efd' },
                { name: 'Erledigt', cards: [{ id: 'k5', title: 'Offenheit zeigen' }], color: '#198754' }] } };
    const kurz = cv.cardShort(NOTE);
    assert.deepEqual(kurz.zeilen, ['Offen (1): Teile bestellen', 'In Arbeit (1): Offen: noch zu klaeren', 'Erledigt (1): Offenheit zeigen'],
        'only the name of its own column goes; another word or a longer word stays');
    const read = cv.cardRead(NOTE);
    assert.ok(!JSON.stringify(read.abschnitte).includes('Offen: Teile'), 'the reading view drops it too');
});
