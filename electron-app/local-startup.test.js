const assert = require('node:assert/strict');
const test = require('node:test');

const {
  findZombieListeners,
  killZombiePythonProcesses,
  startMediaCompose,
  startMiroFishLocal,
  startN8nLocal,
} = require('./local-startup');
const { createStartupPolicy } = require('./startup-policy');

function recordingLogger() {
  const lines = [];
  const rec = (level) => (...parts) => lines.push(`${level} ${parts.map(String).join(' ')}`);
  return { lines, log: rec('log'), info: rec('info'), warn: rec('warn'), error: rec('error') };
}

const AUS = () => createStartupPolicy({}, { logger: recordingLogger() });
const ERLAUBT = (list) => createStartupPolicy({ VIBEMIND_STARTUP_ALLOW: list }, { logger: recordingLogger() });

test('media-compose aus: kein docker compose', () => {
  const calls = [];
  const result = startMediaCompose({
    policy: AUS(), composePath: 'C:\\v\\docker-compose.media.yml',
    existsSync: () => true, execSync: (c) => calls.push(c), logger: recordingLogger(),
  });
  assert.equal(result, 'skipped');
  assert.deepEqual(calls, []);
});

test('media-compose erlaubt: startet media mit 15 s Timeout', () => {
  const calls = [];
  const result = startMediaCompose({
    policy: ERLAUBT('media-compose'), composePath: 'C:\\v\\docker-compose.media.yml',
    existsSync: () => true, execSync: (c, o) => calls.push([c, o.timeout]), logger: recordingLogger(),
  });
  assert.equal(result, 'started');
  assert.deepEqual(calls, [['docker compose -f "C:\\v\\docker-compose.media.yml" up -d media', 15000]]);
});

test('n8n-local aus: kein Compose-Aufruf, keine Besitzer-Anmeldung', () => {
  const logger = recordingLogger();
  const policy = createStartupPolicy({}, { logger });
  const execCalls = [];
  const provisioned = [];
  const result = startN8nLocal({
    policy,
    env: { N8N_ENABLED: 'true', N8N_API_URL: 'http://100.67.177.45:5678' },
    composePath: 'C:\\v\\docker-compose.n8n.yml', cwd: 'C:\\v',
    existsSync: () => true,
    exec: (...args) => execCalls.push(args),
    provisionOwner: (url) => provisioned.push(url),
    logger,
  });
  assert.equal(result, 'skipped');
  assert.deepEqual(execCalls, []);
  assert.deepEqual(provisioned, []);
  assert.ok(logger.lines.some((l) => l.includes('n8n-local uebersprungen') && l.includes('http://100.67.177.45:5678/rest/owner/setup')));
});

test('n8n-local erlaubt: Compose und erst danach Besitzer-Anmeldung', () => {
  const provisioned = [];
  const result = startN8nLocal({
    policy: ERLAUBT('n8n-local'),
    env: { N8N_ENABLED: 'true' },
    composePath: 'C:\\v\\docker-compose.n8n.yml', cwd: 'C:\\v',
    existsSync: () => true,
    exec: (command, options, callback) => {
      assert.equal(command, 'docker compose -f "C:\\v\\docker-compose.n8n.yml" up -d');
      assert.equal(options.cwd, 'C:\\v');
      callback(null, 'ok', '');
    },
    provisionOwner: (url) => provisioned.push(url),
    logger: recordingLogger(),
  });
  assert.equal(result, 'started');
  assert.deepEqual(provisioned, ['http://localhost:15678']);
});

test('n8n ohne N8N_ENABLED=true bleibt aus, auch wenn erlaubt', () => {
  const execCalls = [];
  const result = startN8nLocal({
    policy: ERLAUBT('n8n-local'), env: {}, composePath: 'x', cwd: 'y',
    existsSync: () => true, exec: (...a) => execCalls.push(a), provisionOwner: () => {}, logger: recordingLogger(),
  });
  assert.equal(result, 'disabled');
  assert.deepEqual(execCalls, []);
});

test('mirofish-local aus: kein Compose-Aufruf', () => {
  const execCalls = [];
  const result = startMiroFishLocal({
    policy: AUS(), env: { MIROFISH_ENABLED: 'true' },
    composePath: 'C:\\v\\docker-compose.mirofish.yml', cwd: 'C:\\v',
    existsSync: () => true, exec: (...a) => execCalls.push(a), logger: recordingLogger(),
  });
  assert.equal(result, 'skipped');
  assert.deepEqual(execCalls, []);
});

const NETSTAT = [
  '  Proto  Lokale Adresse         Remoteadresse          Status           PID',
  '  TCP    0.0.0.0:8099           0.0.0.0:0              ABHÖREN          4711',
  '  TCP    127.0.0.1:8009         0.0.0.0:0              LISTENING        999',
  '  TCP    0.0.0.0:80990          0.0.0.0:0              LISTENING        5555',
  '  TCP    127.0.0.1:52000        127.0.0.1:8099         ESTABLISHED      6666',
  '  TCP    [::]:8009              [::]:0                 LISTENING        7777',
].join('\r\n');

test('findZombieListeners: nur lauschende fremde PIDs auf 8099/8009, auch deutsches netstat', () => {
  assert.deepEqual(findZombieListeners(NETSTAT, { ownPid: 999 }), [
    { port: 8099, pid: 4711 },
    { port: 8009, pid: 7777 },
  ]);
});

test('zombie-kill aus: netstat ja, taskkill nie, PIDs werden geloggt', () => {
  const logger = recordingLogger();
  const policy = createStartupPolicy({}, { logger });
  const calls = [];
  const found = killZombiePythonProcesses({
    policy, platform: 'win32', ownPid: 999, logger,
    execFileSync: (exe, args) => { calls.push(exe); return exe === 'netstat' ? NETSTAT : ''; },
  });
  assert.deepEqual(calls, ['netstat']);
  assert.equal(found.length, 2);
  assert.ok(logger.lines.includes(
    'log [Startprofil] zombie-kill uebersprungen – haette: taskkill PID 4711 (:8099), taskkill PID 7777 (:8009)'));
});

test('zombie-kill erlaubt: taskkill fuer jede gefundene PID', () => {
  const calls = [];
  killZombiePythonProcesses({
    policy: ERLAUBT('zombie-kill'), platform: 'win32', ownPid: 999, logger: recordingLogger(),
    execFileSync: (exe, args) => { calls.push([exe, ...args]); return exe === 'netstat' ? NETSTAT : ''; },
  });
  assert.deepEqual(calls.slice(1), [
    ['taskkill', '/PID', '4711', '/T', '/F'],
    ['taskkill', '/PID', '7777', '/T', '/F'],
  ]);
});

test('zombie-kill ausserhalb von Windows tut nichts', () => {
  const calls = [];
  assert.deepEqual(killZombiePythonProcesses({
    policy: ERLAUBT('zombie-kill'), platform: 'linux', execFileSync: (e) => calls.push(e), logger: recordingLogger(),
  }), []);
  assert.deepEqual(calls, []);
});
