const test = require('node:test');
const assert = require('node:assert');
const { parseMarkdown, buildInto } = require('./research-markdown.js');

test('Ueberschriften mit ihrer Ebene', () => {
    const blocks = parseMarkdown('# Eins\n\n### Drei\n');
    assert.deepStrictEqual(blocks[0], { kind: 'heading', level: 1, spans: [{ t: 'text', v: 'Eins' }] });
    assert.strictEqual(blocks[1].level, 3);
});

test('Absatz mit Fettung und Kursiv', () => {
    const [block] = parseMarkdown('Ein **fetter** und *schraeger* Satz.');
    assert.strictEqual(block.kind, 'paragraph');
    assert.deepStrictEqual(block.spans, [
        { t: 'text', v: 'Ein ' },
        { t: 'strong', v: 'fetter' },
        { t: 'text', v: ' und ' },
        { t: 'em', v: 'schraeger' },
        { t: 'text', v: ' Satz.' },
    ]);
});

test('Listen, geordnet und ungeordnet', () => {
    const [ul] = parseMarkdown('- eins\n- zwei\n');
    assert.strictEqual(ul.kind, 'list');
    assert.strictEqual(ul.ordered, false);
    assert.strictEqual(ul.items.length, 2);
    const [ol] = parseMarkdown('1. eins\n2. zwei\n');
    assert.strictEqual(ol.ordered, true);
});

test('Codeblock bleibt woertlich', () => {
    const [block] = parseMarkdown('```\nzeile **nicht fett**\n```\n');
    assert.strictEqual(block.kind, 'code');
    assert.strictEqual(block.text, 'zeile **nicht fett**');
});

test('Tabelle mit Kopf- und Datenzeile', () => {
    const [block] = parseMarkdown('| A | B |\n|---|---|\n| 1 | 2 |\n');
    assert.strictEqual(block.kind, 'table');
    assert.strictEqual(block.rows.length, 2);
    assert.deepStrictEqual(block.rows[1][0], [{ t: 'text', v: '1' }]);
});

test('Link mit erlaubtem Schema', () => {
    const [block] = parseMarkdown('Siehe [Quelle](https://example.test/a).');
    const link = block.spans.find(s => s.t === 'link');
    assert.strictEqual(link.href, 'https://example.test/a');
    assert.strictEqual(link.v, 'Quelle');
});

test('javascript:-Link wird zu Text, niemals zu einem href', () => {
    const [block] = parseMarkdown('Klick [hier](javascript:alert(1)).');
    assert.strictEqual(block.spans.some(s => s.t === 'link'), false);
    const zusammen = block.spans.map(s => s.v).join('');
    assert.match(zusammen, /hier/);
});

test('eingebettetes HTML bleibt Text - es entsteht nie ein Element', () => {
    const [block] = parseMarkdown('Harmlos <img src=x onerror=alert(1)> weiter');
    const alleSpans = JSON.stringify(block.spans);
    assert.match(alleSpans, /onerror/);
    assert.strictEqual(block.spans.every(s => ['text','strong','em','code','link'].includes(s.t)), true);
});

test('unbekannte Syntax faellt auf Text zurueck, nicht auf einen Fehler', () => {
    const blocks = parseMarkdown(':::warnung\nirgendwas\n:::\n');
    assert.strictEqual(blocks.length > 0, true);
    assert.strictEqual(blocks.every(b => typeof b.kind === 'string'), true);
});

test('Tabellentrennzeile zaehlt nur, wenn JEDE Zelle Trennzeichen sind - echte Daten bleiben erhalten', () => {
    // Regression: die erste Zelle einer Datenzeile kann wie eine Trennzeile
    // aussehen ("--" fuer "nicht zutreffend"), waehrend spaetere Zellen
    // echten Text tragen. Eine nur am Zeilenanfang verankerte Pruefung
    // wuerde die GANZE Zeile faelschlich als Trennzeile verwerfen.
    const [block] = parseMarkdown('| A | B |\n| :-- | Ergebnis hier |\n| 1 | 2 |\n');
    assert.strictEqual(block.kind, 'table');
    assert.strictEqual(block.rows.length, 3);
    assert.deepStrictEqual(block.rows[1][0], [{ t: 'text', v: ':--' }]);
    assert.deepStrictEqual(block.rows[1][1], [{ t: 'text', v: 'Ergebnis hier' }]);
});

test('Link-URL mit runden Klammern bleibt vollstaendig erhalten', () => {
    // Regression: eine URL wie eine Wikipedia-Seite "Foo_(bar)" enthaelt
    // selbst runde Klammern. Ein Linkmuster, das beim ersten ")" abbricht,
    // zerschneidet die URL mitten im Pfad.
    const [block] = parseMarkdown('Siehe [Beispiel](https://example.test/wiki/Foo_(bar)).');
    const link = block.spans.find(s => s.t === 'link');
    assert.ok(link, 'erwartete einen Link-Span');
    assert.strictEqual(link.href, 'https://example.test/wiki/Foo_(bar)');
    assert.strictEqual(link.v, 'Beispiel');
});

// --- buildInto: die DOM-schreibende Haelfte, mit einem minimalen Fake-Document ---
//
// Kein jsdom, kein Package - ein Node-Stub, der nur aufzeichnet, was buildInto
// tut (Tag, Kinder, textContent, zugewiesene Eigenschaften wie href/rel/target).
// Damit wird die sicherheitskritische Eigenschaft - nur createElement/textContent,
// nie Markup - zu einer echten, automatisierten Pruefung statt einer Laseraussage.

function makeFakeDoc() {
    return {
        createElement(tag) {
            return {
                tagName: String(tag).toUpperCase(),
                children: [],
                textContent: '',
                appendChild(child) {
                    this.children.push(child);
                    return child;
                },
            };
        },
    };
}

function findFirst(node, predicate) {
    if (!node) return null;
    if (predicate(node)) return node;
    for (const child of node.children || []) {
        const found = findFirst(child, predicate);
        if (found) return found;
    }
    return null;
}

function collectTagNames(node, out) {
    if (!node) return out;
    if (node.tagName) out.push(node.tagName);
    for (const child of node.children || []) collectTagNames(child, out);
    return out;
}

function collectTextContent(node, out) {
    if (!node) return out;
    if (node.textContent) out.push(node.textContent);
    for (const child of node.children || []) collectTextContent(child, out);
    return out;
}

test('buildInto: abgelehnter javascript:-Link erzeugt gar kein <a>-Element', () => {
    const doc = makeFakeDoc();
    const root = doc.createElement('div');
    const blocks = parseMarkdown('Klick [hier](javascript:alert(1)).');
    buildInto(root, blocks, doc);
    const tags = collectTagNames(root, []);
    assert.strictEqual(tags.includes('A'), false);
});

test('buildInto: akzeptierter Link erzeugt ein <a> mit rel und target', () => {
    const doc = makeFakeDoc();
    const root = doc.createElement('div');
    const blocks = parseMarkdown('Siehe [Quelle](https://example.test/a).');
    buildInto(root, blocks, doc);
    const anchor = findFirst(root, n => n.tagName === 'A');
    assert.ok(anchor, 'erwartete ein <a>-Element im Baum');
    assert.strictEqual(anchor.href, 'https://example.test/a');
    assert.strictEqual(anchor.rel, 'noopener noreferrer');
    assert.strictEqual(anchor.target, '_blank');
    assert.strictEqual(anchor.textContent, 'Quelle');
});

test('buildInto: Reporttext erreicht den Baum nur als textContent, nie als Markup', () => {
    const doc = makeFakeDoc();
    const root = doc.createElement('div');
    const blocks = parseMarkdown('Harmlos <img src=x onerror=alert(1)> weiter');
    buildInto(root, blocks, doc);
    const tags = collectTagNames(root, []);
    // Kein <img> oder sonstiges aus dem eingebetteten Markup entstandenes
    // Element - nur der feste Satz an Tags, die buildInto selbst waehlt.
    assert.strictEqual(tags.includes('IMG'), false);
    const texts = collectTextContent(root, []);
    assert.match(texts.join(''), /onerror/);
});
