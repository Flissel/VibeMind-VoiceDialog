'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { contextFor, view, isQuestion } = require('./renderer/sentence-answer');
const { EXTERNAL_SPACES } = require('./external-spaces');
const { createTaskNavigator } = require('./task-navigation');

const html = fs.readFileSync(path.join(__dirname, 'renderer', 'index.html'), 'utf8');
const scene = fs.readFileSync(path.join(__dirname, 'renderer', 'multiverse.js'), 'utf8');

/** Every tab of the bar: the fixed ones of index.html and the external ones of the main process. */
const TABS = [...new Set([
    ...[...html.matchAll(/class="space-tab[^"]*"[^>]*data-space="([^"]+)"/g)].map((m) => m[1]),
    ...EXTERNAL_SPACES.map((space) => space.id),
])];

test('every tab names its own space with each sentence of the console', () => {
    for (const id of ['ideas', 'projects', 'desktop', 'roarboot', 'clawport', 'flowzen', 'video', 'orders', 'sales', 'marketing', 'learning', 'events']) {
        assert.ok(TABS.includes(id), `tab ${id} is in the bar`);
    }
    for (const id of TABS) {
        assert.deepEqual(contextFor(id), { space: id }, id);
    }
    // what the console sends: the space on screen (set on arrival for every tab, fixed or external)
    assert.match(scene, /const context = answers \? answers\.contextFor\(this\.currentSpace, ideas\) : ideas;/);
    assert.match(scene, /_arriveAtSpace\(targetSpace, space\) \{[\s\S]{0,200}this\.currentSpace = targetSpace;/);
    assert.match(fs.readFileSync(path.join(__dirname, 'renderer', 'external-spaces.js'), 'utf8'), /app\.navigateToSpace\(space\.id\)/,
        'an external tab goes the same way');
    // the module is loaded before the scene that uses it
    assert.ok(html.indexOf('src="sentence-answer.js"') > 0 && html.indexOf('src="sentence-answer.js"') < html.indexOf('src="multiverse.js"'));
});

test('in the Ideas overview the context of the Ideas chat goes along, still naming the space', () => {
    const ideas = { space: 'ideas', bubble: null, bubbles: [{ id: '00000000-0000-4000-8000-00000000000a', title: 'Bubble A' }] };
    assert.deepEqual(contextFor('ideas', ideas), ideas);
    assert.deepEqual(contextFor('ideas', { bubble: null }), { bubble: null, space: 'ideas' });
    assert.deepEqual(contextFor('desktop', ideas), { space: 'desktop' }, 'the Ideas context stays in Ideas');
    assert.equal(contextFor(''), undefined);
    assert.equal(contextFor(undefined), undefined);
    // the Ideas chat itself names its space
    assert.match(fs.readFileSync(path.join(__dirname, 'renderer', 'ideas-chat.js'), 'utf8'), /const context = \{ space: 'ideas', bubble: null \};/);
});

test('the Dashboard chat names its space too, and never carries the mark of the person', () => {
    const main = fs.readFileSync(path.join(__dirname, 'main.js'), 'utf8');
    assert.match(main, /\{ type: 'chat_text_input', text, context: \{ space: 'clawport' \} \}/);
});

test('not understood is a calm question back; an error shows the German sentence, never the raw one', () => {
    const notUnderstood = { success: true, verstanden: false, rueckfrage: true,
        message: 'Das habe ich nicht verstanden. Sag zum Beispiel: Öffne den Rechner.', fehler: 'NoCapabilityMatch' };
    assert.deepEqual(view(notUnderstood), { kind: 'rueckfrage', text: notUnderstood.message });
    assert.equal(view({ success: false, question: true, message: 'Welche Bubble meinst du?' }).kind, 'rueckfrage');
    assert.equal(view({ verstanden: false, final_text: 'Wie meinst du das genau?' }).text, 'Wie meinst du das genau?');
    assert.ok(isQuestion({ rueckfrage: true }) && !isQuestion({ success: false }));

    const failed = view({ success: false, ok: false, message: 'Das Werkzeug hat eine Angabe abgelehnt.', fehler: 'HTTP 400 {"code":"22P02"}' });
    assert.deepEqual(failed, { kind: 'fehler', text: 'Das Werkzeug hat eine Angabe abgelehnt.' });
    assert.deepEqual(view({ success: false, fehler: 'Traceback …' }), { kind: 'fehler', text: 'Keine Antwort.' }, 'fehler alone is never shown');
    assert.equal(view({ ok: false, message: 'Nichts Verwertbares.' }).kind, 'fehler');
    assert.equal(view(null).kind, 'fehler');
    assert.deepEqual(view({ success: true, message: 'Notiz angelegt.' }), { kind: 'antwort', text: 'Notiz angelegt.' });

    assert.match(scene, /shown\.kind === 'fehler' \? 'error' : shown\.kind === 'rueckfrage' \? 'rueckfrage' : 'agent'/);
    assert.doesNotMatch(scene, /`Error: \$\{err\.message\}`/, 'no raw error in the console');
    assert.match(fs.readFileSync(path.join(__dirname, 'renderer', 'styles', 'game-console.css'), 'utf8'), /\.gc-msg\.gc-rueckfrage \{/);
    assert.match(fs.readFileSync(path.join(__dirname, 'renderer', 'styles', 'ideas-chat.css'), 'utf8'), /\.ideas-chat-rueckfrage \{/);
});

test('a step without a usable answer (ok: false) ends the plan without ✓, and its reason is the German sentence', () => {
    const sent = [];
    const nav = createTaskNavigator((message) => sent.push(message));
    nav.handle('plan_started', { plan_id: 'p1', hops: [{}, {}], space: 'desktop' });
    nav.handle('hop_completed', { space: 'desktop', ok: false, final_text: 'Das Programm hat nicht geantwortet.', fehler: 'TimeoutError: 30s', error: 'TimeoutError: 30s' });
    nav.handle('hop_completed', { space: 'desktop', ok: true, result_preview: "'fertig'" });
    const end = nav.handle('plan_completed', { ok: true, elapsed_s: 1.5 });
    assert.equal(end.state, 'failed', 'no ✓ for a plan with a failed step');

    const sent2 = [];
    const nav2 = createTaskNavigator((message) => sent2.push(message));
    nav2.handle('plan_started', { plan_id: 'p2', hops: [{}], space: 'ideas' });
    const step = nav2.handle('hop_completed', { space: 'ideas', ok: false, final_text: 'Die Bubble gibt es nicht.', fehler: 'supabase_http_error 404' });
    assert.equal(step.error, 'Die Bubble gibt es nicht.');
    assert.equal(step.step_ok, false);
    const failedPlan = nav2.handle('plan_completed', { ok: false });
    assert.equal(failedPlan.state, 'failed');
    assert.ok(!JSON.stringify(sent2).includes('supabase_http_error'), 'the raw original never reaches the renderer');

    const sent3 = [];
    const nav3 = createTaskNavigator((message) => sent3.push(message));
    nav3.handle('plan_started', { plan_id: 'p3', hops: [{}], space: 'ideas' });
    nav3.handle('hop_completed', { space: 'ideas', ok: true, result_preview: "'Notiz angelegt'" });
    assert.equal(nav3.handle('plan_completed', { ok: true }).state, 'done', 'a plan whose steps all answered keeps its ✓');
});
