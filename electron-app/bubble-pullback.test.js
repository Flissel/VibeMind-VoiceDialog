// "Clicked another bubble, a few seconds later the app pulled me back into Bubble A"
// (2026-11-23, voice cda26d8). Measured in the app: with no bubble open the canvas kept loading
// the cards of Bubble A every 5 s (refresh in-place: 1 nodes); its bubbleId was left from an
// earlier visit, and most entries load their cards without setting it.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const A = '00000000-0000-4000-8000-00000000000a'; // "Bubble A"
const B = '0000000b';

function world({ bubbles = [] } = {}) {
    let timers = [];
    let nextId = 1;
    const view = { hidden: false, classList: { contains: (name) => name === 'hidden' && view.hidden } };
    const fetched = [];
    const notes = []; // what the canvas shows on the page next to it (a visible error)
    const window = {
        vibemind: { supabase: { url: 'http://db', anonKey: 'k' } },
        // like multiverse.js: === against userData.id or userData.db_id
        multiverseApp: { getBubbleById: (id) => bubbles.find((b) => b.userData.id === id || b.userData.db_id === id) || null },
    };
    const context = {
        window,
        document: { getElementById: (id) => (id === 'space-view' ? view : null), querySelector: () => null,
            createElement: () => { const el = { className: '', textContent: '', setAttribute() {}, remove() { notes.splice(notes.indexOf(el), 1); } }; return el; } },
        console: { log() {}, warn() {}, error() {} },
        setInterval(fn, ms) { const t = { id: nextId++, fn, ms, every: true }; timers.push(t); return t.id; },
        clearInterval(id) { timers = timers.filter((t) => t.id !== id); },
        setTimeout(fn, ms) { const t = { id: nextId++, fn, ms }; timers.push(t); return t.id; },
        clearTimeout(id) { timers = timers.filter((t) => t.id !== id); },
        fetch: async (url) => {
            const asked = /linked_idea_id=eq\.([^&]+)/.exec(url);
            if (asked) fetched.push(decodeURIComponent(asked[1]));
            return { ok: true, json: async () => (asked ? [{ id: 'card-of-' + decodeURIComponent(asked[1]) }] : []) };
        },
        CustomEvent: class { constructor(type, init) { this.type = type; this.detail = init && init.detail; } },
    };
    window.dispatchEvent = () => true;
    vm.runInNewContext(fs.readFileSync(path.join(__dirname, 'renderer', 'universe_canvas.js'), 'utf8'), context);
    const UniverseCanvas = window.UniverseCanvas;
    const canvas = Object.create(UniverseCanvas.prototype);
    canvas.container = { parentNode: { appendChild: (el) => notes.push(el), querySelector: (sel) => notes.find((n) => '.' + n.className === sel) || null } };
    const shown = [];
    const loadedFor = []; // the bubble the canvas names with each load (it goes with vibemind:canvas-loaded)
    canvas.loadNodes = function (nodes) { shown.push(nodes.map((n) => n.id).join(',')); loadedFor.push(this.bubbleId); };
    return {
        canvas, view, shown, fetched, loadedFor, notes,
        /** Every timer fires, the 5-s poll three times; then the fetches settle. */
        async runAllTimers() {
            for (let round = 0; round < 3; round++) {
                for (const t of [...timers]) { if (!t.every) timers = timers.filter((x) => x !== t); t.fn(); }
                await new Promise((resolve) => setImmediate(resolve));
            }
        },
    };
}

test('the app stays in the bubble the person clicked, whatever timers of the earlier bubble do', async () => {
    const w = world();
    // a plan opened bubble A (Bubble A); its cards were reloaded after "zurück", the poll runs
    w.canvas.setBubble(A);
    w.canvas._mermaidMode = true;
    w.canvas._startMermaidPoll();
    await w.canvas.refresh();
    assert.deepEqual(w.shown, ['card-of-' + A]);

    // the person clicks bubble B: its cards come with the entry (pending content), as in the app
    w.canvas.setBubble(B);
    w.canvas.loadNodes([{ id: 'card-of-' + B }]);
    assert.equal(w.loadedFor[w.loadedFor.length - 1], B, 'the cards of the entry are reported as B');
    w.shown.length = 0;
    w.loadedFor.length = 0;

    await w.runAllTimers();
    assert.ok(w.shown.length > 0, 'the poll keeps the open bubble up to date');
    assert.ok(w.shown.every((cards) => cards === 'card-of-' + B), `only B is shown, got ${w.shown}`);
    assert.ok(w.loadedFor.every((id) => id === B), 'every load names B, so the chat sends the cards with B');
});

test('an answer for the earlier bubble that arrives after the switch is dropped', async () => {
    const w = world();
    w.canvas.setBubble(A);
    const late = w.canvas.refresh(); // asked for A ...
    w.canvas.setBubble(B);           // ... the person opened B meanwhile
    await late;
    assert.deepEqual(w.shown, []);
});

test('with no bubble open nothing is loaded in the background', async () => {
    const w = world();
    w.canvas.setBubble(A);
    w.canvas._startMermaidPoll();
    w.canvas.leaveBubble();
    w.view.hidden = true;
    await w.runAllTimers();
    assert.deepEqual(w.fetched, []);

    // a left-over id with the view hidden (the state measured in the app) loads nothing either
    w.canvas.bubbleId = A;
    w.canvas._startMermaidPoll();
    await w.runAllTimers();
    assert.deepEqual(w.fetched, []);
});

test('only ids of the database are kept; anything else means: not known', () => {
    const w = world();
    w.canvas.setBubble('1');
    assert.equal(w.canvas.bubbleId, null);
    w.canvas.setBubble(B);
    assert.equal(w.canvas.bubbleId, B);
});

test('every entry sets the bubble of the canvas, every exit clears it, and the chat never sets it', () => {
    const nav = fs.readFileSync(path.join(__dirname, 'renderer', 'bubble-navigation.js'), 'utf8');
    const handlers = fs.readFileSync(path.join(__dirname, 'renderer', 'handlers', 'canvas-handlers.js'), 'utf8');
    const html = fs.readFileSync(path.join(__dirname, 'renderer', 'index.html'), 'utf8');
    const chat = fs.readFileSync(path.join(__dirname, 'renderer', 'ideas-chat.js'), 'utf8');
    assert.equal((nav.match(/window\.spaceCanvas\.setBubble\(bubbleId\);/g) || []).length, 2);
    assert.match(nav, /window\.spaceCanvas\.leaveBubble\(\);/);
    for (const [name, source, word] of [['canvas-handlers', handlers, 'msg'], ['index.html', html, 'message']]) {
        const loads = (source.match(new RegExp(`spaceCanvas\\.loadNodes\\(${word}\\.content`, 'g')) || []).length;
        const sets = (source.match(new RegExp(`spaceCanvas\\.fromPython\\(${word}\\);\\s*window\\.spaceCanvas\\.loadNodes\\(${word}\\.content`, 'g')) || []).length;
        assert.equal(sets, loads, name + ': every load of an entered bubble names the bubble first');
        assert.doesNotMatch(source, /setBubble\((msg|message)\.bubble_id\)/, name + ': the local number of Python is never taken as the id');
    }
    assert.doesNotMatch(chat, /canvas\.bubbleId\s*=/);
    const python = fs.readFileSync(path.join(__dirname, '..', 'python', 'ipc', 'canvas_manager.py'), 'utf8');
    assert.match(python, /"type": "entered_bubble",\s*"bubble_id": bubble_id,\s*#[^\n]*\n\s*"db_bubble_id": db_bubble_id,/);
});

// Content after the animation (measured: content at 1471 ms, animation done at 816 ms, first opening
// of a big bubble): entered_bubble arrives with the view already open and names the bubble by
// Python's local number (15). The canvas took that as its bubble: bubbleId null, the chat sent no
// cards although 99 were on screen, refresh() returned at once.
const LOCAL = 15;
const BUBBLE_A = { userData: { type: 'bubble', id: A, db_id: A, title: 'Bubble A' } };
const contentOfA = [{ id: 'card-1' }, { id: 'card-2' }];

for (const [order, entry] of [
    ['content after the animation', (w) => {
        w.canvas.setBubble(A);                                                     // enterSpace: animation done
        w.canvas.fromPython({ bubble_id: LOCAL, content: contentOfA });            // late entered_bubble (old Python)
        w.canvas.loadNodes(contentOfA);
    }],
    ['content after the animation, Python names the database id', (w) => {
        w.canvas.setBubble(A);
        w.canvas.fromPython({ bubble_id: LOCAL, db_bubble_id: A, content: contentOfA });
        w.canvas.loadNodes(contentOfA);
    }],
    ['content during the animation', (w) => {
        const pending = { content: contentOfA };                                   // stored by the early path
        w.canvas.setBubble(A);                                                     // enterSpace callback
        w.canvas.loadNodes(pending.content);
    }],
]) {
    test(`with the local number of Python the canvas keeps the database id: ${order}`, async () => {
        const w = world({ bubbles: [BUBBLE_A] });
        entry(w);
        assert.equal(w.canvas.bubbleId, A);
        assert.deepEqual(w.loadedFor, [A], 'canvas-loaded names A: the chat sends the cards with A');
        assert.equal(w.notes.length, 0);
        // the chat checks exactly this: cards only with the bubble they were loaded for
        const { buildContext } = require('./renderer/ideas-chat');
        const context = buildContext({ bubble: { id: A, title: 'Bubble A' }, nodes: [{ id: 'card-1', title: 'Karte 1' }, { id: 'card-2', title: 'Karte 2' }], nodesBubbleId: w.loadedFor[0] });
        assert.equal(context.cards.length, 2);
        // and the 5-s reload loads A, so cards from agent runs show up
        w.shown.length = 0;
        await w.canvas.refresh();
        assert.deepEqual(w.fetched, [A]);
        assert.deepEqual(w.shown, ['card-of-' + A]);
    });
}

test('Python names another bubble by its database id: the canvas follows it', () => {
    const w = world({ bubbles: [BUBBLE_A] });
    w.canvas.setBubble(A);
    w.canvas.fromPython({ bubble_id: 16, db_bubble_id: B });
    assert.equal(w.canvas.bubbleId, B);
});

test('a bubble open without any known id is a visible error, not a silent null', () => {
    const w = world();
    w.canvas.fromPython({ bubble_id: LOCAL });
    assert.equal(w.canvas.bubbleId, null);
    assert.equal(w.canvas.bubbleUnknown, true);
    assert.equal(w.notes.length, 1);
    assert.match(w.notes[0].textContent, /nicht erkannt/);
    w.canvas.setBubble(A);                      // known again
    assert.equal(w.notes.length, 0);
    w.canvas.fromPython({ bubble_id: LOCAL });
    w.canvas.leaveBubble();                     // leaving: no bubble, no error
    assert.equal(w.canvas.bubbleUnknown, false);
});
