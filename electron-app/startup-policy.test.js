const assert = require('node:assert/strict');
const test = require('node:test');

const {
  DOCKER_BOOTSTRAP_MARKER,
  createStartupAudit,
  createStartupPolicy,
  findForbiddenStartupMarkers,
  stripAnsi,
} = require('./startup-policy');

const EXTERNAL_STARTS = [
  'stale-container cleanup',
  'media Docker',
  'Brain spawn',
  'OpenFang',
  'Supabase realtime',
  'Brain bridge',
  'n8n/MiroFish Docker',
  'Rowboat bridge',
  'Python backend',
];

test('VIBEMIND_E2E_ISOLATED_STARTUP skips every external startup callback', async () => {
  const policy = createStartupPolicy({ VIBEMIND_E2E_ISOLATED_STARTUP: 'true' });
  const calls = [];

  for (const name of EXTERNAL_STARTS) {
    const ran = await policy.runExternalStartup(name, async () => {
      calls.push(name);
      throw new Error(`external startup ran: ${name}`);
    });
    assert.equal(ran, false);
  }

  assert.equal(policy.isIsolatedStartup, true);
  assert.deepEqual(calls, []);
});

test('FAST_STARTUP alone preserves normal Electron startup callbacks', async () => {
  const policy = createStartupPolicy({ FAST_STARTUP: 'true' });
  const calls = [];

  for (const name of EXTERNAL_STARTS) {
    const ran = await policy.runExternalStartup(name, async () => {
      await Promise.resolve();
      calls.push(name);
    });
    assert.equal(ran, true);
  }

  assert.equal(policy.isIsolatedStartup, false);
  assert.deepEqual(calls, EXTERNAL_STARTS);
});

test('isolated startup requires the explicit true value', () => {
  assert.equal(createStartupPolicy({ VIBEMIND_E2E_ISOLATED_STARTUP: 'false' }).isIsolatedStartup, false);
  assert.equal(createStartupPolicy({ VIBEMIND_E2E_ISOLATED_STARTUP: '1' }).isIsolatedStartup, false);
  assert.equal(createStartupPolicy({ VIBEMIND_E2E_ISOLATED_STARTUP: 'TRUE' }).isIsolatedStartup, false);
});

test('forbidden startup markers are matched after ANSI normalization', () => {
  const colored = '[OpenFang]\u001b[0m Starting daemon';

  assert.equal(stripAnsi(colored), '[OpenFang] Starting daemon');
  assert.deepEqual(
    findForbiddenStartupMarkers(colored, ['[OpenFang] Starting daemon']),
    ['[OpenFang] Starting daemon'],
  );
});

test('Docker bootstrap audit marker records only an entered normal-mode callback', async () => {
  const fastAudit = createStartupAudit();
  await createStartupPolicy({ VIBEMIND_E2E_ISOLATED_STARTUP: 'true' }).runExternalStartup(
    'Docker bootstrap',
    async () => fastAudit.markDockerBootstrapStarted(),
  );
  assert.deepEqual(fastAudit.publicMarkers(), []);

  const normalAudit = createStartupAudit();
  await createStartupPolicy({}).runExternalStartup(
    'Docker bootstrap',
    async () => normalAudit.markDockerBootstrapStarted(),
  );
  assert.deepEqual(normalAudit.publicMarkers(), [DOCKER_BOOTSTRAP_MARKER]);
  assert.doesNotMatch(DOCKER_BOOTSTRAP_MARKER, /[A-Z]:\\|token|secret/i);
});
