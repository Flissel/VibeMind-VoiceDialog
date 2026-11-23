// Lauf 14: a sentence with line breaks arrived in one line. The fields of the console and of the bubble
// chat were inputs, which drop line breaks, also when pasted. The bubble chat (ideas-chat.js) in a
// stand-in window: its field is a textarea, Enter sends the lines as written, Shift+Enter does not send.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const BUBBLE = '00000000-0000-4000-8000-00000000000b';

function element(tag) {
    const classes = new Set();
    const listeners = {};
    const el = {
        tag, id: '', children: [], hidden: false, textContent: '', title: '', className: '', dataset: {}, style: {},
        value: '', scrollHeight: 40,
        classList: { add: (c) => classes.add(c), remove: (c) => classes.delete(c), contains: (c) => classes.has(c),
            toggle: (c, on) => { if (on === undefined ? !classes.has(c) : on) classes.add(c); else classes.delete(c); } },
        append(...c) { el.children.push(...c); }, appendChild(c) { el.children.push(c); return c; },
        replaceChildren(...c) { el.children = c; }, insertBefore(c) { el.children.push(c); },
        addEventListener(type, fn) { (listeners[type] = listeners[type] || []).push(fn); },
        fire(type, event) { for (const fn of listeners[type] || []) fn(event); },
        setAttribute() {}, querySelector: () => null, focus() {},
    };
    return el;
}

function find(el, id) {
    if (el.id === id) return el;
    for (const child of el.children || []) {
        const found = find(child, id);
        if (found) return found;
    }
    return null;
}

function chat() {
    const byId = new Map();
    const add = (id) => { const el = element('div'); el.id = id; byId.set(id, el); return el; };
    add('space-view');
    add('space-title').textContent = 'Bubble B';
    const sent = [];
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
        spaceCanvas: { bubbleId: BUBBLE, lastNodes: [] },
        vibemind: { sendChatMessage: async (text, context, typed) => { sent.push({ text, typed }); return { success: true, message: 'ok' }; } },
        addEventListener() {}, dispatchEvent() { return true; },
        CustomEvent: class { constructor(type, init) { this.type = type; this.detail = init && init.detail; } },
        setTimeout() { return 0; }, clearTimeout() {},
    };
    vm.runInNewContext(fs.readFileSync(path.join(__dirname, 'renderer', 'ideas-chat.js'), 'utf8'), { window, globalThis: window, module: undefined });
    const input = find(byId.get('space-view'), 'ideas-chat-input');
    const key = (k, shift = false) => {
        const event = { key: k, shiftKey: shift, isComposing: false, isTrusted: true, prevented: false,
            preventDefault() { this.prevented = true; }, stopPropagation() {} };
        input.fire('keydown', event);
        return event;
    };
    return { input, sent, key };
}

const tick = () => new Promise((resolve) => setImmediate(resolve));

test('the bubble chat: a textarea; Enter sends the lines as written, as typed by the person', async () => {
    const c = chat();
    assert.equal(c.input.tag, 'textarea');
    c.input.value = 'Ergänze bei Karte 1:\nerste Zeile\nzweite Zeile';
    const enter = c.key('Enter');
    await tick();
    assert.ok(enter.prevented, 'no line break added by Enter');
    assert.equal(c.sent.length, 1);
    assert.equal(c.sent[0].text, 'Ergänze bei Karte 1:\nerste Zeile\nzweite Zeile');
    assert.equal(c.sent[0].typed, true);
    assert.equal(c.input.value, '');
});

test('Shift+Enter starts a new line and sends nothing', async () => {
    const c = chat();
    c.input.value = 'erste Zeile';
    const shift = c.key('Enter', true);
    await tick();
    assert.equal(shift.prevented, false, 'the textarea adds its line break');
    assert.equal(c.sent.length, 0);
});
