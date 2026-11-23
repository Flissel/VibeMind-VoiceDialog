// An order the Brain took and a model works on: { ok: true, pending: true, status: 'angenommen' }
// (before: ok false, and the app showed "✕ fehlgeschlagen" while the model was still working).
// Status line (task-navigate.js) and chat (ideas-chat.js) run together in a stand-in window.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const { acceptedOf, targetsOf, createTaskNavigator } = require('./task-navigation');
const { isAccepted, ACCEPTED_LINE } = require('./renderer/ideas-chat');
const { resultArrived, snapshot } = require('./renderer/task-navigate');

const BUBBLE = '00000000-0000-4000-8000-00000000000b';
const CARD_1 = '00000000-0000-4000-8000-000000000001';
const CARD_2 = '00000000-0000-4000-8000-000000000002';
const cards = (text1 = 'kurz', text2 = 'auch kurz') => [
    { id: CARD_1, title: 'Karte 1', content: text1, updated_at: '2026-11-23T10:00:00Z' },
    { id: CARD_2, title: 'Karte 2', content: text2, updated_at: '2026-11-23T10:00:00Z' },
];

function element(tag) {
    const classes = new Set();
    const el = {
        tag, id: '', children: [], hidden: false, textContent: '', title: '', className: '', dataset: {}, style: {},
        classList: { add: (c) => classes.add(c), remove: (c) => classes.delete(c), contains: (c) => classes.has(c),
            toggle: (c, on) => { if (on === undefined ? !classes.has(c) : on) classes.add(c); else classes.delete(c); } },
        append(...c) { el.children.push(...c); }, appendChild(c) { el.children.push(c); return c; },
        replaceChildren(...c) { el.children = c; }, insertBefore(c) { el.children.push(c); },
        addEventListener() {}, setAttribute() {}, querySelector: () => null,
    };
    return el;
}

function world() {
    let now = 0;
    let timers = [];
    const byId = new Map();
    const add = (id, tag = 'div') => { const el = element(tag); el.id = id; byId.set(id, el); return el; };
    const anchor = add('titlebar-space');
    anchor.parentNode = { insertBefore(el) { byId.set(el.id, el); } };
    add('space-view');
    add('space-title').textContent = 'Bubble B';
    const listeners = {};
    let answer = null;
    const window = {
        document: {
            readyState: 'complete', body: element('body'),
            getElementById: (id) => byId.get(id) || null,
            createElement: (tag) => element(tag),
            querySelectorAll: () => [],
            addEventListener() {},
        },
        localStorage: { getItem: () => null, setItem() {} },
        crypto: { randomUUID: () => '00000000-0000-4000-8000-0000000000ff' },
        MutationObserver: class { observe() {} },
        multiverseApp: { currentSpace: 'ideas', spaces: { ideas: {} }, isNavigating: false, isInsideBubble: true, getBubbleById: () => null },
        __currentEvalBubble: { dbId: BUBBLE },
        spaceCanvas: { bubbleId: BUBBLE, lastNodes: cards() },
        vibemind: { sendChatMessage: async () => answer },
        addEventListener(type, fn) { (listeners[type] = listeners[type] || []).push(fn); },
        dispatchEvent(event) { for (const fn of listeners[event.type] || []) fn(event); return true; },
        CustomEvent: class { constructor(type, init) { this.type = type; this.detail = init && init.detail; } },
        setTimeout(fn, ms) { const t = { fn, at: now + ms }; timers.push(t); return t; },
        clearTimeout(t) { timers = timers.filter((x) => x !== t); },
    };
    const context = { window, globalThis: window, module: undefined };
    vm.runInNewContext(fs.readFileSync(path.join(__dirname, 'renderer', 'task-navigate.js'), 'utf8'), context);
    vm.runInNewContext(fs.readFileSync(path.join(__dirname, 'renderer', 'ideas-chat.js'), 'utf8'), context);
    const panel = () => byId.get('space-view').children.find((c) => c.id === 'ideas-chat');
    const chatLog = () => panel().children.find((c) => c.id === 'ideas-chat-log').children.map((c) => c.textContent);
    const statuses = [];
    window.addEventListener('vibemind:task-status', (e) => statuses.push(e.detail.state));
    return {
        window, statuses, chatLog,
        line: () => { const el = byId.get('task-status'); return el && !el.hidden ? el.textContent : ''; },
        chatState: () => panel().children[0].children[2].textContent,
        handle: (message) => window.VibeTaskNav.handle(message),
        answerWith(value) { answer = value; },
        send: (text) => window.VibeIdeasChat.submit(text, { typed: true }),
        loaded(nodes) { window.spaceCanvas.lastNodes = nodes; window.dispatchEvent(new window.CustomEvent('vibemind:canvas-loaded', { detail: { nodes, bubbleId: BUBBLE } })); },
        advance(ms) { now += ms; for (const t of timers.filter((x) => x.at <= now)) { timers = timers.filter((x) => x !== t); t.fn(); } },
    };
}

/** The events of the Brain for one step in the Ideas space, as the main process turns them into messages. */
function plan(w, hop) {
    const navigator = createTaskNavigator((message) => w.handle(message));
    navigator.handle('plan_started', { plan_id: 'p1', hops: [{}], space: 'ideas', intent: 'Recherchiere zu Karte 1' });
    navigator.handle('hop_started', { space: 'ideas', capability: 'idea_research', description: 'Recherche zu Karte 1' });
    navigator.handle('hop_completed', { space: 'ideas', capability: 'idea_research', ...hop });
    navigator.handle('plan_completed', { plan_id: 'p1', ok: hop.ok !== false, elapsed_s: 0.8 });
}

test('accepted order in the plan: "arbeitet … (Auftrag angenommen)", never failed, ✓ once the card changed', () => {
    const w = world();
    plan(w, { ok: true, pending: true, status: 'angenommen', targets: [CARD_1] });
    assert.equal(w.line(), '● Ideas: arbeitet … (Auftrag angenommen)');
    assert.ok(!w.statuses.includes('failed'));
    assert.equal(w.chatState(), 'arbeitet … (Auftrag angenommen)');
    w.advance(5 * 60 * 1000);                       // a model takes minutes; the line stays
    w.loaded(cards());                               // the 5-s reload: nothing new yet
    w.loaded(cards('kurz', 'Karte 2 von Hand geaendert'));   // another card changed: not the result
    assert.equal(w.line(), '● Ideas: arbeitet … (Auftrag angenommen)');
    const done = cards('Ergebnis der Recherche, lang und ausfuehrlich');
    done[0].updated_at = '2026-11-23T10:07:00Z';
    w.loaded(done);
    assert.equal(w.line(), '✓ Ideas: fertig in 0,8 s — Ergebnis an der Karte „Karte 1“');
    assert.equal(w.statuses[w.statuses.length - 1], 'done');
    assert.match(w.chatLog().join('\n'), /✓ fertig — Ergebnis an der Karte „Karte 1“/);
    assert.equal(w.chatState(), '');
});

test('the receipt may come only in the preview of the result (repr of the Python dict)', () => {
    const preview = "{'ok': True, 'pending': True, 'status': 'angenommen', 'targets': ['" + CARD_1 + "'], 'message': 'Recherche laeuft'}";
    assert.equal(acceptedOf({ ok: true, result_preview: preview }), true);
    assert.deepEqual(targetsOf({ ok: true, result_preview: preview }), [CARD_1]);
    assert.deepEqual(targetsOf({ card_id: CARD_2 }), [CARD_2]);
    assert.equal(acceptedOf({ ok: false, pending: true }), false, 'ok false stays an error');
    assert.equal(acceptedOf({ ok: true, result_preview: "{'ok': True}" }), false);
    const w = world();
    plan(w, { ok: true, result_preview: preview });
    assert.equal(w.line(), '● Ideas: arbeitet … (Auftrag angenommen)', 'no receipt text, no raw data');
});

test('a real error still says failed', () => {
    const w = world();
    plan(w, { ok: false, error: 'Werkzeug nicht erreichbar' });
    assert.match(w.line(), /^✕ Ideas: fehlgeschlagen/);
});

test('accepted answer to a chat sentence (no plan events): chat and line say "arbeitet", the card is marked', async () => {
    const w = world();
    w.answerWith({ success: true, ok: true, pending: true, status: 'angenommen', message: 'Recherche laeuft', targets: [CARD_1] });
    await w.send('Recherchiere zu Karte 1');
    assert.equal(w.line(), '● Ideas: arbeitet … (Auftrag angenommen)');
    assert.equal(w.chatLog()[1], ACCEPTED_LINE + ' — Recherche laeuft');
    assert.doesNotMatch(w.chatLog().join('\n'), /fehlgeschlagen|Keine Antwort/);
    const marks = () => w.window.document.getElementById('space-view').children.find((c) => c.id === 'ideas-pending').children;
    assert.deepEqual(marks().map((c) => [c.dataset.cardId, c.dataset.cardState]), [[CARD_1, 'working']], 'the card says "arbeitet"');
    const changed = cards('Ergebnis');
    w.loaded(changed);
    assert.equal(w.line(), '✓ Ideas: fertig — Ergebnis an der Karte „Karte 1“');
    assert.equal(marks().length, 0, 'the mark goes with the result');
});

test('an accepted answer is never an error, even when the Python part says success false', () => {
    assert.equal(isAccepted({ success: false, pending: true, status: 'angenommen' }), true);
    assert.equal(isAccepted({ ok: false, pending: true }), false);
    assert.equal(isAccepted({ ok: true }), false);
});

test('without named cards any changed or new card counts; the first load of a closed bubble is the picture', () => {
    const before = snapshot(cards());
    assert.equal(resultArrived(before, cards(), []), null);
    assert.equal(resultArrived(before, cards().concat([{ id: 'neu', title: 'Karte 3' }]), []), 'neu');
    assert.equal(resultArrived(before, cards('x'), [CARD_2]), null, 'with named cards only those count');
    const w = world();
    w.window.spaceCanvas.lastNodes = [];             // the bubble was not open when the order was taken
    plan(w, { ok: true, pending: true });
    w.loaded(cards());                                // its first load: the picture, not the result
    assert.equal(w.line(), '● Ideas: arbeitet … (Auftrag angenommen)');
    w.loaded(cards('Ergebnis'));
    assert.match(w.line(), /^✓ Ideas: fertig/);
});

test('an order whose result never shows: the line goes after 20 minutes', () => {
    const w = world();
    plan(w, { ok: true, pending: true });
    w.advance(20 * 60 * 1000 - 1);
    assert.notEqual(w.line(), '');
    w.advance(1);
    assert.equal(w.line(), '');
});
