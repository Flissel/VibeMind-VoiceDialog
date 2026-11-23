const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const { buildContext, noteText, cardTitle, createCardStore, MAX_CARDS } = require('./renderer/ideas-chat');

test('inside a bubble the context names the bubble and its cards', () => {
    const context = buildContext({
        bubble: { id: 7, title: 'Marketing' },
        nodes: [
            { id: 'n1', content: { title: 'Zielgruppe' } },
            { id: 'n2', title: 'Kanäle', content_json: { type: 'table' } },
            { id: 'n3', content: { text: 'nur Text' }, format_schema: { type: 'action_list' } },
            null,
            { title: 'ohne Kennung' },
        ],
        bubbles: [{ id: 'b1', title: 'nicht gefragt' }],
        newId: 'u-1',
    });

    assert.deepEqual(context, {
        space: 'ideas',
        bubble: { id: '7', title: 'Marketing' },
        cards: [
            { id: 'n1', title: 'Zielgruppe', format: 'note' },
            { id: 'n2', title: 'Kanäle', format: 'table' },
            { id: 'n3', title: 'nur Text', format: 'action_list' },
        ],
        new_id: 'u-1',
    });
});

test('in the overview the context names the bubbles instead', () => {
    const context = buildContext({ bubble: null, nodes: [{ id: 'n1' }], bubbles: [{ id: 'b1', title: 'Marketing' }, { title: 'ohne' }] });

    assert.deepEqual(context, { space: 'ideas', bubble: null, bubbles: [{ id: 'b1', title: 'Marketing' }] });
});

test('the context is capped', () => {
    const nodes = Array.from({ length: MAX_CARDS + 20 }, (_, i) => ({ id: i, title: 'K' + i }));

    assert.equal(buildContext({ bubble: { id: 1, title: 'B' }, nodes }).cards.length, MAX_CARDS);
});

test('noteText finds the note in a sentence that plainly asks to hold one', () => {
    assert.equal(noteText('Notiere: API Design'), 'API Design');
    assert.equal(noteText('halte fest, dass der Termin am Montag ist'), 'dass der Termin am Montag ist');
    assert.equal(noteText('Merke dir Preisliste prüfen'), 'Preisliste prüfen');
    assert.equal(noteText('schreib auf: Milch'), 'Milch');
    assert.equal(noteText('Formatiere die Zielgruppe als Tabelle'), null);
    assert.equal(noteText('notiere'), null);
    assert.equal(noteText(undefined), null);
});

test('a pending card goes when the stored card arrives, by id or by title', () => {
    const store = createCardStore();

    store.pending('u-1', 'API Design');
    store.pending('u-2', 'Preisliste');
    assert.deepEqual(store.list().map((c) => c.state), ['pending', 'pending']);

    store.matchLoaded([{ id: 'u-1', content: { title: 'anderer Titel' } }]);       // same id
    assert.deepEqual(store.list().map((c) => c.id), ['u-2']);
    store.matchLoaded([{ id: 'db-9', content: { title: ' preisliste ' } }]);       // same title
    assert.deepEqual(store.list(), []);
});

test('a rejected card leaves with its reason; a working card stays until it is confirmed', () => {
    const store = createCardStore();

    store.pending('u-1', 'API Design');
    assert.deepEqual(store.reject('u-1', 'Bubble nicht gefunden'),
        { id: 'u-1', title: 'API Design', state: 'rejected', reason: 'Bubble nicht gefunden' });
    assert.deepEqual(store.list(), []);
    assert.equal(store.reject('gibt-es-nicht', 'x'), null);

    store.pending('u-2', 'Zielgruppe');
    store.working('u-2');
    assert.equal(store.list()[0].state, 'working');
    store.matchLoaded([{ id: 'u-2' }]);
    assert.equal(store.list().length, 1, 'loading the canvas does not end the work of a model');
    store.expire('u-2');
    assert.equal(store.list().length, 1, 'only a pending card expires');
    store.confirm('u-2');
    assert.deepEqual(store.list(), []);

    store.pending('u-3', 'bleibt');
    store.working('u-4', 'Gliederung');
    assert.deepEqual(store.endWork().map((c) => c.id), ['u-3']);
    assert.deepEqual(store.expire('u-3'), []);
});

test('cardTitle reads the title the way the canvas shows it', () => {
    assert.equal(cardTitle({ content: { title: 'A', text: 'B' } }), 'A');
    assert.equal(cardTitle({ content: { text: 'B' } }), 'B');
    assert.equal(cardTitle({ title: 'C' }), 'C');
    assert.equal(cardTitle({ content: 'kein Objekt', title: 'D' }), 'D');
    assert.equal(cardTitle(null), '');
});

test('the chat uses the existing way and is wired into the page', () => {
    const dir = __dirname;
    const html = fs.readFileSync(path.join(dir, 'renderer', 'index.html'), 'utf8');
    const css = fs.readFileSync(path.join(dir, 'renderer', 'styles.css'), 'utf8');
    const preload = fs.readFileSync(path.join(dir, 'preload.js'), 'utf8');
    const main = fs.readFileSync(path.join(dir, 'main.js'), 'utf8');
    const chat = fs.readFileSync(path.join(dir, 'renderer', 'ideas-chat.js'), 'utf8');
    const canvas = fs.readFileSync(path.join(dir, 'renderer', 'universe_canvas.js'), 'utf8');

    assert.ok(html.includes('src="ideas-chat.js"'));
    assert.ok(css.includes("styles/ideas-chat.css"));
    assert.match(preload, /sendChatMessage: \(text, context\) =>\s*ipcRenderer\.invoke\('renderer:chat-text-input', \{ text, context \}\)/);
    assert.match(main, /message\.context = context/);
    assert.match(chat, /vibemind\.sendChatMessage\(text, contextNow\(newId\)\)/);
    assert.doesNotMatch(chat, /fetch\(|WebSocket|XMLHttpRequest|EventSource/, 'no channel of its own');
    assert.match(canvas, /vibemind:canvas-loaded/);
    assert.match(canvas, /vibemind:canvas-node-added/);
});
