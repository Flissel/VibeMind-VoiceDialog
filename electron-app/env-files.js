/**
 * .env-Laden fuer den Electron-Main-Prozess (Spec 2026-10-15 Abschnitt 2).
 * VIBEMIND_ENV_FILE ersetzt die Master-.env (Laufzeit-Checkout liegt nicht unter Vibemind_V1);
 * ohne Wert gilt der bisherige relative Pfad. Secrets werden nur gelesen, nie kopiert.
 * Startprofil-Schluessel kommen nur aus dem Prozess (Launcher), nie aus einer .env.
 */
const path = require('node:path');

const LAUNCH_ONLY_KEYS = Object.freeze(['VIBEMIND_STARTUP_ALLOW']);

function resolveEnvFiles({ dirname, env }) {
  const explicit = typeof env.VIBEMIND_ENV_FILE === 'string' ? env.VIBEMIND_ENV_FILE.trim() : '';
  return {
    rootEnv: explicit ? path.resolve(explicit) : path.join(dirname, '..', '..', '..', '.env'),
    voiceEnv: path.join(dirname, '..', '.env'),
  };
}

function loadEnvFiles({ dirname, env, dotenv, existsSync, logger = console }) {
  const launchValues = Object.fromEntries(LAUNCH_ONLY_KEYS.map((key) => [key, env[key]]));
  const files = resolveEnvFiles({ dirname, env });
  if (typeof env.VIBEMIND_ENV_FILE === 'string' && env.VIBEMIND_ENV_FILE.trim() && !existsSync(files.rootEnv)) {
    logger.warn(`[Main] VIBEMIND_ENV_FILE zeigt auf eine fehlende Datei: ${files.rootEnv}`);
  }
  dotenv.config({ path: files.rootEnv, processEnv: env });                   // master first
  dotenv.config({ path: files.voiceEnv, override: false, processEnv: env }); // voice-only keys added
  for (const key of LAUNCH_ONLY_KEYS) {
    if (launchValues[key] === undefined) delete env[key];
    else env[key] = launchValues[key];
  }
  return files;
}

module.exports = { LAUNCH_ONLY_KEYS, loadEnvFiles, resolveEnvFiles };
