const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const { brainBase, listPlan, summarize, readOrders } = require('./orders-data');

test('the brain is asked on this machine, on the port the app already uses', () => {
    assert.equal(brainBase({}), 'http://127.0.0.1:5000');
    assert.equal(brainBase({ BRAIN_PORT: '5001' }), 'http://127.0.0.1:5001');
    assert.equal(brainBase({ BRAIN_PORT: 'x' }), 'http://127.0.0.1:5000');
});

test('the plan for the schedule is one reading step', () => {
    const plan = listPlan('schedule_list', 'abc');
    assert.equal(plan.plan_id, 'auftraege-abc');
    assert.deepEqual(plan.hops.map((hop) => hop.capability), ['schedule_list']);
});

test('answers become three sections that say what is there and what is not', () => {
    const view = summarize({
        schedule: { ok: true, executed: { s1: { ok: true, result: { success: true, count: 2, tasks: [
            { id: 't1', title: 'Rechnung schreiben', next_run: '2026-11-23T09:00:00Z' },
            { name: 'Ohne Zeit' },
        ] } } } },
        minibook: { online: false, notifications: [], recent_posts: [] },
        research: { ok: true, components: { openfang: { ok: true }, qdrant: { ok: true } } },
    });

    assert.deepEqual(view.sections.map((s) => [s.id, s.state]), [['schedule', 'ok'], ['research', 'ok'], ['minibook', 'aus']]);
    assert.deepEqual(view.sections[0].items, [
        { title: 'Rechnung schreiben', detail: '2026-11-23T09:00:00Z' },
        { title: 'Ohne Zeit', detail: '' },
    ]);
    assert.match(view.sections[2].text, /nicht erreichbar/);
});

test('an empty schedule is "leer", a failed step is "fehler", and nothing is invented', () => {
    const empty = summarize({ schedule: { executed: { s1: { ok: true, result: { tasks: [], count: 0 } } } }, minibook: null, research: null });
    assert.deepEqual(empty.sections.map((s) => s.state), ['leer', 'fehler', 'fehler']);
    assert.deepEqual(empty.sections[0].items, []);

    const failed = summarize({ schedule: { executed: { s1: { ok: false, error: 'RuntimeError: x\n  File "/app/secret.py"' } } }, minibook: { online: true, recent_posts: [{ title: 'Hallo', author: 'a' }] }, research: { ok: false, components: { qdrant: { ok: false }, openfang: { ok: true } } } });
    assert.equal(failed.sections[0].state, 'fehler');
    assert.equal(failed.sections[0].text, 'Die Terminliste konnte nicht gelesen werden (RuntimeError).', 'only the kind of error, no detail');
    assert.equal(failed.sections[1].state, 'fehler');
    assert.match(failed.sections[1].text, /qdrant/);
    assert.deepEqual(failed.sections[2].items, [{ title: 'Hallo', detail: 'a' }]);
});

test('reading asks the brain three times and survives each of them failing', async () => {
    const asked = [];
    const view = await readOrders({
        base: 'http://127.0.0.1:5000',
        id: () => 'x1',
        fetchJson: async (url, options) => {
            asked.push(`${options && options.method || 'GET'} ${url}`);
            if (url.endsWith('/api/research/health')) throw new Error('weg');
            if (url.endsWith('/api/minibook/activity')) return { online: false };
            return { executed: { s1: { ok: true, result: { tasks: [] } } } };
        },
    });

    assert.deepEqual(asked.sort(), [
        'GET http://127.0.0.1:5000/api/minibook/activity',
        'GET http://127.0.0.1:5000/api/research/health',
        'POST http://127.0.0.1:5000/api/multihop/execute',
    ]);
    assert.deepEqual(view.sections.map((s) => s.state), ['leer', 'fehler', 'aus']);
});

test('the entry is a local page with its own narrow bridge, and tasks of these spaces lead to it', () => {
    const { EXTERNAL_SPACES, resolveSpaces, describeForRenderer } = require('./external-spaces');
    const { appKeyForSpace } = require('./task-navigation');
    const entry = EXTERNAL_SPACES.find((space) => space.id === 'orders');

    assert.equal(entry.label, 'Aufträge');
    const resolved = resolveSpaces({}).find((space) => space.id === 'orders');
    assert.ok(fs.existsSync(resolved.file), 'the page exists');
    assert.equal(resolved.url, '');
    assert.equal(describeForRenderer({}).find((space) => space.id === 'orders').configured, true);
    for (const space of ['schedule', 'research', 'minibook']) assert.equal(appKeyForSpace(space), 'orders', space);

    const page = fs.readFileSync(resolved.file, 'utf8');
    assert.match(page, /Content-Security-Policy/);
    assert.doesNotMatch(page, /https?:\/\/(?!www\.w3\.org)/, 'the page loads nothing from the network');
    const preload = fs.readFileSync(path.join(__dirname, 'auftraege-preload.js'), 'utf8');
    assert.match(preload, /exposeInMainWorld\('auftraege'/);
    assert.equal((preload.match(/ipcRenderer\.\w+\(/g) || []).length, 1, 'one call, nothing else');
    assert.match(fs.readFileSync(path.join(__dirname, 'main.js'), 'utf8'), /ipcMain\.handle\('orders:read'/);
});

test('a local page gets its preload and is loaded as a file', () => {
    const { ExternalSpaceManager } = require('./external-spaces');
    const made = [];
    class View { constructor(options) { made.push(options); this.webContents = { session: { webRequest: { onBeforeSendHeaders() {} } }, setWindowOpenHandler() {}, on() {} }; } setBounds() {} }
    const manager = new ExternalSpaceManager(null, { BrowserView: View, shell: {}, logger: { log() {} }, env: {} });
    const targets = [];
    manager._load = function (id) { targets.push(this._targets(this.spaces.get(id))); };
    manager._create('orders');
    manager._create('sales');

    assert.match(made[0].webPreferences.preload, /auftraege-preload\.js$/);
    assert.equal(made[0].webPreferences.sandbox, true);
    assert.equal(made[1].webPreferences.preload, undefined, 'a remote page gets no bridge');
    assert.equal(targets[0][0].kind, 'file');
    assert.deepEqual(targets[1], []);
});

test('the page reading its list is no task of the person: the status line leaves that plan out', () => {
  const { createTaskNavigator } = require('./task-navigation');
  const { OWN_PLAN_PREFIX } = require('./orders-data');
  assert.equal(OWN_PLAN_PREFIX, 'auftraege-');
  const sent = [];
  const nav = createTaskNavigator((message) => sent.push(message));
  // the sentence: one plan, one ✓
  nav.handle('plan_started', { plan_id: 'lesen_1', hops: [{}], space: 'schedule' });
  nav.handle('hop_completed', { space: 'schedule', ok: true, result_preview: "'leer'" });
  assert.equal(nav.handle('plan_completed', { ok: true }).state, 'done');
  const before = sent.length;
  // then the tab opens and its page reads the list: nothing of that reaches the line
  assert.equal(nav.handle('plan_started', { plan_id: 'auftraege-0aef4f', hops: [{}], space: 'schedule' }), null);
  assert.equal(nav.handle('hop_started', { space: 'schedule' }), null);
  assert.equal(nav.handle('hop_completed', { space: 'schedule', ok: true }), null);
  assert.equal(nav.handle('plan_completed', { ok: true, plan_id: 'auftraege-0aef4f' }), null);
  assert.equal(sent.length, before, 'no second ✓, no jump');
  // the next plan of a sentence shows again
  nav.handle('plan_started', { plan_id: 'lesen_2', hops: [{}], space: 'schedule' });
  assert.ok(sent.length > before);
});
