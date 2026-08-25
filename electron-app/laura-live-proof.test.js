const assert = require('node:assert/strict');
const test = require('node:test');

const {
  API_ARGUMENTS,
  buildElectronEnvironment,
  createEphemeralToken,
  formatPublicResult,
  parseArguments,
} = require('./scripts/laura-ui-live-proof');

test('live proof exposes a deterministic help mode and the declared API command', () => {
  assert.deepEqual(parseArguments(['--help']), { help: true });
  assert.deepEqual(parseArguments([]), { help: false });
  assert.deepEqual(API_ARGUMENTS, ['run', '--directory', 'services/local-api', 'laura-api']);
});

test('live proof creates fresh non-empty tokens without embedding them in public results', () => {
  const first = createEphemeralToken();
  const second = createEphemeralToken();

  assert.ok(first.length >= 32);
  assert.notEqual(first, second);
  assert.equal(formatPublicResult({
    token: first,
    workspacePath: 'private-workspace',
    healthStatus: 200,
    projectCount: 0,
  }), JSON.stringify({ healthStatus: 200, projectCount: 0 }));
});

test('live proof builds explicit positive and fail-closed Electron environments', () => {
  const base = { SAFE_FLAG: 'yes', ELECTRON_RUN_AS_NODE: '1' };
  const positive = buildElectronEnvironment(base, 'secret-token', true);
  const negative = buildElectronEnvironment(base, 'secret-token', false);

  assert.equal(positive.LAURA_TOKEN, 'secret-token');
  assert.equal(negative.LAURA_TOKEN, '');
  assert.equal(positive.LAURA_URL, 'http://127.0.0.1:8765');
  assert.equal(negative.LAURA_URL, 'http://127.0.0.1:8765');
  assert.equal(positive.FAST_STARTUP, 'true');
  assert.equal(positive.VIBEMIND_E2E_ISOLATED_STARTUP, 'true');
  assert.equal(positive.MIROFISH_ENABLED, 'false');
  assert.equal(positive.N8N_ENABLED, 'false');
  assert.equal(positive.SKIP_BRAIN_SPAWN, 'true');
  assert.equal(positive.ELECTRON_RUN_AS_NODE, undefined);
});
