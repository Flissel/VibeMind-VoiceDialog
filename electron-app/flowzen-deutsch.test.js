// Lauf 39: the Flowzen diary still spoke English ("What should I do next?", "No journal entries yet...").
// The page now speaks German; moods and states sent by Flowzen in English get German names.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const page = fs.readFileSync(path.join(__dirname, 'flowzen-diary.html'), 'utf8');
const script = [...page.matchAll(/<script[^>]*>([\s\S]*?)<\/script>/g)].map((m) => m[1]).join('\n');

test('no English text is left on the diary page', () => {
  assert.match(page, /<html lang="de">/);
  for (const english of ['Journal', 'What should I do next', 'Thinking...', 'I did this', "'\\u2713 Accepted'", "'\\u2192 Skip'",
    'No journal entries', 'Press the button', "' of '", 'On request', 'Every 30 min', ' Energy ', ' activities ',
    '>Time<', '>Mood<', '>Category<', '>idle<', "'Early Morning'", "'Afternoon'", "'Evening'", "'Night'"]) {
    assert.ok(!page.includes(english), `still English: ${english}`);
  }
});

test('the German texts are there, with umlauts', () => {
  for (const german of ['Blue Rose — Tagebuch', '>Zeit<', '>Stimmung<', '>Kategorie<', 'Was soll ich als Nächstes tun?',
    'Denke nach …', "'\\u2713 Erledigt'", "'\\u2713 Angenommen'", "'\\u2192 Überspringen'", 'Noch keine Tagebucheinträge …',
    'Drück den Knopf oben, um den ersten Eintrag anzulegen', "' von '", 'Auf Wunsch', 'Alle 30 Minuten', ' Energie ', ' Aktivitäten ',
    "'Früher Morgen'", "'Nachmittag'"]) {
    assert.ok(page.includes(german), `missing: ${german}`);
  }
  assert.doesNotMatch(page, /Naechst|Eintraege|Aktivitaet|Ueberspring|Frueh|Drueck|muede/);
});

test('moods and states from Flowzen are shown in German; unknown ones as sent', () => {
  const start = script.indexOf('var WINDOW_NAMES');
  const end = script.indexOf('// Helper: escape HTML');
  assert.ok(start >= 0 && end > start);
  const sandbox = {};
  vm.runInNewContext(script.slice(start, end) + '\nthis.out = { moodName: moodName, STATE_NAMES: STATE_NAMES };', sandbox);
  const { moodName, STATE_NAMES } = sandbox.out;
  assert.equal(moodName('tired'), 'müde');
  assert.equal(moodName('focused'), 'fokussiert');
  assert.equal(moodName('elated'), 'elated');
  assert.equal(moodName(undefined), '');
  assert.equal(STATE_NAMES.idle, 'ruhig');
  assert.match(script, /moodEl\.textContent = moodName\(data\.mood\)/);
  assert.match(script, /badge\.textContent = STATE_NAMES\[data\.state\] \|\| data\.state; badge\.className = 'state-badge ' \+ data\.state;/);
  assert.match(script, /moodName\(entry\.mood\) \+ ' \\u00B7 Energie '/);
});

test('the Flowzen panel in the main window speaks the same German', () => {
  const read = (...p) => fs.readFileSync(path.join(__dirname, ...p), 'utf8');
  const html = read('renderer', 'index.html');
  const panelHtml = html.slice(html.indexOf('<div id="flowzen-panel"'), html.indexOf('<!-- Roarboot Space is now rendered'));
  for (const english of ['Journal', '>Time<', '>Mood<', '>Category<', '>idle<', 'What should I do next', 'No entries yet']) {
    assert.ok(!panelHtml.includes(english), `panel still English: ${english}`);
  }
  for (const german of ['Blue Rose — Tagebuch', '>Zeit<', '>Stimmung<', '>Kategorie<', '>ruhig<', 'Was soll ich als Nächstes tun?', 'Noch keine Tagebucheinträge …']) {
    assert.ok(panelHtml.includes(german), `panel missing: ${german}`);
  }
  for (const file of [['renderer', 'index.html'], ['renderer', 'handlers', 'dashboard-handlers.js']]) {
    assert.doesNotMatch(read(...file), /Was soll ich machen\?/, file.join('/'));
  }

  const panel = read('renderer', 'flowzen-panel.js');
  for (const english of ['Thinking...', "'Early Morning'", 'Frueh', ' energy ', ' activities', 'On request']) {
    assert.ok(!panel.includes(english), `panel script still English: ${english}`);
  }
  const els = {};
  const document = { getElementById: (id) => (els[id] = els[id] || { id, textContent: '', className: '', classList: { add() {}, remove() {} }, addEventListener() {} }) };
  const window = { vibemind: { blueRoseRecommend: () => new Promise(() => {}) } };
  vm.runInNewContext(panel, { window, document });
  window.flowzenPanel.updateFlowzenPanel({ current_time_window: 'early_morning', mood: 'tired', category: 'Testkategorie', state: 'idle' });
  assert.equal(els['fz-time-window'].textContent, 'Früher Morgen');
  assert.equal(els['fz-mood'].textContent, 'müde');
  assert.equal(els['flowzen-state-badge'].textContent, 'ruhig');
  assert.equal(els['flowzen-state-badge'].className, 'flowzen-state idle');
  window.flowzenPanel.requestFlowzenRecommend();
  assert.equal(els['fz-recommend-btn'].textContent, 'Denke nach …');
});
