const assert = require('node:assert/strict');
const test = require('node:test');

const { createStartupPolicy } = require('./startup-policy');

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

test('FAST_STARTUP skips every external startup callback', async () => {
  const policy = createStartupPolicy({ FAST_STARTUP: 'true' });
  const calls = [];

  for (const name of EXTERNAL_STARTS) {
    const ran = await policy.runExternalStartup(name, async () => {
      calls.push(name);
      throw new Error(`external startup ran: ${name}`);
    });
    assert.equal(ran, false);
  }

  assert.equal(policy.isFastStartup, true);
  assert.deepEqual(calls, []);
});

test('normal startup preserves external callback order and awaits completion', async () => {
  const policy = createStartupPolicy({});
  const calls = [];

  for (const name of EXTERNAL_STARTS) {
    const ran = await policy.runExternalStartup(name, async () => {
      await Promise.resolve();
      calls.push(name);
    });
    assert.equal(ran, true);
  }

  assert.equal(policy.isFastStartup, false);
  assert.deepEqual(calls, EXTERNAL_STARTS);
});

test('FAST_STARTUP requires the explicit true value', () => {
  assert.equal(createStartupPolicy({ FAST_STARTUP: 'false' }).isFastStartup, false);
  assert.equal(createStartupPolicy({ FAST_STARTUP: '1' }).isFastStartup, false);
  assert.equal(createStartupPolicy({ FAST_STARTUP: 'TRUE' }).isFastStartup, false);
});
