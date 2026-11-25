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

function fakeDoc() {
    const make = (tag) => {
        const node = {
            tagName: tag.toUpperCase(), className: '', textContent: '', title: '', id: '', type: '', disabled: false,
            dataset: {}, style: {}, children: [], listeners: {},
            append(...kids) { for (const k of kids) { this.children.push(k); } },
            replaceChildren(...kids) { this.children = kids; },
            addEventListener(type, fn) { (this.listeners[type] = this.listeners[type] || []).push(fn); },
            fire(type, event = {}) { for (const fn of this.listeners[type] || []) fn(event); },
        };
        return node;
    };
    return { createElement: make };
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
    rerun.fire('click');
    assert.equal(calls.run, 1);
    const buttons = nodes.filter((n) => n.className === 'bewertung-todo-btn');
    assert.deepEqual(buttons.map((b) => [b.dataset.todoNr, b.dataset.todoWie, b.textContent]),
        [['2', 'agent', 'Agent soll das erledigen'], ['2', 'hand', 'erledigt'], ['1', 'agent', 'Agent soll das erledigen'], ['1', 'hand', 'erledigt']]);
    buttons[0].fire('click');
    buttons[3].fire('click');
    assert.deepEqual(calls.todo, [[2, 'agent'], [1, 'hand']]);
    nodes.find((n) => n.className === 'bewertung-karte' && n.dataset.cardId === 'k-2').fire('click');
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
