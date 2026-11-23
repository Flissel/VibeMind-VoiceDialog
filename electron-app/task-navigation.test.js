const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const { SPACE_TO_APP, appKeyForSpace, parseSse, resultText, createTaskNavigator } = require('./task-navigation');
const { decide, describe, labelFor, shows, shorten, BUSY_MS, KEEP_MS, WAITING_TEXT } = require('./renderer/task-navigate');

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

test('one navigation per plan and space: a plan is followed into each space once', () => {
    const sent = [];
    const navigator = createTaskNavigator((m) => sent.push(m));
    const jumps = () => sent.filter((m) => m.type === 'task_navigate');

    navigator.handle('plan_started', { plan_id: 'p1' });
    navigator.handle('hop_started', { space: null, capability: 'chitchat' });          // general step
    navigator.handle('hop_started', { space: 'n8n', capability: 'n8n_list' });             // no place yet
    assert.deepEqual(sent.map((m) => m.state), ['reset'], 'a new plan only clears what the one before ended with');
    navigator.handle('hop_started', { space: 'coding', capability: 'code_generate', description: 'App bauen' });
    navigator.handle('hop_started', { space: 'coding', capability: 'code_status' });   // same space: no second jump
    navigator.handle('hop_started', { space: 'video', capability: 'video_status' });   // the plan moves on
    navigator.handle('hop_started', { space: 'coding', capability: 'code_status' });   // and back: not followed again
    navigator.handle('hop_completed', { space: 'video' });

    assert.deepEqual(jumps().map((m) => m.space), ['projects', 'video']);
    assert.deepEqual(jumps()[0], {
        type: 'task_navigate', space: 'projects', registry_space: 'coding',
        capability: 'code_generate', description: 'App bauen',
    });

    navigator.handle('plan_started', { plan_id: 'p2' });
    navigator.handle('hop_started', { space: 'video', capability: 'video_status' });
    assert.deepEqual(jumps().map((m) => m.space), ['projects', 'video', 'video']);
});

test('Sales and software design have a place in the app', () => {
    assert.equal(appKeyForSpace('sales'), 'sales');
    assert.equal(appKeyForSpace('swe-design'), 'swedesign');
});

test('a plan reports where it stands and how it ended', () => {
    const sent = [];
    const navigator = createTaskNavigator((m) => sent.push(m));
    const states = () => sent.filter((m) => m.type === 'task_status' && m.state !== 'reset');

    navigator.handle('plan_started', { plan_id: 'p7', hops: [{}, {}] });
    navigator.handle('hop_started', { space: 'sales', capability: 'sales_draft', description: 'Angebot entwerfen' });
    assert.deepEqual(states()[0], {
        type: 'task_status', state: 'running', plan_id: 'p7', space: 'sales', registry_space: 'sales',
        step: 'Angebot entwerfen', done: 0, total: 2, result: '', error: '', stage: '',
        stage_nr: null, stage_total: null, stage_label: '', result_ref: '',
    });

    navigator.handle('hop_completed', {
        space: 'sales', description: 'Angebot entwerfen', ok: true,
        result_preview: "{'ok': True, 'message': 'Entwurf A-17 angelegt'}",
    });
    assert.equal(states()[1].done, 1);
    assert.equal(states()[1].result, 'Entwurf A-17 angelegt');
    assert.equal(states()[1].step_ok, true);

    navigator.handle('hop_completed', { space: null, ok: true, result_preview: "'Zusammenfassung'" }); // general step
    navigator.handle('plan_completed', { plan_id: 'p7', ok: true, elapsed_s: 6.4 });
    const end = states().at(-1);
    assert.equal(end.state, 'done');
    assert.equal(end.space, 'sales', 'the last step with a place in the app');
    assert.equal(end.result, 'Entwurf A-17 angelegt');
    assert.equal(end.elapsed_s, 6.4);
    assert.equal(end.done, 2);
});

test('a failed step and a failed plan are reported as failed, with the reason', () => {
    const sent = [];
    const navigator = createTaskNavigator((m) => sent.push(m));

    navigator.handle('plan_started', { plan_id: 'p8', hops: [{}] });
    navigator.handle('hop_started', { space: 'desktop', description: 'Chrome öffnen' });
    navigator.handle('hop_completed', { space: 'desktop', ok: false, error: 'Dienst nicht erreichbar', result_preview: 'None' });
    navigator.handle('plan_completed', { plan_id: 'p8', ok: false, elapsed_s: 1.2 });

    const end = sent.at(-1);
    assert.equal(end.state, 'failed');
    assert.equal(end.error, 'Dienst nicht erreichbar');
    assert.equal(end.result, '');
});

test('a plan without a place in the app reports nothing', () => {
    const sent = [];
    const navigator = createTaskNavigator((m) => sent.push(m));

    navigator.handle('plan_started', { plan_id: 'p9' });
    navigator.handle('hop_started', { space: null });
    navigator.handle('hop_completed', { space: null, ok: true });
    navigator.handle('plan_completed', { plan_id: 'p9', ok: true });

    assert.deepEqual(sent, [{ type: 'task_status', state: 'reset', plan_id: 'p9' }]);
});

test('resultText makes a short line out of a Python repr', () => {
    assert.equal(resultText("{'success': True, 'message': 'Bubble \"Marketing\" erstellt'}"), 'Bubble "Marketing" erstellt');
    assert.equal(resultText("'nur ein Satz'"), 'nur ein Satz');
    assert.equal(resultText("'1 bubbles:\\n- Marketing (score=0)'"), '1 bubbles: - Marketing (score=0)', 'no backslash-n in the line (seen in the app on 2026-11-23)');
    assert.equal(resultText("'2 bubbles:\\n- Marketing (id=fa8d4158-f721-4290-a0cf-7f20da754372, score=0)\\n- Vertrieb (id=0b1c2d3e-0000-4000-8000-123456789abc, score=3)'"),
        '2 bubbles: - Marketing - Vertrieb', 'identifiers of rows are not shown');
    assert.equal(resultText("'Karte fa8d4158-f721-4290-a0cf-7f20da754372 angelegt'"), 'Karte angelegt');
    assert.equal(resultText('None'), '');
    assert.equal(resultText(undefined), '');
    assert.equal(resultText('x'.repeat(600)).length, 240);
});

test('the status line names space, step and result', () => {
    const running = describe({ state: 'running', step: 'Angebot entwerfen', done: 0, total: 2 }, 'Sales', false);
    assert.equal(running.text, '● Sales: Angebot entwerfen (1/2)');
    assert.equal(running.state, 'running');

    const away = describe({ state: 'running', step: 'Angebot entwerfen', done: 1, total: 2 }, 'Sales', true);
    assert.equal(away.text, '● Sales: Angebot entwerfen (2/2) →', 'the arrow says: click to go there');

    const done = describe({ state: 'done', done: 2, total: 2, result: 'Entwurf A-17 angelegt', elapsed_s: 6.4 }, 'Sales', false);
    assert.equal(done.text, '✓ Sales: fertig in 6,4 s — Entwurf A-17 angelegt');

    const failed = describe({ state: 'failed', error: 'Dienst nicht erreichbar' }, 'Desktop', false);
    assert.equal(failed.text, '✕ Desktop: fehlgeschlagen — Dienst nicht erreichbar');
});

test('external spaces take their name from the scene', () => {
    assert.equal(labelFor('swedesign', {}), 'SWE Design');
    assert.equal(labelFor('sales', { sales: { name: 'Sales' } }), 'Sales');
    assert.equal(labelFor('unbekannt', {}), 'unbekannt');
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
    assert.match(html, /case 'task_status':/);
    assert.match(html, /window\.VibeTaskNav\.handle\(message\)/);
});

test('every arrival moves the tabs, and a change of space does not wait for animation frames', () => {
    const scene = fs.readFileSync(path.join(__dirname, 'renderer', 'multiverse.js'), 'utf8');
    const navigator = fs.readFileSync(path.join(__dirname, 'renderer', 'space-navigator.js'), 'utf8');

    const arrive = scene.slice(scene.indexOf('_arriveAtSpace(targetSpace, space) {'), scene.indexOf('animateCameraTo(targetPosition'));
    assert.match(arrive, /spaceNavigator\.syncSpace\(targetSpace\)/);
    assert.match(arrive, /vibemind:space-arrived/);

    const move = scene.slice(scene.indexOf('animateCameraTo(targetPosition'), scene.indexOf('initGameConsole() {'));
    assert.match(move, /this\._cameraStep\(updateCamera\)/);
    assert.doesNotMatch(move, /requestAnimationFrame\(updateCamera\)/);

    assert.match(navigator, /syncSpace: syncSpace/);
    assert.match(navigator, /if \(app && app\.isNavigating\) \{\s*wanted = spaceId;/, 'a click during a move is kept, not dropped');
    const sync = navigator.slice(navigator.indexOf('function syncSpace'), navigator.indexOf('function updateAgentDisplay'));
    assert.doesNotMatch(sync, /hideFlowzen\(|showFlowzen\(/, 'syncSpace runs after the page of the space was shown and must not hide it');
});

test('stage and result pointer are passed on and shown once the Brain sends them', () => {
    const sent = [];
    const navigator = createTaskNavigator((m) => sent.push(m));

    navigator.handle('plan_started', { plan_id: 'p10', hops: [{}] });
    navigator.handle('hop_started', { space: 'swedesign', description: 'Anforderungen sammeln', stage: 'Requirements' });
    assert.equal(sent.at(-1).stage, 'Requirements');
    navigator.handle('hop_completed', { space: 'swedesign', ok: true, stage: 'Requirements', result_ref: 'shuttle:42', result_preview: "'12 Anforderungen'" });
    assert.equal(sent.at(-1).result_ref, 'shuttle:42');

    const line = describe({ state: 'running', stage: 'Requirements', step: 'Anforderungen sammeln', done: 0, total: 1 }, 'SWE Design', false);
    assert.equal(line.text, '● SWE Design: Requirements · Anforderungen sammeln');
    navigator.handle('hop_started', { space: 'swedesign', description: 'x', stage: 'requirements', stage_nr: 3, stage_total: 6, stage_label: 'Requirements' });
    assert.equal(sent.at(-1).stage_nr, 3);
    const short = describe(sent.at(-1), 'SWE Design', false);
    assert.equal(short.text, '\u25CF SWE Design: Stufe 3 von 6, Requirements');
    const done = describe({ state: 'done', result: '12 Anforderungen', result_ref: 'shuttle:42' }, 'SWE Design', false);
    assert.equal(done.title, '12 Anforderungen\nshuttle:42');
});
test('a finished task is named only in its own space; a running one everywhere', () => {
    assert.equal(shows({ state: 'running', space: 'sales' }, 'ideas'), 'line');
    assert.equal(shows({ state: 'failed', space: 'ideas' }, 'ideas'), 'line');
    assert.equal(shows({ state: 'failed', space: 'ideas' }, 'sales'), 'dot', 'an old error of another space is not shown here');
    assert.equal(shows({ state: 'done', space: 'ideas' }, 'desktop'), 'dot');
    assert.equal(shows(null, 'ideas'), 'none');
    assert.ok(KEEP_MS <= 30000, 'a finished task does not stay for long');
});

test('a new sentence and a new plan clear what an earlier task ended with', () => {
    const page = fs.readFileSync(path.join(__dirname, 'renderer', 'task-navigate.js'), 'utf8');
    const scene = fs.readFileSync(path.join(__dirname, 'renderer', 'multiverse.js'), 'utf8');
    const chat = fs.readFileSync(path.join(__dirname, 'renderer', 'ideas-chat.js'), 'utf8');

    assert.match(page, /addEventListener\('vibemind:sentence-sent', \(\) => \{[^}]*fresh\(\);/);
    assert.match(page, /message\.state === 'reset'\) \{ fresh\(\); return 'reset'; \}/);
    assert.match(scene, /CustomEvent\('vibemind:sentence-sent'\)/);
    assert.match(chat, /CustomEvent\('vibemind:sentence-sent'\)/);
});

test('a finished task shows the answer to the sentence, not the raw result of its last step', () => {
    const page = fs.readFileSync(path.join(__dirname, 'renderer', 'task-navigate.js'), 'utf8');
    const scene = fs.readFileSync(path.join(__dirname, 'renderer', 'multiverse.js'), 'utf8');
    const chat = fs.readFileSync(path.join(__dirname, 'renderer', 'ideas-chat.js'), 'utf8');

    assert.match(page, /if \(message\.state === 'done' && answer\) message = \{ \.\.\.message, result: answer \};/, 'the answer came first');
    assert.match(page, /if \(answer && current && current\.state === 'done'\) \{\s*current\.result = answer;/, 'the end of the plan came first');
    assert.match(scene, /CustomEvent\('vibemind:sentence-answered'/);
    assert.match(chat, /CustomEvent\('vibemind:sentence-answered'/);

    assert.equal(shorten(' 15 Bubbles:\n„A“, „B“ \t(und 13 weitere). '), '15 Bubbles: „A“, „B“ (und 13 weitere).');
    assert.equal(shorten('x'.repeat(500)).length, 240);
    assert.equal(shorten(undefined), '');
});

test('a plan that names its space at the start is followed at once', () => {
    const sent = [];
    const navigator = createTaskNavigator((m) => sent.push(m));

    navigator.handle('plan_started', { plan_id: 'p11', space: 'sales', intent: 'Entwirf eine Mail', hops: [{}, {}] });
    assert.deepEqual(sent.map((m) => m.type + ':' + (m.state || m.space)), ['task_status:reset', 'task_navigate:sales', 'task_status:running']);
    assert.equal(sent[2].space, 'sales');
    assert.equal(sent[2].step, '', 'no step yet');
    assert.equal(sent[2].total, 2);

    navigator.handle('hop_started', { space: 'sales', description: 'Kontakt suchen' });
    assert.equal(sent.filter((m) => m.type === 'task_navigate').length, 1, 'the first step in the same space does not jump again');
    assert.equal(sent.at(-1).step, 'Kontakt suchen');

    navigator.handle('plan_started', { plan_id: 'p12', space: 'gibt-es-nicht' });
    assert.equal(sent.at(-1).state, 'reset', 'an unknown space: wait for the steps as before');
});

test('a neutral line stands in the title bar from the moment a sentence is sent', () => {
    const page = fs.readFileSync(path.join(__dirname, 'renderer', 'task-navigate.js'), 'utf8');

    assert.equal(WAITING_TEXT, '\u25CF arbeitet \u2026');
    assert.match(page, /if \(!current\) \{\s*current = \{ state: 'running', space: '', waiting: true \};/, 'only when nothing is running already');
    assert.match(page, /if \(current && current\.waiting\) clear\(\);/, 'an answer without a plan removes it');
    assert.match(page, /if \(current && current\.waiting\) \{\s*el\.textContent = WAITING_TEXT;/);
});
