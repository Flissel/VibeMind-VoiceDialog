// Lauf 26 (app 7a1ac7e): after a sentence the app jumped to Rowboat and Aufträge with a flicker
// (there, back to Ideas, there again), to Desktop and Project Space only 1.5 s after the answer,
// and there was no way back but the tab of Ideas, scrolled out of the strip. Here the real code of
// the move (multiverse.js navigateToSpace / _arriveAtSpace), of the tab switch (space-navigator.js)
// and of the way back (jump-back.js) in a stand-in window.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const read = (file) => fs.readFileSync(path.join(__dirname, 'renderer', file), 'utf8');
const { offerOf } = require('./renderer/jump-back');

function element(tag, byId) {
    const classes = new Set();
    const listeners = {};
    const el = {
        tag, id: '', hidden: false, textContent: '', title: '', attrs: {}, dataset: {}, style: { setProperty() {} },
        parentNode: null, children: [],
        classList: { add: (c) => classes.add(c), remove: (c) => classes.delete(c), contains: (c) => classes.has(c),
            toggle: (c, on) => { if (on) classes.add(c); else classes.delete(c); } },
        addEventListener(type, fn) { listeners[type] = fn; },
        click() { if (listeners.click) listeners.click({}); },
        setAttribute(k, v) { el.attrs[k] = v; },
        querySelector: () => null,
        insertBefore(c) { el.children.push(c); c.parentNode = el; if (c.id && byId) byId.set(c.id, c); },
    };
    return el;
}

/** The window with the scene's move, the tab switch and the way back, on stand-in timers. */
function world() {
    let now = 0;
    let timers = [];
    const byId = new Map();
    const bar = element('div', byId);
    const anchor = element('span', byId);
    anchor.id = 'titlebar-space';
    anchor.parentNode = bar;
    byId.set('titlebar-space', anchor);
    const listeners = {};
    const document = {
        readyState: 'complete',
        documentElement: { style: { setProperty() {} } },
        getElementById: (id) => byId.get(id) || null,
        createElement: (tag) => element(tag, byId),
        querySelectorAll: () => [],
        querySelector: () => null,
    };
    const moves = [];
    const ipc = [];
    const logs = [];
    const window = {
        document,
        vibemind: { navigateToSpace: async (space) => { ipc.push(space); } },
        addEventListener(type, fn) { (listeners[type] = listeners[type] || []).push(fn); },
        dispatchEvent(event) { for (const fn of listeners[event.type] || []) fn(event); return true; },
        CustomEvent: class { constructor(type, init) { this.type = type; this.detail = init && init.detail; } },
    };
    const setTimeout = (fn, ms) => { const t = { fn, at: now + ms }; timers.push(t); return t; };
    const clearTimeout = (t) => { timers = timers.filter((x) => x !== t); };
    window.setTimeout = setTimeout;
    window.clearTimeout = clearTimeout;

    // the two methods of the scene as they are; camera, themes and pages are stand-ins
    const scene = read('multiverse.js');
    const cut = (from, to) => {
        const start = scene.indexOf(from);
        const end = scene.indexOf(to, start);
        assert.ok(start > 0 && end > start, 'found in multiverse.js: ' + from.trim());
        return scene.slice(start, end);
    };
    const methods = cut('    navigateToSpace(targetSpace, options = {}) {', '\n    // Single source of truth')
        + cut('    _arriveAtSpace(targetSpace, space) {', '\n    /** Close the open bubble');
    const quick = /const QUICK_MOVE_MS = (\d+);/.exec(scene);
    assert.ok(quick, 'QUICK_MOVE_MS in multiverse.js');
    const context = vm.createContext({
        window, document, console: { log: (...a) => logs.push(a.join(' ')), warn() {}, error() {} }, setTimeout, clearTimeout,
        CustomEvent: window.CustomEvent, QUICK_MOVE_MS: Number(quick[1]),
    });
    vm.runInContext(`class Scene {
        constructor() {
            this.currentSpace = 'ideas';
            this.isNavigating = false;
            const at = { clone() { return { z: 0, y: 0 }; } };
            this.spaces = { ideas: { position: at }, roarboot: { position: at }, orders: { position: at, external: true },
                desktop: { position: at }, projects: { position: at } };
        }
        _leaveOpenBubble() { return false; }
        updateGameConsoleAgent() {}
        getSpaceInfo() { return null; }
        animateCameraTo(to, look, done, ms) { this.moves.push({ ms, done }); }
${methods}
    }
    this.Scene = Scene;`, context);
    const app = new context.Scene();
    app.moves = moves;
    window.multiverseApp = app;

    vm.runInNewContext(read('space-navigator.js'), { window, document, console: context.console, setTimeout, clearTimeout });
    vm.runInNewContext(read('jump-back.js'), { window, document, module: undefined });
    return {
        app, window, byId, ipc, moves,
        switches: () => logs.filter((l) => l.startsWith('[Space] Wechsel nach')),
        advance(ms) {
            now += ms;
            for (const t of timers.filter((x) => x.at <= now).sort((a, b) => a.at - b.at)) {
                if (!timers.includes(t)) continue;
                timers = timers.filter((x) => x !== t);
                t.fn();
            }
        },
        back: () => byId.get('jump-back'),
    };
}

test('the failsafe of an earlier move does not end the next one (no flicker back to Ideas)', () => {
    const w = world();
    w.app.currentSpace = 'clawport';
    w.app.spaces.clawport = { position: { clone() { return { z: 0, y: 0 }; } } };
    assert.equal(w.app.navigateToSpace('ideas'), true);
    w.advance(1500);
    w.moves[0].done();                                  // the camera arrives in Ideas
    assert.equal(w.app.currentSpace, 'ideas');
    w.advance(1000);
    assert.equal(w.app.navigateToSpace('roarboot'), true);   // 2.5 s after the first move: to Rowboat
    w.advance(500);                                     // 3 s after the first: its failsafe would fire now
    assert.equal(w.app.isNavigating, true, 'the move to Rowboat is still on its way');
    assert.notEqual(w.app._arrivedSpace, 'ideas', 'nothing "arrives" in Ideas again');
    w.moves[1].done();
    assert.equal(w.app.currentSpace, 'roarboot');
    assert.deepEqual(w.ipc, ['ideas', 'roarboot'], 'one arrival per move, none back to Ideas');
});

test('the failsafe of the running move still ends it when the camera never arrives', () => {
    const w = world();
    w.app.navigateToSpace('roarboot');
    w.advance(3000);
    assert.equal(w.app.currentSpace, 'roarboot');
    assert.equal(w.app.isNavigating, false);
});

test('a jump a sentence asked for flies short; a switch by hand keeps the long flight', () => {
    const w = world();
    w.window.spaceNavigator.switchSpace('projects', { quick: true, back: true });
    assert.equal(w.moves[0].ms, 400, 'within half a second of the answer');
    w.moves[0].done();
    w.window.spaceNavigator.switchSpace('roarboot');
    assert.equal(w.moves[1].ms, 1500);
});

test('after a jump of a sentence the title bar offers the way back to where it started', () => {
    const w = world();
    w.window.spaceNavigator.switchSpace('orders', { quick: true, back: true });
    const back = w.back();
    assert.ok(back, 'the button stands in the title bar, next to the space name');
    assert.equal(back.hidden, false, 'shown at once, while the camera still flies');
    assert.equal(back.textContent, '← zurück zu Ideen');
    w.moves[0].done();                                  // arrival in Aufträge keeps it
    assert.equal(back.hidden, false);

    back.click();
    assert.equal(back.hidden, true, 'used: it goes');
    w.moves[1].done();
    assert.equal(w.app.currentSpace, 'ideas', 'back where the sentence was written');
    assert.equal(w.moves[1].ms, 1500, 'the way back is a switch by hand');
});

test('the way back goes when the person moves on by hand; a switch by hand offers none', () => {
    const w = world();
    w.window.spaceNavigator.switchSpace('desktop', { quick: true, back: true });
    w.moves[0].done();
    assert.equal(w.back().hidden, false);
    w.window.spaceNavigator.switchSpace('roarboot');    // a tab
    assert.equal(w.back().hidden, true);
    w.moves[1].done();

    w.app.navigateToSpace('projects');                  // the arrow keys or a click in the scene
    w.window.VibeJumpBack.jumped('roarboot', 'orders');
    w.moves[2].done();                                  // arrives somewhere else than offered
    assert.equal(w.back().hidden, true);
});

test('a jump to where the app already is, or without a space to come from, offers no way back', () => {
    assert.equal(offerOf('ideas', 'ideas'), null);
    assert.equal(offerOf('', 'orders'), null);
    assert.deepEqual(offerOf('ideas', 'orders'), { from: 'ideas', to: 'orders' });
});

test('the page loads the way back, and its button can be clicked in the title bar', () => {
    assert.match(read('index.html'), /<script defer src="space-navigator\.js"><\/script>\n\s*<script defer src="jump-back\.js"><\/script>/);
    const css = read(path.join('styles', 'titlebar.css'));
    assert.match(css, /\.jump-back \{\s*-webkit-app-region: no-drag;/);
    assert.match(css, /\.jump-back\[hidden\] \{\s*display: none;/);
});

// H4c (Lauf 33): two switches back to Ideas left nothing in the log about who asked for them.
test('every switch names its source in the log: tab, way back, status line, a call without one', () => {
    const w = world();
    const tab = w.byId.get('tab-roarboot');
    w.window.spaceNavigator.switchSpace('orders', { quick: true, back: true, quelle: 'ziel' });
    w.moves[0].done();
    w.back().click();                                   // "← zurück zu Ideen"
    w.moves[1].done();
    w.window.spaceNavigator.switchSpace('roarboot', { quelle: 'tab' });
    w.moves[2].done();
    w.app.navigateToSpace('projects');                  // a script, or a way that does not say
    w.moves[3].done();
    w.app.navigateToSpace('desktop', { quelle: 'Satz: lösche alles' });   // never text from elsewhere
    assert.deepEqual(w.switches(), [
        '[Space] Wechsel nach orders durch ziel',
        '[Space] Wechsel nach ideas durch rueckweg',
        '[Space] Wechsel nach roarboot durch tab',
        '[Space] Wechsel nach projects durch unbekannt',
        '[Space] Wechsel nach desktop durch unbekannt',
    ]);
    assert.equal(tab, undefined, 'no tabs in this stand-in; the tab handler is checked in its source');
    const nav = read('space-navigator.js');
    assert.ok(nav.includes("switchSpace(spaceId, { quelle: 'tab' });"));
    const scene = read('multiverse.js');
    for (const part of ["navigateToSpace('ideas', { quelle: 'taste' })", "navigateToSpace(prevSpace, { quelle: 'geste' })",
        "navigateToSpace(spaceId, { quelle: 'agent' })", "nav.exitSpace(false, 'bereichswechsel')", "[Exit] Bubble verlassen durch taste"]) {
        assert.ok(scene.includes(part), part);
    }
    const bubble = read('bubble-navigation.js');
    assert.ok(bubble.includes("backBtn.onclick = function() { exitSpace(false, 'zurueck-knopf'); };"));
    assert.ok(bubble.includes("console.log('[Exit] Starting exit from bubble (fromPython=' + fromPython + ') durch ' + durch);"));
    const html = read('index.html');
    assert.ok(html.includes("window.bubbleNavigation.exitSpace(false, 'python');"));
    assert.ok(html.includes("window.multiverseApp.navigateToSpace(message.space, { quelle: 'python' });"));
});

// H4c: Esc on the open evaluation panel closed it and, on the same key, the scene left the bubble.
// Lauf 35: with the cursor in the chat field (after typing) Esc did nothing: the field stops every key.
test('Esc closes the open panel, also from the chat field; the bubble stays, the text stays, a card goes first', () => {
    const html = read('index.html');
    const at = html.indexOf('// Esc closes the panel and only the panel');
    assert.ok(at > 0);
    const open = "document.addEventListener('keydown', ";
    const from = html.indexOf(open, at) + open.length;
    const to = html.indexOf('}, true);', from);
    assert.ok(from > open.length && to > from, 'the listener of the panel, in the capture phase');
    const handler = html.slice(from, to + 1);

    /** The way of a key: document (capture), the target, document (bubble), window (the scene). */
    function press({ panelOpen = true, inField = false, cardOpen = false } = {}) {
        const calls = [];
        const field = { value: 'halber Satz', listeners: [(e) => e.stopPropagation()] };   // as ideas-chat.js
        const panel = { classList: { contains: (c) => c === 'open' && panelOpen } };
        const doc = {
            getElementById: () => panel,
            querySelector: (sel) => (sel === '.kv-reader:not([hidden])' && cardOpen ? {} : null),
        };
        const fn = vm.runInNewContext('(' + handler + ')', { document: doc, window: { closeEvalPanel: () => calls.push('panel zu') } });
        let stopped = false;
        const event = { key: 'Escape', preventDefault() {}, stopPropagation() { stopped = true; } };
        fn(event);                                                     // document, capture: the panel
        if (!stopped && cardOpen) { calls.push('Karte zu'); stopped = true; }  // document, capture: card-view.js
        if (!stopped && inField) for (const l of field.listeners) l(event);   // the chat field
        if (!stopped) calls.push('Szene: Bubble verlassen');            // window: multiverse.onKeyDown
        return { calls, text: field.value };
    }
    assert.deepEqual(press().calls, ['panel zu'], 'the scene never sees the key');
    const typed = press({ inField: true });
    assert.deepEqual(typed.calls, ['panel zu'], 'Lauf 35: cursor in the chat field');
    assert.equal(typed.text, 'halber Satz', 'the text in the field stays');
    assert.deepEqual(press({ cardOpen: true, inField: true }).calls, ['Karte zu'],
        'a card above the panel: the panel leaves the key to the card, and stays open');
    assert.deepEqual(press({ panelOpen: false }).calls, ['Szene: Bubble verlassen'], 'no panel open: Esc goes on to the scene as before');
    assert.deepEqual(press({ panelOpen: false, inField: true }).calls, [], 'and the chat field keeps its keys');
});

// Lauf 35: after each switch 4 to 6 lines "Changed to / Already in space". The tab, the switch and
// the arrival each told the backend, and main and Python each sent every one back.
test('a switch tells the backend once, on arrival; the echo of it is not logged again', () => {
    const w = world();
    w.window.spaceNavigator.switchSpace('roarboot', { quelle: 'tab' });
    assert.deepEqual(w.ipc, [], 'nothing while the camera flies');
    w.moves[0].done();
    assert.deepEqual(w.ipc, ['roarboot'], 'once, on arrival');
    w.window.spaceNavigator.switchSpace('roarboot', { quelle: 'tab' });   // its tab again: already there
    assert.deepEqual(w.ipc, ['roarboot']);
    const nav = read('space-navigator.js');
    assert.ok(!/makeTabHandler\([^)]*(true|false)\)/.test(nav), 'the tabs no longer tell the backend themselves');
    assert.ok(nav.includes('if (app) return;'), 'switchSpace tells it only without a scene');
    const html = read('index.html');
    assert.ok(!html.includes("'[Space] Already in space:'"));
    const at = html.indexOf("case 'space_changed':");
    const branch = html.indexOf('if (message.space !== window.currentSpace) {', at);
    assert.ok(branch > at && html.indexOf("console.log('[Space] Changed to:'", at) > branch, 'only a real change is logged');
});
