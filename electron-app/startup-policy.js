const { stripVTControlCharacters } = require('node:util');

const DOCKER_BOOTSTRAP_MARKER =
  '[Main] NORMAL_STARTUP Docker bootstrap entered: stale-container cleanup and media Docker';
const ISOLATED_PRE_QUIT_VIDEO_CLEANUP_MARKER =
  '[Main] VIBEMIND_E2E_ISOLATED_STARTUP active — pre-quit video BrowserView destroyed';

// Spec 2026-10-15 Abschnitt 1: benannte Nebenwirkungen, Vorgabe aus.
const STARTUP_SIDE_EFFECTS = Object.freeze([
  'docker-cleanup',
  'media-compose',
  'n8n-local',
  'mirofish-local',
  'openfang-spawn',
  'brain-spawn',
  'rowboat-autoclean',
  'bubble-sync',
  'zombie-kill',
]);

function parseStartupAllow(raw) {
  const allowed = [];
  const unknown = [];
  if (typeof raw !== 'string') return { allowed, unknown };
  for (const part of raw.split(',')) {
    const name = part.trim().toLowerCase();
    if (!name) continue;
    if (STARTUP_SIDE_EFFECTS.includes(name)) {
      if (!allowed.includes(name)) allowed.push(name);
    } else if (!unknown.includes(name)) {
      unknown.push(name);
    }
  }
  allowed.sort((a, b) => STARTUP_SIDE_EFFECTS.indexOf(a) - STARTUP_SIDE_EFFECTS.indexOf(b));
  return { allowed, unknown };
}

function formatStartupProfileLine(allowed) {
  const skipped = STARTUP_SIDE_EFFECTS.filter((name) => !allowed.includes(name));
  return `[Startprofil] erlaubt=[${allowed.join(',')}] uebersprungen=[${skipped.join(',')}]`;
}

function errorText(err) {
  return err && typeof err.message === 'string' ? err.message : String(err);
}

function createStartupPolicy(environment, options = {}) {
  const logger = options.logger || console;
  const isIsolatedStartup = environment.VIBEMIND_E2E_ISOLATED_STARTUP === 'true';
  const parsed = parseStartupAllow(environment.VIBEMIND_STARTUP_ALLOW);
  const allowed = Object.freeze(isIsolatedStartup ? [] : parsed.allowed);
  const unknown = Object.freeze(parsed.unknown);
  const skipped = Object.freeze(STARTUP_SIDE_EFFECTS.filter((name) => !allowed.includes(name)));
  let isolatedPreQuitCleanupDone = false;
  let shuttingDown = false;

  function assertKnown(name) {
    if (!STARTUP_SIDE_EFFECTS.includes(name)) {
      throw new TypeError(`Unbekannte Startprofil-Nebenwirkung: ${name}`);
    }
  }

  return Object.freeze({
    isIsolatedStartup,
    allowed,
    skipped,
    unknown,
    isAllowed(name) {
      assertKnown(name);
      return allowed.includes(name);
    },
    isShuttingDown() {
      return shuttingDown;
    },
    beginShutdown() {
      shuttingDown = true;
    },
    startupLogLine() {
      return formatStartupProfileLine(allowed);
    },
    logStartupProfile() {
      for (const name of unknown) logger.warn(`[Startprofil] unbekannter Name ignoriert: ${name}`);
      logger.log(formatStartupProfileLine(allowed));
    },
    logSkipped(name, wouldHaveDone) {
      assertKnown(name);
      logger.log(`[Startprofil] ${name} uebersprungen – haette: ${wouldHaveDone}`);
    },
    pythonEnv() {
      const flag = (name) => (allowed.includes(name) ? '1' : '0');
      return {
        VIBEMIND_ROWBOAT_AUTOCLEAN: flag('rowboat-autoclean'),
        VIBEMIND_BUBBLE_SYNC_ENABLED: flag('bubble-sync'),
        VIBEMIND_CANVAS_REFORMAT_ENABLED: flag('bubble-sync'),
      };
    },
    async runExternalStartup(name, start) {
      if (isIsolatedStartup) return false;
      if (shuttingDown) {
        logger.log(`[Startprofil] Startblock "${name}" uebersprungen – App wird beendet`);
        return false;
      }
      try {
        await start();
        return true;
      } catch (err) {
        logger.error(`[Startprofil] Startblock "${name}" fehlgeschlagen: ${errorText(err)}`);
        return false;
      }
    },
    runIsolatedPreQuitCleanup(cleanup) {
      if (!isIsolatedStartup || isolatedPreQuitCleanupDone) return false;
      isolatedPreQuitCleanupDone = true;
      cleanup();
      return true;
    },
  });
}

function buildPythonBackendEnv({ baseEnv, policy, vibemindRoot, delimiter }) {
  const existing = baseEnv.PYTHONPATH || '';
  return {
    ...baseEnv,
    PYTHONPATH: existing ? `${vibemindRoot}${delimiter}${existing}` : vibemindRoot,
    // Profil gewinnt gegen .env (Spec Abschnitt 1)
    ...policy.pythonEnv(),
  };
}

function stripAnsi(value) {
  return stripVTControlCharacters(String(value));
}

function findForbiddenStartupMarkers(output, markers) {
  const normalized = stripAnsi(output);
  return markers.filter((marker) => normalized.includes(marker));
}

function createStartupAudit() {
  let dockerBootstrapStarted = false;
  return Object.freeze({
    markDockerBootstrapStarted() {
      dockerBootstrapStarted = true;
    },
    publicMarkers() {
      return dockerBootstrapStarted ? [DOCKER_BOOTSTRAP_MARKER] : [];
    },
  });
}

module.exports = {
  buildPythonBackendEnv,
  DOCKER_BOOTSTRAP_MARKER,
  ISOLATED_PRE_QUIT_VIDEO_CLEANUP_MARKER,
  STARTUP_SIDE_EFFECTS,
  createStartupAudit,
  createStartupPolicy,
  findForbiddenStartupMarkers,
  formatStartupProfileLine,
  parseStartupAllow,
  stripAnsi,
};
