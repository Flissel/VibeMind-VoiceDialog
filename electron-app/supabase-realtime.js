/**
 * Supabase Realtime Subscription Manager for VibeMind.
 *
 * Subscribes to Postgres changes on VibeMind tables and translates
 * them into the same IPC message format that the Python backend uses.
 * This allows the Electron renderer to receive live updates from
 * Supabase without going through the Python process.
 *
 * Feature flag: USE_SUPABASE_REALTIME=true (default: false)
 */

// Loaded on first use: the mapping below is also read by tests and tools that
// have no need for the Supabase SDK.
function getSupabaseClient() {
  return require('./supabase-client').getSupabaseClient();
}

const REALTIME_COLOR = '\x1b[36m'; // Cyan
const RST = '\x1b[0m';

/**
 * Maps Supabase table events to Electron IPC message types.
 *
 * Each entry: { table, event, messageType, transform }
 * - table: Postgres table name
 * - event: INSERT | UPDATE | DELETE | *
 * - messageType: the `type` field sent to renderer via python-message channel
 * - transform: optional function to reshape the payload
 */
const SUBSCRIPTIONS = [
  // Ideas / Bubbles
  { table: 'ideas', event: 'INSERT', messageType: 'node_added',
    transform: (row) => ({ node: { id: row.id, title: row.title, description: row.description, type: 'idea', score: row.score, status: row.status, parent_id: row.parent_id } }) },
  { table: 'ideas', event: 'UPDATE', messageType: 'node_updated',
    // metadata: the reasons given for ratings live in the bubble row (renderer/ideas-chat.js)
    transform: (row) => ({ node: { id: row.id, title: row.title, description: row.description, score: row.score, status: row.status, metadata: row.metadata || null } }) },
  { table: 'ideas', event: 'DELETE', messageType: 'node_removed',
    transform: (old) => ({ node_id: old.id }) },

  // Projects
  { table: 'projects', event: 'INSERT', messageType: 'project_created',
    transform: (row) => ({ project: { id: row.id, name: row.name, status: row.status, generation_status: row.generation_status } }) },
  { table: 'projects', event: 'UPDATE', messageType: 'project_status_update',
    transform: (row) => ({ project_id: row.id, status: row.status, generation_status: row.generation_status, progress: row.progress }) },

  // Canvas
  { table: 'canvas_nodes', event: 'INSERT', messageType: 'node_added',
    // Phase 11.U.F — nest x/y under position + use content.{title,text} so
    // universe_canvas.js renderNode picks them up (it reads data.position?.x
    // and data.content?.title, not flat row.x / row.title)
    transform: (row) => ({ node: {
      id: row.id, type: row.node_type || 'note',
      position: { x: row.x || 100, y: row.y || 100 },
      content: { title: row.title || '', text: row.content || '' },
      metadata: row.metadata || null,
    } }) },
  { table: 'canvas_nodes', event: 'UPDATE', messageType: 'node_updated',
    // Renderer expects msg.updates (not msg.node) — see handlers/canvas-handlers.js:90
    // Phase 11.U.N rev5 — content_json + format_schema in updates so the
    // Mermaid renderer sees freshly-formatted nodes via realtime.
    transform: (row) => ({
      node_id: row.id,
      updates: {
        position: { x: row.x || 100, y: row.y || 100 },
        title: row.title || '',
        content: { title: row.title || '', text: row.content || '' },
        content_json: row.content_json || null,
        format_schema: row.format_schema || null,
        format_type: (row.content_json && row.content_json.type) || null,
        metadata: row.metadata || null,
      },
    }) },
  // Phase 11.U.I rev8 — DELETE subscription was missing; UI never refreshed
  // after a node was removed. Renderer handler at index.html node_removed →
  // onNodeDeleted → in mermaid-mode triggers _scheduleMermaidRefresh.
  { table: 'canvas_nodes', event: 'DELETE', messageType: 'node_removed',
    transform: (old) => ({ node_id: old.id }) },
  { table: 'canvas_edges', event: 'INSERT', messageType: 'edge_added',
    // Phase 11.U.H — emit `edge_added` (matches renderer handler at
    // index.html:1142) with from_node_id/to_node_id shape that onEdgeAdded
    // reads. The keys `from`/`to` and message-type `edge_created` were a
    // mismatch with the rest of the system.
    transform: (row) => ({ edge: {
      id: row.id,
      from_node_id: row.from_node_id,
      to_node_id: row.to_node_id,
      type: row.edge_type,
    } }) },
  // Phase 11.U.I rev8 — edge DELETE also missing
  { table: 'canvas_edges', event: 'DELETE', messageType: 'edge_removed',
    transform: (old) => ({
      edge: { id: old.id, from_node_id: old.from_node_id, to_node_id: old.to_node_id },
    }) },

  // Shuttles
  { table: 'shuttles', event: 'INSERT', messageType: 'shuttle_launched',
    transform: (row) => ({ shuttle_id: row.shuttle_id, bubble_id: row.bubble_id, bubble_name: row.bubble_name }) },
  { table: 'shuttles', event: 'UPDATE', messageType: 'shuttle_stage_update',
    transform: (row) => ({ shuttle_id: row.shuttle_id, status: row.status, stage: row.current_stage, score: row.score }) },

  // Scheduled Tasks
  { table: 'scheduled_tasks', event: 'INSERT', messageType: 'schedule_created',
    transform: (row) => ({ task: { id: row.id, title: row.title, trigger_type: row.trigger_type, status: row.status } }) },

  // Flowzen
  { table: 'flowzen_diary', event: 'INSERT', messageType: 'flowzen_diary_entry',
    transform: (row) => ({ entry: { id: row.id, text: row.entry_text, mood: row.mood, energy: row.energy } }) },

  // Videos
  { table: 'video_projects', event: 'UPDATE', messageType: 'video_project_update',
    transform: (row) => ({ project_id: row.id, name: row.name, status: row.status }) },

  // Persistent Tasks
  { table: 'persistent_tasks', event: 'INSERT', messageType: 'task_created',
    transform: (row) => ({ task: { id: row.id, title: row.title, intent_type: row.intent_type, status: row.status } }) },
  { table: 'persistent_tasks', event: 'UPDATE', messageType: 'task_updated',
    transform: (row) => ({ task_id: row.id, status: row.status, result: row.result }) },
];

/**
 * The IPC message for one row change. `table` tells the renderer where the row
 * came from: `ideas` and `canvas_nodes` both map to node_added / node_removed,
 * but only an ideas row is a bubble of the overview.
 */
function buildRealtimeMessage(sub, row) {
  const data = sub.transform ? sub.transform(row) : row;
  return { ...data, type: sub.messageType, source: 'supabase', table: sub.table };
}

/**
 * The row a change is about. On DELETE Realtime sends an empty object as `new`
 * and the old row (just its key) as `old`; reading `new` first lost the id, so
 * a removed bubble never left the screen.
 */
function rowForEvent(payload) {
  if (!payload) return {};
  const row = payload.eventType === 'DELETE' ? payload.old : (payload.new || payload.old);
  return row || {};
}

/** Ids of rows whose INSERT was already forwarded. */
const _seenIds = new Set();
const MAX_SEEN = 1000;

/**
 * True when the same INSERT arrives a second time. Only inserts are filtered:
 * every UPDATE and DELETE of a known row is a new fact and must go through
 * (the old filter dropped each later change of a row it had seen once).
 * A DELETE forgets the id, because undoing a delete re-inserts the same row.
 */
function isRepeatedInsert(seen, eventType, rowId) {
  if (!rowId) return false;
  if (eventType === 'DELETE') { seen.delete(rowId); return false; }
  if (eventType !== 'INSERT') return false;
  if (seen.has(rowId)) return true;
  seen.add(rowId);
  if (seen.size > MAX_SEEN) {
    const oldest = [...seen].slice(0, 200);
    for (const id of oldest) seen.delete(id);
  }
  return false;
}

/**
 * Initialize Realtime subscriptions.
 * @param {BrowserWindow} mainWindow - Electron main window
 */
function initRealtimeSubscriptions(mainWindow) {
  if (process.env.USE_SUPABASE_REALTIME !== 'true') {
    console.log(`${REALTIME_COLOR}[Supabase-RT]${RST} Disabled (USE_SUPABASE_REALTIME != true)`);
    return null;
  }

  const supabase = getSupabaseClient();

  // Group subscriptions by table to minimize channels
  const tableMap = {};
  for (const sub of SUBSCRIPTIONS) {
    if (!tableMap[sub.table]) tableMap[sub.table] = [];
    tableMap[sub.table].push(sub);
  }

  const channels = [];
  for (const [table, subs] of Object.entries(tableMap)) {
    const channel = supabase.channel(`vibemind-${table}`);

    for (const sub of subs) {
      channel.on(
        'postgres_changes',
        { event: sub.event, schema: 'public', table: sub.table },
        (payload) => {
          const row = rowForEvent(payload);
          if (isRepeatedInsert(_seenIds, payload.eventType, row.id || '')) return;

          // Transform and send to renderer
          const message = buildRealtimeMessage(sub, row);

          if (mainWindow && !mainWindow.isDestroyed()) {
            mainWindow.webContents.send('python-message', message);
          }

          console.log(
            `${REALTIME_COLOR}[Supabase-RT]${RST} ${sub.table}.${payload.eventType} -> ${sub.messageType}`
          );
        }
      );
    }

    channel.subscribe((status) => {
      if (status === 'SUBSCRIBED') {
        console.log(`${REALTIME_COLOR}[Supabase-RT]${RST} Subscribed to ${table}`);
      } else if (status === 'CHANNEL_ERROR') {
        console.warn(`${REALTIME_COLOR}[Supabase-RT]${RST} Channel error for ${table}`);
      }
    });

    channels.push(channel);
  }

  console.log(
    `${REALTIME_COLOR}[Supabase-RT]${RST} Initialized ${channels.length} table subscriptions ` +
    `(${SUBSCRIPTIONS.length} event mappings)`
  );

  return channels;
}

/**
 * Cleanup all subscriptions.
 */
function destroyRealtimeSubscriptions(channels) {
  if (!channels) return;
  const supabase = getSupabaseClient();
  for (const ch of channels) {
    supabase.removeChannel(ch);
  }
  console.log(`${REALTIME_COLOR}[Supabase-RT]${RST} All subscriptions removed`);
}

module.exports = {
  initRealtimeSubscriptions,
  destroyRealtimeSubscriptions,
  buildRealtimeMessage,
  rowForEvent,
  isRepeatedInsert,
  SUBSCRIPTIONS,
};
