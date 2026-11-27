// Lauf 39: the Agent Farm list said "Keine Workflows" while the n8n editor showed ten. The list asked Python,
// whose module spaces.n8n is missing; now the main process asks n8n itself. Invented ids and names.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { n8nListRest, n8nDeactivateRest } = require('./n8n-access');

const read = (...parts) => fs.readFileSync(path.join(__dirname, ...parts), 'utf8');
const ENV = { N8N_API_KEY: 'test-n8n-key' };

function pages(list) {
  const calls = [];
  const fetchImpl = async (url, init) => {
    calls.push({ url, init });
    const cursor = new URL(url).searchParams.get('cursor') || '';
    const page = list[cursor];
    return { ok: true, status: 200, json: async () => page };
  };
  return { calls, fetchImpl };
}

test('the list: every page of n8n, with the key in the header, localhost asked as 127.0.0.1', async () => {
  const f = pages({
    '': { data: [{ id: 'Wf00000000000001', name: 'Testlauf A', active: true, updatedAt: '2026-03-01T10:00:00.000Z' },
      { id: 'Wf00000000000002', name: 'Testlauf B', active: false }], nextCursor: 'c2' },
    c2: { data: [{ id: 'Wf00000000000003', name: 'Testlauf C', active: false }, { id: '../boese', name: 'x' }], nextCursor: null },
  });
  const result = await n8nListRest(ENV, { fetchImpl: f.fetchImpl });
  assert.equal(result.error, undefined);
  assert.deepEqual(result.workflows.map((w) => [w.id, w.name, w.active]),
    [['Wf00000000000001', 'Testlauf A', true], ['Wf00000000000002', 'Testlauf B', false], ['Wf00000000000003', 'Testlauf C', false]]);
  assert.equal(f.calls.length, 2);
  assert.ok(f.calls[0].url.startsWith('http://127.0.0.1:15678/api/v1/workflows?limit=100'));
  assert.ok(f.calls[1].url.includes('cursor=c2'));
  assert.equal(f.calls[0].init.headers['X-N8N-API-KEY'], 'test-n8n-key');
  assert.doesNotMatch(JSON.stringify(result), /test-n8n-key/);
});

test('no key, a refusal or no answer: an empty list with a reason in German, never the key', async () => {
  let asked = 0;
  assert.deepEqual(await n8nListRest({}, { fetchImpl: async () => { asked += 1; } }),
    { workflows: [], error: 'Die Workflows lassen sich nicht lesen: N8N_API_KEY fehlt.' });
  assert.equal(asked, 0);
  assert.deepEqual(await n8nListRest(ENV, { fetchImpl: async () => ({ ok: false, status: 500 }) }),
    { workflows: [], error: 'Die Workflows lassen sich nicht lesen: n8n antwortet mit 500.' });
  assert.deepEqual(await n8nListRest(ENV, { fetchImpl: async () => { throw new Error('ECONNREFUSED'); } }),
    { workflows: [], error: 'Die Workflows lassen sich nicht lesen: n8n nicht erreichbar.' });
});

test('deactivating goes to n8n like activating; a bad id sends nothing', async () => {
  const calls = [];
  const fetchImpl = async (url, init) => { calls.push([url, init.method]); return { ok: true, status: 200 }; };
  assert.deepEqual(await n8nDeactivateRest(ENV, 'Wf00000000000001', { fetchImpl }), { success: true });
  assert.deepEqual(calls, [['http://127.0.0.1:15678/api/v1/workflows/Wf00000000000001/deactivate', 'POST']]);
  assert.deepEqual(await n8nDeactivateRest(ENV, '../x', { fetchImpl }), { success: false, error: 'keine gültige Workflow-id' });
  assert.equal(calls.length, 1);
});

test('the main process answers list, activate and deactivate itself; the page shows the reason', () => {
  const main = read('main.js');
  assert.match(main, /ipcMain\.handle\('agentfarm:n8n-list', \(\) => require\('\.\/n8n-access'\)\.n8nListRest\(process\.env\)\);/);
  assert.match(main, /ipcMain\.handle\('agentfarm:n8n-activate', \(_event, \{ workflowId \} = \{\}\) => require\('\.\/n8n-access'\)\.n8nActivateRest\(process\.env, workflowId\)\);/);
  assert.match(main, /ipcMain\.handle\('agentfarm:n8n-deactivate', \(_event, \{ workflowId \} = \{\}\) => require\('\.\/n8n-access'\)\.n8nDeactivateRest\(process\.env, workflowId\)\);/);
  assert.doesNotMatch(main, /type: 'n8n_list' \}, 'n8n_list_result'\);/);
  const page = read('agentfarm', 'src', 'features', 'WorkflowBuilder.tsx');
  assert.match(page, /if \(result\?\.error\) setError\(result\.error\)/);
});

test('Lauf 41: a refused key (401) says what to do, names only the variable; the page shows only the error', async () => {
  const result = await n8nListRest(ENV, { fetchImpl: async () => ({ ok: false, status: 401 }) });
  assert.deepEqual(result.workflows, []);
  assert.match(result.error, /^Die Workflows lassen sich nicht lesen: n8n lehnt N8N_API_KEY ab \(401\)\. /);
  assert.match(result.error, /Einstellungen → n8n API/);
  assert.match(result.error, /in der \.env als N8N_API_KEY eintragen, dann die App neu starten\.$/);
  assert.doesNotMatch(result.error, /test-n8n-key/);

  const page = read('agentfarm', 'src', 'features', 'WorkflowBuilder.tsx');
  assert.match(page, /\) : workflows\.length === 0 && error \? null : workflows\.length === 0 \? \(/, 'no "Keine Workflows" below an error');
});

test('Lauf 41: the button ↗ opens n8n where the embedded editor has it, not under the address of the other machine', () => {
  const main = read('main.js');
  const handler = main.slice(main.indexOf("ipcMain.handle('clawport:open-n8n-editor'"));
  const body = handler.slice(0, handler.indexOf('\n    });'));
  assert.match(body, /const n8nUrl = require\('\.\/n8n-access'\)\.n8nBaseUrl\(process\.env\);/);
  assert.doesNotMatch(body, /N8N_API_URL/);
  const { n8nBaseUrl } = require('./n8n-access');
  assert.equal(n8nBaseUrl({ N8N_API_URL: 'http://n8n.example.test:5678', N8N_UI_URL: 'http://localhost:15678' }), 'http://localhost:15678');
});
