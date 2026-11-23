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

test('only the measured sentences, none for the Desktop space; the Dashboard gets the task sentence (no jump since Lauf 8)', () => {
    const all = new Set([...start.EVERYWHERE, ...Object.values(start.OWN).flat()]);
    assert.deepEqual([...all].sort(), [
        'Halte fest: … in der Bubble …', 'Welche Bubbles gibt es?',
        'Welche geplanten Aufgaben gibt es?', 'Woran denkt das Gehirn gerade?',
    ]);
    assert.equal(start.OWN.desktop, undefined);
    assert.deepEqual(start.examplesFor('clawport'), ['Welche geplanten Aufgaben gibt es?', 'Woran denkt das Gehirn gerade?', 'Welche Bubbles gibt es?']);
    assert.ok(start.examplesFor('desktop').every((sentence) => !/desktop/i.test(sentence)));
});

test('a click fills the field; a start stops at its first gap, the person writes the rest', () => {
    assert.equal(start.fieldText('Woran denkt das Gehirn gerade?'), 'Woran denkt das Gehirn gerade?');
    assert.equal(start.fieldText('Halte fest: … in der Bubble …'), 'Halte fest: ');
});

/** #gc-messages, #gc-input and #gc-send-btn in a row, as in index.html. */
function page() {
    const byId = {};
    const node = (tag) => {
        const classes = new Set();
        const el = {
            tag, children: [], textContent: '', className: '', on: {}, attrs: {}, parentNode: null,
            classList: { contains: (c) => classes.has(c), toggle: (c, on) => { if (on) classes.add(c); else classes.delete(c); } },
            replaceChildren() { this.children = []; },
            appendChild(c) { this.children = this.children.filter((x) => x !== c).concat([c]); c.parentNode = this; return c; },
            insertBefore(c, before) {
                const at = this.children.indexOf(before);
                this.children.splice(at < 0 ? 0 : at, 0, c); c.parentNode = this; return c;
            },
            addEventListener(type, fn) { this.on[type] = fn; },
            setAttribute(name, value) { this.attrs[name] = value; },
            focus() { this.focused = true; },
            set id(value) { byId[value] = this; },
        };
        return el;
    };
    const messages = node('div');
    const row = node('div');
    const input = row.appendChild(node('input'));
    const send = row.appendChild(node('button'));
    input.value = '';
    Object.assign(byId, { 'gc-messages': messages, 'gc-input': input, 'gc-send-btn': send });
    messages.scrollHeight = 900;
    const doc = { readyState: 'complete', createElement: node, getElementById: (id) => byId[id] || null };
    return { node, doc, messages, input, row, send };
}

test('the view: label and buttons in #gc-messages, new sentences on each space, fill but never send', () => {
    const listeners = {};
    const { node, doc, messages, input } = page();
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

    // gc-send-btn only to set "?" before it: no click on it, no sending
    assert.doesNotMatch(read('renderer/start-examples.js'), /sendGameConsoleMessage|\.click\(\)|send\.(on|dispatch)/, 'a click only fills');
    assert.match(read('renderer/index.html'), /<script defer src="start-examples\.js"><\/script>/);
    assert.match(read('renderer/styles/game-console.css'), /\.gc-messages:has\(\.gc-msg\) > \.gc-start \{\s*display: none;/);
});

test('"?" at the input shows the sentences again below a full list; a sentence or "?" hides them', () => {
    const { node, doc, messages, input, row, send } = page();
    const win = { multiverseApp: { currentSpace: 'ideas' }, addEventListener() {} };
    start.mount(win, doc);
    const box = messages.children[0];
    const help = row.children[row.children.indexOf(send) - 1];
    assert.equal(help.textContent, '?', 'the button stands right before the send button');
    assert.equal(help.title, 'Beispielsätze zeigen');
    assert.equal(help.attrs['aria-expanded'], 'false');

    const sent = messages.appendChild(node('div'));    // the list is no longer empty
    sent.className = 'gc-msg';
    help.on.click();
    assert.equal(box.classList.contains('gc-start-shown'), true);
    assert.equal(messages.children.at(-1), box, 'at the end of the list, where the person reads');
    assert.equal(messages.scrollTop, 900);
    assert.equal(help.attrs['aria-expanded'], 'true');

    box.children[2].on.click();                       // "Halte fest: … in der Bubble …"
    assert.equal(input.value, 'Halte fest: ');
    assert.equal(box.classList.contains('gc-start-shown'), false, 'it filled the field: the sentences go');
    help.on.click();
    help.on.click();
    assert.equal(box.classList.contains('gc-start-shown'), false, 'a second "?" hides them');
    assert.match(read('renderer/styles/game-console.css'), /\.gc-messages:has\(\.gc-msg\) > \.gc-start\.gc-start-shown \{\s*display: flex;/);
});
