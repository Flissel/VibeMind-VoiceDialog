/**
 * Main-side provider of the Supabase config for the sandboxed preload.
 *
 * Sandboxed preloads cannot require() local files, so preload.js fetches the
 * values synchronously over IPC instead of requiring ./supabase-config.
 */
const CHANNEL = 'vibemind:supabase-config';

function registerSupabaseConfigHandler(ipcMain, config) {
  const { SUPABASE_URL, SUPABASE_ANON_KEY } = config;
  ipcMain.on(CHANNEL, (event) => {
    event.returnValue = { url: SUPABASE_URL, anonKey: SUPABASE_ANON_KEY };
  });
}

module.exports = { CHANNEL, registerSupabaseConfigHandler };
