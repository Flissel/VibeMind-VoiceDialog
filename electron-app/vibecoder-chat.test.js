// VibeCoder steps 4 and 5: the field is a chat with brain-n8n through the main process; activating needs
// the person's "Ja". Invented ids and names, no real data.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { createVibeCoderChat, hasN8nTools, readAnswer, FRAME, TEXT } = require('./vibecoder-chat');
const { n8nActivateRest } = require('./n8n-access');

const read = (...parts) => fs.readFileSync(path.join(__dirname, ...parts), 'utf8');
const AGENT_ID = 'a0000000-0000-4000-8000-000000000001';
const WF = 'Wf0000000000test';

const CONFIG_WITH = '[general]\nport = 4200\n\n[[mcp_servers]]\nname = "vibemind-db"\n\n[[mcp_servers]]\nname = "n8n"\ntimeout_secs = 60\n';
const CONFIG_WITHOUT = '[[mcp_servers]]\nname = "vibemind-db"\n\n[[mcp_servers]]\nname = "laura"\n';

/** A fake OpenFang (and n8n) that records each call. */
function fake({ agents = [{ id: AGENT_ID, name: 'brain-n8n' }], answer = 'Gern.', status = 200, n8nStatus = 200, workflows = { [WF]: { name: 'Testlauf A', active: false } } } = {}) {
  const calls = [];
  const fetchImpl = async (url, init = {}) => {
    calls.push({ url, method: init.method, headers: init.headers || {}, body: init.body ? JSON.parse(init.body) : null });
    if (url.endsWith('/api/agents')) return { ok: true, status: 200, json: async () => agents };
    if (url.includes('/message')) {
      const s = typeof status === 'function' ? status(calls) : status;
      return { ok: s < 400, status: s, headers: { get: () => 'application/json' }, json: async () => ({ response: answer }) };
    }
    if (url.endsWith('/activate')) return { ok: n8nStatus < 400, status: n8nStatus, json: async () => ({ id: WF, active: true }) };
    if (url.includes('/api/v1/workflows/')) {
      const id = url.split('/api/v1/workflows/')[1];
      const wf = workflows[id];
      return wf ? { ok: true, status: 200, json: async () => ({ id, ...wf }) } : { ok: false, status: 404, json: async () => ({}) };
    }
    throw new Error('unexpected ' + url);
  };
  return { calls, fetchImpl };
}

const env = { OPENFANG_URL: 'http://127.0.0.1:4200', OPENFANG_API_KEY: 'test-of-key', N8N_API_KEY: 'test-n8n-key' };

test('the n8n tools: only an [[mcp_servers]] block named "n8n" counts', () => {
  assert.equal(hasN8nTools(CONFIG_WITH), true);
  assert.equal(hasN8nTools(CONFIG_WITHOUT), false);
  assert.equal(hasN8nTools('[agents.n8n]\nname = "n8n"\n'), false, 'a table of another kind is no MCP server');
  assert.equal(hasN8nTools(undefined), false);
});

test('a sentence goes to brain-n8n with the frame; the key goes in the header, the answer comes back', async () => {
  const f = fake({ answer: 'Ich plane einen Workflow.' });
  const chat = createVibeCoderChat({ env, fetchImpl: f.fetchImpl, readFile: () => CONFIG_WITH });
  const result = await chat.send('Baue mir einen Workflow');
  assert.equal(result.ok, true);
  assert.equal(result.reply, 'Ich plane einen Workflow.');
  assert.equal(result.n8nTools, true);
  assert.equal(result.notice, null);
  const post = f.calls.find((c) => c.method === 'POST');
  assert.equal(post.url, `http://127.0.0.1:4200/api/agents/${AGENT_ID}/message`);
  assert.equal(post.body.message, FRAME + 'Baue mir einen Workflow');
  assert.equal(post.headers.Authorization, 'Bearer test-of-key');
  assert.doesNotMatch(JSON.stringify(result), /test-of-key|test-n8n-key/, 'no key in what the renderer gets');
});

test('without the n8n tools the field says so, and talking still works', async () => {
  const f = fake();
  const chat = createVibeCoderChat({ env, fetchImpl: f.fetchImpl, readFile: () => CONFIG_WITHOUT });
  assert.deepEqual(chat.state(), { agent: 'brain-n8n', n8nTools: false, notice: TEXT.noTools });
  const result = await chat.send('Hallo');
  assert.equal(result.ok, true);
  assert.equal(result.notice, TEXT.noTools);
  const unreadable = createVibeCoderChat({ env, fetchImpl: f.fetchImpl, readFile: () => { throw new Error('ENOENT'); } });
  assert.equal(unreadable.state().n8nTools, false);
});

test('OpenFang down, the agent missing, or a renewed id: a clear sentence, one new lookup', async () => {
  const down = createVibeCoderChat({ env, fetchImpl: async () => { throw new Error('ECONNREFUSED'); }, readFile: () => CONFIG_WITH });
  assert.equal((await down.send('Hallo')).error, TEXT.noOpenFang);
  const none = createVibeCoderChat({ env, fetchImpl: fake({ agents: [{ id: 'x', name: 'other' }] }).fetchImpl, readFile: () => CONFIG_WITH });
  assert.equal((await none.send('Hallo')).error, TEXT.noAgent);
  let posts = 0;
  const renewed = fake({ status: () => (++posts === 1 ? 404 : 200) });
  const chat = createVibeCoderChat({ env, fetchImpl: renewed.fetchImpl, readFile: () => CONFIG_WITH });
  assert.equal((await chat.send('Hallo')).ok, true);
  assert.equal(renewed.calls.filter((c) => c.url.endsWith('/api/agents')).length, 2);
});

test('the answer: AKTIVIEREN and WORKFLOW lines are read and taken out of the text', () => {
  const answer = readAnswer(`Fertig.\nWORKFLOW: ${WF}\nAKTIVIEREN: ${WF} | Testlauf A\nAKTIVIEREN: ../etc | Boese`);
  assert.equal(answer.text, 'Fertig.\nAKTIVIEREN: ../etc | Boese', 'an id that is no workflow id stays as text');
  assert.deepEqual(answer.changed, [WF]);
  assert.deepEqual(answer.proposals, [{ workflowId: WF, name: 'Testlauf A' }]);
});

test('activating: only "Ja" to a proposal of this chat, once, through the n8n REST interface', async () => {
  const f = fake({ answer: `Bereit.\nAKTIVIEREN: ${WF} | Testlauf A` });
  const chat = createVibeCoderChat({ env, fetchImpl: f.fetchImpl, readFile: () => CONFIG_WITH });
  const result = await chat.send('Aktiviere ihn');
  assert.equal(result.proposals.length, 1);
  const [proposal] = result.proposals;
  assert.equal(f.calls.some((c) => c.url.includes('/activate')), false, 'the agent\'s line activates nothing');

  assert.deepEqual(await chat.decide('p999', true), { success: false, error: TEXT.unknownProposal });
  const yes = await chat.decide(proposal.id, true);
  assert.equal(yes.activated, true);
  const call = f.calls.find((c) => c.url.includes('/activate'));
  assert.equal(call.url, `http://127.0.0.1:15678/api/v1/workflows/${WF}/activate`);
  assert.equal(call.method, 'POST');
  assert.equal(call.headers['X-N8N-API-KEY'], 'test-n8n-key');
  assert.equal((await chat.decide(proposal.id, true)).success, false, 'a proposal counts once');

  const again = await chat.send('Noch einmal');
  const no = await chat.decide(again.proposals[0].id, false);
  assert.equal(no.activated, false);
  assert.equal(f.calls.filter((c) => c.url.includes('/activate')).length, 1, '"Nein" activates nothing');
});

test('n8n REST activation: without a key nothing is sent; the reason names the variable, not a value', async () => {
  const calls = [];
  const fetchImpl = async (url) => { calls.push(url); return { ok: true, status: 200 }; };
  assert.deepEqual(await n8nActivateRest({}, WF, { fetchImpl }), { success: false, error: 'N8N_API_KEY fehlt' });
  assert.deepEqual(await n8nActivateRest(env, '../x', { fetchImpl }), { success: false, error: 'keine gueltige Workflow-id' });
  assert.equal(calls.length, 0);
  const refused = await n8nActivateRest(env, WF, { fetchImpl: async () => ({ ok: false, status: 401 }) });
  assert.deepEqual(refused, { success: false, error: 'n8n antwortet mit 401' });
});

test('main process and preload: the field talks only through these three channels', () => {
  const main = read('main.js');
  assert.match(main, /ipcMain\.handle\('agentfarm:vibecoder-state', \(\) => vibecoder\(\)\.state\(\)\);/);
  assert.match(main, /ipcMain\.handle\('agentfarm:vibecoder-send', \(_event, \{ text \}\) => vibecoder\(\)\.send\(text\)\);/);
  assert.match(main, /ipcMain\.handle\('agentfarm:vibecoder-decide', \(_event, \{ proposalId, yes \}\) => vibecoder\(\)\.decide\(proposalId, yes === true\)\);/);
  const preload = read('agentfarm-preload.js');
  for (const name of ['vibecoderState', 'vibecoderSend', 'vibecoderDecide']) assert.match(preload, new RegExp(`${name}:`));
  assert.doesNotMatch(preload, /OPENFANG_API_KEY|N8N_API_KEY/);
});

test('the field: the chat replaces the checklist; the old Python channels of the VibeCoder are gone', () => {
  const page = read('agentfarm', 'src', 'features', 'WorkflowBuilder.tsx');
  assert.match(page, /<VibeCoderChat onWorkflowChanged=/);
  assert.doesNotMatch(page, /ChecklistPhase|ChatPhase|n8nChatStart|n8nClaudeBuild/);
  const main = read('main.js');
  assert.doesNotMatch(main, /agentfarm:n8n-chat-|agentfarm:n8n-claude-build/);
  const field = read('agentfarm', 'src', 'features', 'VibeCoderChat.tsx');
  assert.match(field, /Ja, aktivieren/);
  assert.match(field, /data-vibecoder-tools/);
  assert.match(field, /api\.vibecoderDecide\(proposal\.id, yes\)/);
});

test('the question names the workflow as n8n has it; an unknown or active one gets no button', async () => {
  const f = fake({ answer: `Bereit.
AKTIVIEREN: ${WF} | Harmloser Test
AKTIVIEREN: Wf0000000000none | Gibt es nicht
AKTIVIEREN: Wf00000000active | Laeuft`,
    workflows: { [WF]: { name: 'Testlauf A', active: false }, Wf00000000active: { name: 'Testlauf B', active: true } } });
  const chat = createVibeCoderChat({ env, fetchImpl: f.fetchImpl, readFile: () => CONFIG_WITH });
  const result = await chat.send('Aktiviere ihn');
  assert.equal(result.proposals.length, 1);
  assert.equal(result.proposals[0].name, 'Testlauf A', 'the name of n8n, not of the agent');
  assert.equal(result.proposals[0].workflowId, WF);
  assert.equal(result.proposals[0].claimedName, 'Harmloser Test');
  assert.match(result.reply, /Wf0000000000none.*keinen Knopf/);
  assert.match(result.reply, /„Testlauf B" ist schon aktiv\./);
  const lookup = f.calls.find((c) => c.url.endsWith(`/api/v1/workflows/${WF}`));
  assert.equal(lookup.method, 'GET');
  assert.equal(lookup.headers['X-N8N-API-KEY'], 'test-n8n-key');
  const field = read('agentfarm', 'src', 'features', 'VibeCoderChat.tsx');
  assert.match(field, /data-vibecoder-name-differs/);
});
