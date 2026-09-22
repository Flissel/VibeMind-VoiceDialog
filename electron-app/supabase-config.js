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

const SUPABASE_URL = process.env.SUPABASE_URL || 'http://192.168.178.65:54321';
const SUPABASE_ANON_KEY = process.env.SUPABASE_ANON_KEY ||
  // Local dev default key (from `npx supabase status`)
  'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6ImFub24iLCJleHAiOjE5ODM4MTI5OTZ9.CRXP1A7WOeoJeXxjNni43kdQwgnWNReilDMblYTn_I0';

module.exports = { SUPABASE_URL, SUPABASE_ANON_KEY };
