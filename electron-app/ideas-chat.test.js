const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const { buildContext, reloadsCards, noteText, cardTitle, fullTitle, isAccepted, ACCEPTED_LINE, createCardStore, createHistory, reasonsFor, bubbleDbId, MAX_CARDS, FULL_CARDS, HISTORY_MAX, MAX_REASONS } = require('./renderer/ideas-chat');

const B1 = '00000000-0000-4000-8000-00000000000d';
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
        bubbles: [{ id: B1, title: 'Marketing' }, { id: B2, title: 'Vertrieb' }],
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
        cards_total: 3,
        selection: ['n2'],
        last_id: 'n3',
        bubbles: [{ id: B1, title: 'Marketing' }, { id: B2, title: 'Vertrieb' }],
        new_id: 'u-1',
    });
});

test('with a bubble open whose id is not known, the list of bubbles lets the Brain find it by title', () => {
    const context = buildContext({ bubble: { id: '1', title: 'Marketing' }, nodes: [], bubbles: [{ id: B1, title: 'Marketing' }, { id: 1, title: 'Ordnungszahl' }] });

    assert.deepEqual(context.bubble, { id: null, title: 'Marketing' });
    assert.deepEqual(context.bubbles, [{ id: B1, title: 'Marketing' }]);
});

test('cards go to the Brain only with the bubble they were loaded for', () => {
    const BUBBLE_A = '00000000-0000-4000-8000-00000000000a';
    const BUBBLE_B = '0000000b';
    const open = { id: BUBBLE_B, title: 'Bubble B' };
    const cardOfA = [{ id: 'k1', title: 'Research' }];

    // measured 2026-11-23: Bubble B open, the canvas held the one card of Bubble A
    const wrong = buildContext({ bubble: open, nodes: cardOfA, nodesBubbleId: BUBBLE_A, selection: ['k1'], lastId: 'k1' });
    assert.deepEqual(wrong.bubble, open);
    assert.deepEqual(wrong.cards, []);
    assert.equal(wrong.cards_withheld, true);
    assert.deepEqual(wrong.selection, []);
    assert.equal(wrong.last_id, undefined);

    // the cards of the open bubble go as before
    const right = buildContext({ bubble: open, nodes: [{ id: 'k9', title: 'Preise' }], nodesBubbleId: BUBBLE_B });
    assert.deepEqual(right.cards.map((c) => c.id), ['k9']);
    assert.equal(right.cards_withheld, undefined);

    // a bubble or cards of unknown origin cannot be checked: no cards
    assert.deepEqual(buildContext({ bubble: { id: '1', title: 'X' }, nodes: cardOfA, nodesBubbleId: BUBBLE_A }).cards, []);
    assert.deepEqual(buildContext({ bubble: open, nodes: cardOfA, nodesBubbleId: null }).cards, []);
});

test('the chat checks the cards against a bubble it did not take from the canvas', () => {
    const chat = fs.readFileSync(path.join(__dirname, 'renderer', 'ideas-chat.js'), 'utf8');
    const canvas = fs.readFileSync(path.join(__dirname, 'renderer', 'universe_canvas.js'), 'utf8');
    assert.match(canvas, /'vibemind:canvas-loaded', \{ detail: \{ nodes: this\.lastNodes, bubbleId: this\.bubbleId \|\| null \} \}/);
    assert.match(chat, /nodesBubbleId = event\.detail && event\.detail\.bubbleId \? String\(event\.detail\.bubbleId\) : null;/);
    assert.match(chat, /buildContext\(\{ bubble: inside \? openBubble\(\) : null, nodes, nodesBubbleId,/);
    const open = chat.slice(chat.indexOf('function openBubble()'), chat.indexOf('function overviewBubbles()'));
    assert.doesNotMatch(open, /canvas\s*&&\s*canvas\.bubbleId/, 'the bubble on screen is not read from the canvas');
});

test('a sentence that takes something back or removes it loads the cards again', () => {
    for (const sentence of ['Nimm das zurück', 'zurueck', 'Mach das rückgängig', 'rueckgaengig bitte', 'undo', 'Lösche die Karte Preise', 'loesch das', 'Entferne Druckerei']) {
        assert.equal(reloadsCards(sentence), true, sentence);
    }
    for (const sentence of ['Notiere: API Design', 'Zeig die Notizen dieser Bubble', 'Verbinde die beiden', '', null]) {
        assert.equal(reloadsCards(sentence), false, String(sentence));
    }
});

test('after the answer to such a sentence the chat reloads the canvas in place, and a deleted card leaves the context', () => {
    const source = fs.readFileSync(path.join(__dirname, 'renderer', 'ideas-chat.js'), 'utf8');
    assert.match(source, /if \(!failed && reloadsCards\(text\)\) reloadCards\(\);/);
    assert.match(source, /canvas\.refresh\(\)/, 'refresh() loads in place, without entering the bubble again');
    assert.match(source, /addEventListener\('vibemind:canvas-node-removed'/);
    const canvas = fs.readFileSync(path.join(__dirname, 'renderer', 'universe_canvas.js'), 'utf8');
    const deleted = canvas.slice(canvas.indexOf('onNodeDeleted(nodeId) {'), canvas.indexOf('onNodeDeleted(nodeId) {') + 200);
    assert.match(deleted, /vibemind:canvas-node-removed/);
});

test('in the overview the context names the bubbles instead', () => {
    const context = buildContext({ bubble: null, nodes: [{ id: 'n1' }], bubbles: [{ id: B1, title: 'Marketing' }, { title: 'ohne' }, { id: 3, title: 'nur eine Ordnungszahl' }] });

    assert.deepEqual(context, { space: 'ideas', bubble: null, bubbles: [{ id: B1, title: 'Marketing' }] });
});

test('the context is capped at 500 cards; beyond the first 100 only id and title', () => {
    const nodes = Array.from({ length: MAX_CARDS + 20 }, (_, i) => ({ id: i, title: 'Karte ' + (i + 1), content_json: { type: 'swot' } }));

    const context = buildContext({ bubble: { id: 1, title: 'B' }, nodes });
    assert.equal(MAX_CARDS, 500);
    assert.equal(FULL_CARDS, 100);
    assert.equal(context.cards.length, MAX_CARDS);
    assert.equal(context.cards_total, MAX_CARDS + 20, 'a cut list says how many cards there are');
    assert.deepEqual(Object.keys(context.cards[99]).sort(), ['format', 'id', 'score', 'title']);
    assert.deepEqual(context.cards[100], { id: '100', title: 'Karte 101' }, 'the 101st card can be named');
    assert.deepEqual(context.cards[499], { id: '499', title: 'Karte 500' });
});

test('a bubble with 101 cards: every card is in the context, the total is there', () => {
    const nodes = Array.from({ length: 101 }, (_, i) => ({ id: 'c' + i, title: 'Karte ' + (i + 1) }));
    const context = buildContext({ bubble: { id: 1, title: 'B' }, nodes });
    assert.equal(context.cards.length, 101);
    assert.equal(context.cards[100].title, 'Karte 101');
    assert.equal(context.cards_total, 101);
});

test('cards_total is always set, also for a short list and an empty bubble', () => {
    const nodes = [{ id: 'a', title: 'Karte 1' }, { id: 'b', title: 'Karte 2' }, { id: 'c', title: 'Karte 3' }];
    assert.equal(buildContext({ bubble: { id: 1, title: 'B' }, nodes }).cards_total, 3);
    assert.equal(buildContext({ bubble: { id: 1, title: 'B' }, nodes: [] }).cards_total, 0);
});

test('titles in the context are whole, not cut', () => {
    const long = 'Karte 1 ' + 'mit einem sehr langen Titel, '.repeat(8) + 'Ende';
    assert.ok(long.length > 200);
    const context = buildContext({ bubble: { id: 1, title: 'B' }, nodes: [{ id: 'a', title: long }, { id: 'b', content: { title: long } }] });
    assert.equal(context.cards[0].title, long);
    assert.equal(context.cards[1].title, long);
    assert.equal(fullTitle({ id: 'c', content: { text: 'x'.repeat(300) } }).length, 120, 'a card without title: the start of its text');
});

test('a title stored cut ("…", the start of a long noted sentence) is named by the whole sentence', () => {
    const sentence = 'Karte 1 – der Code muss bei fehlendem Netz drei Tage lokal gespeichert und danach ohne Anmeldung pruefbar sein';
    const cut = sentence.slice(0, 80).trimEnd() + '…';
    // as the canvas loads it (content: { title, text }) and as the row comes (title, content text)
    assert.equal(fullTitle({ id: 'a', content: { title: cut, text: sentence } }), sentence);
    assert.equal(fullTitle({ id: 'a', title: cut, content: sentence + '\nmehr Text' }), sentence);
    const context = buildContext({ bubble: { id: 1, title: 'B' }, nodes: [{ id: 'a', content: { title: cut, text: sentence } }] });
    assert.equal(context.cards[0].title, sentence);
    // a title that only happens to end with "…", or whose text says something else, stays as it is
    assert.equal(fullTitle({ id: 'b', content: { title: 'Karte 2 …', text: 'ganz anderer Text' } }), 'Karte 2 …');
    assert.equal(fullTitle({ id: 'c', content: { title: cut, text: 'x'.repeat(20) } }), cut);
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
    assert.match(preload, /sendChatMessage: \(text, context, typed\) =>\s*ipcRenderer\.invoke\('renderer:chat-text-input', \{ text, context, typed: typed === true && sentByPerson\(text\) \}\)/);
    assert.match(main, /const message = chatMessage\(text, context, typed\);/);
    assert.match(chat, /vibemind\.sendChatMessage\(text, contextNow\(newId\), typed === true\)/);
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
    assert.match(chat, /if \(asks && newId\) store\.settle\(newId\);/);
    // a question back (question, rueckfrage or verstanden: false) is calm, never a failure
    assert.match(chat, /const asks = !accepted && !!response && \(response\.question === true \|\| response\.rueckfrage === true \|\| response\.verstanden === false\);/);
    assert.match(chat, /const failed = !accepted && !asks &&/);
    assert.match(chat, /if \(status\.state === 'failed'\) store\.failAll\(\);/);
    assert.match(chat, /say\(message, failed \? 'error' : asks \? 'rueckfrage' : 'agent', asked\);/);
    assert.doesNotMatch(chat, /response\.fehler/, 'the raw original of an error is never shown');
});

test('the id of the open bubble is its database id, never the local number of the Python part', () => {
    // The state measured in the running app on 2026-11-23, bubble "Bubble A" open:
    // spaceCanvas.bubbleId null, __currentBubbleId 1, selectedBubbleId the UUID. The app sent "1".
    const scene = { userData: { id: B1, db_id: B1, title: 'Bubble A', data: { id: B1 } } };
    const lookup = (value) => (value === 1 || value === B1 ? scene : null);

    assert.equal(bubbleDbId([undefined, B1, null, 1, undefined], lookup), B1, 'as measured');
    assert.equal(bubbleDbId([null, null, null, 1], lookup), B1, 'only the local number is known: looked up');
    assert.equal(bubbleDbId([null, 'Bubble A', null, 7], () => null), null, 'a title or a number is no id');
    assert.equal(bubbleDbId([null, null, null, 1], () => ({ userData: { id: 1, title: 'ohne Kennung' } })), null);
    assert.equal(bubbleDbId([], lookup), null);

    assert.deepEqual(buildContext({ bubble: { id: B1, title: 'Bubble A' }, nodes: [] }).bubble, { id: B1, title: 'Bubble A' });
    for (const wrong of [null, 1, '1', 'Bubble A']) {
        assert.deepEqual(buildContext({ bubble: { id: wrong, title: 'Bubble A' }, nodes: [] }).bubble,
            { id: null, title: 'Bubble A' }, 'rather no id than a wrong one: ' + String(wrong));
    }
});

test('the chat reads the open bubble through the database id only', () => {
    const chat = fs.readFileSync(path.join(__dirname, 'renderer', 'ideas-chat.js'), 'utf8');
    const open = chat.slice(chat.indexOf('        function openBubble() {'), chat.indexOf('        function overviewBubbles() {'));

    assert.match(open, /id: bubbleDbId\(candidates, lookup\),/);
    assert.doesNotMatch(open, /id: root\.__currentBubbleId|\|\| root\.__currentBubbleId \|\|/, 'the local number is only used to look the bubble up');
    assert.match(chat, /context\.bubble = \{ id: isDbId\(bubble\.id\) \? String\(bubble\.id\) : null, title:/);
});

test('database ids come in three forms and are passed on unchanged', () => {
    // Counted in the stock on 2026-11-23: 9 of 15 bubbles carry 8 hex characters, 6 a UUID;
    // connections carry 32 hex characters.
    const short = '0000000b';
    const long = '0123456789abcdef0123456789abcdef';

    for (const id of [short, long, B1]) {
        assert.deepEqual(buildContext({ bubble: { id, title: 'X' }, nodes: [] }).bubble, { id, title: 'X' }, id);
    }
    const scene = { userData: { id: 3, db_id: short, title: 'Bubble A' } };
    assert.equal(bubbleDbId([null, null, null, 1], (value) => (value === 1 ? scene : null)), short, 'looked up through the local number');
    assert.equal(bubbleDbId([short, B1], () => null), short, 'the first database id wins, whatever its form');

    for (const wrong of ['1', 'Bubble A', '0000000', '0000000bx', 'zz00000b', '']) {
        assert.equal(buildContext({ bubble: { id: wrong, title: 'X' }, nodes: [] }).bubble.id, null, wrong);
    }

    const context = buildContext({ bubble: null, bubbles: [{ id: short, title: 'A' }, { id: B1, title: 'B' }, { id: 2, title: 'nur Ordnungszahl' }] });
    assert.deepEqual(context.bubbles.map((b) => b.id), [short, B1]);

    // cards and the marked card are not judged by form at all: whatever id the canvas row has goes through
    const cards = buildContext({ bubble: { id: short, title: 'X' }, nodes: [{ id: short, title: 'K1' }, { id: long, title: 'K2' }, { id: B2, title: 'K3' }], selection: [long], lastId: short });
    assert.deepEqual(cards.cards.map((c) => c.id), [short, long, B2]);
    assert.deepEqual(cards.selection, [long]);
    assert.equal(cards.last_id, short);
});
