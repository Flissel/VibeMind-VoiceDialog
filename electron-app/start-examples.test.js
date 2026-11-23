const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const start = require('./renderer/start-examples');

const read = (file) => fs.readFileSync(path.join(__dirname, file), 'utf8');

test('each space gets its own sentences first, then those from every tab, at most three', () => {
    assert.deepEqual(start.examplesFor('ideas'), ['Welche Bubbles gibt es?', 'Halte fest: … in der Bubble …', 'Woran denkt das Gehirn gerade?']);
    assert.deepEqual(start.examplesFor('thebrain'), ['Woran denkt das Gehirn gerade?', 'Welche Bubbles gibt es?']);
    assert.deepEqual(start.examplesFor('orders'), ['Welche geplanten Aufgaben gibt es?', 'Woran denkt das Gehirn gerade?', 'Welche Bubbles gibt es?']);
    assert.deepEqual(start.examplesFor('video'), start.EVERYWHERE, 'a space without a sentence of its own: the ones from every tab');
});

test('only the measured sentences, none for the Desktop space, none that jump from the Dashboard', () => {
    const all = new Set([...start.EVERYWHERE, ...Object.values(start.OWN).flat()]);
    assert.deepEqual([...all].sort(), [
        'Halte fest: … in der Bubble …', 'Welche Bubbles gibt es?',
        'Welche geplanten Aufgaben gibt es?', 'Woran denkt das Gehirn gerade?',
    ]);
    assert.equal(start.OWN.desktop, undefined);
    assert.equal(start.OWN.clawport, undefined, 'the task sentence from the Dashboard tab still jumps to Aufträge');
    assert.ok(start.examplesFor('desktop').every((sentence) => !/desktop/i.test(sentence)));
});

test('a click fills the field; a start stops at its first gap, the person writes the rest', () => {
    assert.equal(start.fieldText('Woran denkt das Gehirn gerade?'), 'Woran denkt das Gehirn gerade?');
    assert.equal(start.fieldText('Halte fest: … in der Bubble …'), 'Halte fest: ');
});

test('the view: label and buttons in #gc-messages, new sentences on each space, fill but never send', () => {
    const listeners = {};
    const node = (tag) => ({
        tag, children: [], textContent: '', className: '', on: {},
        replaceChildren() { this.children = []; },
        appendChild(c) { this.children.push(c); return c; },
        insertBefore(c) { this.children.unshift(c); return c; },
        addEventListener(type, fn) { this.on[type] = fn; },
        focus() { this.focused = true; },
    });
    const messages = node('div');
    const input = node('input');
    input.value = '';
    const doc = {
        readyState: 'complete',
        createElement: node,
        getElementById: (id) => ({ 'gc-messages': messages, 'gc-input': input })[id] || null,
    };
    const win = { multiverseApp: { currentSpace: 'orders' }, addEventListener: (type, fn) => { listeners[type] = fn; } };
    start.mount(win, doc);
    const box = messages.children[0];
    assert.equal(box.className, 'gc-start');
    assert.equal(box.children[0].textContent, 'Sag zum Beispiel:');
    assert.equal(box.children[1].textContent, '„Welche geplanten Aufgaben gibt es?“');
    box.children[1].on.click();
    assert.equal(input.value, 'Welche geplanten Aufgaben gibt es?');
    assert.equal(input.focused, true);

    listeners['vibemind:space-arrived']({ detail: { space: 'thebrain' } });
    assert.equal(box.children[1].textContent, '„Woran denkt das Gehirn gerade?“');

    assert.doesNotMatch(read('renderer/start-examples.js'), /sendGameConsoleMessage|gc-send-btn|\.click\(\)/, 'a click only fills');
    assert.match(read('renderer/index.html'), /<script defer src="start-examples\.js"><\/script>/);
    assert.match(read('renderer/styles/game-console.css'), /\.gc-messages:has\(\.gc-msg\) > \.gc-start \{\s*display: none;/);
});
