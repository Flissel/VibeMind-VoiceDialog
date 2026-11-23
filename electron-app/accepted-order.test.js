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
        Date: { now: () => now },                    // the clock of the stand-in timers
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
    w.advance(2 * 60 * 1000);                       // a model takes minutes; the line stays
    w.loaded(cards());                               // the 5-s reload: nothing new yet
    w.loaded(cards('kurz', 'Karte 2 von Hand geaendert'));   // another card changed: not the result
    assert.equal(w.line(), '● Ideas: arbeitet … (Auftrag angenommen)');
    const done = cards('Ergebnis der Recherche, lang und ausfuehrlich');
    done[0].updated_at = '2026-11-23T10:07:00Z';
    w.loaded(done);
    // the duration is the work on the order (2 min), not the 0,8 s the plan took to accept it
    assert.equal(w.line(), '✓ Ideas: fertig in 2 min — Ergebnis an der Karte „Karte 1“');
    assert.equal(w.statuses[w.statuses.length - 1], 'done');
    assert.match(w.chatLog().join('\n'), /✓ fertig in 2 min — Ergebnis an der Karte „Karte 1“/);
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
    assert.equal(w.line(), '✓ Ideas: fertig in 0,0 s — Ergebnis an der Karte „Karte 1“');
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

const ORDER = '0000abcd-0000-4000-8000-0000000000aa';

test('no end reported: after 3 minutes the line says "noch in Arbeit, Nr. …" plainly, the chat says it once', async () => {
    const w = world();
    w.answerWith({ success: true, ok: true, pending: true, status: 'angenommen', message: 'Auftrag angenommen, Nr. 0000abcd', orders: [ORDER] });
    await w.send('Was hältst du von Karte 1?');
    assert.equal(w.line(), '● Ideas: arbeitet … (Auftrag angenommen)');
    w.advance(3 * 60 * 1000 - 1);
    assert.equal(w.line(), '● Ideas: arbeitet … (Auftrag angenommen)');
    w.advance(1);
    assert.equal(w.line(), 'Ideas: noch in Arbeit, Nr. 0000abcd', 'no dot, no "arbeitet …"');
    w.advance(60 * 1000);
    const said = w.chatLog().filter((t) => /noch in Arbeit/.test(t));
    assert.deepEqual(said, ['● noch in Arbeit, Nr. 0000abcd — das Ergebnis erscheint, sobald es da ist.']);
    w.advance(20 * 60 * 1000);
    assert.equal(w.line(), '', 'after the upper limit the line goes');
});

test('an assessment ends when the bubble gets a new reason: no card changes for it', async () => {
    const w = world();
    const row = (n) => ({ id: BUBBLE, metadata: { bewertungen: Array.from({ length: n }, (_, i) => ({ text: 'Grund ' + i, karten: [CARD_1] })) } });
    const bubbleRow = (r) => w.window.dispatchEvent(new w.window.CustomEvent('vibemind:bubble-row', { detail: { row: r } }));
    bubbleRow(row(1));                                  // the bubble as it was opened
    w.answerWith({ success: true, ok: true, pending: true, status: 'angenommen', message: 'Auftrag angenommen', orders: [ORDER] });
    await w.send('Was hältst du von Karte 1?');
    bubbleRow(row(1));                                  // the 5-s reload: nothing new
    w.loaded(cards());
    assert.equal(w.line(), '● Ideas: arbeitet … (Auftrag angenommen)');
    bubbleRow({ id: '00000000-0000-4000-8000-00000000000c', metadata: { bewertungen: [{}, {}, {}] } });
    assert.equal(w.line(), '● Ideas: arbeitet … (Auftrag angenommen)', 'another bubble does not count');
    bubbleRow(row(2));
    assert.match(w.line(), /^✓ Ideas: fertig.*Einschätzung an der Bubble$/);
    // Lauf 7: the "angenommen" line itself changes, no second line under it
    assert.deepEqual(w.chatLog(), ['Was hältst du von Karte 1?', '✓ fertig in 0 s — Einschätzung an der Bubble']);
});

test('a hint or a question back is never "✕ fehlgeschlagen": calm, with ℹ or ?', async () => {
    // the plan reports the step with ok false, but the Brain marks it as a hint
    const w = world();
    plan(w, { ok: false, hinweis: true, final_text: 'Die Tabelle hat keine Spalten.' });
    assert.equal(w.line(), 'ℹ Ideas: Die Tabelle hat keine Spalten.');
    assert.ok(!w.statuses.includes('failed'));

    const q = world();
    plan(q, { ok: false, rueckfrage: true, final_text: 'Ja, zurück?' });
    assert.equal(q.line(), '? Ideas: Ja, zurück?');

    // the plan failed, the answer to the sentence is a question back: the line turns calm
    const a = world();
    a.answerWith({ success: true, question: true, message: 'Welche Karte meinst du?' });
    plan(a, { ok: false, error: 'mehrdeutig' });
    assert.match(a.line(), /^✕/);
    await a.send('Mach daraus eine Tabelle');
    assert.equal(a.line(), '? Ideas: Welche Karte meinst du?');
    assert.match(a.chatLog().join('\n'), /Welche Karte meinst du\?/);

    // and the chat: a hint stays a hint
    const h = world();
    h.answerWith({ success: true, hinweis: true, message: 'Die Tabelle hat keine Spalten.' });
    await h.send('Mach Karte 1 zur Tabelle');
    assert.doesNotMatch(h.chatLog().join('\n'), /fehlgeschlagen|Keine Antwort/);
    const chat = fs.readFileSync(path.join(__dirname, 'renderer', 'ideas-chat.js'), 'utf8');
    assert.match(chat, /say\(message, failed \? 'error' : asks \? 'rueckfrage' : hint \? 'hinweis' : 'agent', asked, null, ask\);/);
    const css = fs.readFileSync(path.join(__dirname, 'renderer', 'styles', 'titlebar.css'), 'utf8');
    assert.match(css, /\.task-status\[data-state="note"\] \{/);
});

test('the end of the plan that took the order is the acceptance: no "fertig", no duration, until the result', async () => {
    const w = world();
    // the answer to the sentence comes first, the end of its plan a moment later
    w.answerWith({ success: true, ok: true, pending: true, status: 'angenommen', message: 'Auftrag angenommen', orders: [ORDER] });
    const navigator = createTaskNavigator((message) => w.handle(message));
    navigator.handle('plan_started', { plan_id: 'p7', hops: [{}], space: 'ideas' });
    await w.send('Was hältst du von Karte 1?');
    navigator.handle('hop_completed', { space: 'ideas', ok: true, result_preview: "'eingereiht'" });   // no mark in the hop
    navigator.handle('plan_completed', { plan_id: 'p7', ok: true, elapsed_s: 2.0 });
    assert.equal(w.line(), '● Ideas: arbeitet … (Auftrag angenommen)');
    assert.doesNotMatch(w.line(), /fertig|2,0 s/);
    // the receipt only at the end of the plan: accepted, without duration
    const sent = [];
    const nav = createTaskNavigator((m) => sent.push(m));
    nav.handle('plan_started', { plan_id: 'p8', hops: [{}], space: 'ideas' });
    nav.handle('hop_completed', { space: 'ideas', ok: true });
    const end = nav.handle('plan_completed', { plan_id: 'p8', ok: true, pending: true, status: 'angenommen', elapsed_s: 2.0 });
    assert.equal(end.state, 'accepted');
    assert.equal(end.elapsed_s, null);
    w.advance(7 * 60 * 1000);
    w.loaded(cards('Ergebnis'));
    assert.equal(w.line(), '✓ Ideas: fertig in 7 min — Ergebnis an der Karte „Karte 1“');
});

test('two sentences at once: the answer that arrives last is the line, also for the earlier sentence', () => {
    const w = world();
    const send = () => w.window.dispatchEvent(new w.window.CustomEvent('vibemind:sentence-sent'));
    const answered = (detail) => w.window.dispatchEvent(new w.window.CustomEvent('vibemind:sentence-answered', { detail }));
    send();
    send();
    answered({ text: 'In diesem Bereich kann ich das noch nicht.', success: true, note: 'rueckfrage', space: 'ideas' });
    assert.match(w.line(), /^\?/, 'the question of the second sentence first');
    answered({ text: '15 Bubbles.', success: true, note: '', space: 'ideas' });
    assert.match(w.line(), /^✓ .*15 Bubbles\./, 'then the later answer of the first sentence');
});

test('the console keeps each sentence with its answers as a pair, and nothing fades', () => {
    const scene = fs.readFileSync(path.join(__dirname, 'renderer', 'multiverse.js'), 'utf8');
    assert.doesNotMatch(scene, /GC_FADE_DELAY|_gcFadeLater|gc-fading/, 'answers stay to be read');
    assert.match(scene, /pair\.className = 'gc-pair';/);
    assert.match(scene, /div\.classList\.add\('gc-answer'\);\s*ask\.__pair\.appendChild\(div\);/);
    assert.match(scene, /findIndex\(\(unit\) => !unit\.__waiting\)/, 'a pair still waiting is never cut');
    assert.match(scene, /space: context && context\.space \? context\.space : this\.currentSpace,/);
    assert.match(fs.readFileSync(path.join(__dirname, 'renderer', 'styles', 'game-console.css'), 'utf8'), /\.gc-msg\.gc-answer \{/);
});

// Danach 2: das Gehirn sagt an /stand, wie ein angenommener Auftrag steht. Das beendet die Zeile
// auch dann, wenn sich keine Karte aendert (Einschaetzung, Vorschlag, abgebrochenes White Paper).
const tick = () => new Promise((resolve) => setImmediate(resolve));

async function acceptedWithStand(stands) {
    const w = world();
    const asked = [];
    w.window.vibemind.orderStand = async (id) => { asked.push(id); return stands.shift() || { stand: 'laeuft' }; };
    w.answerWith({ success: true, ok: true, pending: true, status: 'angenommen', message: 'Auftrag angenommen', orders: [ORDER] });
    // as in the app: the plan of the sentence runs before its answer comes
    w.handle({ type: 'task_status', state: 'running', space: 'ideas', plan_id: 'p1', step: 'Einschätzen', done: 0, total: 1 });
    await w.send('Was hältst du von Karte 1?');
    return { w, asked };
}

test('/stand fertig ends the line with the sentence of the Brain and its duration, no card change needed', async () => {
    const { w, asked } = await acceptedWithStand([{ stand: 'laeuft' }, { stand: 'fertig', meldung: 'Einschätzung liegt an der Bubble.', dauer_s: 42, saetze: [] }]);
    w.advance(5000); await tick();
    assert.equal(w.line(), '● Ideas: arbeitet … (Auftrag angenommen)', 'laeuft keeps the line');
    w.advance(5000); await tick();
    assert.deepEqual(asked, [ORDER, ORDER], 'asked every 5 s with the number of the order');
    assert.equal(w.line(), '✓ Ideas: fertig in 42,0 s — Einschätzung liegt an der Bubble.');
    assert.deepEqual(w.chatLog(), ['Was hältst du von Karte 1?', '✓ fertig in 42 s — Einschätzung liegt an der Bubble.'],
        'the line "Auftrag angenommen" became the end, with the message and the duration of /stand');
    w.advance(60000); await tick();
    assert.equal(asked.length, 2, 'no more asking once it ended');
});

test('/stand vorschlag is calm and offers its sentences as buttons; abgebrochen calm; fehler is ✕ with the sentence', async () => {
    const proposal = await acceptedWithStand([{ stand: 'vorschlag', meldung: 'Ein Vorschlag für Karte 1 liegt vor.', hinweis: true,
        saetze: ['Vorschlag zeigen', 'Vorschlag übernehmen', 'Vorschlag verwerfen'] }]);
    proposal.w.advance(5000); await tick();
    assert.equal(proposal.w.line(), 'ℹ Ideas: Ein Vorschlag für Karte 1 liegt vor.');
    assert.ok(proposal.w.chatLog().some((t) => t.startsWith('ℹ Ein Vorschlag für Karte 1 liegt vor.')));
    assert.ok(!proposal.w.statuses.includes('failed'));

    const stopped = await acceptedWithStand([{ stand: 'abgebrochen', meldung: '' }]);
    stopped.w.advance(5000); await tick();
    assert.equal(stopped.w.line(), 'ℹ Ideas: Der Auftrag wurde abgebrochen.');

    // paket-563f4393: the check of the Brain threw the result away (Lauf 5: the summary in the wrong form)
    const thrown = await acceptedWithStand([{ stand: 'verworfen', meldung: 'Der Agent hat nicht in der vereinbarten Form geantwortet; es wurde nichts geändert.' }]);
    thrown.w.advance(5000); await tick();
    assert.equal(thrown.w.line(), 'ℹ Ideas: Der Agent hat nicht in der vereinbarten Form geantwortet; es wurde nichts geändert.');
    const bare = await acceptedWithStand([{ stand: 'verworfen' }]);
    bare.w.advance(5000); await tick();
    assert.equal(bare.w.line(), 'ℹ Ideas: Das Ergebnis wurde verworfen; an der Karte hat sich nichts geändert.');

    const failed = await acceptedWithStand([{ stand: 'fehler', meldung: 'Das White Paper ließ sich nicht schreiben.' }]);
    failed.w.advance(5000); await tick();
    assert.equal(failed.w.line(), '✕ Ideas: fehlgeschlagen — Das White Paper ließ sich nicht schreiben.');
});

test('/stand: the main process reads only, checks the id and lets only known fields through', () => {
    const { standOf, ORDER_STANDS } = require('./task-navigation');
    assert.deepEqual([...ORDER_STANDS], ['laeuft', 'fertig', 'vorschlag', 'abgebrochen', 'verworfen', 'uebernommen', 'ungeprueft', 'wartet', 'fehler', 'unbekannt']);
    assert.equal(standOf({ stand: 'irgendwas' }), null);
    assert.deepEqual(standOf({ stand: 'fehler', meldung: "ConnectionError: HTTPConnectionPool(host='dienst-a')", ok: false, geheim: 'x' }),
        { stand: 'fehler', meldung: 'Der Dienst ist gerade nicht erreichbar.', ok: false, dauer_s: null, hinweis: false, saetze: [] });
    const main = fs.readFileSync(path.join(__dirname, 'task-navigation.js'), 'utf8');
    assert.match(main, /const ORDER_ID = \/\^\[A-Za-z0-9-\]\{4,64\}\$\/;/);
    assert.match(main, /path: '\/api\/agent-auftraege\/' \+ encodeURIComponent\(id\) \+ '\/stand'/);
    assert.match(fs.readFileSync(path.join(__dirname, 'main.js'), 'utf8'), /initTaskNavigation\(mainWindow, \{ ipcMain \}\);/);
    assert.match(fs.readFileSync(path.join(__dirname, 'preload.js'), 'utf8'), /orderStand: \(id\) => ipcRenderer\.invoke\('task:order-stand', String\(id\)\)/);
});

// Lauf 5: ein abgelehnter Auftrag, den das Gehirn an /stand nicht kennt, haengt nicht auf "arbeitet …".
test('/stand unbekannt for 5 minutes: the line says plainly that no answer came', async () => {
    const { w } = await acceptedWithStand(Array.from({ length: 80 }, () => ({ stand: 'unbekannt' })));
    for (let i = 0; i < 59; i += 1) { w.advance(5000); await tick(); }
    assert.notEqual(w.line(), 'ℹ Ideas: Keine Rückmeldung zum Auftrag Nr. 0000abcd.', 'not before 5 minutes');
    w.advance(5000); await tick();
    assert.equal(w.line(), 'ℹ Ideas: Keine Rückmeldung zum Auftrag Nr. 0000abcd.');
    assert.ok(!w.statuses.includes('failed'));
    assert.ok(w.chatLog().includes('ℹ Keine Rückmeldung zum Auftrag Nr. 0000abcd.'));
});

// Lauf 5: "Formuliere … aus", 6 s spaeter von Hand "Ergaenze …". Der neue Satz nimmt die Zeile, nicht
// den Auftrag: dessen Vorschlag kommt trotzdem, im Chat bei seinem Satz.
test('a later sentence does not lose an open order: its proposal still comes, at its own sentence', async () => {
    const { w, asked } = await acceptedWithStand([{ stand: 'laeuft' }, { stand: 'vorschlag', meldung: 'Ein Vorschlag für Karte 1 liegt vor.',
        saetze: ['Vorschlag zeigen', 'Vorschlag übernehmen', 'Vorschlag verwerfen'] }]);
    w.advance(5000); await tick();
    w.answerWith({ success: true, ok: true, message: 'Ergänzt bei Karte 1.' });
    await w.send('Ergänze bei Karte 1: eine Zeile');
    w.handle({ type: 'task_status', state: 'running', space: 'ideas', plan_id: 'p2', step: 'Ergänzen', done: 0, total: 1 });
    assert.match(w.line(), /^● Ideas/);
    w.advance(5000); await tick();
    assert.deepEqual(asked, [ORDER, ORDER], 'still asked after the new sentence');
    const log = w.chatLog();
    const at = log.indexOf('ℹ Ein Vorschlag für Karte 1 liegt vor.');
    assert.ok(at > -1, 'the chat says the proposal');
    assert.ok(at < log.indexOf('Ergänze bei Karte 1: eine Zeile'), 'at the sentence that gave the order, not under the new one');
    assert.match(w.line(), /^● Ideas/, 'the running task keeps the line');
    w.handle({ type: 'task_status', state: 'done', space: 'ideas', plan_id: 'p2', result: 'Ergänzt bei Karte 1.' });
    assert.equal(log.filter((t) => t.startsWith('ℹ Ein Vorschlag')).length, 1, 'said once');
});

test('an open order ending while nothing else runs takes the line', async () => {
    const { w } = await acceptedWithStand([{ stand: 'laeuft' }, { stand: 'fertig', meldung: 'Fertig.', dauer_s: 9 }]);
    w.advance(5000); await tick();
    w.answerWith({ success: true, ok: true, message: 'Ergänzt.' });
    await w.send('Ergänze bei Karte 2: eine Zeile');
    w.handle({ type: 'task_status', state: 'done', space: 'ideas', plan_id: 'p3', result: 'Ergänzt.' });
    w.advance(5000); await tick();
    assert.equal(w.line(), '✓ Ideas: fertig in 9,0 s — Fertig.');
});

// Danach 4: ausserhalb der Ideen haengt die Standzeile nicht auf "arbeitet …".
const answered = (w, detail) => w.window.dispatchEvent(new w.window.CustomEvent('vibemind:sentence-answered', { detail }));

test('outside Ideas: answered, but the plan never reports its end: the answer ends the line after 15 s', () => {
    const w = world();
    w.window.multiverseApp.currentSpace = 'video';   // the person is in that space
    w.handle({ type: 'task_status', state: 'running', space: 'video', plan_id: 'p5', step: 'Video schneiden', done: 0, total: 1 });
    answered(w, { text: 'Das Video liegt bereit.', success: true, space: 'video' });
    w.advance(10000);
    // a further step of the same plan: it still works, the wait starts again
    w.handle({ type: 'task_status', state: 'running', space: 'video', plan_id: 'p5', step: 'Video exportieren', done: 1, total: 2 });
    w.advance(14999);
    assert.match(w.line(), /^● Video Studio/);
    w.advance(1);
    assert.match(w.line(), /^✓ Video Studio: fertig — Das Video liegt bereit\./);
});

test('outside Ideas: the plan reports its end in time: nothing extra happens later', () => {
    const w = world();
    w.handle({ type: 'task_status', state: 'running', space: 'video', plan_id: 'p6', step: 'Video schneiden', done: 0, total: 1 });
    answered(w, { text: 'Fertig geschnitten.', success: true, space: 'video' });
    w.handle({ type: 'task_status', state: 'failed', space: 'video', plan_id: 'p6', error: 'Der Dienst ist gerade nicht erreichbar.' });
    const before = w.statuses.length;
    w.advance(20000);
    assert.equal(w.statuses.length, before, 'the timer of the answer does not overwrite the reported end');
});

test('outside Ideas: an order accepted without a number ends calmly, not "arbeitet" for minutes', () => {
    const w = world();
    w.window.multiverseApp.currentSpace = 'roarboot';
    answered(w, { text: 'Auftrag angenommen', success: true, accepted: true, space: 'roarboot', targets: [], orders: [] });
    assert.equal(w.line(), '● Rowboat: arbeitet … (Auftrag angenommen)');
    w.advance(10000);
    assert.equal(w.line(), 'ℹ Rowboat: Auftrag angenommen. Das Ergebnis erscheint im Bereich, sobald es fertig ist.');
    assert.ok(!w.statuses.includes('failed'));
});

test('a sentence of the console that fails reports it: the line does not wait 60 s', () => {
    const scene = fs.readFileSync(path.join(__dirname, 'renderer', 'multiverse.js'), 'utf8');
    assert.match(scene, /catch \(err\) \{[\s\S]{0,400}vibemind:sentence-answered[\s\S]{0,200}success: false, space: this\.currentSpace/);
    const chat = fs.readFileSync(path.join(__dirname, 'renderer', 'ideas-chat.js'), 'utf8');
    assert.match(chat, /catch \(error\) \{[\s\S]{0,400}vibemind:sentence-answered[\s\S]{0,200}success: false, space: 'ideas'/);
});

test('the chat says a long order in minutes and seconds, in the same line', async () => {
    const { w } = await acceptedWithStand([{ stand: 'fertig', meldung: 'Die Einschätzung steht an der Bubble.', dauer_s: 105 }]);
    w.advance(5000); await tick();
    assert.deepEqual(w.chatLog(), ['Was hältst du von Karte 1?', '✓ fertig in 1 min 45 s — Die Einschätzung steht an der Bubble.']);
});

test('no end for 3 minutes: the same line says "noch in Arbeit", then its end replaces that', async () => {
    const stands = Array.from({ length: 36 }, () => ({ stand: 'laeuft' }));
    stands.push({ stand: 'fehler', meldung: 'Das Modell hat nicht geantwortet.' });
    const { w } = await acceptedWithStand(stands);
    for (let i = 0; i < 36; i += 1) { w.advance(5000); await tick(); }
    assert.deepEqual(w.chatLog(), ['Was hältst du von Karte 1?', '● noch in Arbeit, Nr. 0000abcd — das Ergebnis erscheint, sobald es da ist.']);
    w.advance(5000); await tick();
    assert.deepEqual(w.chatLog(), ['Was hältst du von Karte 1?', '✕ Das Modell hat nicht geantwortet.']);
});

// cc/ideen-paket-3: zwei neue Staende an /stand; ein unbekannter mit Satz endet ruhig.
test('/stand uebernommen ends with ✓ and the message, no buttons; ungeprueft calm with ℹ; unknown with a sentence ends calmly', async () => {
    const { standOf } = require('./task-navigation');
    // as the Brain answers (auftrag_id, stand, meldung, ok, hinweis), passed through the main process
    const brain = (body) => standOf({ auftrag_id: ORDER, ...body });

    const taken = await acceptedWithStand([brain({ stand: 'uebernommen', meldung: 'Der Vorschlag steht jetzt in Karte 1.', ok: true, dauer_s: 3 })]);
    taken.w.advance(5000); await tick();
    assert.equal(taken.w.line(), '✓ Ideas: fertig in 3,0 s — Der Vorschlag steht jetzt in Karte 1.');
    assert.deepEqual(taken.w.chatLog(), ['Was hältst du von Karte 1?', '✓ fertig in 3 s — Der Vorschlag steht jetzt in Karte 1.']);

    const unchecked = await acceptedWithStand([brain({ stand: 'ungeprueft', meldung: 'Der Auftrag kam zurück, das Ergebnis ließ sich nicht prüfen.', ok: false, hinweis: true })]);
    unchecked.w.advance(5000); await tick();
    assert.equal(unchecked.w.line(), 'ℹ Ideas: Der Auftrag kam zurück, das Ergebnis ließ sich nicht prüfen.');
    assert.ok(!unchecked.w.statuses.includes('failed') && !unchecked.w.statuses.includes('done'), 'neither ✕ nor ✓');

    const strange = await acceptedWithStand([brain({ stand: 'neu_im_gehirn', meldung: 'Das Gehirn sagt etwas Neues.', ok: true })]);
    strange.w.advance(5000); await tick();
    assert.equal(strange.w.line(), 'ℹ Ideas: Das Gehirn sagt etwas Neues.', 'not until "Keine Rückmeldung"');

    // unknown without a sentence: the main process passes nothing, the order stays open
    assert.equal(brain({ stand: 'neu_im_gehirn' }), null);
    const quiet = await acceptedWithStand([brain({ stand: 'neu_im_gehirn' })]);
    quiet.w.advance(5000); await tick();
    assert.equal(quiet.w.line(), '● Ideas: arbeitet … (Auftrag angenommen)');
    assert.equal(brain({ stand: 'Böse<script>', meldung: 'x' }), null, 'only plain state names pass');
});

// Lauf 8 (window log): "Formuliere … aus", 8 s later "Ergänze bei …". The Brain took the order only
// after 16 s and sent its acceptance under the plan of the change; the change ended 0.7 s later.
// The card it changed is no result of the order: only /stand ends a numbered order.
test('a change made before the order was taken does not end the order; its proposal still comes', async () => {
    const w = world();
    const asked = [];
    const stands = [{ stand: 'laeuft' }, { stand: 'vorschlag', meldung: 'Karte 1 wurde inzwischen geändert; ein Vorschlag liegt vor.', hinweis: true,
        saetze: ['Vorschlag zeigen', 'Vorschlag trotzdem übernehmen', 'Vorschlag verwerfen'] }];
    w.window.vibemind.orderStand = async (id) => { asked.push(id); return stands.shift() || { stand: 'laeuft' }; };
    const replies = [];
    w.window.vibemind.sendChatMessage = () => new Promise((resolve) => replies.push(resolve));
    const status = (fields) => w.handle({ type: 'task_status', space: 'ideas', registry_space: 'ideas', result: '…', error: '', ...fields });

    status({ state: 'reset', plan_id: 'ideen_A' });
    status({ state: 'running', plan_id: 'ideen_A', step: '', done: 0, total: 1 });
    const order = w.send('Formuliere die Notiz Karte 1 aus');
    w.advance(8000);
    status({ state: 'reset', plan_id: 'ideen_B' });
    status({ state: 'running', plan_id: 'ideen_B', step: '', done: 0, total: 1 });
    const change = w.send('Ergänze bei Karte 1: eine offene Frage');
    w.advance(8000);
    status({ state: 'running', plan_id: 'ideen_B', step: 'Ausformulieren', done: 0, total: 1 });
    status({ state: 'running', plan_id: 'ideen_B', step: 'Notiz ändern', done: 0, total: 1 });
    status({ state: 'running', plan_id: 'ideen_B', step: 'Ausformulieren', done: 1, total: 1, step_ok: true, accepted: true });
    status({ state: 'accepted', plan_id: 'ideen_B', step: 'Ausformulieren', done: 1, total: 1, elapsed_s: null, targets: [] });
    replies[0]({ type: 'chat_response', success: true, message: 'Auftrag angenommen, Nr. 0000abcd – zuständig: brain-ideas.',
        event_type: 'brain.multihop', plan_id: 'ideen_A', pending: true, status: 'angenommen', targets: [], orders: [ORDER] });
    await order;
    status({ state: 'running', plan_id: 'ideen_B', step: 'Notiz ändern', done: 2, total: 1, result: 'erledigt', step_ok: true });
    status({ state: 'accepted', plan_id: 'ideen_B', step: 'Ausformulieren', done: 2, total: 1, elapsed_s: null, targets: [] });
    replies[1]({ type: 'chat_response', success: true, message: '„Karte 1“ ergänzt.', event_type: 'brain.multihop', plan_id: 'ideen_B' });
    await change;
    w.advance(700);
    const changed = cards('kurz\n\nOffene Frage: eine offene Frage');
    changed[0].updated_at = '2026-11-23T10:00:16Z';
    w.loaded(changed);                               // the 5-s reload shows the change
    assert.equal(w.line(), '● Ideas: arbeitet … (Auftrag angenommen)', 'the change is no result of the order');
    assert.doesNotMatch(w.chatLog().join('\n'), /✓ fertig/);

    w.advance(5000); await tick();
    w.advance(5000); await tick();
    assert.deepEqual(asked, [ORDER, ORDER], '/stand is still asked');
    assert.equal(w.line(), 'ℹ Ideas: Karte 1 wurde inzwischen geändert; ein Vorschlag liegt vor.');
    const log = w.chatLog();
    assert.ok(log.includes('ℹ Karte 1 wurde inzwischen geändert; ein Vorschlag liegt vor.'), 'the proposal shows in the chat');
    assert.ok(log.indexOf('ℹ Karte 1 wurde inzwischen geändert; ein Vorschlag liegt vor.') < log.indexOf('Ergänze bei Karte 1: eine offene Frage'),
        'in place of the "angenommen" line of the order, under its sentence');
});

test('an order without a number still ends by the changed card', () => {
    const w = world();
    plan(w, { ok: true, pending: true, status: 'angenommen', targets: [CARD_1] });
    w.window.vibemind.orderStand = async () => ({ stand: 'laeuft' });
    w.loaded(cards());
    const done = cards('Ergebnis, lang');
    done[0].updated_at = '2026-11-23T10:07:00Z';
    w.loaded(done);
    assert.match(w.line(), /^✓ Ideas: fertig/);
});

// Lauf 8: order taken, then a change after the acceptance, /stand "vorschlag", then "Vorschlag verwerfen".
// The answer to "verwerfen" comes without any plan event (window log: chat_response without plan_id).
test('"Vorschlag verwerfen" answered without a plan: the line does not stay on "arbeitet"', async () => {
    const { w } = await acceptedWithStand([{ stand: 'laeuft' }, { stand: 'laeuft' }, { stand: 'vorschlag', meldung: 'Karte 1 wurde inzwischen geändert; ein Vorschlag liegt vor.',
        hinweis: true, saetze: ['Vorschlag zeigen', 'Vorschlag trotzdem übernehmen', 'Vorschlag verwerfen'] }]);
    w.advance(5000); await tick();
    const status = (fields) => w.handle({ type: 'task_status', space: 'ideas', registry_space: 'ideas', result: '…', error: '', ...fields });
    w.answerWith({ type: 'chat_response', success: true, message: '„Karte 1“ ergänzt.', event_type: 'brain.multihop', plan_id: 'ideen_B' });
    const change = w.send('Ergänze bei Karte 1: eine offene Frage');
    status({ state: 'reset', plan_id: 'ideen_B' });
    status({ state: 'running', plan_id: 'ideen_B', step: 'Notiz ändern', done: 0, total: 1 });
    status({ state: 'done', plan_id: 'ideen_B', step: 'Notiz ändern', done: 1, total: 1, result: 'erledigt', elapsed_s: 1.7 });
    await change;
    w.advance(5000); await tick();
    w.advance(5000); await tick();
    assert.equal(w.line(), 'ℹ Ideas: Karte 1 wurde inzwischen geändert; ein Vorschlag liegt vor.');
    w.answerWith({ type: 'chat_response', success: true, message: 'Der Vorschlag ist verworfen; an der Notiz ist nichts geändert.',
        event_type: 'brain.multihop', request_id: 'r-25' });
    await w.send('Vorschlag verwerfen');
    w.advance(3000); await tick();
    assert.doesNotMatch(w.line(), /arbeitet/);
    assert.doesNotMatch(w.chatState(), /arbeitet/);
    w.advance(60000); await tick();
    assert.doesNotMatch(w.line(), /arbeitet/);
});

// Restart of the Brain (2026-11-23): the bridge answers itself, as clawport_handlers passes a hint on.
test('Brain not reachable: a calm ℹ with the sentence, chat and line end, no "arbeitet"', async () => {
    const w = world();
    w.answerWith({ type: 'chat_response', success: true, event_type: 'brain.multihop.hint', hinweis: true,
        message: 'Das Gehirn ist gerade nicht erreichbar. Versuch es in ein, zwei Minuten noch einmal; geändert habe ich nichts.' });
    await w.send('Gruppiere die Karten');
    assert.equal(w.line(), 'ℹ Ideas: Das Gehirn ist gerade nicht erreichbar. Versuch es in ein, zwei Minuten noch einmal; geändert habe ich nichts.');
    assert.ok(w.chatLog().some((t) => t.includes('Das Gehirn ist gerade nicht erreichbar.')));
    assert.doesNotMatch(w.chatLog().join('\n'), /nicht ganz verstanden|fehlgeschlagen/);
    assert.equal(w.chatState(), '');
    assert.ok(!w.statuses.includes('failed'));
    w.advance(60000); await tick();
    assert.doesNotMatch(w.line(), /arbeitet/);
});

test('a judgement: its new card does not end the order; /stand brings the answer, short, the rest at the card', async () => {
    // Lauf 9: the order wrote a new card "Einschätzung: …" before /stand said fertig; the chat said
    // only "Ergebnis an der Karte". The answer of /stand is a long text: shown cut, with where the rest is.
    const answer = 'Es fehlen ein Zeitplan, die Verantwortlichen und die Kosten. Offen sind auch die Mengen und die Fragen zur Zahlung. '
        + 'Dazu kommt, dass noch kein Termin für den Versuch steht und niemand die Bestellung der Teile übernommen hat, '
        + 'was den Beginn verschiebt.';
    const { w } = await acceptedWithStand([{ stand: 'laeuft' }, { stand: 'laeuft' }, { stand: 'fertig', meldung: answer, dauer_s: 85 }]);
    w.advance(5000); await tick();
    w.loaded(cards().concat([{ id: '00000000-0000-4000-8000-000000000003', title: 'Einschätzung: Was fehlt noch?', content: 'lang' }]));
    assert.equal(w.line(), '● Ideas: arbeitet … (Auftrag angenommen)', 'the new card is no end: /stand says it');
    w.advance(5000); await tick();
    w.advance(5000); await tick();
    const end = '✓ fertig in 1 min 25 s — Es fehlen ein Zeitplan, die Verantwortlichen und die Kosten. '
        + 'Offen sind auch die Mengen und die Fragen zur Zahlung. … mehr an der Karte';
    assert.deepEqual(w.chatLog(), ['Was hältst du von Karte 1?', end]);
    assert.doesNotMatch(w.chatLog().join('\n'), /Ergebnis an der Karte/);
});

test('a short answer of /stand stands whole, without "mehr an der Karte"', async () => {
    const { w } = await acceptedWithStand([{ stand: 'fertig', meldung: 'Die Karten stehen jetzt in 2 Gruppen.', dauer_s: 9 }]);
    w.advance(5000); await tick();
    assert.equal(w.chatLog()[1], '✓ fertig in 9 s — Die Karten stehen jetzt in 2 Gruppen.');
});

test('the jump is the same from every place to type: a sentence in an open bubble goes to the space of its result', () => {
    // Abnahme point 4: the result lies in another space, the app goes there. From the console it
    // did; from the chat of an open bubble (the one place to type there) the plan stayed a note.
    const w = world();
    const app = w.window.multiverseApp;
    app.spaces.orders = {};
    const went = [];
    app.navigateToSpace = (space) => { went.push(space); };
    w.window.vibemind.sendChatMessage = () => new Promise(() => {});   // the answer is still to come
    w.send('Welche geplanten Aufgaben gibt es?');
    assert.equal(w.handle({ type: 'task_navigate', space: 'orders', registry_space: 'schedule', description: '' }), 'navigate');
    assert.deepEqual(went, ['orders']);

    const quiet = world();                             // a plan nobody asked for in this bubble
    quiet.window.multiverseApp.spaces.orders = {};
    quiet.window.multiverseApp.navigateToSpace = () => { throw new Error('no jump'); };
    assert.equal(quiet.handle({ type: 'task_navigate', space: 'orders', registry_space: 'schedule', description: '' }), 'note');
});

test('an event is told to its sentence by the trace, not by its plan: overlapping sentences without counting on order', async () => {
    const w = world();
    let n = 0;
    w.window.crypto.randomUUID = () => '00000000-0000-4000-8000-0000000000' + String(++n).padStart(2, '0');
    const contexts = [];
    w.window.vibemind.orderStand = async () => ({ stand: 'laeuft' });
    w.window.vibemind.sendChatMessage = async (text, context) => {
        contexts.push(context);
        return { success: true, ok: true, pending: true, status: 'angenommen', message: 'Auftrag angenommen', orders: [ORDER] };
    };
    const TRACE_1 = '00000000-0000-4000-8000-000000000001';
    w.handle({ type: 'task_status', state: 'running', space: 'ideas', plan_id: 'p1', trace_id: TRACE_1, step: 'Einschätzen', done: 0, total: 1 });
    await w.send('Was hältst du von Karte 1?');
    assert.equal(contexts[0].trace_id, TRACE_1, 'the sentence carries its trace to the Brain');
    assert.equal(w.line(), '● Ideas: arbeitet … (Auftrag angenommen)');

    // measured 2026-11-23: the end of the order's run came under the plan_id of a later sentence
    w.handle({ type: 'task_status', state: 'done', space: 'ideas', plan_id: 'p2', trace_id: TRACE_1, step: 'Einschätzen', done: 1, total: 1, result: 'erledigt' });
    assert.equal(w.line(), '● Ideas: arbeitet … (Auftrag angenommen)', 'its own trace: still the acceptance, no "fertig"');

    // a run of another sentence ends: its own news, not folded into the acceptance
    w.handle({ type: 'task_status', state: 'done', space: 'ideas', plan_id: 'p1', trace_id: '00000000-0000-4000-8000-000000000099', step: 'Notiz ändern', done: 1, total: 1, result: 'erledigt' });
    assert.match(w.line(), /^✓ Ideas: fertig/);
});

test('ziel: the answer and the end of the plan lead there at once; /stand only when the person is not busy elsewhere', async () => {
    const ZIEL = { space: 'ideas', bubble_id: BUBBLE, node_id: CARD_1 };
    const followed = [];
    let open = false;
    const stub = { create: () => ({ follow: (z) => { followed.push(z); return true; }, opens: () => open }) };

    // a sentence that wrote: its answer names the place
    const w = world();
    w.window.VibeResultTarget = stub;
    w.answerWith({ success: true, message: 'Notiz „Karte 1“ festgehalten.', ziel: ZIEL });
    await w.send('Halt fest: Karte 1');
    assert.deepEqual(followed, [ZIEL]);
    // the end of its plan names it as well (the follower does not start anew for the same place)
    w.handle({ type: 'task_status', state: 'done', space: 'ideas', plan_id: 'p1', step: 'Notiz anlegen', done: 1, total: 1, result: 'erledigt', ziel: ZIEL });
    assert.deepEqual(followed, [ZIEL, ZIEL]);

    // an order that ends at /stand while the person sits in another open bubble: no pulling out
    const inside = await acceptedWithStand([{ stand: 'fertig', meldung: 'Fertig.', dauer_s: 9, ziel: ZIEL }]);
    inside.w.window.VibeResultTarget = stub;
    followed.length = 0;
    inside.w.advance(5000); await tick();
    assert.deepEqual(followed, [], 'world: an open bubble that is not the one of the result');

    // the same, with the bubble of the result open: the card is marked
    open = true;
    const there = await acceptedWithStand([{ stand: 'fertig', meldung: 'Fertig.', dauer_s: 9, ziel: ZIEL }]);
    there.w.window.VibeResultTarget = stub;
    there.w.advance(5000); await tick();
    assert.deepEqual(followed, [ZIEL]);

    // without ziel nothing is followed
    open = false;
    followed.length = 0;
    const plain = await acceptedWithStand([{ stand: 'fertig', meldung: 'Fertig.', dauer_s: 9 }]);
    plain.w.window.VibeResultTarget = stub;
    plain.w.advance(5000); await tick();
    assert.deepEqual(followed, []);
});

// Lauf 10, "Gruppiere die Karten": the plan reports "accepted" 5 ms before the answer that names the order;
// a reload of the cards in between ended it at once ("✓ fertig in 0 s — Ergebnis an der Karte", and it stayed).
test('grouping: a card reload before the answer does not end the order; /stand ends it later', async () => {
    const w = world();
    const replies = [];
    const stands = [{ stand: 'laeuft' }, { stand: 'fertig', meldung: '2 Gruppen angelegt.' }];
    w.window.vibemind.orderStand = async () => stands.shift() || { stand: 'fertig', meldung: '2 Gruppen angelegt.' };
    w.window.vibemind.sendChatMessage = () => new Promise((resolve) => replies.push(resolve));
    const status = (fields) => w.handle({ type: 'task_status', space: 'ideas', registry_space: 'ideas', result: '', error: '', ...fields });
    w.loaded(cards());
    status({ state: 'reset', plan_id: 'ideen_G' });
    const sent = w.send('Gruppiere die Karten');
    status({ state: 'running', plan_id: 'ideen_G', step: 'Nach Thema gruppieren', done: 0, total: 1 });
    w.advance(1900);
    status({ state: 'running', plan_id: 'ideen_G', step: 'Nach Thema gruppieren', done: 1, total: 1, step_ok: true, accepted: true });
    status({ state: 'accepted', plan_id: 'ideen_G', step: 'Nach Thema gruppieren', done: 1, total: 1, elapsed_s: null, targets: [] });
    w.loaded(cards().concat([{ id: '00000000-0000-4000-8000-000000000009', title: 'Gruppe A', content: '' }]));
    replies[0]({ type: 'chat_response', success: true, message: 'Auftrag angenommen, Nr. 0000abcd – zuständig: brain-ideas.',
        event_type: 'brain.multihop', plan_id: 'ideen_G', pending: true, status: 'angenommen', targets: [], orders: [ORDER] });
    await sent;
    assert.ok(!w.chatLog().some((l) => /fertig in 0 s/.test(l)), 'no second end line');
    assert.match(w.line(), /^● Ideas: arbeitet/);
    for (let i = 0; i < 12 && !/^✓/.test(w.line()); i++) { w.advance(5000); await tick(); }
    assert.match(w.line(), /^✓ Ideas: fertig/);
    assert.equal(w.chatLog().filter((l) => /fertig/.test(l)).length, 1, 'one end line, from /stand');
});
