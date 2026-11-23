/**
 * What the entry "Auftraege" shows: the three spaces that have no page of their own
 * (Schedule, Research, Minibook), read from the brain on this machine.
 *
 * Reading only. The page says what is there and what is not; it invents nothing and
 * shows no error detail (only the kind of error).
 */
const crypto = require('node:crypto');

function brainBase(env = process.env) {
  const port = parseInt(env.BRAIN_PORT || '5000', 10);
  return `http://127.0.0.1:${Number.isInteger(port) && port > 0 && port < 65536 ? port : 5000}`;
}

// The page's own reads run as plans of the brain; the status line leaves them out (task-navigation.js):
// they are no task of the person (measured: "… im Dashboard?" showed two ✓, the second was this read).
const OWN_PLAN_PREFIX = 'auftraege-';

function listPlan(capability, id) {
  return {
    plan_id: `${OWN_PLAN_PREFIX}${id}`,
    intent: '',
    rationale: 'Anzeige im Eintrag Auftraege',
    hops: [{ step_id: 's1', description: capability, capability, arg_template: '', retries: 1 }],
  };
}

function text(value) {
  return typeof value === 'string' ? value.trim().slice(0, 200) : '';
}

function errorKind(error) {
  const match = /^([A-Za-z]+(?:Error|Exception))\b/.exec(typeof error === 'string' ? error : '');
  return match ? match[1] : 'Fehler';
}

function scheduleSection(answer) {
  const base = { id: 'schedule', title: 'Termine und Erinnerungen', items: [] };
  const step = answer && answer.executed && answer.executed.s1;
  if (!step) return { ...base, state: 'fehler', text: 'Das Gehirn hat nicht geantwortet.' };
  if (step.ok !== true) {
    return { ...base, state: 'fehler', text: `Die Terminliste konnte nicht gelesen werden (${errorKind(step.error)}).` };
  }
  const tasks = Array.isArray(step.result && step.result.tasks) ? step.result.tasks : [];
  const items = tasks.slice(0, 50).map((task) => ({
    title: text(task && (task.title || task.name || task.description || task.id)) || 'Ohne Titel',
    detail: text(task && (task.next_run || task.run_at || task.when || task.schedule)),
  }));
  return items.length
    ? { ...base, state: 'ok', text: `${items.length} geplant.`, items }
    : { ...base, state: 'leer', text: 'Nichts geplant.' };
}

function researchSection(answer) {
  const base = { id: 'research', title: 'Recherche', items: [] };
  if (!answer || typeof answer !== 'object') return { ...base, state: 'fehler', text: 'Das Gehirn hat nicht geantwortet.' };
  const parts = Object.entries(answer.components || {});
  const down = parts.filter(([, part]) => !part || part.ok !== true).map(([name]) => name);
  if (answer.ok === true && !down.length) return { ...base, state: 'ok', text: 'Bereit. Recherchen starten Sie im Chat.' };
  return { ...base, state: 'fehler', text: `Nicht bereit${down.length ? `: ${down.join(', ')}` : '.'}` };
}

function minibookSection(answer) {
  const base = { id: 'minibook', title: 'Minibook', items: [] };
  if (!answer || typeof answer !== 'object') return { ...base, state: 'fehler', text: 'Das Gehirn hat nicht geantwortet.' };
  if (answer.online !== true) return { ...base, state: 'aus', text: 'Minibook ist nicht erreichbar.' };
  const posts = Array.isArray(answer.recent_posts) ? answer.recent_posts : [];
  const items = posts.slice(0, 20).map((post) => ({
    title: text(post && (post.title || post.content)) || 'Beitrag',
    detail: text(post && (post.author || post.project)),
  }));
  return { ...base, state: items.length ? 'ok' : 'leer', text: items.length ? `${items.length} neue Beiträge.` : 'Keine neuen Beiträge.', items };
}

function summarize({ schedule, minibook, research }) {
  return { sections: [scheduleSection(schedule), researchSection(research), minibookSection(minibook)] };
}

async function defaultFetchJson(url, options = {}) {
  const response = await fetch(url, { ...options, signal: AbortSignal.timeout(20000) });
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}

async function readOrders({ base = brainBase(), fetchJson = defaultFetchJson, id = () => crypto.randomBytes(3).toString('hex') } = {}) {
  const quiet = (promise) => promise.catch(() => null);
  const [schedule, minibook, research] = await Promise.all([
    quiet(fetchJson(`${base}/api/multihop/execute`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ plan: listPlan('schedule_list', id()) }),
    })),
    quiet(fetchJson(`${base}/api/minibook/activity`)),
    quiet(fetchJson(`${base}/api/research/health`)),
  ]);
  return summarize({ schedule, minibook, research });
}

module.exports = { brainBase, listPlan, summarize, readOrders, OWN_PLAN_PREFIX };
