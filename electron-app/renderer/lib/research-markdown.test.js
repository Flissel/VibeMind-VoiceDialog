const test = require('node:test');
const assert = require('node:assert');
const { parseMarkdown } = require('./research-markdown.js');

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
