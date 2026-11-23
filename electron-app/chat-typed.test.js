// eingabe "getippt" may only come from a person who typed or clicked in one of the two chat fields
// (Desktop tasks run only from typed input). Two layers guard it:
//   1. the renderer (multiverse.js console, ideas-chat.js bubble chat) claims `typed` only for an event
//      the browser marks isTrusted; every call from code leaves it false;
//   2. the preload checks the claim in its isolated world (chat-input.test.js, preload part).
// Here layer 1 in behaviour: the real code of both fields in a stand-in window, with the events a
// person raises (isTrusted true) and the ones a script can raise (isTrusted false, direct calls).
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const read = (file) => fs.readFileSync(path.join(__dirname, 'renderer', file), 'utf8');

function element(tag, byId) {
    const classes = new Set();
    const listeners = {};
    const el = {
        tag, id: '', type: '', children: [], hidden: false, textContent: '', title: '', dataset: {}, style: {}, attrs: {},
        value: '', scrollHeight: 20, parentNode: null, firstChild: null,
        classList: { add: (c) => classes.add(c), remove: (c) => classes.delete(c), contains: (c) => classes.has(c),
            toggle: (c, on) => { if (on === undefined ? !classes.has(c) : on) classes.add(c); else classes.delete(c); } },
        set className(v) { for (const c of String(v).split(' ').filter(Boolean)) classes.add(c); },
        get className() { return [...classes].join(' '); },
        append(...c) { for (const x of c) el.appendChild(x); },
        appendChild(c) {
            el.children = el.children.filter((x) => x !== c).concat([c]);
            c.parentNode = el; el.firstChild = el.children[0];
            if (c.id && byId) byId.set(c.id, c);
            return c;
        },
        insertBefore(c, ref) {
            const i = el.children.indexOf(ref);
            el.children.splice(i < 0 ? el.children.length : i, 0, c);
            c.parentNode = el; el.firstChild = el.children[0];
            if (c.id && byId) byId.set(c.id, c);
        },
        replaceChildren(...c) { el.children = []; el.append(...c); },
        addEventListener(type, fn) { (listeners[type] = listeners[type] || []).push(fn); },
        fire(type, event) { for (const fn of listeners[type] || []) fn(event); },
        setAttribute(k, v) { el.attrs[k] = v; }, querySelector: () => null, focus() {}, blur() {},
    };
    return el;
}

/** An event as the browser hands it to the listeners; isTrusted false is what a script can raise. */
function key(k, { trusted, shift = false } = {}) {
    return { key: k, shiftKey: shift, isComposing: false, isTrusted: trusted, ctrlKey: false, metaKey: false,
        prevented: false, preventDefault() { this.prevented = true; }, stopPropagation() {} };
}
const click = (trusted) => ({ isTrusted: trusted, preventDefault() {}, stopPropagation() {} });
const tick = () => new Promise((resolve) => setImmediate(resolve));

/** The console of multiverse.js as it is (init, send) and start-examples.js with its "?". */
function consoleWorld() {
    const scene = read('multiverse.js');
    const helper = /const FIELD_MAX_PX[\s\S]*?\n\}\n/.exec(scene)[0];
    const start = scene.indexOf('    initGameConsole() {');
    const end = scene.indexOf('\n    addGcMessage(', start);
    // without the doc comment of addGcMessage at the end (only that one: no "*/" inside it)
    const methods = scene.slice(start, end).replace(/\n\s*\/\*\*(?:(?!\*\/)[\s\S])*\*\/\s*$/, '');
    const byId = new Map();
    const add = (id, tag = 'div') => { const el = element(tag, byId); el.id = id; byId.set(id, el); return el; };
    add('game-console');
    const messages = add('gc-messages');
    const row = add('gc-input-row');
    const input = add('gc-input', 'textarea');
    const send = add('gc-send-btn', 'button');
    row.appendChild(input); row.appendChild(send);
    add('gc-spinner');
    const sent = [];
    const docListeners = {};
    const document = {
        readyState: 'complete', activeElement: input,
        getElementById: (id) => byId.get(id) || null,
        createElement: (tag) => element(tag, byId),
        addEventListener(type, fn) { (docListeners[type] = docListeners[type] || []).push(fn); },
    };
    const window = {
        crypto: { randomUUID: () => '00000000-0000-4000-8000-0000000000ff' },
        vibemind: { sendChatMessage: async (text, context, typed) => { sent.push({ text, typed }); return { success: true, message: 'ok' }; } },
        VibeSentenceAnswer: require('./renderer/sentence-answer'),
        addEventListener() {}, dispatchEvent() { return true; },
    };
    const context = vm.createContext({ window, document, console: { log() {}, warn() {}, error() {} },
        CustomEvent: class { constructor(type, init) { this.type = type; this.detail = init && init.detail; } } });
    vm.runInContext(helper + 'class Scene {\n' + methods + '\n    addGcMessage() { return {}; }\n}\nthis.Scene = Scene;', context);
    const app = new context.Scene();
    app.currentSpace = 'desktop';
    app.initGameConsole();
    window.multiverseApp = app;
    // the "?" of the console, as the page mounts it
    vm.runInNewContext(read('start-examples.js'), { window, document, self: window, module: undefined });
    return { app, input, send, sent, byId, messages };
}

/** The bubble chat of ideas-chat.js as it is, with start-examples.js loaded first (as in index.html). */
function bubbleWorld() {
    const byId = new Map();
    const add = (id) => { const el = element('div', byId); el.id = id; byId.set(id, el); return el; };
    add('space-view');
    add('space-title').textContent = 'Bubble A';
    const sent = [];
    const window = {
        document: { readyState: 'complete', body: element('body', byId), getElementById: (id) => byId.get(id) || null,
            createElement: (tag) => element(tag, byId), querySelectorAll: () => [], addEventListener() {} },
        localStorage: { getItem: () => null, setItem() {} },
        crypto: { randomUUID: () => '00000000-0000-4000-8000-0000000000ff' },
        MutationObserver: class { observe() {} },
        multiverseApp: { currentSpace: 'ideas', spaces: { ideas: {} }, isNavigating: false, isInsideBubble: true, getBubbleById: () => null },
        __currentEvalBubble: { dbId: '00000000-0000-4000-8000-00000000000b' },
        spaceCanvas: { bubbleId: '00000000-0000-4000-8000-00000000000b', lastNodes: [] },
        vibemind: { sendChatMessage: async (text, context, typed) => { sent.push({ text, typed }); return { success: true, message: 'ok' }; } },
        addEventListener() {}, dispatchEvent() { return true; },
        CustomEvent: class { constructor(type, init) { this.type = type; this.detail = init && init.detail; } },
        setTimeout() { return 0; }, clearTimeout() {},
    };
    const context = { window, self: window, document: window.document, globalThis: window, module: undefined };
    vm.runInNewContext(read('start-examples.js'), context);
    vm.runInNewContext(read('ideas-chat.js'), context);
    const input = byId.get('ideas-chat-input');
    const row = input.parentNode;
    const send = row.children.find((c) => c.classList.contains('ideas-chat-send'));
    const help = row.children.find((c) => c.id === 'ideas-chat-help');
    return { window, input, row, send, help, sent };
}

test('console: only a trusted Enter or a trusted click on ▶ says "typed"; every call from code does not', async () => {
    const w = consoleWorld();
    const typedOf = async (act) => { w.sent.length = 0; w.input.value = 'Öffne den Rechner'; act(); await tick(); return w.sent.map((s) => s.typed); };

    assert.deepEqual(await typedOf(() => w.input.fire('keydown', key('Enter', { trusted: true }))), [true], 'Enter by the person');
    assert.deepEqual(await typedOf(() => w.send.fire('click', click(true))), [true], 'click on ▶ by the person');

    assert.deepEqual(await typedOf(() => w.input.fire('keydown', key('Enter', { trusted: false }))), [false],
        'dispatchEvent(new KeyboardEvent(...)) of a script');
    assert.deepEqual(await typedOf(() => w.send.fire('click', click(false))), [false], 'send.click() of a script');
    assert.deepEqual(await typedOf(() => w.app.sendGameConsoleMessage()), [false], 'the send function called directly');
    assert.deepEqual(await typedOf(() => w.app.sendGameConsoleMessage({})), [false], 'called with an empty option');

    assert.deepEqual(await typedOf(() => w.input.fire('keydown', key('Enter', { trusted: true, shift: true }))), [],
        'Shift+Enter sends nothing (a new line)');
});

test('console "?": a click on it and on a sentence only fills the field, it never sends', async () => {
    const w = consoleWorld();
    const help = w.byId.get('gc-help-btn');
    assert.ok(help, 'the "?" of the console');
    assert.equal(help.type, 'button');
    w.input.value = '';
    help.fire('click', click(true));
    const sentence = w.messages.children.find((c) => c.classList.contains('gc-start')).children.find((c) => c.tag === 'button');
    sentence.fire('click', click(true));
    await tick();
    assert.notEqual(w.input.value, '', 'the field is filled');
    assert.deepEqual(w.sent, [], 'nothing sent');
});

test('bubble chat: only a trusted Enter or a trusted submit says "typed"; every call from code does not', async () => {
    const w = bubbleWorld();
    assert.equal(w.input.tag, 'textarea');
    const typedOf = async (act) => { w.sent.length = 0; w.input.value = 'Ergänze bei Karte 1:\nerste Zeile'; act(); await tick(); return w.sent.map((s) => s.typed); };

    assert.deepEqual(await typedOf(() => w.input.fire('keydown', key('Enter', { trusted: true }))), [true], 'Enter by the person');
    assert.deepEqual(await typedOf(() => w.row.fire('submit', click(true))), [true], 'the form sent by a click of the person on ▶');

    assert.deepEqual(await typedOf(() => w.input.fire('keydown', key('Enter', { trusted: false }))), [false],
        'dispatchEvent(new KeyboardEvent(...)) of a script');
    assert.deepEqual(await typedOf(() => w.row.fire('submit', click(false))), [false], 'send.click() or form.requestSubmit() of a script');
    assert.deepEqual(await typedOf(() => w.window.VibeIdeasChat.submit('Öffne den Rechner')), [false], 'the send function called directly');
    assert.deepEqual(await typedOf(() => w.window.VibeIdeasChat.submit('Öffne den Rechner', {})), [false], 'called with an empty option');

    assert.deepEqual(await typedOf(() => w.input.fire('keydown', key('Enter', { trusted: true, shift: true }))), [],
        'Shift+Enter sends nothing (a new line)');
});

test('bubble chat "?": a button that never submits its form; a click on a sentence only fills the field', async () => {
    const w = bubbleWorld();
    assert.ok(w.help, 'the "?" of the bubble chat');
    assert.equal(w.help.type, 'button', 'type button: a click does not submit the form');
    w.input.value = '';
    w.help.fire('click', click(true));
    const box = w.window.document.getElementById('ideas-chat-log').children.find((c) => c.classList.contains('ideas-chat-start'));
    box.children.find((c) => c.tag === 'button').fire('click', click(true));
    await tick();
    assert.notEqual(w.input.value, '', 'the field is filled');
    assert.deepEqual(w.sent, [], 'nothing sent');
});
