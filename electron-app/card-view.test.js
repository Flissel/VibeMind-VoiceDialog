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
            ['Offen: Logo'], '1 Karte in 2 Spalten', 'Kanban'],
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
    assert.match(md.html, /<span class="kv-link" title="https:\/\/example.org\/a\?b=&quot;c&quot;">Quelle<\/span>/);
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
                    open(id) { this.opened.push(id); return true; }, close() { this.closed += 1; }, setQuery() {} };
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
