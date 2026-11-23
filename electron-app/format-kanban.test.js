// The board in the format panel (renderer/format-renderer.js): its own columns, not todo/doing/done a
// second time. Lauf 10: the Ideas server sends both for one board (columns with a colour, and the same
// cards as todo/doing/done); both drawn doubled every card. Titles invented.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function build() {
    const window = {};
    vm.runInNewContext(fs.readFileSync(path.join(__dirname, 'renderer', 'format-renderer.js'), 'utf8'),
        { window, document: {}, console: { log() {}, warn() {}, error() {} } });
    return window.VibeFormatBuild.kanban;
}

const heads = (text) => text.split('\n').map((l) => /^ {4}COL_\d+\["(.*)"\]$/.exec(l)).filter(Boolean).map((m) => m[1]);
const cards = (text) => text.split('\n').filter((l) => /^ {4}COL_\d+_\d+\[/.test(l)).length;

test('a board with columns: only its columns, each card once', () => {
    const text = build()({ type: 'kanban',
        todo: [{ title: 'Punkt 1' }], doing: [{ title: 'Punkt 2' }], done: [{ title: 'Punkt 3' }],
        columns: [{ name: 'Offen', cards: [{ id: 'k3', title: 'Punkt 1' }, { id: 'k4', title: 'Punkt 4' }], color: '#6c757d' },
            { name: 'In Arbeit', cards: [{ id: 'k1', title: 'Punkt 2' }], color: '#0d6efd' },
            { name: 'Erledigt', cards: [{ id: 'k2', title: 'Punkt 3' }], color: '#198754' }] });
    assert.deepEqual(heads(text), ['Offen (2)', 'In Arbeit (1)', 'Erledigt (1)']);
    assert.equal(cards(text), 4);
});

test('an old card without columns: todo / doing / done as before, with German heads', () => {
    const text = build()({ type: 'kanban', todo: [{ title: 'Punkt 1' }], doing: [{ text: 'Punkt 2' }], done: [] });
    assert.deepEqual(heads(text), ['Offen (1)', 'In Arbeit (1)', 'Erledigt (0)']);
    assert.equal(cards(text), 2);
});
