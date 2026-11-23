// "Clicked another bubble, a few seconds later the app pulled me back into Bubble A" (
// 2026-11-23, voice cda26d8). Measured in the app: with no bubble open the canvas kept loading
// the cards of Bubble A every 5 s (refresh in-place: 1 nodes); its bubbleId was left from an
// earlier visit, and most entries load their cards without setting it.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const A = '00000000-0000-4000-8000-00000000000a'; // "Bubble A"
const B = '0000000b';

function world() {
    let timers = [];
    let nextId = 1;
    const view = { hidden: false, classList: { contains: (name) => name === 'hidden' && view.hidden } };
    const fetched = [];
    const window = {
        vibemind: { supabase: { url: 'http://db', anonKey: 'k' } },
        multiverseApp: { getBubbleById: () => null },
    };
    const context = {
        window,
        document: { getElementById: (id) => (id === 'space-view' ? view : null), querySelector: () => null },
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
    const shown = [];
    const loadedFor = []; // the bubble the canvas names with each load (it goes with vibemind:canvas-loaded)
    canvas.loadNodes = function (nodes) { shown.push(nodes.map((n) => n.id).join(',')); loadedFor.push(this.bubbleId); };
    return {
        canvas, view, shown, fetched, loadedFor,
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
        const sets = (source.match(new RegExp(`spaceCanvas\\.setBubble\\(${word}\\.bubble_id\\);\\s*window\\.spaceCanvas\\.loadNodes\\(${word}\\.content`, 'g')) || []).length;
        assert.equal(sets, loads, name + ': every load of an entered bubble names the bubble first');
    }
    assert.doesNotMatch(chat, /canvas\.bubbleId\s*=/);
});
