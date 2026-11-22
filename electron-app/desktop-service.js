/**
 * Starts the desktop automation service when the Desktop space is opened.
 *
 * The launcher starts it with everything else, but after a restart of the machine (or when
 * it was stopped to free memory) the space showed "offline" and nothing answered the
 * renderer's `start_automation_ui`. The main process now answers: if nothing is healthy on
 * the port, it starts the service the way the launcher does.
 *
 * The service drives mouse and keyboard. It is always bound to 127.0.0.1, whatever the
 * environment says.
 */
const fs = require('node:fs');
const path = require('node:path');
const { spawn: spawnProcess } = require('node:child_process');

const PORT = 8007;
// The health router is mounted under /api/health and its own route is /health; /api/health alone
// answers 404 on a running service (measured 2026-11-22), which would start a second instance.
const HEALTH_PATH = '/api/health/health';
const RETRY_AFTER_MS = 2 * 60 * 1000; // a start that did not come up is tried again after this

// What the operating system gives every process. The service gets this and nothing else from
// the app: the app has loaded its own .env (keys, and settings such as LOG_FILE that the service
// reads too and that made it crash at start, measured 2026-11-22). The launcher starts the
// service without those values; so does the app.
const SYSTEM_ENV = new Set([
  'systemroot', 'systemdrive', 'windir', 'path', 'pathext', 'comspec', 'temp', 'tmp',
  'userprofile', 'username', 'userdomain', 'homedrive', 'homepath', 'appdata', 'localappdata',
  'programdata', 'programfiles', 'programfiles(x86)', 'programw6432', 'commonprogramfiles',
  'commonprogramfiles(x86)', 'commonprogramw6432', 'public', 'os', 'computername',
  'number_of_processors', 'processor_architecture', 'processor_identifier',
  'home', 'lang', 'lc_all', 'tz',
]);

function systemEnv(env) {
  return Object.fromEntries(Object.entries(env).filter(([name]) => SYSTEM_ENV.has(name.toLowerCase())));
}

/** How to start the service, or null when its place or the interpreter is unknown or missing. */
function launchSpec(env = process.env, exists = fs.existsSync) {
  const dir = typeof env.DESKTOP_AUTOMATION_DIR === 'string' ? env.DESKTOP_AUTOMATION_DIR.trim() : '';
  const python = typeof env.VIBEMIND_PYTHON === 'string' ? env.VIBEMIND_PYTHON.trim() : '';
  if (!dir || !python) return null;
  if (!exists(python) || !exists(path.join(dir, 'server.py'))) return null;
  const logRoot = env.LOCALAPPDATA ? path.join(env.LOCALAPPDATA, 'VibeMind', 'logs', 'automation_ui') : path.join(dir, 'logs');
  return {
    command: python,
    args: ['server.py'],
    cwd: dir,
    env: { ...systemEnv(env), PORT: String(PORT), HOST: '127.0.0.1' },
    log: path.join(logRoot, 'backend.log'),
  };
}

async function probeHealth() {
  try {
    const response = await fetch(`http://127.0.0.1:${PORT}${HEALTH_PATH}`, { signal: AbortSignal.timeout(2000) });
    return response.ok;
  } catch (_) {
    return false;
  }
}

function spawnDetached(spec) {
  fs.mkdirSync(path.dirname(spec.log), { recursive: true });
  const out = fs.openSync(spec.log, 'a');
  const child = spawnProcess(spec.command, spec.args, {
    cwd: spec.cwd, env: spec.env, detached: true, windowsHide: true, stdio: ['ignore', out, out],
  });
  child.unref(); // the service outlives the app, as it does when the launcher starts it
  fs.closeSync(out);
  return child;
}

function createDesktopService({ spec = launchSpec, probe = probeHealth, spawn = spawnDetached, now = Date.now, logger = console } = {}) {
  let startedAt = null;
  return {
    /** Never throws. state: laeuft | gestartet | startet | nicht eingerichtet | fehler */
    async ensureRunning() {
      if (await probe()) {
        startedAt = null;
        return { state: 'laeuft' };
      }
      if (startedAt !== null && now() - startedAt < RETRY_AFTER_MS) return { state: 'startet' };
      const how = spec();
      if (!how) return { state: 'nicht eingerichtet' };
      try {
        const child = spawn(how);
        startedAt = now();
        logger.log(`[DesktopService] gestartet (PID ${child && child.pid})`);
        return { state: 'gestartet' };
      } catch (error) {
        logger.log(`[DesktopService] Start gescheitert (${error && error.name})`);
        return { state: 'fehler' };
      }
    },
  };
}

module.exports = { PORT, HEALTH_PATH, launchSpec, createDesktopService };
