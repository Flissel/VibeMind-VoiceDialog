// The status line of renderer/task-navigate.js in a small stand-in for the window: events in the
// order the app gets them, and what the line shows after each.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const SOURCE = fs.readFileSync(path.join(__dirname, 'renderer', 'task-navigate.js'), 'utf8');

function element(id) {
    return {
        id, hidden: false, textContent: '', title: '', className: '', dataset: {},
        listeners: {},
        addEventListener(type, fn) { this.listeners[type] = fn; },
    };
}

function scene() {
    let now = 0;
    let timers = [];
    const byId = new Map();
    const anchor = element('titlebar-space');
    anchor.parentNode = { insertBefore(el) { byId.set(el.id, el); } };
    byId.set('titlebar-space', anchor);
    const listeners = {};
    const window = {
        document: {
            getElementById: (id) => byId.get(id) || null,
            createElement: () => element(''),
            querySelectorAll: () => [],
        },
        multiverseApp: { currentSpace: 'ideas', spaces: { ideas: {}, roarboot: {} }, isNavigating: false },
        addEventListener(type, fn) { (listeners[type] = listeners[type] || []).push(fn); },
        dispatchEvent(event) { for (const fn of listeners[event.type] || []) fn(event); return true; },
        CustomEvent: class { constructor(type, init) { this.type = type; this.detail = init && init.detail; } },
        setTimeout(fn, ms) { const t = { fn, at: now + ms }; timers.push(t); return t; },
        clearTimeout(t) { timers = timers.filter((x) => x !== t); },
    };
    vm.runInNewContext(SOURCE, { window, globalThis: window, module: undefined });
    const line = () => byId.get('task-status');
    return {
        handle: window.VibeTaskNav.handle,
        emit: (type, detail) => window.dispatchEvent(new window.CustomEvent(type, { detail })),
        advance(ms) {
            now += ms;
            for (const t of timers.filter((x) => x.at <= now)) { timers = timers.filter((x) => x !== t); t.fn(); }
        },
        visible: () => Boolean(line()) && !line().hidden,
        text: () => (line() ? line().textContent : ''),
        GRACE: window.VibeTaskNav.ANSWER_GRACE_MS,
    };
}

test('an answer that comes before the events of the plan does not make the line vanish and come back', () => {
    const s = scene();
    s.emit('vibemind:sentence-sent');
    assert.equal(s.visible(), true);
    assert.equal(s.text(), '● arbeitet …');

    s.advance(1000);
    s.emit('vibemind:sentence-answered', { text: 'Notiz angelegt.', success: true });
    assert.equal(s.visible(), true, 'still there right after the answer');

    s.advance(200);
    s.handle({ type: 'task_status', state: 'reset', plan_id: 'p1' });
    assert.equal(s.visible(), true, 'the reset of a new plan keeps the waiting line');
    s.handle({ type: 'task_status', state: 'running', space: 'ideas', step: 'festhalten', done: 0, total: 1, plan_id: 'p1' });
    assert.equal(s.visible(), true);
    s.handle({ type: 'task_status', state: 'done', space: 'ideas', step: 'festhalten', done: 1, total: 1, elapsed_s: 1.2, plan_id: 'p1' });
    assert.equal(s.visible(), true);
    assert.match(s.text(), /fertig in 1,2 s — Notiz angelegt\./);
});

test('an answer without any plan in the app removes the waiting line after a short wait', () => {
    const s = scene();
    s.emit('vibemind:sentence-sent');
    s.emit('vibemind:sentence-answered', { text: 'Hallo.', success: true });
    s.advance(s.GRACE - 1);
    assert.equal(s.visible(), true);
    s.advance(1);
    assert.equal(s.visible(), false);
});

test('a sentence that never gets an answer loses the waiting line after a minute', () => {
    const s = scene();
    s.emit('vibemind:sentence-sent');
    s.advance(59999);
    assert.equal(s.visible(), true);
    s.advance(1);
    assert.equal(s.visible(), false);
});
