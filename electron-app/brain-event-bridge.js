/**
 * Phase 11.G — Brain Event Bridge
 *
 * Subscribes to Brain's space-event SSE stream (/api/events/stream) and
 * forwards bubble.* / idea.* events to the renderer as Electron IPC messages
 * matching the existing handler shapes (bubble_created, bubble_updated, ...).
 *
 * Why: Brain is the new orchestrator. When it dispatches a tool that creates
 * a bubble, the App needs to see it in real time. Supabase-Realtime would
 * require USE_SUPABASE_REALTIME=true plus type-mapping fixes; Brain-SSE is
 * a direct path that works regardless of which DB is used.
 *
 * Maps:
 *   bubble.create  -> bubble_created  { bubble: {id, title, ...} }
 *   bubble.update  -> bubble_updated  { bubble: {id, title, ...} }
 *   bubble.delete  -> bubble_deleted  { bubble_id }
 *   idea.create    -> node_added      { node: {id, title, ...} }
 *   idea.update    -> node_updated    { node: {id, title, ...} }
 *   idea.delete    -> node_removed    { node_id }
 *   bubble.enter   -> bubble_entered  { bubble_id, bubble_name }
 *   bubble.exit    -> bubble_exited   {}
 */

const http = require('http');

const BRAIN_HOST = process.env.BRAIN_HOST || '127.0.0.1';
const BRAIN_PORT = parseInt(process.env.BRAIN_PORT || '5000', 10);
const STREAM_PATH = '/api/events/stream';
const COLOR = '\x1b[35m';   // magenta
const RST = '\x1b[0m';

let _req = null;
let _reconnectTimer = null;
let _mainWindow = null;
let _connected = false;

/**
 * Map a brain space-event to Electron IPC message-type + payload.
 * Returns null if event has no known mapping (we don't forward those).
 */
function mapEventToIpc(ev) {
    const eid = ev.event_id || '';
    const params = ev.params || {};
    const result = ev.result || '';

    switch (eid) {
        case 'bubble.create': {
            // result text: "Created bubble 'X' (id=Y)" — extract id
            let id = '';
            const m = /id=([^\s)]+)/i.exec(result);
            if (m) id = m[1];
            return {
                type: 'bubble_created',
                source: 'brain-bridge',
                bubble: {
                    id: id || params.title || '?',
                    title: params.title || '?',
                    description: params.description || '',
                    score: 0,
                },
            };
        }
        case 'bubble.update': {
            return {
                type: 'bubble_updated',
                source: 'brain-bridge',
                bubble: {
                    id: params.bubble_id || params.bubble_name || '?',
                    title: params.new_title || params.bubble_name || '?',
                    old_title: params.bubble_name || '',
                    description: params.new_description || '',
                },
            };
        }
        case 'bubble.delete': {
            return {
                type: 'bubble_deleted',
                source: 'brain-bridge',
                bubble_id: params.bubble_name || params.bubble_id || '?',
            };
        }
        case 'bubble.enter': {
            return {
                type: 'bubble_entered',
                source: 'brain-bridge',
                bubble_id: params.bubble_name || '?',
                bubble_name: params.bubble_name || '?',
            };
        }
        case 'bubble.exit': {
            return { type: 'bubble_exited', source: 'brain-bridge' };
        }
        case 'idea.create': {
            // Phase 11.U.E — DO NOT emit node_added here. The space_event_bus
            // auto-publishes a `ui.refresh_bubbles` immediately after every
            // mutating event, which triggers a full canvas reload from DB
            // (correct titles + content). Emitting node_added too would race
            // and leave a broken placeholder visible for ~5-50ms.
            return null;
        }
        case 'idea.update': {
            // Same reasoning as idea.create — let the auto-refresh handle it.
            return null;
        }
        case 'idea.delete': {
            // Phase 11.U.E — auto-refresh handles it. Skip direct IPC.
            return null;
        }
        case 'ui.refresh_bubbles': {
            return {
                type: 'force_resync_bubbles',
                source: 'brain-bridge',
            };
        }
        case 'idea.connect':
        case 'idea.disconnect':
        case 'idea.auto_link': {
            // Phase 11.U.E — let the auto-refresh re-load nodes+edges from DB.
            // The renderer's loadNodes() rebuilds the full canvas, picking up
            // the new edges with proper from/to_node_id mappings. Direct IPC
            // would race and either flash a temporary state or stale visual.
            return null;
        }
        default:
            return null;
    }
}

function _connect() {
    if (_req) return;
    if (!_mainWindow || _mainWindow.isDestroyed()) return;

    console.log(`${COLOR}[Brain-Bridge]${RST} Connecting to ${BRAIN_HOST}:${BRAIN_PORT}${STREAM_PATH}`);
    const opts = {
        host: BRAIN_HOST, port: BRAIN_PORT, path: STREAM_PATH,
        method: 'GET',
        headers: { 'Accept': 'text/event-stream', 'Connection': 'keep-alive' },
    };

    _req = http.request(opts, (res) => {
        if (res.statusCode !== 200) {
            console.warn(`${COLOR}[Brain-Bridge]${RST} HTTP ${res.statusCode} — backing off`);
            res.resume();
            _reconnect(5000);
            return;
        }
        _connected = true;
        console.log(`${COLOR}[Brain-Bridge]${RST} Connected — listening for space events`);
        res.setEncoding('utf8');
        let buffer = '';
        let currentEventName = '';
        let currentData = '';

        res.on('data', (chunk) => {
            buffer += chunk;
            // SSE messages are newline-separated, fields like "event: foo" / "data: ..."
            let idx;
            while ((idx = buffer.indexOf('\n')) >= 0) {
                const line = buffer.slice(0, idx).replace(/\r$/, '');
                buffer = buffer.slice(idx + 1);
                if (!line) {
                    // empty line = end of message
                    if (currentEventName === 'space_event' && currentData) {
                        try {
                            const ev = JSON.parse(currentData);
                            _handleSpaceEvent(ev);
                        } catch (e) {
                            console.debug(`${COLOR}[Brain-Bridge]${RST} parse fail`, e);
                        }
                    }
                    currentEventName = '';
                    currentData = '';
                    continue;
                }
                if (line.startsWith(':')) continue;  // SSE comment
                if (line.startsWith('event: ')) {
                    currentEventName = line.slice(7).trim();
                } else if (line.startsWith('data: ')) {
                    currentData += (currentData ? '\n' : '') + line.slice(6);
                }
            }
        });

        res.on('end', () => {
            console.log(`${COLOR}[Brain-Bridge]${RST} stream ended`);
            _connected = false; _req = null;
            _reconnect(2000);
        });
        res.on('error', (err) => {
            console.warn(`${COLOR}[Brain-Bridge]${RST} stream error:`, err.message);
            _connected = false; _req = null;
            _reconnect(3000);
        });
    });

    _req.on('error', (err) => {
        console.warn(`${COLOR}[Brain-Bridge]${RST} connect error:`, err.message);
        _req = null; _connected = false;
        _reconnect(5000);
    });

    _req.end();
}

function _reconnect(delayMs) {
    if (_reconnectTimer) return;
    _reconnectTimer = setTimeout(() => {
        _reconnectTimer = null;
        _connect();
    }, delayMs);
}

function _handleSpaceEvent(ev) {
    const ipc = mapEventToIpc(ev);
    if (!ipc) return;
    if (!_mainWindow || _mainWindow.isDestroyed()) return;
    _mainWindow.webContents.send('python-message', ipc);
    console.log(
        `${COLOR}[Brain-Bridge]${RST} ${ev.event_id} -> ${ipc.type}`
    );
}

function initBrainEventBridge(mainWindow) {
    _mainWindow = mainWindow;
    _connect();
    return { close };
}

function close() {
    if (_reconnectTimer) { clearTimeout(_reconnectTimer); _reconnectTimer = null; }
    if (_req) { try { _req.destroy(); } catch (_) {} _req = null; }
    _connected = false;
    console.log(`${COLOR}[Brain-Bridge]${RST} closed`);
}

module.exports = { initBrainEventBridge };
