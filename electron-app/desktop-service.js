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

function envValue(env, name) {
  const key = Object.keys(env).find((candidate) => candidate.toLowerCase() === name.toLowerCase());
  return key ? env[key] : '';
}

/**
 * The service outlives the app. A direct child would inherit the app's open sockets, among them
 * the DevTools port: it kept that port after the app had ended, and the next start of the app came
 * up without it (measured 2026-11-22). So the service is started through the shell's own
 * "start a program" (Start-Process without redirection), which hands no handles down. cmd then
 * opens the log file itself. Paths travel as environment values, not inside the command text.
 */
function detachedCommand(spec) {
  const root = envValue(spec.env, 'SystemRoot') || 'C:\\Windows';
  const script = "Start-Process -FilePath $env:ComSpec -ArgumentList ('/d /c \"\"' + $env:VM_SERVICE_COMMAND"
    + " + '\" ' + $env:VM_SERVICE_ARGS + ' >> \"' + $env:VM_SERVICE_LOG + '\" 2>&1\"')"
    + ' -WorkingDirectory $env:VM_SERVICE_CWD -WindowStyle Hidden';
  return {
    command: path.join(root, 'System32', 'WindowsPowerShell', 'v1.0', 'powershell.exe'),
    args: ['-NoProfile', '-NonInteractive', '-Command', script],
    env: {
      ...spec.env,
      VM_SERVICE_COMMAND: spec.command,
      VM_SERVICE_ARGS: spec.args.join(' '),
      VM_SERVICE_LOG: spec.log,
      VM_SERVICE_CWD: spec.cwd,
    },
  };
}

function spawnDetached(spec) {
  fs.mkdirSync(path.dirname(spec.log), { recursive: true });
  const how = detachedCommand(spec);
  const child = spawnProcess(how.command, how.args, { env: how.env, windowsHide: true, stdio: 'ignore' });
  child.unref();
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
        logger.log(`[DesktopService] Start angestossen (Starter-PID ${child && child.pid})`);
        return { state: 'gestartet' };
      } catch (error) {
        logger.log(`[DesktopService] Start gescheitert (${error && error.name})`);
        return { state: 'fehler' };
      }
    },
  };
}

module.exports = { PORT, HEALTH_PATH, launchSpec, detachedCommand, createDesktopService };
