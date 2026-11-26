// VibeCoder step 1 (2026-11-26): the display tells the truth. "n8n offline" came from a missing Python
// module (spaces.n8n) while n8n ran, and the VibeCoder field stayed empty. Now: online/offline from the
// main process (/healthz), and the field says in one sentence that the VibeCoder is not connected.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const { n8nHealth } = require('./n8n-access');

const read = (...parts) => fs.readFileSync(path.join(__dirname, ...parts), 'utf8');
const loadNotice = () => import(pathToFileURL(path.join(__dirname, 'agentfarm', 'src', 'vibecoder.ts')).href);

test('n8n health: /healthz of the configured address; localhost is asked as 127.0.0.1', async () => {
  const asked = [];
  const ok = await n8nHealth({}, { fetchImpl: async (url) => { asked.push(url); return { ok: true, status: 200 }; } });
  assert.deepEqual(ok, { online: true, url: 'http://localhost:15678' });
  assert.deepEqual(asked, ['http://127.0.0.1:15678/healthz']);
  await n8nHealth({ N8N_API_URL: 'https://n8n.example.test' }, { fetchImpl: async (url) => { asked.push(url); return { ok: true }; } });
  assert.equal(asked[1], 'https://n8n.example.test/healthz');
});

test('n8n health: an error status, no answer or a timeout is offline, with a short reason and no stack', async () => {
  assert.deepEqual(await n8nHealth({}, { fetchImpl: async () => ({ ok: false, status: 503 }) }),
    { online: false, url: 'http://localhost:15678', error: 'n8n antwortet mit 503' });
  assert.deepEqual(await n8nHealth({}, { fetchImpl: async () => { throw new Error('ECONNREFUSED 127.0.0.1:15678'); } }),
    { online: false, url: 'http://localhost:15678', error: 'n8n nicht erreichbar' });
  const hanging = (url, { signal }) => new Promise((_, reject) => signal.addEventListener('abort', () => reject(new Error('aborted'))));
  assert.equal((await n8nHealth({}, { fetchImpl: hanging, timeoutMs: 20 })).online, false);
});

test('the main process answers agentfarm:n8n-status and clawport:n8n-status itself, not through Python', () => {
  const main = read('main.js');
  assert.match(main, /ipcMain\.handle\('agentfarm:n8n-status', \(\) => require\('\.\/n8n-access'\)\.n8nHealth\(process\.env\)\);/);
  assert.match(main, /ipcMain\.handle\('clawport:n8n-status', \(\) => require\('\.\/n8n-access'\)\.n8nHealth\(process\.env\)\);/);
  assert.doesNotMatch(main, /type: 'n8n_status' \}/);
});

test('the field: the sentence for a page without the channel names no raw error', async () => {
  const { VIBECODER_NOT_CONNECTED } = await loadNotice();
  assert.match(VIBECODER_NOT_CONNECTED, /noch nicht verbunden/);
  assert.doesNotMatch(VIBECODER_NOT_CONNECTED, /module|spaces\.n8n|Error/i, 'the raw error is not shown');
  const field = read('agentfarm', 'src', 'features', 'VibeCoderChat.tsx');
  assert.match(field, /import \{ VIBECODER_NOT_CONNECTED \} from '\.\.\/vibecoder'/);
  assert.match(field, /\{!connected && \(\s*<p data-vibecoder-notice/);
});
