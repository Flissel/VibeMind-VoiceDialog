/**
 * Supabase Client Singleton for VibeMind Electron App.
 *
 * Connects to local Supabase stack (Docker).
 * Used by supabase-realtime.js for live subscriptions
 * and by IPC handlers for direct queries.
 */

const { createClient } = require('@supabase/supabase-js');

const SUPABASE_URL = process.env.SUPABASE_URL || 'http://localhost:54321';
const SUPABASE_KEY = process.env.SUPABASE_ANON_KEY ||
  // Local dev default key (from `npx supabase status`)
  'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZS1kZW1vIiwicm9sZSI6ImFub24iLCJleHAiOjE5ODM4MTI5OTZ9.CRXP1A7WOeoJeXxjNni43kdQwgnWNReilDMblYTn_I0';

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
