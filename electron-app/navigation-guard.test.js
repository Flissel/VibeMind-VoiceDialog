const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const { guardFlag, STUCK_MS } = require('./renderer/navigation-guard');

/** Timers by hand: run(ms) moves the clock. */
function clock() {
    let now = 0;
    let next = 1;
    const pending = new Map();
    return {
        timers: {
            setTimeout(fn, ms) { const id = next++; pending.set(id, { at: now + ms, fn }); return id; },
            clearTimeout(id) { pending.delete(id); },
        },
        run(ms) {
            now += ms;
            for (const [id, timer] of [...pending]) if (timer.at <= now) { pending.delete(id); timer.fn(); }
        },
        waiting: () => pending.size,
    };
}

test('a flag that is cleared in time is left alone', () => {
    const time = clock();
    const scene = { isNavigating: false };
    const stuck = [];
    guardFlag(scene, 'isNavigating', { ms: 6000, timers: time.timers, onStuck: (info) => stuck.push(info) });

    scene.isNavigating = true;
    assert.equal(scene.isNavigating, true);
    time.run(1500);
    scene.isNavigating = false;
    time.run(10000);

    assert.equal(scene.isNavigating, false);
    assert.deepEqual(stuck, []);
    assert.equal(time.waiting(), 0, 'no timer is left behind');
});

test('a flag that stays set clears itself and reports it', () => {
    const time = clock();
    const scene = { isNavigating: false };
    const stuck = [];
    guardFlag(scene, 'isNavigating', { ms: 6000, timers: time.timers, onStuck: (info) => stuck.push(info) });

    scene.isNavigating = true;
    time.run(5999);
    assert.equal(scene.isNavigating, true);
    time.run(1);

    assert.equal(scene.isNavigating, false, 'the navigation is free again');
    assert.deepEqual(stuck, [{ flag: 'isNavigating', afterMs: 6000 }]);

    scene.isNavigating = true;      // and it guards the next move as well
    time.run(6000);
    assert.equal(stuck.length, 2);
});

test('setting the flag again while it is set does not keep it alive', () => {
    const time = clock();
    const page = { isEnteringBubble: false };
    const stuck = [];
    guardFlag(page, 'isEnteringBubble', { ms: 6000, timers: time.timers, onStuck: (info) => stuck.push(info) });

    page.isEnteringBubble = true;
    time.run(4000);
    page.isEnteringBubble = true;
    time.run(2000);

    assert.equal(page.isEnteringBubble, false);
    assert.equal(stuck.length, 1);
});

test('the limit is far above the longest regular move', () => {
    assert.ok(STUCK_MS >= 4000, 'a change of space takes 1.5 s, its own failsafe 3 s');
});

test('scene and bubble entry are guarded, and the guard is loaded before the scene', () => {
    const read = (...parts) => fs.readFileSync(path.join(__dirname, ...parts), 'utf8');
    const html = read('renderer', 'index.html');
    const scene = read('renderer', 'multiverse.js');
    const bubble = read('renderer', 'bubble-navigation.js');

    assert.ok(html.indexOf('src="navigation-guard.js"') > -1);
    assert.ok(html.indexOf('src="navigation-guard.js"') < html.indexOf('src="multiverse.js"'));
    assert.match(scene, /guardFlag\(this, 'isNavigating', \{ onStuck: \(info\) => this\._navigationStuck\(info\) \}\)/);
    assert.match(scene, /vibemind:navigation-stuck/);
    assert.match(bubble, /guardFlag\(window, 'isEnteringBubble'/);
});

test('a move nobody can see ends at its next step', () => {
    const scene = fs.readFileSync(path.join(__dirname, 'renderer', 'multiverse.js'), 'utf8');

    assert.match(scene, /_moveDuration\(ms\) \{\s*return document\.visibilityState === 'hidden' \? 1 : ms;/);
    assert.match(scene, /const duration = this\._moveDuration\(1500\);/, 'change of space');
    assert.match(scene, /const duration = this\._moveDuration\(800\);/, 'entering a bubble');
    assert.match(scene, /const duration = this\._moveDuration\(600\);/, 'leaving a bubble');
});
