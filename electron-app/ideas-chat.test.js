const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const { buildContext, noteText, cardTitle, createCardStore, createHistory, reasonsFor, bubbleDbId, MAX_CARDS, HISTORY_MAX, MAX_REASONS } = require('./renderer/ideas-chat');

const B1 = 'fa8d4158-f721-4290-a0cf-7f20da754372';
const B2 = '0b1c2d3e-0000-4000-8000-123456789abc';

test('inside a bubble the context names the bubble and its cards', () => {
    const context = buildContext({
        bubble: { id: B1, title: 'Marketing' },
        nodes: [
            { id: 'n1', content: { title: 'Zielgruppe' }, metadata: { bewertung: { wert: 80 } } },
            { id: 'n2', title: 'Kanäle', content_json: { type: 'table' } },
            { id: 'n3', content: { text: 'nur Text' }, format_schema: { type: 'action_list' } },
            null,
            { title: 'ohne Kennung' },
        ],
        bubbles: [{ id: B2, title: 'nicht gefragt' }],
        newId: 'u-1',
        selection: ['n2', 'gibt-es-nicht'],
        lastId: 'n3',
    });

    assert.deepEqual(context, {
        space: 'ideas',
        bubble: { id: B1, title: 'Marketing' },
        cards: [
            { id: 'n1', title: 'Zielgruppe', format: 'note', score: 80 },
            { id: 'n2', title: 'Kanäle', format: 'table', score: null },
            { id: 'n3', title: 'nur Text', format: 'action_list', score: null },
        ],
        selection: ['n2'],
        last_id: 'n3',
        new_id: 'u-1',
    });
});

test('in the overview the context names the bubbles instead', () => {
    const context = buildContext({ bubble: null, nodes: [{ id: 'n1' }], bubbles: [{ id: B1, title: 'Marketing' }, { title: 'ohne' }, { id: 3, title: 'nur eine Ordnungszahl' }] });

    assert.deepEqual(context, { space: 'ideas', bubble: null, bubbles: [{ id: B1, title: 'Marketing' }] });
});

test('the context is capped', () => {
    const nodes = Array.from({ length: MAX_CARDS + 20 }, (_, i) => ({ id: i, title: 'K' + i }));

    const context = buildContext({ bubble: { id: 1, title: 'B' }, nodes });
    assert.equal(MAX_CARDS, 100);
    assert.equal(context.cards.length, MAX_CARDS);
    assert.equal(context.cards_total, MAX_CARDS + 20, 'a cut list says how many cards there are');
    assert.equal(buildContext({ bubble: { id: 1, title: 'B' }, nodes: nodes.slice(0, 3) }).cards_total, undefined);
});

test('noteText finds the note in a sentence that plainly asks to hold one', () => {
    assert.equal(noteText('Notiere: API Design'), 'API Design');
    assert.equal(noteText('halte fest, dass der Termin am Montag ist'), 'dass der Termin am Montag ist');
    assert.equal(noteText('Merke dir Preisliste prüfen'), 'Preisliste prüfen');
    assert.equal(noteText('schreib auf: Milch'), 'Milch');
    assert.equal(noteText('Notiz: Budget klären'), 'Budget klären');
    assert.equal(noteText('halt fest: Raum buchen'), 'Raum buchen');
    assert.equal(noteText('Formatiere die Zielgruppe als Tabelle'), null);
    assert.equal(noteText('Was habe ich mir notiert?'), null, 'a question makes no card');
    assert.equal(noteText('Merke ich mir das richtig?'), null);
    assert.equal(noteText('Kannst du notiere sagen?'), null, 'only at the start of the sentence');
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

    store.pending('u-5', 'Doppelt');
    store.working('u-6', 'Tabelle');
    store.settle('u-5');
    store.settle('u-6');
    assert.deepEqual(store.list(), [], 'a report of the database ends both states');

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

test('each bubble has its own chat history', () => {
    const history = createHistory();

    history.add('b1', { text: 'Notiere: A', kind: 'user' });
    history.add('b2', { text: 'Notiere: B', kind: 'user' });
    history.add('b1', { text: 'festgehalten', kind: 'agent' });

    assert.deepEqual(history.get('b1').map((e) => e.text), ['Notiere: A', 'festgehalten']);
    assert.deepEqual(history.get('b2').map((e) => e.text), ['Notiere: B']);
    assert.deepEqual(history.get('gibt-es-nicht'), []);

    history.get('b1').push({ text: 'von aussen', kind: 'user' });
    assert.equal(history.get('b1').length, 2, 'the list handed out is a copy');

    for (let i = 0; i < HISTORY_MAX + 5; i++) history.add('b3', { text: String(i), kind: 'user' });
    assert.equal(history.get('b3').length, HISTORY_MAX);
    assert.equal(history.get('b3')[0].text, '5', 'the oldest lines go first');
});

test('the reasons of a bubble: newest first, cards by title, a deleted card is named as gone', () => {
    const nodes = [{ id: 'n1', content: { title: 'Zielgruppe' } }, { id: 'n2', title: 'Kanäle' }];
    const row = { id: 'b1', metadata: { bewertungen: [
        { id: 'r1', text: 'Zielgruppe ist klar', karten: ['n1'], wert: 80, erstellt_am: '2026-11-23T07:00:00Z' },
        { id: 'r2', text: ' Kanäle fehlen noch ', karten: ['n2', 'weg'], erstellt_am: '2026-11-23T08:00:00Z' },
        { id: 'r3', text: '   ' },
        null,
    ] } };

    assert.deepEqual(reasonsFor(row, nodes), [
        { id: 'r2', text: 'Kanäle fehlen noch', wert: null, erstellt_am: '2026-11-23T08:00:00Z',
            karten: [{ id: 'n2', title: 'Kanäle' }, { id: 'weg', gone: true }] },
        { id: 'r1', text: 'Zielgruppe ist klar', wert: 80, erstellt_am: '2026-11-23T07:00:00Z',
            karten: [{ id: 'n1', title: 'Zielgruppe' }] },
    ]);
    assert.deepEqual(reasonsFor(null, nodes), []);
    assert.deepEqual(reasonsFor({ id: 'b1', metadata: {} }, nodes), []);

    const many = { metadata: { bewertungen: Array.from({ length: MAX_REASONS + 10 }, (_, i) => ({ id: i, text: 't' + i })) } };
    assert.equal(reasonsFor(many, []).length, MAX_REASONS);
});

test('a changed bubble row reaches the chat with its metadata', () => {
    const { SUBSCRIPTIONS, buildRealtimeMessage } = require('./supabase-realtime');
    const sub = SUBSCRIPTIONS.find((s) => s.table === 'ideas' && s.event === 'UPDATE');
    const message = buildRealtimeMessage(sub, { id: 'b1', title: 'Marketing', metadata: { bewertungen: [{ id: 'r1', text: 'x' }] } });

    assert.equal(message.table, 'ideas');
    assert.equal(message.node.metadata.bewertungen[0].id, 'r1');
    const html = fs.readFileSync(path.join(__dirname, 'renderer', 'index.html'), 'utf8');
    assert.match(html, /message\.table === 'ideas'\) \{\s*if \(window\.VibeIdeasChat && window\.VibeIdeasChat\.bubbleRow\)/);
});

test('the Enter key opens a bubble the same way as the enter button', () => {
    const scene = fs.readFileSync(path.join(__dirname, 'renderer', 'multiverse.js'), 'utf8');
    const enter = scene.slice(scene.indexOf('    enterCurrentSelection() {'), scene.indexOf('    getProjectById(projectId) {'));

    // enterSpace sets the mark that the user wants in; the bare camera move does not open the canvas.
    assert.match(enter, /window\.vibemind\.enterBubble\(bubbleId\);\s*window\.bubbleNavigation\.enterSpace\(bubbleId\);\s*return;/);
});

test('entering and leaving a bubble do not wait for animation frames', () => {
    const scene = fs.readFileSync(path.join(__dirname, 'renderer', 'multiverse.js'), 'utf8');
    const moves = scene.slice(scene.indexOf('    enterBubbleWithAnimation(bubbleIndex, onComplete) {'), scene.indexOf('    addBubble(bubbleData) {'));

    assert.equal((moves.match(/this\._cameraStep\(updateCamera\)/g) || []).length, 2, 'entry and exit');
    assert.doesNotMatch(moves, /requestAnimationFrame\(updateCamera\)/, 'a covered window gets no frames: the view would never open');
});

test('a failed plan and a question back take the card noted in advance away', () => {
    const store = createCardStore();
    store.pending('u-1', 'API Design');
    store.working('u-2', 'Gliederung');

    assert.deepEqual(store.failAll().map((c) => c.id), ['u-2'], 'only what was noted in advance; work of a model ends separately');

    const chat = fs.readFileSync(path.join(__dirname, 'renderer', 'ideas-chat.js'), 'utf8');
    assert.match(chat, /if \(failed && newId\) store\.reject\(newId, message\);/, 'a refused tool: the card goes, the chat names the reason');
    assert.match(chat, /if \(response && response\.question && newId\) store\.settle\(newId\);/);
    assert.match(chat, /if \(status\.state === 'failed'\) store\.failAll\(\);/);
    assert.match(chat, /say\(message, failed \? 'error' : 'agent', asked\);/);
});

test('the id of the open bubble is its database id, never the local number of the Python part', () => {
    // The state measured in the running app on 2026-11-23, bubble "Sheerlay" open:
    // spaceCanvas.bubbleId null, __currentBubbleId 1, selectedBubbleId the UUID. The app sent "1".
    const scene = { userData: { id: B1, db_id: B1, title: 'Sheerlay', data: { id: B1 } } };
    const lookup = (value) => (value === 1 || value === B1 ? scene : null);

    assert.equal(bubbleDbId([undefined, B1, null, 1, undefined], lookup), B1, 'as measured');
    assert.equal(bubbleDbId([null, null, null, 1], lookup), B1, 'only the local number is known: looked up');
    assert.equal(bubbleDbId([null, 'Sheerlay', null, 7], () => null), null, 'a title or a number is no id');
    assert.equal(bubbleDbId([null, null, null, 1], () => ({ userData: { id: 1, title: 'ohne Kennung' } })), null);
    assert.equal(bubbleDbId([], lookup), null);

    assert.deepEqual(buildContext({ bubble: { id: B1, title: 'Sheerlay' }, nodes: [] }).bubble, { id: B1, title: 'Sheerlay' });
    for (const wrong of [null, 1, '1', 'Sheerlay']) {
        assert.deepEqual(buildContext({ bubble: { id: wrong, title: 'Sheerlay' }, nodes: [] }).bubble,
            { id: null, title: 'Sheerlay' }, 'rather no id than a wrong one: ' + String(wrong));
    }
});

test('the chat reads the open bubble through the database id only', () => {
    const chat = fs.readFileSync(path.join(__dirname, 'renderer', 'ideas-chat.js'), 'utf8');
    const open = chat.slice(chat.indexOf('        function openBubble() {'), chat.indexOf('        function overviewBubbles() {'));

    assert.match(open, /id: bubbleDbId\(candidates, lookup\),/);
    assert.doesNotMatch(open, /id: root\.__currentBubbleId|\|\| root\.__currentBubbleId \|\|/, 'the local number is only used to look the bubble up');
    assert.match(chat, /context\.bubble = \{ id: isUuid\(bubble\.id\) \? String\(bubble\.id\) : null, title:/);
});
