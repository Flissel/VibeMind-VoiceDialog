const assert = require('node:assert/strict');
const test = require('node:test');

const {
  DOCKER_BOOTSTRAP_MARKER,
  ISOLATED_PRE_QUIT_VIDEO_CLEANUP_MARKER,
  STARTUP_SIDE_EFFECTS,
  createStartupAudit,
  createStartupPolicy,
  findForbiddenStartupMarkers,
  formatStartupProfileLine,
  parseStartupAllow,
  stripAnsi,
} = require('./startup-policy');

function recordingLogger() {
  const lines = [];
  const rec = (level) => (...parts) => lines.push([level, parts.map(String).join(' ')]);
  return { lines, log: rec('log'), info: rec('info'), warn: rec('warn'), error: rec('error') };
}

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

test('isolated startup destroys the video BrowserView once before Electron closes windows', () => {
  const policy = createStartupPolicy({ VIBEMIND_E2E_ISOLATED_STARTUP: 'true' });
  const order = [];

  const firstRun = policy.runIsolatedPreQuitCleanup(() => order.push('video BrowserView destroyed'));
  order.push('Electron closes windows');
  const secondRun = policy.runIsolatedPreQuitCleanup(() => order.push('duplicate destroy'));

  assert.equal(firstRun, true);
  assert.equal(secondRun, false);
  assert.deepEqual(order, ['video BrowserView destroyed', 'Electron closes windows']);
});

test('normal startup never runs isolated pre-quit video cleanup', () => {
  const policy = createStartupPolicy({ FAST_STARTUP: 'true' });
  const calls = [];

  const ran = policy.runIsolatedPreQuitCleanup(() => calls.push('video BrowserView destroyed'));

  assert.equal(ran, false);
  assert.deepEqual(calls, []);
});

test('isolated pre-quit video cleanup marker is public and secret-free', () => {
  assert.match(
    ISOLATED_PRE_QUIT_VIDEO_CLEANUP_MARKER,
    /ISOLATED_STARTUP.*pre-quit video BrowserView destroyed/,
  );
  assert.doesNotMatch(ISOLATED_PRE_QUIT_VIDEO_CLEANUP_MARKER, /[A-Z]:\\|token|secret/i);
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

test('Startprofil kennt genau die neun Nebenwirkungen der Spec', () => {
  assert.deepEqual([...STARTUP_SIDE_EFFECTS], [
    'docker-cleanup', 'media-compose', 'n8n-local', 'mirofish-local',
    'openfang-spawn', 'brain-spawn', 'rowboat-autoclean', 'bubble-sync', 'zombie-kill',
  ]);
});

test('Vorgabe: ohne VIBEMIND_STARTUP_ALLOW ist alles aus', () => {
  const policy = createStartupPolicy({}, { logger: recordingLogger() });
  assert.deepEqual([...policy.allowed], []);
  assert.deepEqual([...policy.skipped], [...STARTUP_SIDE_EFFECTS]);
  for (const name of STARTUP_SIDE_EFFECTS) assert.equal(policy.isAllowed(name), false);
  assert.equal(createStartupPolicy({ VIBEMIND_STARTUP_ALLOW: '' }).isAllowed('docker-cleanup'), false);
});

test('Liste wird getrimmt, kleingeschrieben, dedupliziert und in fester Reihenfolge gefuehrt', () => {
  const policy = createStartupPolicy(
    { VIBEMIND_STARTUP_ALLOW: ' Docker-Cleanup , brain-spawn,docker-cleanup,, ZOMBIE-KILL ' },
    { logger: recordingLogger() },
  );
  assert.deepEqual([...policy.allowed], ['docker-cleanup', 'brain-spawn', 'zombie-kill']);
  assert.equal(policy.isAllowed('docker-cleanup'), true);
  assert.equal(policy.isAllowed('media-compose'), false);
  assert.deepEqual(parseStartupAllow(undefined), { allowed: [], unknown: [] });
});

test('unbekannte Namen werden mit Warnung ignoriert', () => {
  const logger = recordingLogger();
  const policy = createStartupPolicy({ VIBEMIND_STARTUP_ALLOW: 'n8n-local,eyeterm,Eyeterm' }, { logger });
  assert.deepEqual([...policy.allowed], ['n8n-local']);
  assert.deepEqual([...policy.unknown], ['eyeterm']);
  policy.logStartupProfile();
  const warnings = logger.lines.filter(([level]) => level === 'warn').map(([, msg]) => msg);
  assert.deepEqual(warnings, ['[Startprofil] unbekannter Name ignoriert: eyeterm']);
});

test('isAllowed wirft bei Tippfehlern im Code', () => {
  const policy = createStartupPolicy({});
  assert.throws(() => policy.isAllowed('docker-clean'), /Unbekannte Startprofil-Nebenwirkung: docker-clean/);
});

test('VIBEMIND_E2E_ISOLATED_STARTUP schlaegt die Erlaubnisliste', () => {
  const policy = createStartupPolicy({
    VIBEMIND_E2E_ISOLATED_STARTUP: 'true',
    VIBEMIND_STARTUP_ALLOW: 'docker-cleanup,brain-spawn',
  });
  assert.equal(policy.isAllowed('docker-cleanup'), false);
  assert.deepEqual([...policy.allowed], []);
});

test('Log-Zeile hat das Spec-Format', () => {
  const logger = recordingLogger();
  createStartupPolicy({}, { logger }).logStartupProfile();
  assert.deepEqual(logger.lines, [[
    'log',
    '[Startprofil] erlaubt=[] uebersprungen=[docker-cleanup,media-compose,n8n-local,mirofish-local,openfang-spawn,brain-spawn,rowboat-autoclean,bubble-sync,zombie-kill]',
  ]]);
  assert.equal(
    formatStartupProfileLine(['docker-cleanup', 'zombie-kill']),
    '[Startprofil] erlaubt=[docker-cleanup,zombie-kill] uebersprungen=[media-compose,n8n-local,mirofish-local,openfang-spawn,brain-spawn,rowboat-autoclean,bubble-sync]',
  );
});

test('logSkipped beschreibt, was getan worden waere', () => {
  const logger = recordingLogger();
  createStartupPolicy({}, { logger }).logSkipped('docker-cleanup', 'docker rm -f generation-a');
  assert.deepEqual(logger.lines, [['log', '[Startprofil] docker-cleanup uebersprungen – haette: docker rm -f generation-a']]);
});

test('ein Fehler in einem Block bricht die Folgebloecke nicht ab', async () => {
  const logger = recordingLogger();
  const policy = createStartupPolicy({}, { logger });
  const calls = [];
  const results = [
    await policy.runExternalStartup('eins', async () => calls.push('eins')),
    await policy.runExternalStartup('Laura', async () => { throw new Error('Laura renderer missing'); }),
    await policy.runExternalStartup('Python backend', async () => calls.push('python')),
    await policy.runExternalStartup('kaputt-ohne-Error', async () => { throw 'nur ein String'; }),
  ];
  assert.deepEqual(results, [true, false, true, false]);
  assert.deepEqual(calls, ['eins', 'python']);
  const errors = logger.lines.filter(([level]) => level === 'error').map(([, msg]) => msg);
  assert.deepEqual(errors, [
    '[Startprofil] Startblock "Laura" fehlgeschlagen: Laura renderer missing',
    '[Startprofil] Startblock "kaputt-ohne-Error" fehlgeschlagen: nur ein String',
  ]);
});

test('nach beginShutdown laufen keine weiteren Startbloecke', async () => {
  const logger = recordingLogger();
  const policy = createStartupPolicy({}, { logger });
  const calls = [];
  assert.equal(await policy.runExternalStartup('vorher', async () => calls.push('vorher')), true);
  assert.equal(policy.isShuttingDown(), false);
  policy.beginShutdown();
  assert.equal(policy.isShuttingDown(), true);
  assert.equal(await policy.runExternalStartup('Python backend', async () => calls.push('python')), false);
  assert.deepEqual(calls, ['vorher']);
  assert.ok(logger.lines.some(([level, msg]) =>
    level === 'log' && msg === '[Startprofil] Startblock "Python backend" uebersprungen – App wird beendet'));
});

test('Beenden waehrend ein Block laeuft: laufender Block endet, Folgeblock startet nicht', async () => {
  const policy = createStartupPolicy({}, { logger: recordingLogger() });
  const calls = [];
  let release;
  const gate = new Promise((resolve) => { release = resolve; });
  const running = policy.runExternalStartup('post-window', async () => {
    calls.push('start');
    await gate;
    calls.push('ende');
  });
  policy.beginShutdown();
  release();
  assert.equal(await running, true);
  assert.equal(await policy.runExternalStartup('Python backend', async () => calls.push('python')), false);
  assert.deepEqual(calls, ['start', 'ende']);
});
