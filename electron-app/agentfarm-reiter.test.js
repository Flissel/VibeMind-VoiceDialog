// R2: the Agent Farm hides "Pipeline" and "Teams", opens on n8n, and a switch to a hidden tab is ignored.
// The localStorage switch "vibemind.agentfarm.alleReiter" = "1" brings every tab back.
const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const { pathToFileURL } = require('node:url');

const load = () => import(pathToFileURL(path.join(__dirname, 'agentfarm', 'src', 'reiter.ts')).href);
const store = (value) => () => ({ getItem: (key) => (key === 'vibemind.agentfarm.alleReiter' ? value : null) });

test('by default Pipeline and Teams are hidden; n8n, Rowboat and OpenFang stay', async () => {
    const r = await load();
    const all = r.alleReiter(store(null));
    assert.equal(all, false);
    assert.deepEqual(r.shownTabs(all).map(t => t.label), ['n8n', 'Rowboat', 'OpenFang']);
    assert.equal(r.startTab(all), 'n8n');
});

test('the localStorage switch "1" shows every tab again, Pipeline first', async () => {
    const r = await load();
    const all = r.alleReiter(store('1'));
    assert.equal(all, true);
    assert.deepEqual(r.shownTabs(all).map(t => t.label), ['Pipeline', 'Teams', 'n8n', 'Rowboat', 'OpenFang']);
    assert.equal(r.startTab(all), 'autogen');
    assert.equal(r.alleReiter(store('true')), false, 'only "1" counts');
});

test('a missing or throwing storage counts as hidden', async () => {
    const r = await load();
    assert.equal(r.alleReiter(() => null), false);
    assert.equal(r.alleReiter(() => undefined), false);
    assert.equal(r.alleReiter(() => { throw new Error('SecurityError'); }), false);
    assert.equal(r.alleReiter(() => ({ getItem() { throw new Error('blocked'); } })), false);
});

test('a switch command to a hidden tab is ignored, to a shown tab it goes through', async () => {
    const r = await load();
    assert.equal(r.switchTarget('teams', false), null);
    assert.equal(r.switchTarget('autogen', false), null);
    assert.equal(r.switchTarget('n8n', false), 'n8n');
    assert.equal(r.switchTarget('openfang', false), 'openfang');
    assert.equal(r.switchTarget('nichts', false), null);
    assert.equal(r.switchTarget(undefined, false), null);
    assert.equal(r.switchTarget('teams', true), 'teams');
});

test('App.tsx takes its tabs, start tab and switch filter from reiter.ts; the hidden views stay in the code', () => {
    const src = require('node:fs').readFileSync(path.join(__dirname, 'agentfarm', 'src', 'App.tsx'), 'utf8');
    assert.match(src, /from '\.\/reiter'/);
    assert.match(src, /useState<AgentFarmTab>\(startTab\(ALL\)\)/);
    assert.match(src, /switchTarget\(data\?\.tab, ALL\)/);
    assert.doesNotMatch(src, /\{ key: 'autogen', label: 'Pipeline' \}/, 'the list lives in reiter.ts only');
    assert.match(src, /activeTab === 'autogen'/, 'the Pipeline view is hidden, not removed');
    assert.match(src, /activeTab === 'teams'/, 'the Teams view is hidden, not removed');
});
