/**
 * Supabase connection config — single source of truth.
 *
 * Deliberately dependency-free (no `@supabase/supabase-js`, no Electron
 * APIs) so it can be `require()`d cheaply from BOTH:
 *   - supabase-client.js  (main process — builds the real SDK client)
 *   - preload.js           (exposes the values to the renderer via
 *                            contextBridge; pulling in the full supabase-js
 *                            SDK there just to read two strings would be
 *                            unnecessarily heavy)
 *
 * The renderer (contextIsolation: true, nodeIntegration: false) cannot read
 * process.env directly, so it must not hardcode its own copy of these
 * values either — see preload.js's `vibemind.supabase` bridge entry and
 * renderer/universe_canvas.js.
 *
 * Fallbacks point at the local dev Supabase stack. Override via the
 * SUPABASE_URL / SUPABASE_ANON_KEY env vars to target a different instance
 * — that is a config change, not a code change, and it is the operator's
 * decision, not this module's.
 */

const SUPABASE_URL = process.env.SUPABASE_URL || 'http://127.0.0.1:54321';
const SUPABASE_ANON_KEY = process.env.SUPABASE_ANON_KEY ||
  // Local dev default key (from `npx supabase status`)
  'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6ImFub24iLCJleHAiOjE5ODM4MTI5OTZ9.CRXP1A7WOeoJeXxjNni43kdQwgnWNReilDMblYTn_I0';

/**
 * Realtime options for the main-process client.
 *
 * Electron's main process runs on a Node without a global WebSocket (Electron 33
 * = Node 20). supabase-js then refuses to build its Realtime client ("Node.js
 * detected but native WebSocket not found"), so the live DB -> UI updates never
 * start. In that case the `ws` package is handed in as transport. `ws` is only
 * loaded when it is needed, which keeps this module cheap for preload consumers.
 */
function buildRealtimeOptions(deps = {}) {
  // `'nativeWebSocket' in deps`, not a default value: a caller that passes `undefined` means
  // "this runtime has none" (the test did, and passed only on a Node without WebSocket).
  const nativeWebSocket = 'nativeWebSocket' in deps ? deps.nativeWebSocket : globalThis.WebSocket;
  const loadWs = deps.loadWs || (() => require('ws'));
  const options = { params: { eventsPerSecond: 10 } };
  if (typeof nativeWebSocket !== 'function') options.transport = loadWs();
  return options;
}

module.exports = { SUPABASE_URL, SUPABASE_ANON_KEY, buildRealtimeOptions };
