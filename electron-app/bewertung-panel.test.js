// The evaluation panel of a bubble: one source (metadata.bewertung_lauf), the total is the sum of
// the five bars, the threshold comes from the backend, "veraltet" once a card changed after the run.
// Invented bubble and cards; the run has the form the fixed tool bubble_bewertung writes.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('fs');
const path = require('path');

const panel = require('./renderer/bewertung-panel.js');

const ZEIT = '2026-03-02T10:00:00+00:00';

function lauf(overrides = {}) {
    return {
        version: 1,
        zeit: ZEIT,
        score: 61,
        sichten: {
            coding: { punkte: 14, urteil: 'Schnittstellen fehlen.' },
            swe_design: { punkte: 12, urteil: 'Abnahmekriterien fehlen.' },
            research: { punkte: 10, urteil: '' },
            rowboat: { punkte: 9, urteil: 'Vorwissen kaum festgehalten.' },
            ideas: { punkte: 16, urteil: '' },
        },
        todos: [
            { nr: 1, sicht: 'coding', titel: 'Datenmodell beschreiben', fehlt: 'Es fehlt ein Datenmodell.', karten: ['k-1'],
              punkte: 4, art: 'karte_fuellen', erledigt: false, erledigt_zeit: null, erledigt_durch: null },
            { nr: 2, sicht: 'swe_design', titel: 'Abnahme festlegen', fehlt: 'Keine Abnahmekriterien.', karten: ['k-2', 'k-weg'],
              punkte: 6, art: 'karte_ergaenzen', erledigt: false, erledigt_zeit: null, erledigt_durch: null },
            { nr: 3, sicht: 'rowboat', titel: 'Begriffe sammeln', fehlt: 'Begriffe sind nicht erklärt.', karten: [],
              punkte: 3, art: 'entscheidung', erledigt: true, erledigt_zeit: ZEIT, erledigt_durch: 'agent' },
        ],
        kartenstand: 'abc',
        gekuerzt: false,
        ...overrides,
    };
}

const cards = [
    { id: 'k-1', title: 'Grundidee', updated_at: '2026-03-01T09:00:00+00:00' },
    { id: 'k-2', title: 'Ablauf', updated_at: '2026-03-02T09:59:59+00:00' },
];

function row(meta) {
    return { id: 'idee-1', title: 'Beispielbubble', metadata: meta };
}

test('the total is the sum of the five bars; rowboat shows as Wissenslage', () => {
    const s = panel.standOf({ row: row({ bewertung_lauf: lauf({ score: 99 }) }), cards });
    assert.equal(s.leer, false);
    assert.deepEqual(s.sichten.map((b) => [b.label, b.punkte]),
        [['Coding', 14], ['SWE Design', 12], ['Research', 10], ['Wissenslage', 9], ['Ideen', 16]]);
    assert.equal(s.score, 61, 'the bars, not a number beside them');
    const odd = panel.standOf({ row: row({ bewertung_lauf: lauf({ sichten: { coding: { punkte: 40 }, ideas: { punkte: -3 } } }) }) });
    assert.equal(odd.score, 25, 'each bar 0 to 25');
});

test('the threshold comes from the backend; without it the default 95, and it decides the state', () => {
    const s = panel.standOf({ row: row({ bewertung_lauf: lauf() }), cards });
    assert.equal(s.schwelle, 95);
    assert.equal(s.schwelleVorgabe, true);
    assert.equal(s.zustand, 'unter_schwelle');
    const low = panel.standOf({ row: row({ bewertung_lauf: lauf() }), cards, schwelle: 60 });
    assert.equal(low.schwelle, 60);
    assert.equal(low.schwelleVorgabe, false);
    assert.equal(low.zustand, 'befoerderbar');
    assert.equal(panel.farbe(low), 'green');
    assert.equal(panel.standOf({ row: row({ bewertung_lauf: lauf() }), schwelle: 'x' }).schwelle, 95);
});

test('out of date once a card was changed after the run, whatever the score', () => {
    const later = [...cards, { id: 'k-3', title: 'Neu', updated_at: '2026-03-02T10:00:01+00:00' }];
    const s = panel.standOf({ row: row({ bewertung_lauf: lauf() }), cards: later, schwelle: 60 });
    assert.equal(s.veraltet, true);
    assert.equal(s.geaendert, 1);
    assert.equal(s.zustand, 'veraltet', 'not promotable while out of date');
    assert.equal(s.zustandLabel, 'Karten geändert – neu bewerten');
    assert.equal(panel.farbe(s), 'yellow');
});

test('to-dos: open first by points, cards resolved, a gone card named, done ones last', () => {
    const s = panel.standOf({ row: row({ bewertung_lauf: lauf() }), cards });
    assert.deepEqual(s.todos.map((t) => t.nr), [2, 1, 3]);
    assert.equal(s.offen, 2);
    assert.deepEqual(s.todos[0].karten, [{ id: 'k-2', title: 'Ablauf', gone: false }, { id: 'k-weg', title: '', gone: true }]);
    assert.equal(s.todos[0].artLabel, 'Karte ergänzen');
    assert.equal(s.todos[2].durch, 'agent');
});

test('metadata as text, a hand value apart, the course; no run at all is an empty panel', () => {
    const meta = JSON.stringify({
        handwert: { score: 80, zeit: ZEIT },
        eval_history: [{ zeit: ZEIT, score: 80, art: 'hand' }, { zeit: ZEIT, score: 61, sichten: {}, art: 'lauf' }, { score: 'x' }],
    });
    const s = panel.standOf({ row: row(meta) });
    assert.equal(s.leer, true);
    assert.deepEqual(s.handwert, { score: 80, zeit: ZEIT });
    assert.deepEqual(s.verlauf.map((h) => [h.score, h.art]), [[80, 'hand'], [61, 'lauf']]);
    assert.equal(panel.farbe(s), '');
    // the old evaluations are no source any more
    const old = panel.standOf({ row: row({ ai_eval: { completeness: 8 }, last_eval: { total_score: 47 } }) });
    assert.equal(old.leer, true);
});

test('the sentences of the buttons; a bad number gives none', () => {
    assert.equal(panel.LAUF_SATZ, 'Bewerte diese Bubble');
    assert.equal(panel.todoSatz(2, 'agent'), 'Erledige To-do 2');
    assert.equal(panel.todoSatz('2', 'hand'), 'To-do 2 erledigt');
    assert.equal(panel.todoSatz(0, 'agent'), '');
    assert.equal(panel.todoSatz(2.5, 'agent'), '');
    assert.equal(panel.todoSatz(25, 'hand'), 'To-do 25 erledigt');
    assert.equal(panel.todoSatz(26, 'hand'), '', 'the Brain numbers 1 to 25');
    assert.equal(panel.todoSatz(2, 'x'), '');
});

// ---- the drawn panel, with a small stand-in for the document ----

// A click with the mouse says how often it was clicked (detail 1); a click from Enter/Space says 0.
const MOUSE = { detail: 1, isTrusted: true };
const KEYBOARD_CLICK = { detail: 0, isTrusted: true };

function fakeDoc() {
    const doc = { activeElement: null };
    const make = (tag) => {
        const node = {
            tagName: tag.toUpperCase(), className: '', textContent: '', title: '', id: '', type: '', disabled: false,
            dataset: {}, style: {}, children: [], listeners: {},
            append(...kids) { for (const k of kids) { this.children.push(k); } },
            replaceChildren(...kids) { this.children = kids; },
            contains(other) { return all(this).includes(other); },
            addEventListener(type, fn) { (this.listeners[type] = this.listeners[type] || []).push(fn); },
            fire(type, event = {}) { for (const fn of this.listeners[type] || []) fn(event); },
            focus() { doc.activeElement = this; this.fire('focus'); },
            blur() { if (doc.activeElement === this) doc.activeElement = doc.body; },
        };
        return node;
    };
    doc.createElement = make;
    doc.body = make('body');
    doc.activeElement = doc.body;
    return doc;
}

function all(node) {
    return [node, ...node.children.flatMap(all)];
}

function textOf(node) {
    return all(node).map((n) => n.textContent).join(' | ');
}

test('the panel: German, score and threshold, warning, to-do buttons that call back, card links', () => {
    const doc = fakeDoc();
    const box = doc.createElement('div');
    const later = [...cards, { id: 'k-3', title: 'Neu', updated_at: '2026-03-02T11:00:00+00:00' }];
    const calls = { run: 0, todo: [], card: [] };
    panel.render(doc, box, panel.standOf({ row: row({ bewertung_lauf: lauf(), handwert: { score: 80 } }), cards: later }), {
        onRun: () => { calls.run += 1; },
        onTodo: (nr, wie) => calls.todo.push([nr, wie]),
        onCard: (id) => calls.card.push(id),
    });
    const text = textOf(box);
    for (const part of ['Beispielbubble', '61', 'Schwelle zum Befördern: 95 (Vorgabe)', 'Karten geändert – neu bewerten',
        'Wohl veraltet: eine Karte wurde nach der Bewertung geändert', 'Wissenslage', '9/25', 'To-dos', ' (2 offen von 3)',
        'Abnahme festlegen', '+6', 'Karte gelöscht', 'erledigt vom Agenten', 'Handwert', '80 von Hand', 'Neu bewerten']) {
        assert.ok(text.includes(part), part);
    }
    assert.ok(!/GO|NEEDS_WORK|Top Missing|Rowboat/.test(text), 'no old words');
    const nodes = all(box);
    const rerun = nodes.find((n) => n.id === 'eval-rerun-btn');
    assert.equal(rerun.dataset.satz, 'Bewerte diese Bubble');
    rerun.fire('click', MOUSE);
    assert.equal(calls.run, 1);
    const buttons = nodes.filter((n) => n.className === 'bewertung-todo-btn');
    assert.deepEqual(buttons.map((b) => [b.dataset.todoNr, b.dataset.todoWie, b.textContent]),
        [['2', 'agent', 'Agent soll das erledigen'], ['2', 'hand', 'erledigt'], ['1', 'agent', 'Agent soll das erledigen'], ['1', 'hand', 'erledigt']]);
    buttons[0].fire('click', MOUSE);
    buttons[3].fire('click', MOUSE);
    assert.deepEqual(calls.todo, [[2, 'agent'], [1, 'hand']]);
    nodes.find((n) => n.className === 'bewertung-karte' && n.dataset.cardId === 'k-2').fire('click', MOUSE);
    assert.deepEqual(calls.card, ['k-2']);
    const mark = nodes.find((n) => n.className === 'score-bar-schwelle');
    assert.equal(mark.style.left, '95%');

    panel.render(doc, box, panel.standOf({ row: row({}) }), { laeuft: true });
    const empty = textOf(box);
    assert.ok(empty.includes('Noch keine Bewertung für diese Bubble.') && empty.includes('Bewertung läuft'));
    assert.equal(all(box).find((n) => n.id === 'eval-rerun-btn').disabled, true, 'no second run while one goes');
});

test('white paper and decision to-dos are done by hand: no agent button; at the threshold only a careful word', () => {
    const doc = fakeDoc();
    const box = doc.createElement('div');
    const run = lauf({ todos: [
        { nr: 1, sicht: 'ideas', titel: 'Papier', fehlt: 'Kein White Paper.', karten: [], punkte: 5, art: 'white_paper', erledigt: false },
        { nr: 2, sicht: 'ideas', titel: 'Wahl', fehlt: 'Offen.', karten: [], punkte: 2, art: 'entscheidung', erledigt: false },
    ] });
    panel.render(doc, box, panel.standOf({ row: row({ bewertung_lauf: run }), cards, schwelle: 60 }), {});
    const nodes = all(box);
    assert.deepEqual(nodes.filter((n) => n.className === 'bewertung-todo-btn').map((b) => [b.dataset.todoNr, b.dataset.todoWie]),
        [['1', 'hand'], ['2', 'hand']]);
    const text = textOf(box);
    assert.ok(text.includes('Von Hand: „Erstelle ein White Paper aus dieser Bubble“'));
    assert.ok(text.includes('Schwelle erreicht'));
    assert.ok(text.includes('Beförderbar, wenn seit der Bewertung keine Karte geändert wurde'));
});

test('the window: one source, no threshold of its own, the module loaded before the bar', () => {
    const html = fs.readFileSync(path.join(__dirname, 'renderer', 'index.html'), 'utf8');
    assert.ok(html.indexOf('src="bewertung-panel.js"') > 0 && html.indexOf('src="bewertung-panel.js"') < html.indexOf('src="bubble-bar.js"'));
    assert.ok(!/>= 66|>= 60|NEEDS_WORK|ai_eval|per_agent|missing_items/.test(html), 'no old evaluation read in the window');
    assert.match(html, /canvas_nodes\?linked_idea_id=eq\.\$\{encodeURIComponent\(row\.id\)\}&select=id,title,updated_at/);
    assert.match(html, /window\.VibeBewertung\.standOf\(\{ row, cards \}\)/);
    assert.match(html, /window\.startBewertung = function/);
});

// ---- Lauf 34: a key on a focused button must not send a to-do by itself ----

function drawn({ now, ...actions } = {}) {
    const doc = fakeDoc();
    const box = doc.createElement('div');
    const clock = { t: now === undefined ? 10000 : now };
    const calls = { todo: [], run: 0, card: [] };
    panel.render(doc, box, panel.standOf({ row: row({ bewertung_lauf: lauf() }), cards }), {
        now: () => clock.t,
        onTodo: (nr, wie) => calls.todo.push([nr, wie]),
        onRun: () => { calls.run += 1; },
        onCard: (id) => calls.card.push(id),
        ...actions,
    });
    const nodes = all(box);
    const todoBtn = (nr, wie) => nodes.find((n) => n.className === 'bewertung-todo-btn' && n.dataset.todoNr === String(nr) && n.dataset.todoWie === wie);
    return { doc, box, clock, calls, nodes, todoBtn, run: nodes.find((n) => n.id === 'eval-rerun-btn') };
}

test('a mouse click works and gives the focus away at once', () => {
    const p = drawn();
    const b = p.todoBtn(2, 'agent');
    b.focus();
    b.fire('click', MOUSE);
    assert.deepEqual(p.calls.todo, [[2, 'agent']]);
    assert.equal(p.doc.activeElement, p.doc.body, 'no button keeps the focus after the click');
    p.run.focus();
    p.run.fire('click', MOUSE);
    assert.equal(p.calls.run, 1);
    assert.equal(p.doc.activeElement, p.doc.body);
});

test('Tab and then Enter (or Space) still work', () => {
    const p = drawn();
    p.clock.t += 2000;                         // the person reads, then tabs to the button
    const b = p.todoBtn(1, 'hand');
    b.focus();
    p.clock.t += 300;
    b.fire('keydown', { key: 'Enter', repeat: false, isTrusted: true });
    b.fire('click', KEYBOARD_CLICK);
    assert.deepEqual(p.calls.todo, [[1, 'hand']]);
    const r = p.run;
    r.focus();
    p.clock.t += 300;
    r.fire('keydown', { key: ' ', repeat: false, isTrusted: true });
    r.fire('click', KEYBOARD_CLICK);
    assert.equal(p.calls.run, 1);
});

test('a key held down, a key right after drawing, a key without focus or a script click send nothing', () => {
    const p = drawn();
    const b = p.todoBtn(2, 'agent');
    // the focus landed on the button while Enter was still held: only repeats arrive
    b.focus();
    p.clock.t += 600;
    b.fire('keydown', { key: 'Enter', repeat: true, isTrusted: true });
    b.fire('click', KEYBOARD_CLICK);
    // a fresh key, but within 400 ms after the panel was drawn
    const q = drawn();
    const c = q.todoBtn(2, 'agent');
    c.focus();
    q.clock.t += panel.KEY_GRACE_MS - 1;
    c.fire('keydown', { key: 'Enter', repeat: false, isTrusted: true });
    c.fire('click', KEYBOARD_CLICK);
    // a key that was pressed before the button got the focus
    const r = drawn();
    const d = r.todoBtn(1, 'agent');
    r.clock.t += 1000;
    d.fire('keydown', { key: 'Enter', repeat: false, isTrusted: true });
    r.clock.t += 10;
    d.focus();
    d.fire('click', KEYBOARD_CLICK);
    // a click() raised by a script: no key at all
    d.fire('click', { detail: 0, isTrusted: false });
    // the second click of one key press does not count again
    const s = drawn();
    const e = s.todoBtn(1, 'hand');
    s.clock.t += 1000;
    e.focus();
    s.clock.t += 100;
    e.fire('keydown', { key: 'Enter', repeat: false, isTrusted: true });
    e.fire('click', KEYBOARD_CLICK);
    e.fire('click', KEYBOARD_CLICK);
    assert.deepEqual([p.calls.todo, q.calls.todo, r.calls.todo], [[], [], []]);
    assert.deepEqual(s.calls.todo, [[1, 'hand']]);
});

test('drawing again puts the focus on no button and takes it from the old one', () => {
    const p = drawn();
    const b = p.todoBtn(2, 'agent');
    b.focus();
    panel.render(p.doc, p.box, panel.standOf({ row: row({ bewertung_lauf: lauf() }), cards }), { now: () => p.clock.t });
    assert.equal(p.doc.activeElement, p.doc.body);
    assert.ok(!all(p.box).includes(p.doc.activeElement));
});

test('while a to-do of the panel is open the to-do buttons and Neu bewerten are off, with the reason', () => {
    const sp = panel.createTodoSperre({ now: () => 0 });
    sp.start(2, 'agent');
    sp.sent('spur-1');
    const p = drawn({ sperre: sp.current() });
    const buttons = p.nodes.filter((n) => n.className === 'bewertung-todo-btn');
    assert.ok(buttons.length > 0 && buttons.every((b) => b.disabled));
    assert.equal(p.run.disabled, true);
    assert.ok(textOf(p.box).includes('To-do 2 ist abgeschickt'));
    buttons[0].fire('click', MOUSE);
    assert.deepEqual(p.calls.todo, [], 'a switched-off button sends nothing');
    const running = drawn({ laeuft: true });
    assert.ok(running.nodes.filter((n) => n.className === 'bewertung-todo-btn').every((b) => b.disabled), 'and while an evaluation runs');
});

test('the lock: answer, question back, "Ja, erledigen", the order, the database, and time limits', () => {
    const clock = { t: 0 };
    const sp = panel.createTodoSperre({ now: () => clock.t });
    assert.equal(sp.current(), null);

    // question back, then "Ja, erledigen" starts an order; the to-do done in the database ends it
    sp.start(3, 'agent');
    sp.sent('spur-a');
    sp.answered({ trace_id: 'spur-x', note: 'rueckfrage' });
    assert.equal(sp.current().phase, 'gesendet', 'the answer of another sentence does not count');
    sp.answered({ trace_id: 'spur-a', note: 'rueckfrage', success: true });
    assert.equal(sp.current().phase, 'rueckfrage');
    assert.match(sp.current().text, /Rückfrage im Chat offen/);
    sp.answered({ trace_id: 'spur-b', accepted: true, orders: ['auftrag-1'] });
    assert.equal(sp.current().phase, 'auftrag');
    sp.order('auftrag-1', { stand: 'laeuft' });
    assert.equal(sp.current().phase, 'auftrag');
    sp.stand({ leer: false, todos: [{ nr: 3, erledigt: false }, { nr: 1, erledigt: true }] });
    assert.equal(sp.current().phase, 'auftrag', 'another to-do done does not free it');
    sp.stand({ leer: false, todos: [{ nr: 3, erledigt: true }] });
    assert.equal(sp.current(), null);

    // any other sentence drops the question back
    sp.start(1, 'agent');
    sp.sent('spur-c');
    sp.answered({ trace_id: 'spur-c', note: 'rueckfrage' });
    sp.answered({ trace_id: 'spur-d', note: '' });
    assert.equal(sp.current(), null);

    // the order ended (also with an error): free again
    sp.start(1, 'agent');
    sp.sent('spur-e');
    sp.answered({ trace_id: 'spur-e', accepted: true, orders: ['auftrag-2'] });
    sp.order('auftrag-9', { stand: 'fehler' });
    assert.equal(sp.current().phase, 'auftrag', 'another order');
    sp.order('auftrag-2', { stand: 'fehler' });
    assert.equal(sp.current(), null);

    // marked done by hand: the answer frees it, the database shows it done
    sp.start(2, 'hand');
    sp.sent('spur-f');
    sp.answered({ trace_id: 'spur-f', success: true });
    assert.equal(sp.current(), null);

    // nothing sent: cleared; an answer that never comes and a forgotten question end by time
    sp.start(2, 'agent');
    sp.clear();
    assert.equal(sp.current(), null);
    sp.start(2, 'agent');
    sp.sent('spur-g');
    clock.t += panel.SPERRE_MS.gesendet + 1;
    assert.equal(sp.current(), null);
    sp.start(2, 'agent');
    sp.sent('spur-h');
    sp.answered({ trace_id: 'spur-h', note: 'rueckfrage' });
    clock.t += panel.SPERRE_MS.rueckfrage + 1;
    assert.equal(sp.current(), null, 'the Brain forgets the question after 120 s');
});

test('the window keeps the lock: a to-do button goes through it, a second one waits, a new bubble frees it', () => {
    const html = fs.readFileSync(path.join(__dirname, 'renderer', 'index.html'), 'utf8');
    assert.match(html, /onTodo: _bewertungTodo,/);
    assert.match(html, /sperre: _todoSperre \? _todoSperre\.current\(\) : null,/);
    assert.match(html, /if \(!sp \|\| sp\.current\(\) \|\| _bewertungLauf\) return;/);
    assert.match(html, /addEventListener\('vibemind:sentence-sent'/);
    assert.match(html, /addEventListener\('vibemind:sentence-answered'/);
    assert.match(html, /if \(_todoSperre && _todoSperre\.current\(\)\) return false;/);
    assert.match(html, /if \(_todoSperre\) _todoSperre\.clear\(\);/);
    assert.match(html, /if \(_todoSperre\) _todoSperre\.stand\(stand\);/);
});

// ---- H1: the bar only opens the panel; a run starts in it, a young run asks once more ----

test('a run younger than 10 minutes with no card changed asks once more; otherwise not', () => {
    const t = Date.parse(ZEIT);
    const fresh = panel.standOf({ row: row({ bewertung_lauf: lauf() }), cards });
    assert.equal(panel.brauchtBestaetigung(fresh, t + 9 * 60 * 1000), true);
    assert.equal(panel.brauchtBestaetigung(fresh, t + 10 * 60 * 1000), false, 'ten minutes old: no question');
    const changed = panel.standOf({ row: row({ bewertung_lauf: lauf() }),
        cards: [...cards, { id: 'k-3', title: 'Neu', updated_at: '2026-03-02T10:01:00+00:00' }] });
    assert.equal(panel.brauchtBestaetigung(changed, t + 2 * 60 * 1000), false, 'a card changed: run without asking');
    assert.equal(panel.brauchtBestaetigung(panel.standOf({ row: row({}), cards }), t), false, 'no run yet');
});

test('the question replaces "Neu bewerten": yes runs, Abbrechen does not, both behind the key guard', () => {
    const calls = { confirm: 0, cancel: 0 };
    const p = drawn({ bestaetigen: true, onConfirm: () => { calls.confirm += 1; }, onCancel: () => { calls.cancel += 1; } });
    assert.equal(p.run, undefined, 'no run button while the question is open');
    assert.ok(textOf(p.box).includes('Trotzdem neu bewerten?'));
    const yes = p.nodes.find((n) => n.id === 'eval-rerun-confirm-btn');
    assert.equal(yes.textContent, 'Ja, neu bewerten (1 Abo-Aufruf)');
    yes.focus();
    yes.fire('click', KEYBOARD_CLICK);
    assert.equal(calls.confirm, 0, 'a key on a focused button right after drawing sends nothing');
    yes.fire('click', MOUSE);
    assert.equal(calls.confirm, 1);
    p.nodes.find((n) => n.textContent === 'Abbrechen').fire('click', MOUSE);
    assert.equal(calls.cancel, 1);
    assert.equal(drawn().run.textContent, 'Neu bewerten (1 Abo-Aufruf)');
});

test('the window: the bar button only toggles, the open panel reads again after a run', () => {
    const html = fs.readFileSync(path.join(__dirname, 'renderer', 'index.html'), 'utf8');
    assert.match(html, /bestaetigen: _runConfirm/);
    assert.match(html, /VibeBewertung\.brauchtBestaetigung\(_bewertungStand\)/);
    for (const name of ['vibemind:order-ended', 'vibemind:canvas-node-updated']) assert.ok(html.includes(`'${name}'`), name);
    assert.match(html, /setInterval\(_refreshIfOpen, BEWERTUNG_OFFEN_MS\)/);
    assert.match(html, /clearInterval\(_offenTimer\)/);
});
