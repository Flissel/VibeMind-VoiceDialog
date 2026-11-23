// "In Ideas it is not the same for all: in one bubble Summarize, White Paper, the Eval button,
// Start Voice and the chat are missing" (2026-11-23). Every open bubble now has one fixed bar,
// the same in an empty and a full one, below the header, covering nothing (bubble-bar.js).
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const bar = require('./renderer/bubble-bar');

const BUBBLE = '00000000-0000-4000-8000-00000000000b';
const SENTENCES = { summary: 'Fasse diese Bubble zusammen', whitepaper: 'Erstelle ein White Paper aus dieser Bubble' };

function element(doc, tag) {
    const classes = new Set();
    const listeners = {};
    const attrs = {};
    const el = {
        tag, id: '', children: [], parentNode: null, textContent: '', title: '', value: '', type: '',
        disabled: false, dataset: {}, className: '',
        classList: { add: (c) => classes.add(c), remove: (c) => classes.delete(c), contains: (c) => classes.has(c),
            toggle: (c, on) => { if (on === undefined ? !classes.has(c) : on) classes.add(c); else classes.delete(c); } },
        setAttribute(k, v) { attrs[k] = String(v); }, getAttribute: (k) => (k in attrs ? attrs[k] : null),
        addEventListener(type, fn) { (listeners[type] = listeners[type] || []).push(fn); },
        fire(type, event = {}) { for (const fn of listeners[type] || []) fn({ currentTarget: el, target: el, stopPropagation() {}, ...event }); },
        click() { if (!el.disabled) el.fire('click', { isTrusted: false }); },
        append(...kids) { for (const k of kids) { k.parentNode = el; el.children.push(k); } },
        insertBefore(kid, next) {
            kid.parentNode = el;
            const at = next ? el.children.indexOf(next) : -1;
            if (at < 0) el.children.push(kid); else el.children.splice(at, 0, kid);
        },
    };
    Object.defineProperty(el, 'nextSibling', { get: () => {
        const kids = el.parentNode ? el.parentNode.children : [];
        return kids[kids.indexOf(el) + 1] || null;
    } });
    return el;
}

function page({ cards = [], view = 'karten', voice = true } = {}) {
    const doc = { body: null, activeElement: null };
    const all = (node, out = []) => { out.push(node); for (const k of node.children) all(k, out); return out; };
    doc.createElement = (tag) => element(doc, tag);
    doc.getElementById = (id) => all(doc.root).find((n) => n.id === id) || null;
    doc.root = element(doc, 'html');
    doc.body = element(doc, 'body');
    doc.root.append(doc.body);
    const spaceView = element(doc, 'div'); spaceView.id = 'space-view';
    const header = element(doc, 'div'); header.id = 'space-header';
    const canvasEl = element(doc, 'div'); canvasEl.id = 'space-canvas';
    spaceView.append(header, canvasEl);
    const indicator = element(doc, 'span'); indicator.id = 'voice-indicator'; indicator.className = 'inactive';
    const status = element(doc, 'span'); status.id = 'voice-status'; status.textContent = 'Voice: Inactive';
    const oldVoice = element(doc, 'button'); oldVoice.id = 'voice-btn';
    const score = element(doc, 'span'); score.id = 'eval-toggle-score'; score.textContent = '—';
    doc.body.append(spaceView, indicator, status, oldVoice, score);

    const calls = { sent: [], zoom: [], search: [], views: [], voice: 0, eval: 0, folded: false };
    oldVoice.click = () => { calls.voice += 1; };
    let shownView = view;
    let query = '';
    const spaceCanvas = {
        lastNodes: cards,
        currentView: () => shownView,
        cardsState: () => (shownView === 'karten' ? { count: cards.length, shown: cards.length, query, smaller: true, bigger: false } : null),
        searchCards: (text) => { query = text; calls.search.push(text); return true; },
        zoomBy: (step) => { calls.zoom.push(step); return true; },
        showView: (name) => { shownView = name; calls.views.push(name); },
    };
    const win = {
        spaceCanvas,
        vibemind: { bubbleSentences: SENTENCES, ...(voice ? { startVoice() {} } : {}) },
        VibeIdeasChat: {
            submit: (text, opts) => { calls.sent.push([text, opts.typed]); return Promise.resolve(); },
            fold: (f) => { calls.folded = f; },
            folded: () => calls.folded,
        },
        toggleEvalPanel: () => { calls.eval += 1; },
    };
    const b = bar.create(doc, win);
    b.mount();
    const ids = () => all(b.element).filter((n) => n.id).map((n) => n.id);
    return { doc, win, b, calls, spaceView, header, indicator, status, score, ids, btn: (id) => doc.getElementById(id) };
}

const threeCards = [{ id: 'k1', title: 'Karte 1' }, { id: 'k2', title: 'Karte 2' }, { id: 'k3', title: 'Karte 3' }];

test('the same buttons, in the same order, in an empty and in a full bubble', () => {
    const full = page({ cards: threeCards });
    const empty = page({ cards: [] });
    const expected = ['bubble-bar', 'bubble-search', 'bubble-count', 'bubble-zoom-out', 'bubble-zoom-in', 'bubble-view-btn',
        'bubble-summary-btn', 'bubble-whitepaper-btn', 'bubble-eval-btn', 'bubble-voice-btn', 'bubble-chat-btn'];
    assert.deepEqual(full.ids(), expected);
    assert.deepEqual(empty.ids(), expected);
    // labels in German, the same everywhere
    for (const p of [full, empty]) {
        assert.equal(p.btn('bubble-summary-btn').textContent, 'Zusammenfassung');
        assert.equal(p.btn('bubble-whitepaper-btn').textContent, 'White Paper');
        assert.equal(p.btn('bubble-eval-btn').textContent, 'Bewerten');
        assert.equal(p.btn('bubble-voice-btn').textContent, 'Sprache starten');
        assert.equal(p.btn('bubble-chat-btn').textContent, 'Chat ausblenden');
    }
    assert.equal(full.btn('bubble-count').textContent, '3 Karten');
    assert.equal(empty.btn('bubble-count').textContent, '0 Karten');
});

test('below the header, covering nothing: a row of its own, the view knows it', () => {
    const p = page({ cards: threeCards });
    assert.equal(p.b.element.parentNode, p.spaceView);
    assert.equal(p.spaceView.children.indexOf(p.b.element), p.spaceView.children.indexOf(p.header) + 1);
    assert.ok(p.spaceView.classList.contains('with-bar'));
    p.b.mount();
    assert.equal(p.spaceView.children.filter((c) => c.id === 'bubble-bar').length, 1, 'mounted once');
    const css = fs.readFileSync(path.join(__dirname, 'renderer', 'styles', 'bubble-bar.css'), 'utf8');
    assert.match(css, /#space-view\.with-bar #space-canvas \{\s*height: calc\(100% - 84px\);/);
    assert.match(css, /#space-view\.with-bar #ideas-chat \{\s*top: 84px;/);
    // the controls every view used to bring along are hidden inside a bubble: the bar works them
    for (const old of ['.kv-bar', '.kv-back', '.mermaid-zoom-controls', '.canvas-toolbar', '.zoom-controls', '.ideas-empty-hint']) {
        assert.ok(css.includes(`#space-view.with-bar ${old}`), old);
    }
    assert.ok(css.includes('body.bubble-open #eval-toggle') && css.includes('body.bubble-open #voice-panel'));
    const html = fs.readFileSync(path.join(__dirname, 'renderer', 'index.html'), 'utf8');
    assert.match(html, /<script defer src="bubble-bar\.js"><\/script>/);
    assert.doesNotMatch(html, /edge-bar\.js/);
    assert.match(html, /<div id="space-canvas"><\/div>\s*<!-- [^>]*-->\s*<\/div>/, 'the bubble view holds only header and canvas');
    assert.match(html, /<button id="back-btn">← Zurück<\/button>/, 'German in the header too');
    assert.match(fs.readFileSync(path.join(__dirname, 'renderer', 'styles.css'), 'utf8'), /styles\/bubble-bar\.css/);
});

test('mounting again writes no class: the observer on the class of the view would call it without end', () => {
    const p = page({ cards: threeCards });
    let writes = 0;
    const add = p.spaceView.classList.add;
    p.spaceView.classList.add = (c) => { writes += 1; add(c); };
    p.b.mount();
    p.b.mount();
    assert.equal(writes, 0);
    // the watch: one change of the view, one sync, then quiet
    let observed = null;
    class Observer { constructor(fn) { this.fn = fn; } observe(el) { if (el === p.spaceView) observed = this.fn; } }
    p.b.watch(Observer);
    observed();
    observed();
    assert.equal(writes, 0);
    assert.ok(p.doc.body.classList.contains('bubble-open'));
});

test('what cannot work now is switched off with its reason, not gone', () => {
    const empty = page({ cards: [], voice: false });
    for (const id of ['bubble-summary-btn', 'bubble-whitepaper-btn', 'bubble-view-btn']) {
        assert.equal(empty.btn(id).disabled, true, id);
        assert.equal(empty.btn(id).title, 'Noch keine Karten in dieser Bubble', id);
    }
    assert.equal(empty.btn('bubble-voice-btn').disabled, true);
    assert.equal(empty.btn('bubble-voice-btn').title, 'Sprachdienst nicht verfügbar');
    assert.equal(empty.btn('bubble-eval-btn').disabled, false, 'the evaluation can be opened in any bubble');
    assert.equal(empty.btn('bubble-chat-btn').disabled, false);
    assert.equal(empty.btn('bubble-search').disabled, false);

    const plan = bar.plan({ view: 'karten', cards: { count: 2, shown: 2, query: '', smaller: true, bigger: true } });
    assert.equal(plan.summary.title, 'Gehirn-Chat nicht verfügbar');
    assert.equal(plan.evaluate.disabled, true);
    assert.equal(plan.chat.disabled, true);
    assert.equal(plan.chat.title, 'Chat nur im Ideen-Bereich');
});

test('Zusammenfassung and White Paper send the fixed sentence through the chat, typed only on a click of the person', () => {
    const p = page({ cards: threeCards });
    p.btn('bubble-summary-btn').fire('click', { isTrusted: true });
    p.btn('bubble-whitepaper-btn').fire('click', { isTrusted: true });
    p.btn('bubble-summary-btn').fire('click', { isTrusted: false });   // raised by a script
    assert.deepEqual(p.calls.sent, [[SENTENCES.summary, true], [SENTENCES.whitepaper, true], [SENTENCES.summary, false]]);
    assert.equal(p.btn('bubble-summary-btn').title, `Schickt „${SENTENCES.summary}“ an das Gehirn`);
    const empty = page({ cards: [] });
    empty.btn('bubble-summary-btn').fire('click', { isTrusted: true });
    assert.deepEqual(empty.calls.sent, [], 'switched off sends nothing');
});

test('search, zoom and the view work the canvas; in the diagram the search is off, the zoom works the diagram', () => {
    const p = page({ cards: threeCards });
    const search = p.btn('bubble-search');
    search.value = 'Karte 2';
    search.fire('input');
    assert.deepEqual(p.calls.search, ['Karte 2']);
    assert.equal(p.btn('bubble-zoom-in').disabled, true, 'biggest size reached');
    p.btn('bubble-zoom-out').fire('click');
    assert.deepEqual(p.calls.zoom, [-1]);
    p.btn('bubble-view-btn').fire('click');
    assert.deepEqual(p.calls.views, ['graph']);
    assert.equal(p.btn('bubble-view-btn').textContent, 'Karten');
    assert.equal(search.disabled, true);
    assert.equal(search.title, 'Suche gilt den Karten – erst „Karten“ wählen');
    assert.equal(p.btn('bubble-zoom-in').disabled, false);
    assert.equal(p.btn('bubble-zoom-in').title, 'Verbindungsbild vergrößern');
    p.btn('bubble-view-btn').fire('click');
    assert.deepEqual(p.calls.views, ['graph', 'karten']);
});

test('voice, evaluation and chat: the bar shows their state and works them', () => {
    const p = page({ cards: threeCards });
    p.btn('bubble-voice-btn').fire('click');
    assert.equal(p.calls.voice, 1, 'the old voice button keeps the voice state; the bar clicks it');
    p.indicator.className = 'active';
    p.b.render();
    assert.equal(p.btn('bubble-voice-btn').textContent, 'Sprache stoppen');
    p.indicator.className = 'connecting';
    p.b.render();
    assert.equal(p.btn('bubble-voice-btn').disabled, true);
    assert.deepEqual(bar.voiceState({ available: true, indicator: 'inactive', status: 'Voice: Error' }).state, 'fehler');

    p.score.textContent = '46,5';
    p.btn('bubble-eval-btn').fire('click');
    assert.equal(p.calls.eval, 1);
    assert.equal(p.btn('bubble-eval-btn').textContent, 'Bewerten · 46,5');

    p.btn('bubble-chat-btn').fire('click');
    assert.equal(p.calls.folded, true);
    assert.equal(p.btn('bubble-chat-btn').textContent, 'Chat einblenden');
    assert.equal(p.btn('bubble-chat-btn').getAttribute('aria-pressed'), 'false');
});

// ---- the reasons of a bubble: in the database, "0" in the app ----

function canvasWorld(rowsById) {
    const events = [];
    const asked = [];
    const window = {
        vibemind: { supabase: { url: 'http://db', anonKey: 'k' } },
        multiverseApp: { getBubbleById: () => null },
        dispatchEvent: (e) => { events.push(e); return true; },
    };
    const context = {
        window,
        document: { getElementById: () => null, querySelector: () => null, createElement: () => ({ setAttribute() {} }) },
        console: { log() {}, warn() {}, error() {} },
        setInterval: () => 1, clearInterval() {}, setTimeout: () => 1, clearTimeout() {},
        fetch: async (url) => {
            const id = /\/ideas\?id=eq\.([^&]+)/.exec(url);
            if (id) asked.push(decodeURIComponent(id[1]));
            return { ok: true, json: async () => (id && rowsById[decodeURIComponent(id[1])] ? [rowsById[decodeURIComponent(id[1])]] : []) };
        },
        CustomEvent: class { constructor(type, init) { this.type = type; this.detail = init && init.detail; } },
    };
    vm.runInNewContext(fs.readFileSync(path.join(__dirname, 'renderer', 'universe_canvas.js'), 'utf8'), context);
    const canvas = Object.create(window.UniverseCanvas.prototype);
    canvas.container = { parentNode: null };
    return { canvas, events, asked };
}

test('opening a bubble loads its row from the database, so its reasons show', async () => {
    const reasons = [{ id: 'r1', text: 'Grund eins', karten: ['k1'], erstellt_am: '2026-11-23T10:00:00Z' },
        { id: 'r2', text: 'Grund zwei', karten: [], erstellt_am: '2026-11-23T11:00:00Z' }];
    const w = canvasWorld({ [BUBBLE]: { id: BUBBLE, metadata: { bewertungen: reasons } } });
    w.canvas.setBubble(BUBBLE);
    await new Promise((resolve) => setImmediate(resolve));
    assert.deepEqual(w.asked, [BUBBLE]);
    const announced = w.events.filter((e) => e.type === 'vibemind:bubble-row');
    assert.equal(announced.length, 1);
    assert.equal(announced[0].detail.row.metadata.bewertungen.length, 2);
    // the chat's list counts what came: 2, not 0
    const { reasonsFor } = require('./renderer/ideas-chat');
    assert.equal(reasonsFor(announced[0].detail.row, [{ id: 'k1', title: 'Karte 1' }]).length, 2);
    // the same bubble again: no second load from setBubble (the 5-s poll repeats it)
    w.canvas.setBubble(BUBBLE);
    await new Promise((resolve) => setImmediate(resolve));
    assert.deepEqual(w.asked, [BUBBLE]);
});

test('a row that arrives after another bubble was opened is not announced', async () => {
    const other = '00000000-0000-4000-8000-00000000000c';
    const w = canvasWorld({ [BUBBLE]: { id: BUBBLE, metadata: { bewertungen: [] } } });
    w.canvas.setBubble(BUBBLE);
    w.canvas.bubbleId = other;   // the person opened another bubble while the answer was on its way
    await new Promise((resolve) => setImmediate(resolve));
    assert.equal(w.events.filter((e) => e.type === 'vibemind:bubble-row').length, 0);
});

test('the chat takes the reasons of the row the canvas announces', () => {
    const src = fs.readFileSync(path.join(__dirname, 'renderer', 'ideas-chat.js'), 'utf8');
    assert.match(src, /addEventListener\('vibemind:bubble-row', \(event\) => bubbleRow\(event\.detail && event\.detail\.row\)\)/);
});

test('the old result windows are gone: nobody sends idea_summarized or white_paper_generated any more', () => {
    const renderer = path.join(__dirname, 'renderer');
    for (const file of ['summaries-panel.js', 'whitepaper-panel.js']) {
        assert.ok(!fs.existsSync(path.join(renderer, file)), file);
    }
    const sources = [path.join(renderer, 'index.html'), path.join(renderer, 'handlers', 'canvas-handlers.js'),
        path.join(renderer, 'styles', 'panels.css'), path.join(renderer, 'styles', 'bubble-bar.css')]
        .map((f) => fs.readFileSync(f, 'utf8')).join('\n');
    for (const gone of ['summaries-panel', 'whitepaper-panel', 'summaries-toggle', 'whitepaper-toggle',
        'idea_summarized', 'white_paper_generated', 'summariesPanel', 'whitepaperPanel']) {
        assert.ok(!sources.includes(gone), gone);
    }
});

test('the bar does not jump: "Bewerten" keeps its width with or without a count', () => {
    const css = fs.readFileSync(path.join(__dirname, 'renderer', 'styles', 'bubble-bar.css'), 'utf8');
    // measured in Chromium at 12px: "Bewerten" 71 px, "Bewerten · 47" 94 px, "Bewerten · 999" 100 px
    assert.match(css, /#bubble-bar #bubble-eval-btn \{\s*min-width: 104px;\s*font-variant-numeric: tabular-nums;/);
});
