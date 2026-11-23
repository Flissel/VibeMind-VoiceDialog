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

function scene({ currentSpace = 'ideas' } = {}) {
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
        multiverseApp: {
            currentSpace, spaces: { ideas: {}, roarboot: {}, desktop: {} }, isNavigating: false, isInsideBubble: false,
            dashboardOpened: 0,
            enterDesktopDashboard() { this.dashboardOpened += 1; },
        },
        // The tab switch of the scene: arrives at once here (the camera move is not part of this test).
        spaceNavigator: {
            switchSpace(space) {
                window.multiverseApp.currentSpace = space;
                window.dispatchEvent(new window.CustomEvent('vibemind:space-arrived', { detail: { space } }));
            },
        },
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
        app: window.multiverseApp,
        emit: (type, detail) => window.dispatchEvent(new window.CustomEvent(type, { detail })),
        // the Enter that sends a sentence: a trusted key press reaches the window first
        pressEnter: () => window.dispatchEvent({ type: 'keydown', key: 'Enter', isTrusted: true }),
        advance(ms) {
            now += ms;
            for (const t of timers.filter((x) => x.at <= now)) { timers = timers.filter((x) => x !== t); t.fn(); }
        },
        visible: () => Boolean(line()) && !line().hidden,
        text: () => (line() ? line().textContent : ''),
        GRACE: window.VibeTaskNav.ANSWER_GRACE_MS,
        KEEP: window.VibeTaskNav.KEEP_MS,
    };
}

const { createTaskNavigator } = require('./task-navigation');

/** A sentence typed into the console below the scene (Enter, then the app sends it), as in the app. */
function typedSentence(s) {
    s.pressEnter();
    s.emit('vibemind:sentence-sent');
}

/** The events of the Brain as the main process turns them into messages (task-navigation.js). */
function brain(s, space, capability) {
    const navigator = createTaskNavigator((message) => s.handle(message));
    return {
        started: () => navigator.handle('plan_started', { plan_id: 'p1', hops: [{}], space, intent: 'Zeig mir meine Bubbles' }),
        hopStarted: () => navigator.handle('hop_started', { space, capability, description: capability + ' via shortcut' }),
        hopCompleted: () => navigator.handle('hop_completed', { space, capability, ok: true, result_preview: '15 bubbles: - BUBBLE-V2-082701 (id=abc, score=0)' }),
        completed: () => navigator.handle('plan_completed', { plan_id: 'p1', ok: true, elapsed_s: 1.3 }),
    };
}

const ANSWER = '15 Bubbles: „BUBBLE-V2-082701“ und 14 weitere.';

for (const [name, order] of [
    ['plan first, answer last', ['started', 'hopStarted', 'hopCompleted', 'completed', 'answer']],
    ['answer before the plan started', ['answer', 'started', 'hopStarted', 'hopCompleted', 'completed']],
    ['answer between the steps', ['started', 'hopStarted', 'answer', 'hopCompleted', 'completed']],
]) {
    test(`a typed sentence of another space jumps there and shows its result (${name})`, () => {
        // measured in the app on 2026-11-23 (voice 9b7b46c): typed with a real Enter in roarboot,
        // the app stayed in roarboot and the finished line stood hidden in the element
        const s = scene({ currentSpace: 'roarboot' });
        const b = brain(s, 'bubbles', 'bubble_list');
        typedSentence(s);
        for (const step of order) {
            if (step === 'answer') s.emit('vibemind:sentence-answered', { text: ANSWER, success: true });
            else b[step]();
            s.advance(150);
        }
        assert.equal(s.app.currentSpace, 'ideas', 'the app jumped into the space of the task');
        assert.equal(s.visible(), true, 'the finished line is visible');
        assert.match(s.text(), /^✓ Ideas: fertig in 1,3 s — 15 Bubbles: „BUBBLE-V2-082701“ und 14 weitere\.$/);
        // it stays as long as under dfd8bed, then goes
        s.advance(s.KEEP - 1000);
        assert.equal(s.visible(), true);
        s.advance(1000);
        assert.equal(s.visible(), false);
    });
}

test('input after the send still keeps the app where the user works', () => {
    const s = scene({ currentSpace: 'roarboot' });
    const b = brain(s, 'bubbles', 'bubble_list');
    typedSentence(s);
    s.pressEnter(); // the user goes on typing here
    b.started();
    assert.equal(s.app.currentSpace, 'roarboot');
});

test('a jump of a plan still waiting for a camera move is dropped once the person acts', () => {
    const s = scene({ currentSpace: 'roarboot' });
    const b = brain(s, 'bubbles', 'bubble_list');
    typedSentence(s);
    s.app.isNavigating = true;      // a camera move runs: the jump waits
    b.started();
    assert.equal(s.app.currentSpace, 'roarboot');
    s.pressEnter();                 // the person does something else meanwhile
    s.app.isNavigating = false;
    for (let i = 0; i < 40; i++) s.advance(300); // every retry runs out
    assert.equal(s.app.currentSpace, 'roarboot', 'the plan does not pull the person away afterwards');
});

test('a Desktop sentence does not jump; its result stands in the line wherever the user is', () => {
    // 2026-11-23: the Desktop space works in the background as the eyes of the Brain.
    const s = scene({ currentSpace: 'roarboot' });
    const b = brain(s, 'desktop', 'desktop_open_app');
    typedSentence(s);
    b.started();
    b.hopStarted(); b.hopCompleted(); b.completed();
    s.emit('vibemind:sentence-answered', { text: 'Der Rechner ist offen.', success: true });
    for (let i = 0; i < 40; i++) s.advance(300); // every retry and wait runs out
    assert.equal(s.app.currentSpace, 'roarboot', 'no jump into the Desktop space');
    assert.equal(s.app.dashboardOpened, 0);
    assert.equal(s.visible(), true);
    assert.match(s.text(), /^✓ Desktop: fertig in 1,3 s — Der Rechner ist offen\. →$/);
});

test('an Ideas sentence still jumps (the list of spaces without jump names only desktop)', () => {
    const s = scene({ currentSpace: 'roarboot' });
    const b = brain(s, 'ideas', 'idea_list');
    typedSentence(s);
    b.started();
    assert.equal(s.app.currentSpace, 'ideas');
});

test('raw data of a tool is never shown: the neutral line stays until the sentence comes', () => {
    const s = scene({ currentSpace: 'roarboot' });
    const navigator = createTaskNavigator((message) => s.handle(message));
    typedSentence(s);
    navigator.handle('plan_started', { plan_id: 'p1', hops: [{}], space: 'desktop', intent: 'x' });
    navigator.handle('hop_started', { space: 'desktop', capability: 'desktop_open_app' });
    const seen = [s.text()];
    navigator.handle('hop_completed', { space: 'desktop', ok: true, result_preview: "{'_meta': {'progressToken': 3}, 'content': [{'type': 'text'}]}" });
    seen.push(s.text());
    navigator.handle('plan_completed', { plan_id: 'p1', ok: true, elapsed_s: 2.1 });
    seen.push(s.text());
    assert.equal(s.visible(), true, 'never empty in between');
    assert.equal(s.text(), '● arbeitet …');
    s.advance(600);
    s.emit('vibemind:sentence-answered', { text: 'Der Rechner ist offen.', success: true });
    seen.push(s.text());
    for (const text of seen) assert.doesNotMatch(text, /_meta|\{'/, text);
    assert.match(s.text(), /— Der Rechner ist offen\./);
});

test('without an answer the finished line comes after a short wait, still without raw data', () => {
    const s = scene({ currentSpace: 'roarboot' });
    const navigator = createTaskNavigator((message) => s.handle(message));
    typedSentence(s);
    navigator.handle('plan_started', { plan_id: 'p1', hops: [{}], space: 'desktop', intent: 'x' });
    navigator.handle('hop_completed', { space: 'desktop', ok: true, result_preview: "{'_meta': {}}" });
    navigator.handle('plan_completed', { plan_id: 'p1', ok: true, elapsed_s: 2.1 });
    assert.equal(s.text(), '● arbeitet …');
    s.advance(5000);
    assert.equal(s.visible(), true);
    assert.equal(s.text(), '✓ Desktop: fertig in 2,1 s →');
});

test('a result that arrives during the camera move into its space is shown at once', () => {
    const s = scene({ currentSpace: 'roarboot' });
    const b = brain(s, 'bubbles', 'bubble_list');
    // the move does not end at once here: the switch waits for it
    s.app.isNavigating = true;
    typedSentence(s);
    s.emit('vibemind:sentence-answered', { text: ANSWER, success: true });
    b.started(); b.hopStarted(); b.hopCompleted(); b.completed();
    assert.equal(s.app.currentSpace, 'roarboot', 'still on the way');
    assert.equal(s.visible(), true, 'the line is not hidden while the app is on its way');
    assert.match(s.text(), /fertig in 1,3 s — 15 Bubbles/);
    s.app.isNavigating = false;
    s.advance(300);
    assert.equal(s.app.currentSpace, 'ideas');
    assert.equal(s.visible(), true);
});

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

// Lauf 10: after the end the line was hidden, but the hidden #task-status still said "● arbeitet …".
test('at the end the hidden line keeps no old text', () => {
    const s = scene();
    s.emit('vibemind:sentence-sent');
    assert.equal(s.text(), '\u25CF arbeitet \u2026');
    s.emit('vibemind:sentence-answered', { text: 'Hallo.', success: true });
    s.advance(s.GRACE);
    assert.equal(s.visible(), false);
    assert.equal(s.text(), '');
});
