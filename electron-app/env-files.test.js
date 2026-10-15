const assert = require('node:assert/strict');
const path = require('node:path');
const test = require('node:test');

const { LAUNCH_ONLY_KEYS, loadEnvFiles, resolveEnvFiles } = require('./env-files');

const DIR = 'C:\\betrieb\\voice\\electron-app';
const quiet = { log() {}, warn() {}, info() {}, error() {} };

// Verhaelt sich wie dotenv.config ohne override: setzt nur fehlende Schluessel.
function fakeDotenv(files) {
  const calls = [];
  return {
    calls,
    config({ path: file, processEnv, override }) {
      calls.push(file);
      for (const [key, value] of Object.entries(files[file] || {})) {
        if (override || processEnv[key] === undefined) processEnv[key] = value;
      }
      return { parsed: files[file] || {} };
    },
  };
}

test('ohne VIBEMIND_ENV_FILE gilt der bisherige relative Pfad', () => {
  assert.deepEqual(resolveEnvFiles({ dirname: DIR, env: {} }), {
    rootEnv: path.join(DIR, '..', '..', '..', '.env'),
    voiceEnv: path.join(DIR, '..', '.env'),
  });
  assert.equal(resolveEnvFiles({ dirname: DIR, env: { VIBEMIND_ENV_FILE: '   ' } }).rootEnv, path.join(DIR, '..', '..', '..', '.env'));
});

test('VIBEMIND_ENV_FILE ersetzt die Master-.env', () => {
  const files = resolveEnvFiles({ dirname: DIR, env: { VIBEMIND_ENV_FILE: 'C:\\Users\\User\\Desktop\\Vibemind_V1\\.env' } });
  assert.equal(files.rootEnv, 'C:\\Users\\User\\Desktop\\Vibemind_V1\\.env');
  assert.equal(files.voiceEnv, path.join(DIR, '..', '.env'));
});

test('Master zuerst, voice ergaenzt nur fehlende Schluessel', () => {
  const env = { VIBEMIND_ENV_FILE: 'C:\\V1\\.env' };
  const dotenv = fakeDotenv({
    'C:\\V1\\.env': { OPENAI_API_KEY: 'master', N8N_API_URL: 'http://100.67.177.45:5678' },
    [path.join(DIR, '..', '.env')]: { OPENAI_API_KEY: 'voice', NUR_VOICE: '1' },
  });
  loadEnvFiles({ dirname: DIR, env, dotenv, existsSync: () => true, logger: quiet });
  assert.deepEqual(dotenv.calls, ['C:\\V1\\.env', path.join(DIR, '..', '.env')]);
  assert.equal(env.OPENAI_API_KEY, 'master');
  assert.equal(env.NUR_VOICE, '1');
});

test('VIBEMIND_STARTUP_ALLOW aus einer .env schaltet nichts ein', () => {
  assert.deepEqual([...LAUNCH_ONLY_KEYS], ['VIBEMIND_STARTUP_ALLOW']);
  const env = { VIBEMIND_ENV_FILE: 'C:\\V1\\.env' };
  const dotenv = fakeDotenv({ 'C:\\V1\\.env': { VIBEMIND_STARTUP_ALLOW: 'docker-cleanup,zombie-kill' } });
  loadEnvFiles({ dirname: DIR, env, dotenv, existsSync: () => true, logger: quiet });
  assert.equal(Object.prototype.hasOwnProperty.call(env, 'VIBEMIND_STARTUP_ALLOW'), false);
});

test('VIBEMIND_STARTUP_ALLOW aus dem Prozess bleibt erhalten', () => {
  const env = { VIBEMIND_STARTUP_ALLOW: 'brain-spawn' };
  const dotenv = fakeDotenv({ [path.join(DIR, '..', '..', '..', '.env')]: { VIBEMIND_STARTUP_ALLOW: 'docker-cleanup' } });
  loadEnvFiles({ dirname: DIR, env, dotenv, existsSync: () => true, logger: quiet });
  assert.equal(env.VIBEMIND_STARTUP_ALLOW, 'brain-spawn');
});

test('fehlende VIBEMIND_ENV_FILE wird gewarnt, nicht verschwiegen', () => {
  const warnings = [];
  loadEnvFiles({
    dirname: DIR, env: { VIBEMIND_ENV_FILE: 'C:\\weg\\.env' }, dotenv: fakeDotenv({}),
    existsSync: () => false, logger: { ...quiet, warn: (m) => warnings.push(m) },
  });
  assert.deepEqual(warnings, ['[Main] VIBEMIND_ENV_FILE zeigt auf eine fehlende Datei: C:\\weg\\.env']);
});
