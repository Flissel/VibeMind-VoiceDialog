// "At 1400 px Lernen, Events and Aufträge lie outside the window; the bar is 1764 px wide and does
// not scroll" (tour of all views, 2026-11-23). Every space must be reachable at any width.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const { arrowState, step, scrollFor, install } = require('./renderer/tab-scroll');

const STRIP = 1764;              // measured width of all 14 tabs
const AROUND = 32 + 130 + 12;    // padding of the nav, the agent name on the right, the gap
const ARROWS = 2 * 26 + 2 * 4;

function nav(windowWidth, tabs = 14) {
    const listeners = {};
    const make = (tag) => {
        const classes = new Set();
        const el = {
            tag, children: [], dataset: {}, disabled: false, parentNode: null, className: '',
            classList: { add: (c) => classes.add(c), remove: (c) => classes.delete(c), contains: (c) => classes.has(c),
                toggle: (c, on) => (on ? classes.add(c) : classes.delete(c)) },
            setAttribute() {}, addEventListener(type, fn) { (el.l = el.l || {})[type] = fn; },
            append(...k) { for (const c of k) { c.parentNode = el; el.children.push(c); } },
            insertBefore(k) { k.parentNode = el; el.children.push(k); },
            click() { el.l && el.l.click && el.l.click(); },
        };
        return el;
    };
    const width = STRIP / tabs;
    const strip = make('div');
    strip.offsetLeft = 0;
    strip.scrollLeft = 0;
    strip.scrollWidth = STRIP;
    strip.clientWidth = Math.min(STRIP, windowWidth - AROUND - (STRIP > windowWidth - AROUND ? ARROWS : 0));
    strip.scrollTo = ({ left }) => { strip.scrollLeft = Math.max(0, Math.min(left, strip.scrollWidth - strip.clientWidth)); };
    const all = [];
    for (let i = 0; i < tabs; i++) {
        const tab = make('button');
        tab.offsetLeft = Math.round(i * width);
        tab.offsetWidth = Math.round(width);
        all.push(tab);
    }
    strip.querySelector = () => all.find((t) => t.classList.contains('active')) || null;
    const parent = make('nav');
    parent.append(strip);
    const doc = { querySelector: (sel) => (sel === '.space-nav-tabs' ? strip : null), createElement: make };
    const win = { addEventListener(type, fn) { listeners[type] = fn; } };
    const ui = install(doc, win);
    const visible = (tab) => tab.offsetLeft >= strip.scrollLeft - 1 && tab.offsetLeft + tab.offsetWidth <= strip.scrollLeft + strip.clientWidth + 1;
    return { strip, tabs: all, ui, visible, resize: () => listeners.resize && listeners.resize() };
}

for (const width of [1280, 1400, 1920]) {
    test(`at ${width} px every space can be reached, the last ones too`, () => {
        const n = nav(width);
        const overflow = STRIP > width - AROUND;
        assert.equal(n.ui.frame.classList.contains('overflowing'), overflow);
        if (!overflow) {
            assert.ok(n.tabs.every(n.visible), 'all tabs fit');
            return;
        }
        assert.equal(n.ui.back.disabled, true, 'at the start nothing lies left');
        assert.equal(n.ui.forward.disabled, false);
        const last = n.tabs[n.tabs.length - 1];
        assert.equal(n.visible(last), false, 'Aufträge lies outside before');
        let clicks = 0;
        const seen = new Set();
        n.tabs.forEach((t, i) => { if (n.visible(t)) seen.add(i); });
        while (!n.ui.forward.disabled && clicks < 20) {
            n.ui.forward.click(); n.ui.update(); clicks += 1;
            n.tabs.forEach((t, i) => { if (n.visible(t)) seen.add(i); });
        }
        n.tabs.forEach((t, i) => { if (n.visible(t)) seen.add(i); });
        assert.ok(n.visible(last), 'the last tab after the arrows');
        // no tab is jumped over: each was fully on screen at some point
        for (let i = 0; i < n.tabs.length; i++) assert.ok(seen.has(i), `tab ${i} seen`);
        assert.equal(n.ui.back.disabled, false);
        assert.ok(clicks <= 3, `few clicks (${clicks})`);
    });
}

test('the active tab is scrolled into view, also when it is chosen by voice or a plan', () => {
    const n = nav(1280);
    const last = n.tabs[n.tabs.length - 1];
    last.classList.add('active');
    n.ui.showActive();
    assert.ok(n.visible(last));
    n.tabs[0].classList.add('active'); last.classList.remove('active');
    n.ui.showActive();
    assert.ok(n.visible(n.tabs[0]));
});

test('arrow numbers', () => {
    assert.deepEqual(arrowState(0, 2000, 1764), { overflow: false, back: false, forward: false });
    assert.deepEqual(arrowState(0, 1000, 1764), { overflow: true, back: false, forward: true });
    assert.deepEqual(arrowState(764, 1000, 1764), { overflow: true, back: true, forward: false });
    assert.equal(step(1000), 800);
    assert.equal(scrollFor(1600, 126, 0, 1000), 734);
    assert.equal(scrollFor(100, 126, 500, 1000), 92);
    assert.equal(scrollFor(600, 126, 500, 1000), 500);
});

test('the page loads it and the strip may shrink and scroll', () => {
    const html = fs.readFileSync(path.join(__dirname, 'renderer', 'index.html'), 'utf8');
    assert.match(html, /<script defer src="tab-scroll\.js"><\/script>/);
    const css = fs.readFileSync(path.join(__dirname, 'renderer', 'styles', 'space-nav.css'), 'utf8');
    assert.match(css, /\.space-tabs-frame \.space-nav-tabs \{[^}]*min-width: 0;[^}]*overflow-x: auto;/);
    assert.match(css, /\.space-tabs-frame \.space-tab \{[^}]*flex-shrink: 0;/);
});
