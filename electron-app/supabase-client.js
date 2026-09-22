/**
 * Supabase Client Singleton for VibeMind Electron App.
 *
 * Connects to local Supabase stack (Docker).
 * Used by supabase-realtime.js for live subscriptions
 * and by IPC handlers for direct queries.
 */

const { createClient } = require('@supabase/supabase-js');
const { SUPABASE_URL, SUPABASE_ANON_KEY } = require('./supabase-config');

// Kept as SUPABASE_KEY for backward compatibility with this module's
// existing exports (no other file imports the raw constants today, but the
// name is part of the public shape of this module).
const SUPABASE_KEY = SUPABASE_ANON_KEY;

let _client = null;

function getSupabaseClient() {
  if (!_client) {
    _client = createClient(SUPABASE_URL, SUPABASE_KEY, {
      realtime: {
        params: { eventsPerSecond: 10 },
      },
    });
    console.log(`[Supabase] Client created: ${SUPABASE_URL}`);
  }
  return _client;
}

module.exports = { getSupabaseClient, SUPABASE_URL, SUPABASE_KEY };
