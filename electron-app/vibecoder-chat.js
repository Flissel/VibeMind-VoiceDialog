/**
 * VibeCoder steps 4 and 5: the field is a chat with the OpenFang agent brain-n8n, through the main process.
 *
 * - Each sentence of the field goes to OpenFang (POST /api/agents/<id>/message); the id is looked up by name
 *   (GET /api/agents) and looked up again once when OpenFang answers 404 (it renews ids on every restart).
 * - The key of OpenFang (OPENFANG_API_KEY) stays here; the renderer gets the answer text, nothing else.
 * - Whether the agent has its n8n tools is read from the OpenFang configuration: an [[mcp_servers]] block
 *   named "n8n". Without it the field says that they are still missing; talking still works.
 * - Activating is never done by the agent. It writes a line "AKTIVIEREN: <id> | <name>"; the field shows a
 *   question with [Ja, aktivieren] [Nein]. Only a "Ja" for a proposal made in this chat activates, once,
 *   through the n8n REST interface (n8n-access.js n8nActivateRest).
 * - A line "WORKFLOW: <id>" names a workflow the agent made or changed; the editor on the right shows it.
 */
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { openfangBaseUrl } = require('./openfang-access');
const { n8nActivateRest, n8nWorkflowInfo, isWorkflowId } = require('./n8n-access');

const AGENT = 'brain-n8n';
const ANSWER_MS = 180000;
const LIST_MS = 5000;

/** Said in front of every sentence, so the agent knows the two lines the field reads. */
const FRAME = '[VibeCoder-Feld] Antworte auf Deutsch und knapp. Aktivieren oder ausfuehren darfst du nicht selbst. '
  + 'Willst du einen Workflow aktivieren, schreibe eine eigene Zeile "AKTIVIEREN: <workflow-id> | <name>"; '
  + 'die Person entscheidet mit einem Knopf. Hast du einen Workflow angelegt oder geaendert, schreibe eine '
  + 'eigene Zeile "WORKFLOW: <workflow-id>". Zugangsdaten (Credentials) legst du nie an; dafuer verweise auf den '
  + 'n8n-Editor rechts.\n---\n';

const TEXT = Object.freeze({
  noOpenFang: 'OpenFang antwortet nicht. Ohne OpenFang kann der VibeCoder nicht antworten; der n8n-Editor rechts geht weiter.',
  noAgent: `Der Agent ${AGENT} ist in OpenFang nicht eingerichtet.`,
  failed: 'Der VibeCoder hat nicht geantwortet. Bitte noch einmal versuchen.',
  noTools: 'Dem VibeCoder fehlen noch seine n8n-Werkzeuge: Er kann mit dir planen, aber noch keine Workflows anlegen oder aendern.',
  unknownProposal: 'Diesen Vorschlag gibt es nicht (mehr). Es wurde nichts aktiviert.',
  unknownWorkflow: (id) => `Der VibeCoder schlägt vor, den Workflow ${id} zu aktivieren; n8n kennt ihn nicht oder antwortet nicht. Darum gibt es keinen Knopf dafür.`,
  alreadyActive: (name) => `„${name}" ist schon aktiv.`,
});

function openfangHeaders(env) {
  const key = typeof env.OPENFANG_API_KEY === 'string' ? env.OPENFANG_API_KEY.trim() : '';
  const headers = { 'Content-Type': 'application/json' };
  if (key) headers.Authorization = `Bearer ${key}`;
  return headers;
}

async function withTimeout(fetchImpl, url, init, ms) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), ms);
  try {
    return await fetchImpl(url, { ...init, signal: controller.signal });
  } finally {
    clearTimeout(timer);
  }
}

/** Whether the OpenFang configuration has an MCP server named "n8n". Only the name is read. */
function hasN8nTools(configText) {
  if (typeof configText !== 'string') return false;
  const blocks = configText.split(/^\s*\[\[mcp_servers\]\]\s*$/m).slice(1);
  return blocks.some((block) => {
    const body = block.split(/^\s*\[/m)[0];
    return /^\s*name\s*=\s*["']n8n["']\s*$/m.test(body);
  });
}

function openfangConfigPath(env) {
  const home = (typeof env.OPENFANG_HOME === 'string' && env.OPENFANG_HOME.trim()) || path.join(os.homedir(), '.openfang');
  return path.join(home, 'config.toml');
}

/** "AKTIVIEREN: <id> | <name>" lines and "WORKFLOW: <id>" lines of an answer; the text without them. */
function readAnswer(text) {
  const proposals = [];
  const changed = [];
  const kept = [];
  for (const line of String(text || '').split(/\r?\n/)) {
    const act = line.match(/^\s*AKTIVIEREN:\s*([^|\s]+)\s*(?:\|\s*(.*?))?\s*$/i);
    const wf = line.match(/^\s*WORKFLOW:\s*(\S+)\s*$/i);
    if (act && isWorkflowId(act[1])) {
      proposals.push({ workflowId: act[1], name: (act[2] || act[1]).slice(0, 120) });
    } else if (wf && isWorkflowId(wf[1])) {
      if (!changed.includes(wf[1])) changed.push(wf[1]);
    } else {
      kept.push(line);
    }
  }
  return { text: kept.join('\n').trim(), proposals, changed };
}

function createVibeCoderChat({ env = process.env, fetchImpl = globalThis.fetch, readFile = fs.readFileSync, log = () => {} } = {}) {
  let agentId = null;
  let nextProposal = 1;
  const proposals = new Map();  // proposal id -> { workflowId, name }

  async function findAgent(force) {
    if (agentId && !force) return agentId;
    const res = await withTimeout(fetchImpl, `${openfangBaseUrl(env)}/api/agents`, { method: 'GET', headers: openfangHeaders(env) }, LIST_MS);
    if (!res || !res.ok) throw Object.assign(new Error('list'), { unreachable: true });
    const body = await res.json();
    const list = Array.isArray(body) ? body : (body && Array.isArray(body.agents) ? body.agents : []);
    const found = list.find((agent) => agent && agent.name === AGENT);
    agentId = found ? String(found.id) : null;
    return agentId;
  }

  function tools() {
    try {
      return hasN8nTools(readFile(openfangConfigPath(env), 'utf8'));
    } catch (_) {
      return false;
    }
  }

  /** What the field shows above the chat: tools there or not. */
  function state() {
    const present = tools();
    return { agent: AGENT, n8nTools: present, notice: present ? null : TEXT.noTools };
  }

  async function post(id, text) {
    return withTimeout(fetchImpl, `${openfangBaseUrl(env)}/api/agents/${encodeURIComponent(id)}/message`, {
      method: 'POST', headers: openfangHeaders(env), body: JSON.stringify({ message: FRAME + text }),
    }, ANSWER_MS);
  }

  async function send(text) {
    const sentence = typeof text === 'string' ? text.trim() : '';
    if (!sentence) return { ok: false, error: TEXT.failed, ...state() };
    let id;
    try {
      id = await findAgent(false);
    } catch (_) {
      return { ok: false, error: TEXT.noOpenFang, ...state() };
    }
    if (!id) return { ok: false, error: TEXT.noAgent, ...state() };
    try {
      let res = await post(id, sentence);
      if (res && res.status === 404) {
        id = await findAgent(true);
        if (!id) return { ok: false, error: TEXT.noAgent, ...state() };
        res = await post(id, sentence);
      }
      if (!res || !res.ok) {
        log(`[VibeCoder] OpenFang antwortet mit ${res ? res.status : 'nichts'}`);
        return { ok: false, error: TEXT.failed, ...state() };
      }
      const type = (res.headers && typeof res.headers.get === 'function' && res.headers.get('content-type')) || '';
      const raw = type.startsWith('application/json') ? await res.json() : { response: await res.text() };
      const answer = readAnswer(raw && (raw.response || raw.text) || '');
      // The question shows the workflow as n8n has it (name and id), never the name the agent wrote:
      // a wrong name must not make the person activate another workflow. Without that, no button.
      const shown = [];
      const notes = [];
      for (const p of answer.proposals) {
        const info = await n8nWorkflowInfo(env, p.workflowId, { fetchImpl });
        if (!info) { notes.push(TEXT.unknownWorkflow(p.workflowId)); continue; }
        if (info.active) { notes.push(TEXT.alreadyActive(info.name)); continue; }
        const proposalId = `p${nextProposal++}`;
        proposals.set(proposalId, { workflowId: info.id, name: info.name });
        shown.push({ id: proposalId, workflowId: info.id, name: info.name, claimedName: p.name !== info.name ? p.name : undefined });
      }
      const reply = [answer.text, ...notes].filter(Boolean).join('\n');
      return { ok: true, reply, proposals: shown, changed: answer.changed, ...state() };
    } catch (_) {
      log('[VibeCoder] keine Antwort von OpenFang');
      return { ok: false, error: TEXT.failed, ...state() };
    }
  }

  /** The person's answer to a proposal: only "Ja" to a proposal of this chat activates, once. */
  async function decide(proposalId, yes) {
    const proposal = proposals.get(proposalId);
    if (!proposal) return { success: false, error: TEXT.unknownProposal };
    proposals.delete(proposalId);
    if (!yes) return { success: true, activated: false, workflowId: proposal.workflowId };
    const result = await n8nActivateRest(env, proposal.workflowId, { fetchImpl });
    return { ...result, activated: !!result.success, workflowId: proposal.workflowId };
  }

  return { send, decide, state };
}

module.exports = { createVibeCoderChat, hasN8nTools, readAnswer, AGENT, FRAME, TEXT };
