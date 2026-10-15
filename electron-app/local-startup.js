/**
 * Lokale Nebenwirkungen beim App-Start hinter dem Startprofil
 * (Spec 2026-10-15 Abschnitt 1): media-compose, n8n-local, mirofish-local, zombie-kill.
 * Bei "aus" wird nichts ausgefuehrt, nur geloggt, was getan worden waere.
 */
const http = require('node:http');

const ZOMBIE_PORTS = Object.freeze([8099, 8009]);

function startMediaCompose({ policy, composePath, existsSync, execSync, logger = console }) {
  const command = `docker compose -f "${composePath}" up -d media`;
  if (!policy.isAllowed('media-compose')) {
    policy.logSkipped('media-compose', command);
    return 'skipped';
  }
  if (!existsSync(composePath)) {
    logger.warn(`[Main] Media-Compose fehlt: ${composePath}`);
    return 'missing';
  }
  execSync(command, { timeout: 15000, stdio: 'ignore' });
  logger.log('[Main] Media server container started (port 9877)');
  return 'started';
}

function startLocalCompose({ sideEffect, label, enabledFlag, policy, composePath, cwd, existsSync, exec, onStarted, extraNote, logger }) {
  if (enabledFlag !== 'true') return 'disabled';
  const command = `docker compose -f "${composePath}" up -d`;
  if (!policy.isAllowed(sideEffect)) {
    policy.logSkipped(sideEffect, extraNote ? `${command} + ${extraNote}` : command);
    return 'skipped';
  }
  if (!existsSync(composePath)) {
    logger.warn(`[Main] ${label}: ${composePath} fehlt – Start uebersprungen`);
    return 'missing';
  }
  logger.log(`[Main] Starting ${label} Docker containers...`);
  exec(command, { cwd }, (err, stdout) => {
    if (err) {
      logger.warn(`[Main] ${label} Docker start failed:`, err.message);
      return;
    }
    logger.log(`[Main] ${label} Docker started successfully`);
    if (stdout && String(stdout).trim()) logger.log(`[Main] ${label}:`, String(stdout).trim());
    if (onStarted) onStarted();
  });
  return 'started';
}

function startN8nLocal({ policy, env, composePath, cwd, existsSync, exec, provisionOwner, logger = console }) {
  const n8nUrl = env.N8N_API_URL || 'http://localhost:15678';
  return startLocalCompose({
    sideEffect: 'n8n-local',
    label: 'n8n',
    enabledFlag: env.N8N_ENABLED,
    policy, composePath, cwd, existsSync, exec, logger,
    extraNote: `Besitzer-Anmeldung an ${n8nUrl}/rest/owner/setup`,
    onStarted: () => provisionOwner(n8nUrl),
  });
}

function startMiroFishLocal({ policy, env, composePath, cwd, existsSync, exec, logger = console }) {
  return startLocalCompose({
    sideEffect: 'mirofish-local',
    label: 'MiroFish',
    enabledFlag: env.MIROFISH_ENABLED,
    policy, composePath, cwd, existsSync, exec, logger,
  });
}

// Unveraendert aus main.js (a506ca2 Z. 3376-3414) uebernommen; laeuft nur nach erlaubtem n8n-local.
function provisionN8nOwner(n8nUrl, { request = http.request, schedule = setTimeout, logger = console, maxAttempts = 6 } = {}) {
  let attempts = 0;
  const attempt = () => {
    attempts += 1;
    const url = new URL(`${n8nUrl}/rest/owner/setup`);
    const body = JSON.stringify({
      email: 'admin@vibemind.local',
      password: 'Vibemind1',
      firstName: 'VibeMind',
      lastName: 'Admin',
    });
    const req = request({
      hostname: url.hostname,
      port: url.port,
      path: url.pathname,
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Content-Length': Buffer.byteLength(body) },
    }, (res) => {
      if (res.statusCode === 200) {
        logger.log('[Main] n8n owner account provisioned');
      } else {
        logger.log('[Main] n8n owner already exists or setup skipped (status ' + res.statusCode + ')');
      }
      res.resume();
    });
    req.on('error', () => {
      if (attempts < maxAttempts) {
        logger.log(`[Main] n8n not ready yet, retry ${attempts}/${maxAttempts}...`);
        schedule(attempt, 5000);
      } else {
        logger.warn(`[Main] n8n owner provision gave up after ${maxAttempts} attempts`);
      }
    });
    req.write(body);
    req.end();
  };
  schedule(attempt, 5000);
}

function findZombieListeners(netstatText, { ports = ZOMBIE_PORTS, ownPid = process.pid } = {}) {
  const found = [];
  for (const raw of String(netstatText).split(/\r?\n/)) {
    const parts = raw.trim().split(/\s+/);
    if (parts.length < 5 || parts[0].toUpperCase() !== 'TCP') continue;
    if (!/^(LISTEN|ABH)/i.test(parts[3])) continue; // LISTENING / ABHÖREN
    const pid = Number.parseInt(parts[4], 10);
    if (!(pid > 0) || pid === ownPid) continue;
    for (const port of ports) {
      if (parts[1].endsWith(`:${port}`) && !found.some((f) => f.pid === pid && f.port === port)) {
        found.push({ port, pid });
      }
    }
  }
  return found;
}

function killZombiePythonProcesses({ policy, execFileSync, platform = process.platform, ownPid = process.pid, logger = console }) {
  if (platform !== 'win32') return [];
  let netstat;
  try {
    netstat = execFileSync('netstat', ['-ano'], { timeout: 3000, encoding: 'utf8' });
  } catch (_) {
    return [];
  }
  const found = findZombieListeners(netstat, { ownPid });
  if (!policy.isAllowed('zombie-kill')) {
    if (found.length > 0) {
      policy.logSkipped('zombie-kill', found.map((f) => `taskkill PID ${f.pid} (:${f.port})`).join(', '));
    }
    return found;
  }
  for (const { port, pid } of found) {
    logger.log(`[Main] Killing zombie process on port ${port} (PID ${pid})`);
    try {
      execFileSync('taskkill', ['/PID', String(pid), '/T', '/F'], { timeout: 3000 });
    } catch (_) { /* may already be dead */ }
  }
  return found;
}

module.exports = {
  ZOMBIE_PORTS,
  findZombieListeners,
  killZombiePythonProcesses,
  provisionN8nOwner,
  startMediaCompose,
  startMiroFishLocal,
  startN8nLocal,
};
