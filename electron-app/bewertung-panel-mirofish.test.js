// Lauf 39: the evaluation now comes from MiroFish only. The run has the form MiroFish writes (five views,
// each with five criteria of 0-5 points, a source and the number of calls). Invented bubble and texts.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const panel = require('./renderer/bewertung-panel.js');
const { bannerCss, BANNER_HEIGHT_PX } = require('./fernsteuerung');

const read = (...parts) => fs.readFileSync(path.join(__dirname, ...parts), 'utf8');

const kriterien = (punkte) => punkte.map((p, i) => ({ name: `Kriterium ${i + 1}`, punkte: p, begruendung: `Begründung ${i + 1}.` }));

function mirofishLauf(overrides = {}) {
    return {
        version: 1,
        zeit: '2026-03-02T10:00:00+00:00',
        score: 40,
        quelle: 'mirofish',
        aufrufe: 5,
        sichten: {
            coding: { punkte: 8, urteil: 'Technik nur angedeutet.', kriterien: kriterien([2, 2, 1, 1, 2]) },
            swe_design: { punkte: 9, urteil: 'Ablauf klar, Abnahme fehlt.', kriterien: kriterien([2, 1, 2, 3, 1]) },
            research: { punkte: 7, urteil: 'Kaum Quellen.', kriterien: kriterien([0, 0, 2, 2, 3]) },
            rowboat: { punkte: 7, urteil: 'Vorwissen dünn.', kriterien: kriterien([1, 1, 2, 1, 2]) },
            ideas: { punkte: 9, urteil: 'Idee tragfähig.', kriterien: kriterien([3, 3, 1, 2, 0]) },
        },
        todos: [],
        kartenstand: 'abc',
        gekuerzt: false,
        ...overrides,
    };
}

const row = (lauf) => ({ id: 'idee-1', title: 'Beispielbubble', metadata: { bewertung_lauf: lauf } });

function fakeDoc() {
    const doc = {};
    doc.createElement = (tag) => ({
        tagName: tag.toUpperCase(), className: '', textContent: '', title: '', id: '', type: '', disabled: false,
        dataset: {}, style: {}, children: [], listeners: {},
        append(...kids) { this.children.push(...kids); },
        replaceChildren(...kids) { this.children = kids; },
        contains() { return false; },
        addEventListener(type, fn) { (this.listeners[type] = this.listeners[type] || []).push(fn); },
    });
    doc.body = doc.createElement('body');
    doc.activeElement = doc.body;
    return doc;
}
const all = (node) => [node, ...node.children.flatMap(all)];
function drawn(lauf, actions = {}) {
    const doc = fakeDoc();
    const box = doc.createElement('div');
    panel.render(doc, box, panel.standOf({ row: row(lauf), cards: [] }), actions);
    const nodes = all(box);
    return { nodes, text: nodes.map((n) => n.textContent).join(' | ') };
}

test('each view opens to its verdict and five criteria with points of 5 and the reason', () => {
    const stand = panel.standOf({ row: row(mirofishLauf()), cards: [] });
    const coding = stand.sichten.find((s) => s.key === 'coding');
    assert.equal(coding.kriterien.length, 5);
    assert.deepEqual(coding.kriterien[0], { name: 'Kriterium 1', punkte: 2, begruendung: 'Begründung 1.' });
    for (const s of stand.sichten) assert.equal(s.kriterien.reduce((a, k) => a + k.punkte, 0), s.punkte, s.key);

    const { nodes } = drawn(mirofishLauf());
    const views = nodes.filter((n) => n.tagName === 'DETAILS' && n.className === 'sicht');
    assert.deepEqual(views.map((v) => v.dataset.sicht), ['coding', 'swe_design', 'research', 'rowboat', 'ideas']);
    const research = views[2];
    assert.equal(research.children[0].tagName, 'SUMMARY', 'the bar row is what one clicks');
    const inner = all(research);
    assert.ok(inner.some((n) => n.className === 'sicht-urteil' && n.textContent === 'Kaum Quellen.'));
    assert.deepEqual(inner.filter((n) => n.className === 'kriterium-punkte').map((n) => n.textContent), ['0/5', '0/5', '2/5', '2/5', '3/5']);
    assert.equal(inner.filter((n) => n.className === 'kriterium-begruendung').length, 5);
});

test('criteria: points kept to 0-5, nonsense left out, an old run without criteria says so', () => {
    const odd = mirofishLauf();
    odd.sichten.coding.kriterien = [{ name: 'Zu viel', punkte: 9, begruendung: '' }, { name: 'Zu wenig', punkte: -2 }, 'Text', null, {}];
    const coding = panel.standOf({ row: row(odd), cards: [] }).sichten.find((s) => s.key === 'coding');
    assert.deepEqual(coding.kriterien.map((k) => [k.name, k.punkte]), [['Zu viel', 5], ['Zu wenig', 0]]);
    const old = mirofishLauf();
    old.sichten.ideas = { punkte: 9 };
    assert.ok(drawn(old).text.includes('Keine Kriterien gespeichert.'));
});

test('the source line: MiroFish with five roles and its calls; an older run of the agent says so', () => {
    assert.ok(drawn(mirofishLauf()).text.includes('Bewertet von MiroFish mit fünf Rollen, 5 Abo-Aufrufe'));
    assert.ok(drawn(mirofishLauf({ aufrufe: 1 })).text.includes('Bewertet von MiroFish mit fünf Rollen, 1 Abo-Aufruf |'));
    assert.ok(drawn(mirofishLauf({ aufrufe: 'viele' })).text.includes('Bewertet von MiroFish mit fünf Rollen |'), 'no number: no count');
    assert.ok(drawn(mirofishLauf({ quelle: undefined, aufrufe: undefined })).text.includes('Bewertet vom Agenten (ältere Bewertung)'));
});

test('the run button names what MiroFish costs; there is no quick run anywhere', () => {
    const { nodes } = drawn(mirofishLauf());
    assert.equal(nodes.find((n) => n.id === 'eval-rerun-btn').textContent, 'Neu bewerten (5–10 Abo-Aufrufe)');
    const empty = panel.standOf({ row: { id: 'x', title: 'Leer', metadata: {} } });
    const doc = fakeDoc();
    const box = doc.createElement('div');
    panel.render(doc, box, empty, {});
    assert.equal(all(box).find((n) => n.id === 'eval-rerun-btn').textContent, 'Jetzt bewerten (5–10 Abo-Aufrufe)');
    for (const file of [['renderer', 'bewertung-panel.js'], ['renderer', 'index.html'], ['preload.js']]) {
        const text = read(...file);
        assert.doesNotMatch(text, /Schnell bewerten/, file.join('/'));
        assert.doesNotMatch(text, /\(1 Abo-Aufruf\)/, file.join('/'));
    }
});

test('the bars of the views fill: the fill is a span, so the page gives it a block box', () => {
    const { nodes } = drawn(mirofishLauf());
    const fills = nodes.filter((n) => n.className === 'agent-bar-fill');
    assert.deepEqual(fills.map((f) => [f.tagName, f.style.width]),
        [['SPAN', '32%'], ['SPAN', '36%'], ['SPAN', '28%'], ['SPAN', '28%'], ['SPAN', '36%']]);
    const html = read('renderer', 'index.html');
    assert.match(html, /#eval-panel \.agent-bar-fill,\s*#eval-panel \.history-bar-fill \{ display: block; \}/);
});

test('the total: the stored score against the one maximum of the scale, bar and mark too', () => {
    const { nodes } = drawn(mirofishLauf({ score: 40 }));
    assert.equal(nodes.find((n) => n.className === 'score-number').textContent, '40');
    assert.equal(nodes.find((n) => n.className === 'score-max').textContent, `/${panel.SCORE_MAX}`);
    assert.equal(nodes.find((n) => n.className === 'score-bar-fill').style.width, `${(40 * 100) / panel.SCORE_MAX}%`);
    assert.equal(nodes.find((n) => n.className === 'score-bar-schwelle').style.left, `${Math.min(100, (95 * 100) / panel.SCORE_MAX)}%`);
    const source = read('renderer', 'bewertung-panel.js');
    assert.equal((source.match(/const SCORE_MAX = /g) || []).length, 1, 'one place');
    assert.doesNotMatch(source, /'\/100'/);
});

test('the strip of the test mode no longer covers the head of the panel', () => {
    const css = bannerCss();
    assert.ok(css.includes(`--vm-pruefstreifen: ${BANNER_HEIGHT_PX}px`));
    assert.ok(css.includes(`height: ${BANNER_HEIGHT_PX}px; box-sizing: border-box;`));
    const html = read('renderer', 'index.html');
    assert.match(html, /#eval-panel \{ top: var\(--vm-pruefstreifen, 0px\); height: calc\(100vh - var\(--vm-pruefstreifen, 0px\)\); \}/);
    // without the strip the variable is not set: the panel stays at the top
    assert.doesNotMatch(html, /--vm-pruefstreifen:/);
});
