const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const target = require('./renderer/result-target');

const BUBBLE_DB = '00000000-0000-4000-8000-00000000000b';
const CARD = '00000000-0000-4000-8000-000000000001';

test('a ziel of the Brain passes with plain ids only; node_id may be null', () => {
    assert.deepEqual(target.zielOf({ space: 'ideas', bubble_id: BUBBLE_DB, node_id: CARD }), { space: 'ideas', named: 'ideas', bubble_id: BUBBLE_DB, node_id: CARD });
    assert.deepEqual(target.zielOf({ space: 'ideas', bubble_id: 7, node_id: null }), { space: 'ideas', named: 'ideas', bubble_id: '7', node_id: null });
    assert.deepEqual(target.zielOf({ space: 'ideas', bubble_id: BUBBLE_DB, node_id: '"] x' }), { space: 'ideas', named: 'ideas', bubble_id: BUBBLE_DB, node_id: null });
    assert.equal(target.zielOf({ space: 'ideas', bubble_id: '../x' }), null);
    assert.equal(target.zielOf({ space: 'Ideas!', bubble_id: BUBBLE_DB }), null);
    assert.equal(target.zielOf(null), null);
});

/** The scene, the bubble navigation and the cards on screen, with stand-in timers. */
function scene() {
    let now = 0;
    let timers = [];
    const calls = [];
    const classes = new Set();
    const card = {
        classList: { add: (c) => classes.add(c), remove: (c) => classes.delete(c) },
        scrollIntoView: () => calls.push('scroll'),
    };
    let cardsShown = false;
    const app = {
        currentSpace: 'video', isNavigating: false, isInsideBubble: false,
        spaces: { ideas: { name: 'Ideas' }, video: { name: 'Video' }, sales: { name: 'Sales', external: true }, roarboot: { name: 'Rowboat' }, projects: { name: 'Projects' }, marketing: { name: 'Marketing', hidden: true } },
        // the overview: local id 3, database id BUBBLE_DB
        getBubbleById: (id) => (id === 3 || id === '3' || id === BUBBLE_DB ? { userData: { id: 3, db_id: BUBBLE_DB } } : null),
        navigateToSpace: (space) => calls.push('navigate ' + space),
    };
    const win = {
        multiverseApp: app,
        spaceNavigator: { switchSpace: (space) => calls.push('switch ' + space) },
        bubbleNavigation: {
            enterSpace: (id) => calls.push('enter ' + id),
            exitSpace: () => calls.push('exit'),
        },
        vibemind: { enterBubble: (id) => calls.push('backend enter ' + id) },
        spaceCanvas: { bubbleId: null, selectNode: (id) => calls.push('select ' + id) },
        setTimeout(fn, ms) { const t = { fn, at: now + ms }; timers.push(t); return t; },
        clearTimeout(t) { timers = timers.filter((x) => x !== t); },
    };
    const doc = { querySelector: (sel) => (cardsShown && sel === `[data-card-id="${CARD}"]` ? card : null) };
    return {
        win, app, calls, classes, follower: target.create(win, doc),
        showCards() { cardsShown = true; },
        advance(ms) {
            const until = now + ms;
            while (true) {
                const due = timers.filter((t) => t.at <= until).sort((a, b) => a.at - b.at)[0];
                if (!due) break;
                timers = timers.filter((t) => t !== due);
                now = due.at;
                due.fn();
            }
            now = until;
        },
    };
}

test('from another space: into Ideas, into the bubble the way of the enter button, the card marked', () => {
    const s = scene();
    assert.equal(s.follower.follow({ space: 'ideas', bubble_id: BUBBLE_DB, node_id: CARD }), true);
    assert.deepEqual(s.calls, ['switch ideas']);

    s.app.isNavigating = true;                         // the camera moves
    s.advance(target.STEP_MS);
    assert.deepEqual(s.calls, ['switch ideas'], 'nothing while the camera moves');
    s.app.isNavigating = false;
    s.app.currentSpace = 'ideas';
    s.advance(target.STEP_MS);
    assert.deepEqual(s.calls.slice(1), ['backend enter 3', 'enter 3'], 'the local id of the bubble, as the enter button does');

    s.app.isInsideBubble = true;
    s.win.spaceCanvas.bubbleId = 3;
    s.advance(target.STEP_MS);
    assert.equal(s.classes.has(target.MARK), false, 'the cards are not loaded yet');
    s.showCards();
    s.advance(target.STEP_MS);
    assert.equal(s.classes.has(target.MARK), true);
    assert.ok(s.calls.includes('scroll'));
    assert.ok(s.calls.includes('select ' + CARD));
    assert.equal(s.follower.pending(), null, 'there');
    s.advance(target.MARK_MS);
    assert.equal(s.classes.has(target.MARK), false, 'the ring goes after a while');
});

test('out of another open bubble first; a bubble as a whole (node_id null) ends inside it', () => {
    const s = scene();
    s.app.currentSpace = 'ideas';
    s.app.isInsideBubble = true;
    s.win.spaceCanvas.bubbleId = 9;
    s.follower.follow({ space: 'ideas', bubble_id: BUBBLE_DB, node_id: null });
    assert.deepEqual(s.calls, ['exit']);
    s.app.isInsideBubble = false;
    s.advance(target.STEP_MS);
    assert.deepEqual(s.calls.slice(1), ['backend enter 3', 'enter 3']);
    s.app.isInsideBubble = true;
    s.win.spaceCanvas.bubbleId = BUBBLE_DB;
    s.advance(target.STEP_MS);
    assert.equal(s.follower.pending(), null);
    assert.equal(s.follower.opens({ space: 'ideas', bubble_id: BUBBLE_DB, node_id: null }), true);
});

test('the same ziel twice (answer and end of the plan) does not start anew; without ziel nothing happens', () => {
    const s = scene();
    const ziel = { space: 'ideas', bubble_id: BUBBLE_DB, node_id: CARD };
    s.follower.follow(ziel);
    s.follower.follow({ ...ziel });
    assert.deepEqual(s.calls, ['switch ideas']);
    assert.equal(s.follower.follow(null), false);
    assert.equal(s.follower.follow({ space: 'ideas', bubble_id: '../x' }), false);
});

test('a bubble the overview never shows: it gives up quietly', () => {
    const s = scene();
    s.app.currentSpace = 'ideas';
    s.follower.follow({ space: 'ideas', bubble_id: 'ffff', node_id: null });
    s.advance(target.STEP_MS * (target.TRIES + 2));
    assert.equal(s.follower.pending(), null);
    assert.deepEqual(s.calls, []);
});

test('the page loads it before the status line, and the ring has its style', () => {
    const html = fs.readFileSync(path.join(__dirname, 'renderer', 'index.html'), 'utf8');
    assert.ok(html.indexOf('src="result-target.js"') > -1);
    assert.ok(html.indexOf('src="result-target.js"') < html.indexOf('src="task-navigate.js"'));
    const css = fs.readFileSync(path.join(__dirname, 'renderer', 'styles', 'card-view.css'), 'utf8');
    assert.match(css, /\.kv-card\.kv-ziel \{/);
});

// Routing (24.11.): every space the Brain can name as ziel.space. The names of the Brain are those of
// config/space_agent_registry.yml (state 2026-11-24) and those the coordination named; the spaces of the
// app are read from the page (tabs) and from the external spaces, as the scene has them.
const BRAIN_SPACES = ['ideas', 'bubbles', 'desktop', 'rowboat', 'sales', 'marketing', 'learning', 'coding', 'events', 'orders',
    'mirofish', 'agentfarm', 'research', 'recherche', 'thebrain', 'video', 'flowzen', 'minibook', 'schedule'];
function appSpaces() {
    const html = fs.readFileSync(path.join(__dirname, 'renderer', 'index.html'), 'utf8');
    const { EXTERNAL_SPACES } = require('./external-spaces');
    const spaces = {};
    for (const m of html.matchAll(/class="space-tab[^"]*"[^>]*data-space="([^"]+)"/g)) spaces[m[1]] = { name: m[1] };
    for (const s of EXTERNAL_SPACES) spaces[s.id] = { name: s.label, external: true };
    return spaces;
}

test('every space the Brain can name: the app goes there, or says calmly where the result is', () => {
    const spaces = appSpaces();
    const went = {};
    const told = {};
    for (const name of BRAIN_SPACES) {
        const s = scene();
        s.app.spaces = spaces;
        s.app.currentSpace = 'clawport';
        const followed = s.follower.follow({ space: name });
        went[name] = followed ? s.calls.filter((c) => c.startsWith('switch ')).map((c) => c.slice(7))[0] : null;
        told[name] = s.follower.unreachable({ space: name });
        assert.equal(Boolean(followed), told[name] === '', `${name}: either it goes, or it says why not`);
    }
    assert.deepEqual(went, {
        ideas: 'ideas', bubbles: 'ideas', desktop: 'desktop', rowboat: 'roarboot', sales: 'sales', marketing: 'marketing',
        learning: 'learning', coding: 'projects', events: 'events', orders: 'orders', mirofish: 'mirofish', agentfarm: 'agentfarm',
        research: 'ideas', recherche: 'ideas', thebrain: 'thebrain', video: 'video', flowzen: 'flowzen', minibook: null, schedule: null,
    });
    assert.equal(told.minibook, 'Das Ergebnis liegt im Bereich „Minibook“. Dorthin kann die App nicht springen.');
    assert.equal(told.schedule, 'Das Ergebnis liegt im Bereich „Zeitplan“. Dorthin kann die App nicht springen.');
});

test('a ziel outside Ideas ends in its space; a switched-off space is said calmly, not jumped to', () => {
    const s = scene();
    assert.equal(s.follower.follow({ space: 'sales' }), true);
    assert.deepEqual(s.calls, ['switch sales']);
    s.app.currentSpace = 'sales';
    s.advance(target.STEP_MS);
    assert.equal(s.follower.pending(), null, 'there: no bubble to enter');
    assert.deepEqual(s.calls, ['switch sales']);
    assert.equal(s.follower.follow({ space: 'marketing' }), false);
    assert.equal(s.follower.unreachable({ space: 'marketing' }), 'Das Ergebnis liegt im Bereich „Marketing“. Dorthin kann die App nicht springen.');
    assert.equal(s.follower.unreachable({ space: 'rowboat' }), '', 'Rowboat is roarboot in the app');
});
