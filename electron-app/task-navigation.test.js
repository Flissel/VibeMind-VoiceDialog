const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const { SPACE_TO_APP, appKeyForSpace, parseSse, createTaskNavigator } = require('./task-navigation');
const { decide, BUSY_MS } = require('./renderer/task-navigate');

test('registry spaces map to the keys of the app scene', () => {
    assert.equal(appKeyForSpace('coding'), 'projects');
    assert.equal(appKeyForSpace('rowboat'), 'roarboot');
    assert.equal(appKeyForSpace('bubbles'), 'ideas');
    assert.equal(appKeyForSpace(' Video '), 'video');
    assert.equal(appKeyForSpace('schedule'), 'orders', 'shown on the page Auftraege');
    assert.equal(appKeyForSpace('n8n'), null, 'no place in the app yet');
    assert.equal(appKeyForSpace('gibt-es-nicht'), null);
    assert.equal(appKeyForSpace(null), null);
});

test('every app key in the map exists in the scene', () => {
    const scene = fs.readFileSync(path.join(__dirname, 'renderer', 'multiverse.js'), 'utf8');
    const external = require('./external-spaces').EXTERNAL_SPACES.map((s) => s.id); // added at runtime
    for (const key of new Set(Object.values(SPACE_TO_APP).filter(Boolean))) {
        if (external.includes(key)) continue;
        assert.match(scene, new RegExp(`\\b${key}: \\{`), `scene has no space "${key}"`);
    }
});

test('parseSse reads complete events and keeps the unfinished tail', () => {
    const text = ':connected\n\nevent: plan_started\ndata: {"plan_id":"p1"}\n\n'
        + 'event: hop_started\ndata: {"space":"video","capability":"video_status"}\n\n'
        + ':keepalive\n\nevent: hop_comp';
    const { events, rest } = parseSse(text);

    assert.deepEqual(events.map((e) => e.kind), ['plan_started', 'hop_started']);
    assert.equal(events[1].payload.space, 'video');
    assert.equal(rest, 'event: hop_comp');
});

test('parseSse survives a broken event', () => {
    const { events } = parseSse('event: hop_started\ndata: {kaputt\n\nevent: hop_started\ndata: {"space":"ideas"}\n\n');

    assert.equal(events.length, 1);
    assert.equal(events[0].payload.space, 'ideas');
});

test('one navigation per plan: the first step with a place in the app decides', () => {
    const sent = [];
    const navigator = createTaskNavigator((m) => sent.push(m));

    navigator.handle('plan_started', { plan_id: 'p1' });
    navigator.handle('hop_started', { space: null, capability: 'chitchat' });          // general step
    navigator.handle('hop_started', { space: 'n8n', capability: 'n8n_list' });             // no place yet
    navigator.handle('hop_started', { space: 'coding', capability: 'code_generate', description: 'App bauen' });
    navigator.handle('hop_started', { space: 'video', capability: 'video_status' });   // same plan: no second jump
    navigator.handle('hop_completed', { space: 'video' });

    assert.equal(sent.length, 1);
    assert.deepEqual(sent[0], {
        type: 'task_navigate', space: 'projects', registry_space: 'coding',
        capability: 'code_generate', description: 'App bauen',
    });

    navigator.handle('plan_started', { plan_id: 'p2' });
    navigator.handle('hop_started', { space: 'video', capability: 'video_status' });
    assert.equal(sent.length, 2);
    assert.equal(sent[1].space, 'video');
});

test('the renderer follows a task, but not while the user is busy', () => {
    const base = { space: 'video', currentSpace: 'ideas', knownSpaces: ['ideas', 'video'], now: 100000, insideBubble: false };

    assert.equal(decide({ ...base, lastInputAt: 0 }), 'navigate');
    assert.equal(decide({ ...base, lastInputAt: 100000 - BUSY_MS + 1 }), 'note', 'input a moment ago');
    assert.equal(decide({ ...base, lastInputAt: 100000 - BUSY_MS }), 'navigate');
    assert.equal(decide({ ...base, lastInputAt: 0, insideBubble: true }), 'note', 'an open bubble is not left');
    assert.equal(decide({ ...base, lastInputAt: 0, currentSpace: 'video' }), 'ignore', 'already there');
    assert.equal(decide({ ...base, lastInputAt: 0, space: 'unbekannt' }), 'ignore');
});

test('main process and page are wired to task navigation', () => {
    const main = fs.readFileSync(path.join(__dirname, 'main.js'), 'utf8');
    const html = fs.readFileSync(path.join(__dirname, 'renderer', 'index.html'), 'utf8');

    assert.match(main, /require\('\.\/task-navigation'\)/);
    assert.match(main, /initTaskNavigation\(mainWindow\)/);
    assert.ok(html.indexOf('src="task-navigate.js"') > -1);
    assert.match(html, /case 'task_navigate':/);
    assert.match(html, /window\.VibeTaskNav\.handle\(message\)/);
});
