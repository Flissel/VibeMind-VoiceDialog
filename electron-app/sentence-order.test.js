'use strict';
// Lauf 3 der Pruefung, Nachmessung auf neuem Gehirn: (1) der Kontext nennt den sichtbaren Bereich,
// nie hart "ideas"; (2) jede Antwort gehoert zu ihrem Satz, auch wenn sie spaet kommt.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const read = (name) => fs.readFileSync(path.join(__dirname, ...name.split('/')), 'utf8');
const { EXTERNAL_SPACES } = require('./external-spaces');
const html = read('renderer/index.html');
const TABS = [...new Set([
    ...[...html.matchAll(/class="space-tab[^"]*"[^>]*data-space="([^"]+)"/g)].map((m) => m[1]),
    ...EXTERNAL_SPACES.map((space) => space.id),
])];

/** A small stand-in DOM: enough for ideas-chat.js install(). */
function fakeNode(tag) {
    const classes = new Set();
    const node = {
        tagName: String(tag).toUpperCase(), children: [], parentNode: null, dataset: {}, style: {}, hidden: false,
        id: '', type: '', value: '', textContent: '', title: '', disabled: false, listeners: {},
        get className() { return [...classes].join(' '); },
        set className(v) { classes.clear(); String(v).split(/\s+/).filter(Boolean).forEach((c) => classes.add(c)); },
        classList: {
            add: (...c) => c.forEach((x) => classes.add(x)),
            remove: (...c) => c.forEach((x) => classes.delete(x)),
            contains: (c) => classes.has(c),
            toggle: (c, on) => { const want = on === undefined ? !classes.has(c) : !!on; if (want) classes.add(c); else classes.delete(c); return want; },
        },
        append(...kids) { for (const k of kids) { if (k && typeof k === 'object') k.parentNode = node; node.children.push(k); } },
        appendChild(k) { node.append(k); return k; },
        replaceChildren(...kids) { node.children = []; node.append(...kids); },
        setAttribute() {}, removeAttribute() {}, focus() {},
        addEventListener(type, fn) { (node.listeners[type] = node.listeners[type] || []).push(fn); },
        querySelector: () => null, querySelectorAll: () => [],
    };
    return node;
}

function world({ space = 'ideas', bubbleOpen = false } = {}) {
    const byId = new Map();
    const view = fakeNode('div');
    view.id = 'space-view';
    if (!bubbleOpen) view.classList.add('hidden');
    byId.set('space-view', view);
    const title = fakeNode('span');
    title.textContent = 'Bubble A';
    byId.set('space-title', title);
    const body = fakeNode('body');
    const doc = {
        readyState: 'complete', body,
        getElementById: (id) => byId.get(id) || null,
        createElement: (tag) => fakeNode(tag),
        addEventListener() {},
    };
    const listeners = {};
    const sent = [];
    const win = {
        document: doc,
        localStorage: { getItem: () => null, setItem() {} },
        setTimeout: () => 0, clearTimeout() {},
        crypto: { randomUUID: () => '00000000-0000-4000-8000-0000000000ff' },
        CustomEvent: class { constructor(type, init) { this.type = type; this.detail = init && init.detail; } },
        MutationObserver: class { observe() {} },
        addEventListener(type, fn) { (listeners[type] = listeners[type] || []).push(fn); },
        dispatchEvent(event) { for (const fn of listeners[event.type] || []) fn(event); return true; },
        multiverseApp: { currentSpace: space, spaces: { ideas: { objects: [] } }, selectedBubbleId: bubbleOpen ? '00000000-0000-4000-8000-00000000000a' : null },
        vibemind: {
            sendChatMessage(text, context, typed) {
                return new Promise((resolve) => sent.push({ text, context, typed, resolve }));
            },
        },
    };
    win.window = win;
    vm.createContext(win);
    vm.runInContext(read('renderer/sentence-answer.js'), win);
    vm.runInContext(read('renderer/ideas-chat.js'), win);
    const chat = win.VibeIdeasChat;
    const log = () => {
        const found = [];
        const walk = (n) => { if (n && n.id === 'ideas-chat-log') found.push(n); (n && n.children || []).forEach(walk); };
        walk(view);
        return found[0].children.map((m) => m.textContent);
    };
    return { win, view, body, chat, sent, log, arrive(next) { win.multiverseApp.currentSpace = next; win.dispatchEvent(new win.CustomEvent('vibemind:space-arrived', { detail: { space: next } })); } };
}

test('a sentence typed in any tab names that tab, never "ideas" and never cards of a bubble', () => {
    for (const id of TABS.filter((t) => t !== 'ideas')) {
        const w = world({ space: id });
        assert.deepEqual(JSON.parse(JSON.stringify(w.chat.contextNow())), { space: id }, id);
    }
    // a bubble view still open from before: outside Ideas nothing of it goes along
    const left = world({ space: 'roarboot', bubbleOpen: true });
    assert.deepEqual(JSON.parse(JSON.stringify(left.chat.contextNow())), { space: 'roarboot' });
    // in Ideas with a bubble open: the bubble and its cards
    const inside = world({ space: 'ideas', bubbleOpen: true });
    const context = inside.chat.contextNow();
    assert.equal(context.space, 'ideas');
    assert.ok(context.bubble && 'cards' in context, 'bubble and cards only in the Ideas space');
    // in the Ideas overview: the space, no bubble
    assert.equal(world({ space: 'ideas' }).chat.contextNow().bubble, null);
});

test('one visible field per tab: the Ideas chat rests outside Ideas, the console shows', () => {
    const w = world({ space: 'ideas', bubbleOpen: true });
    assert.ok(w.body.classList.contains('ideas-chat-open'), 'inside a bubble the Ideas chat is the field');
    w.arrive('video');
    assert.ok(!w.body.classList.contains('ideas-chat-open'), 'in another tab the console is the field');
    assert.match(read('renderer/styles/ideas-chat.css'), /body\.ideas-chat-open #game-console \{\s*display: none;/);
    // another tab closes the bubble: its view lay over every other tab
    const scene = read('renderer/multiverse.js');
    assert.match(scene, /this\.isNavigating = true;[\s\S]{0,400}this\._leaveOpenBubble\(targetSpace\);/);
    assert.match(scene, /_leaveOpenBubble\(targetSpace\) \{\s*if \(targetSpace === 'ideas'\) return false;[\s\S]{0,700}nav\.exitSpace\(false, 'bereichswechsel'\)/);
    assert.match(scene, /const shownContext = answers \? answers\.contextFor\(this\.currentSpace, ideas\) : ideas;/);
    assert.match(scene, /const context = trace \? \{ \.\.\.\(shownContext \|\| \{\}\), trace_id: trace \} : shownContext;/);
});

test('two sentences at once, answers in swapped order: each answer stands under its own sentence', async () => {
    const w = world({ space: 'ideas' });
    const first = w.chat.submit('Satz eins');
    const second = w.chat.submit('Satz zwei');
    assert.equal(w.sent.length, 2, 'the second sentence is sent while the first still waits, not dropped');
    w.sent[1].resolve({ success: true, message: 'Antwort zwei' });
    await second;
    w.sent[0].resolve({ success: true, message: 'Antwort eins' });
    await first;
    assert.deepEqual(w.log(), ['Satz eins', 'Antwort eins', 'Satz zwei', 'Antwort zwei']);
});

test('the main process waits per sentence: an answer names its request, a late one finds its own', () => {
    const main = read('main.js');
    assert.match(main, /sendToPythonAndWait\(message, 'chat_response', CHAT_ANSWER_MS, \{ perRequest: true \}\)/);
    assert.match(main, /context: \{ space: 'clawport', trace_id: trace \} \}, 'chat_response', CHAT_ANSWER_MS, \{ perRequest: true \}\)/);
    // longer than the bridge's limit in operation (45 s): its answer, or its own "nicht rechtzeitig", arrives
    assert.match(main, /const CHAT_ANSWER_MS = 60000;/);
    assert.match(main, /message = \{ \.\.\.message, request_id: /);
    assert.match(main, /const waiterKey = message\.type && message\.request_id != null\s*\? responseKey\(message\.type, message\.request_id\) : message\.type;/);
    const python = read('../python/ipc/clawport_handlers.py');
    assert.match(python, /request_id = message\.get\("request_id"\)/);
    assert.doesNotMatch(python.slice(python.indexOf('async def handle_chat_text_input'), python.indexOf('async def handle_get_conversation_history')),
        /self\.send_message\(\{/, 'every answer of a sentence carries its id');
});

test('the console: a late answer goes under its sentence, and the sentence waits for it', () => {
    const scene = read('renderer/multiverse.js');
    assert.doesNotMatch(scene, /if \(!text \|\| this\.gcBusy\) return;/, 'a second sentence is not dropped');
    assert.match(scene, /const ask = this\.addGcMessage\(text, 'user'\);/);
    assert.match(scene, /this\.addGcMessage\(shown\.text, kind, ask\);/);
    assert.match(scene, /pair\.__waiting = true;/);
    assert.match(scene, /if \(ask\.__pair\) ask\.__pair\.__waiting = false;/);
});

// Lauf 5: "Vorschlag übernehmen" ersetzt die Karte samt eigener Ergaenzungen. Der Knopf sagt das vorher.
test('"Vorschlag übernehmen" says first what it replaces, the second click takes it', () => {
    const w = world({ space: 'ideas', bubbleOpen: true });
    w.win.spaceCanvas = { lastNodes: [{ id: '00000000-0000-4000-8000-000000000001', title: 'Karte 1' }] };
    const status = (detail) => w.win.dispatchEvent(new w.win.CustomEvent('vibemind:task-status', { detail: { space: 'ideas', targets: ['00000000-0000-4000-8000-000000000001'], ...detail } }));
    status({ state: 'accepted' });
    status({ state: 'note', note: 'hinweis', result: 'Ein Vorschlag liegt vor.', saetze: ['Vorschlag zeigen', 'Vorschlag übernehmen', 'Vorschlag verwerfen'] });
    const found = [];
    const walk = (n) => { if (n && n.className === 'ideas-chat-answer') found.push(n); (n && n.children || []).forEach(walk); };
    walk(w.view);
    const take = found.find((b) => b.textContent === 'Vorschlag übernehmen');
    assert.ok(take, 'the sentences of the Brain are buttons');
    const click = () => take.listeners.click.forEach((fn) => fn({ isTrusted: true }));
    click();
    assert.equal(w.sent.length, 0, 'the first click sends nothing');
    assert.equal(take.textContent, 'Ja, übernehmen');
    const warn = [];
    const look = (n) => { if (n && n.className === 'ideas-chat-warn') warn.push(n.textContent); (n && n.children || []).forEach(look); };
    look(w.view);
    assert.deepEqual(warn, ['Ersetzt den Inhalt der Karte „Karte 1“, auch deine eigenen Ergänzungen. Zum Übernehmen noch einmal klicken.']);
    click();
    assert.equal(w.sent.length, 1);
    assert.equal(w.sent[0].text, 'Vorschlag übernehmen');
    click();
    assert.equal(w.sent.length, 1, 'once');
    // "Vorschlag zeigen" asks nothing first
    const show = found.find((b) => b.textContent === 'Vorschlag zeigen');
    assert.equal(show.disabled, true, 'after one answer the others rest');
});

test('the new Brain names "Vorschlag trotzdem übernehmen": that button asks first too and sends the sentence itself', () => {
    const w = world({ space: 'ideas', bubbleOpen: true });
    w.win.spaceCanvas = { lastNodes: [{ id: '00000000-0000-4000-8000-000000000001', title: 'Karte 1' }] };
    const status = (detail) => w.win.dispatchEvent(new w.win.CustomEvent('vibemind:task-status', { detail: { space: 'ideas', targets: ['00000000-0000-4000-8000-000000000001'], ...detail } }));
    status({ state: 'accepted' });
    status({ state: 'note', note: 'hinweis', result: 'Ein Vorschlag liegt vor.', saetze: ['Vorschlag zeigen', 'Vorschlag trotzdem übernehmen', 'Vorschlag verwerfen'] });
    const found = [];
    const walk = (n) => { if (n && n.className === 'ideas-chat-answer') found.push(n); (n && n.children || []).forEach(walk); };
    walk(w.view);
    const take = found.find((b) => b.textContent === 'Vorschlag trotzdem übernehmen');
    const click = () => take.listeners.click.forEach((fn) => fn({ isTrusted: true }));
    click();
    assert.equal(w.sent.length, 0);
    click();
    assert.deepEqual(w.sent.map((s) => s.text), ['Vorschlag trotzdem übernehmen'], 'one step at the Brain, not three');
});

test('both sentences named: "Vorschlag übernehmen", once confirmed, sends the writing one', () => {
    const w = world({ space: 'ideas', bubbleOpen: true });
    w.win.spaceCanvas = { lastNodes: [] };
    const status = (detail) => w.win.dispatchEvent(new w.win.CustomEvent('vibemind:task-status', { detail: { space: 'ideas', targets: [], ...detail } }));
    status({ state: 'accepted' });
    status({ state: 'note', note: 'hinweis', result: 'Ein Vorschlag liegt vor.', saetze: ['Vorschlag übernehmen', 'Vorschlag trotzdem übernehmen'] });
    const found = [];
    const walk = (n) => { if (n && n.className === 'ideas-chat-answer') found.push(n); (n && n.children || []).forEach(walk); };
    walk(w.view);
    const take = found.find((b) => b.textContent === 'Vorschlag übernehmen');
    take.listeners.click.forEach((fn) => fn({ isTrusted: true }));
    take.listeners.click.forEach((fn) => fn({ isTrusted: true }));
    assert.deepEqual(w.sent.map((s) => s.text), ['Vorschlag trotzdem übernehmen']);
});

test('another tab while a bubble is open: the app no longer thinks itself inside a bubble, the overlay goes away', () => {
    const scene = read('renderer/multiverse.js');
    const method = (name) => {
        const start = scene.indexOf(`\n    ${name}(`);
        return scene.slice(start, scene.indexOf('\n    }\n', start) + 7);
    };
    const classes = (on) => ({
        set: new Set(on),
        contains(c) { return this.set.has(c); }, add(c) { this.set.add(c); }, remove(c) { this.set.delete(c); },
    });
    const view = { classList: classes([]) };
    const overlay = { classList: classes([]) };
    const sandbox = { console: { log() {} }, Date, Math };
    sandbox.document = { getElementById: (id) => ({ 'space-view': view, 'transition-overlay': overlay })[id] || null };
    sandbox.window = sandbox;
    require('node:vm').runInNewContext(`class Scene {${method('_leaveOpenBubble')}${method('exitBubbleWithAnimation')}}
        this.Scene = Scene;`, sandbox);
    const app = new sandbox.Scene();
    Object.assign(app, { isNavigating: true, isInsideBubble: true, currentSpace: 'ideas' });
    // bubble-navigation.exitSpace: the overlay goes up, the view hides, the exit runs in the next frame
    sandbox.bubbleNavigation = { exitSpace() { overlay.classList.add('active'); view.classList.add('hidden'); app.exitBubbleWithAnimation(); } };
    assert.equal(app._leaveOpenBubble('rowboat'), true);
    assert.equal(app.isInsideBubble, false, 'the move to Rowboat is running, so the exit animation never cleared the flag');
    assert.equal(overlay.classList.contains('active'), false);
});

test('the voice panel stands above the console, however many pairs its list holds', () => {
    const scene = read('renderer/multiverse.js');
    const start = scene.indexOf('\n    _placeVoicePanel(');
    const method = scene.slice(start, scene.indexOf('\n    }\n', start) + 7);
    const panel = { style: {} };
    const consoleEl = { offsetHeight: 60 };
    const sandbox = { document: { getElementById: (id) => ({ 'voice-panel': panel, 'game-console': consoleEl })[id] || null } };
    vm.runInNewContext(`class Scene {${method}} this.Scene = Scene;`, sandbox);
    const app = new sandbox.Scene();
    app.gcVisible = true;
    app._placeVoicePanel();
    assert.equal(panel.style.bottom, '84px', 'only the input row: just above it');
    consoleEl.offsetHeight = 60 + 160;   // the pair list at its full height
    app._placeVoicePanel();
    assert.equal(panel.style.bottom, '244px', 'the list grew: the panel moves up with it, nothing covers it');
    app.gcVisible = false;
    app._placeVoicePanel();
    assert.equal(panel.style.bottom, '20px', 'console closed: back to its own place');
    assert.match(scene, /new ResizeObserver\(\(\) => this\._placeVoicePanel\(\)\)\.observe\(gcEl\)/, 'each new pair moves it again');
    assert.doesNotMatch(scene, /voicePanel\.style\.bottom = '90px'/);
});

// Lauf 24: "Lösche diese Bubble" → "Ja, löschen". The database lost the bubble, the open view kept every
// card and its link. The answer came 390 ms after the deletion (window log). Now the app leaves the
// deleted bubble for the overview, and the console there says the answer, "zurück" included.
test('the open bubble is deleted: the app leaves it, the answer with "zurück" stays readable in the console', async () => {
    const w = world({ space: 'ideas', bubbleOpen: true });
    const BUBBLE = '00000000-0000-4000-8000-00000000000a';
    const consoleSaid = [];
    const exits = [];
    w.win.multiverseApp.addGcMessage = (text, kind) => consoleSaid.push([kind, text]);
    w.win.bubbleNavigation = { exitSpace: () => { exits.push('exit'); w.view.classList.add('hidden'); } };

    assert.equal(w.chat.bubbleRemoved('00000000-0000-4000-8000-0000000000ee'), false, 'another bubble: nothing');
    assert.deepEqual(exits, []);

    const asked = w.chat.submit('Lösche diese Bubble');
    w.sent[0].resolve({ success: true, question: true, message: 'Soll ich die Bubble „Bubble A“ löschen? Sag „Ja, löschen“.' });
    await asked;
    const yes = w.chat.submit('Ja, löschen');
    assert.equal(w.chat.bubbleRemoved(BUBBLE), true, 'the realtime row of the bubble is gone, before the answer');
    assert.deepEqual(exits, ['exit'], 'back to the overview of Ideas');
    assert.deepEqual(consoleSaid, [], 'nothing to say yet: the answer is not there');
    const answer = 'Die Bubble „Bubble A“ ist gelöscht, mit ihren Karten. Mit „Zurück“ holst du alles wieder.';
    w.sent[1].resolve({ success: true, message: answer });
    await yes;
    assert.deepEqual(consoleSaid, [['agent', answer]], 'the console of the overview says it');
});

test('the realtime deletion asks the chat before the scene forgets which bubble was open', () => {
    const html = read('renderer/index.html');
    const at = html.indexOf("case 'node_removed':");
    const chat = html.indexOf('window.VibeIdeasChat.bubbleRemoved(message.node_id)', at);
    const scene = html.indexOf('window.multiverseApp.removeBubble(message.node_id)', at);
    assert.ok(at > -1 && chat > at && scene > chat);
});
