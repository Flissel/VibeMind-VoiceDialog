// "The enter button opened the bubble under the mouse instead of the selected one" (8 of 31
// openings, measured in the app 2026-11-23). Hovering replaced the pinned tooltip of the selected
// bubble and the button took the tooltip's bubble first.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const rule = require('./renderer/enter-target');

const A = '00000000-0000-4000-8000-00000000000a';
const B = '00000000-0000-4000-8000-00000000000b';

/** The multiverse with two bubbles, the real hover code (multiverse.js) and the real button (bubble-navigation.js). */
function world() {
    const elements = new Map();
    const element = (id) => {
        if (!elements.has(id)) {
            const classes = new Set(['hidden']);
            elements.set(id, {
                id, textContent: '', style: {}, onclick: null,
                classList: { add: (c) => classes.add(c), remove: (c) => classes.delete(c), contains: (c) => classes.has(c), toggle() {} },
                addEventListener() {}, removeEventListener() {}, appendChild() {}, querySelector: () => null, setAttribute() {},
            });
        }
        return elements.get(id);
    };
    const opened = [];
    let underMouse = null;
    const window = {
        vibemind: { enterBubble: (id) => opened.push(id), exitBubble() {} },
        addEventListener() {}, dispatchEvent: () => true,
    };
    const context = {
        window,
        document: { getElementById: element, querySelector: () => null, querySelectorAll: () => [], createElement: () => element('x' + Math.random()), body: { appendChild() {} } },
        console: { log() {}, warn() {}, error() {} },
        THREE: {
            Vector2: class {},
            Vector3: class { clone() { return this; } },
            Raycaster: class { setFromCamera() {} intersectObjects(list) { return underMouse ? [{ object: list.find((b) => b.userData.id === underMouse) }] : []; } },
        },
        CustomEvent: class {},
        setTimeout: () => 0, clearTimeout() {}, requestAnimationFrame: () => 0,
    };
    vm.createContext(context);
    vm.runInContext(fs.readFileSync(path.join(__dirname, 'renderer', 'enter-target.js'), 'utf8'), context);
    vm.runInContext(fs.readFileSync(path.join(__dirname, 'renderer', 'multiverse.js'), 'utf8'), context);
    const bubble = (id, title) => ({ userData: { type: 'bubble', id, title }, material: { emissive: { setHex() {} } }, getWorldPosition() {} });
    const app = Object.create(window.MultiverseApp.prototype);
    Object.assign(app, {
        currentSpace: 'ideas', isInsideBubble: false, camera: {},
        spaces: { ideas: { objects: [bubble(A, 'Bubble A'), bubble(B, 'Bubble B')] } },
        container: { getBoundingClientRect: () => ({ left: 0, top: 0, width: 100, height: 100 }) },
        hoveredBubbleIndex: -1, selectedBubbleIndex: -1, selectedBubbleId: null, tooltipPinned: false, tooltipBubbleId: null,
        worldToScreen: () => ({ x: 0, y: 0 }),
    });
    window.multiverseApp = app;
    element('space-view').classList.add('hidden');
    vm.runInContext(fs.readFileSync(path.join(__dirname, 'renderer', 'bubble-navigation.js'), 'utf8'), context);
    const button = element('enter-btn');
    return {
        app, button, opened,
        hover(id) { underMouse = id; app.onContainerMouseMove({ clientX: 1, clientY: 1 }); },
        select(id) { app.selectBubble(id === A ? 0 : 1); },
        click() { button.onclick(); },
    };
}

test('selected B, mouse over A: the button opens B and says so', () => {
    const w = world();
    w.hover(B);
    w.select(B);
    w.hover(A);                       // on the way to the button the mouse crosses A
    assert.equal(w.app.getTooltipBubbleId(), B, 'the pinned tooltip of B stays');
    assert.equal(w.button.textContent, '▶ Öffnen: Bubble B');
    w.click();
    assert.deepEqual(w.opened, [B]);
});

test('selected B, the mouse leaves the tooltip and crosses A: still B', () => {
    const w = world();
    w.select(B);
    w.app.tooltipPinned = false;      // info-panel mouseleave
    w.hover(A);
    w.hover(null);
    assert.equal(w.button.textContent, '▶ Öffnen: Bubble B');
    w.click();
    assert.deepEqual(w.opened, [B]);
});

// Decision: with nothing selected the button opens the bubble whose tooltip is shown. The button
// names it, so what it opens is visible before the click; switching the button off would make the
// quick way in (hover, click) a two-step one without making anything clearer.
test('nothing selected, mouse over A: the button opens A and names it', () => {
    const w = world();
    w.hover(A);
    assert.equal(w.button.textContent, '▶ Öffnen: Bubble A');
    w.app.tooltipPinned = true;       // the mouse reaches the tooltip (info-panel mouseenter)
    w.hover(B);                       // passing B on the way does not take the button over
    assert.equal(w.button.textContent, '▶ Öffnen: Bubble A');
    w.click();
    assert.deepEqual(w.opened, [A]);
});

test('a selection left over from an earlier entry does not count', () => {
    const w = world();
    w.select(B);
    w.app.selectedBubbleIndex = -1;   // enterSpace resets the index, the id stays behind
    w.app.tooltipPinned = false;
    w.hover(A);
    w.click();
    assert.deepEqual(w.opened, [A]);
});

test('the Enter key is unchanged: it opens the selection', () => {
    const w = world();
    w.select(B);
    w.hover(A);
    w.app.enterCurrentSelection();
    assert.deepEqual(w.opened, [B]);
    const source = fs.readFileSync(path.join(__dirname, 'renderer', 'multiverse.js'), 'utf8');
    const body = /enterCurrentSelection\(\) \{([\s\S]*?)\n    \}/.exec(source)[1];
    assert.doesNotMatch(body, /tooltip/i, 'the key never looks at the tooltip');
});

test('rule: selected first, tooltip only without selection, nothing without either', () => {
    assert.equal(rule.target({ selectedIndex: 1, selectedId: B, tooltipId: A }), B);
    assert.equal(rule.target({ selectedIndex: -1, selectedId: B, tooltipId: A }), A);
    assert.equal(rule.target({ selectedIndex: -1, selectedId: null, tooltipId: null }), null);
    assert.equal(rule.hoverMayReplace({ selectedIndex: 0, pinned: false }), false);
    assert.equal(rule.hoverMayReplace({ selectedIndex: -1, pinned: true }), false);
    assert.equal(rule.hoverMayReplace({ selectedIndex: -1, pinned: false }), true);
    assert.equal(rule.label(''), '▶ Öffnen: Bubble');
});
