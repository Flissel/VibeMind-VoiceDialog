const assert = require('node:assert/strict');
const test = require('node:test');

const DockerManager = require('./docker-manager');
const PortAllocator = require('./port-allocator');
const { createStartupPolicy } = require('./startup-policy');

function recordingLogger() {
  const lines = [];
  const rec = (level) => (...parts) => lines.push(`${level} ${parts.map(String).join(' ')}`);
  return { lines, log: rec('log'), info: rec('info'), warn: rec('warn'), error: rec('error') };
}

function fakeExec(psOutput) {
  const calls = [];
  const exec = async (command) => {
    calls.push(command);
    return { stdout: command.startsWith('docker ps') ? psOutput : '', stderr: '' };
  };
  exec.calls = calls;
  return exec;
}

const PS = 'generation-abc\r\nproject-x\r\nvibemind_brain-core.1.q2w3e4\r\nclaude-runner\r\n';

test('docker-cleanup aus: kein docker rm, Log nennt was geloescht worden waere', async () => {
  const logger = recordingLogger();
  const policy = createStartupPolicy({}, { logger });
  const exec = fakeExec(PS);
  const allocator = new PortAllocator({ policy, execAsync: exec, logger });

  const result = await allocator.cleanupStaleContainers();

  assert.deepEqual(exec.calls, ['docker ps -a --format "{{.Names}}"']);
  assert.deepEqual(result, { removed: [], skipped: ['generation-abc', 'project-x'] });
  assert.ok(logger.lines.includes(
    'log [Startprofil] docker-cleanup uebersprungen – haette: docker rm -f generation-abc project-x'));
});

test('docker-cleanup erlaubt: entfernt nur generation-/project-Container', async () => {
  const logger = recordingLogger();
  const policy = createStartupPolicy({ VIBEMIND_STARTUP_ALLOW: 'docker-cleanup' }, { logger });
  const exec = fakeExec(PS);
  const allocator = new PortAllocator({ policy, execAsync: exec, logger });

  const result = await allocator.cleanupStaleContainers();

  assert.deepEqual(exec.calls, [
    'docker ps -a --format "{{.Names}}"',
    'docker rm -f generation-abc',
    'docker rm -f project-x',
  ]);
  assert.deepEqual(result, { removed: ['generation-abc', 'project-x'], skipped: [] });
});

test('ohne Startprofil raeumt PortAllocator nichts ab (fail-closed)', async () => {
  const logger = recordingLogger();
  const exec = fakeExec(PS);
  const result = await new PortAllocator({ execAsync: exec, logger }).cleanupStaleContainers();
  assert.deepEqual(exec.calls, ['docker ps -a --format "{{.Names}}"']);
  assert.deepEqual(result.removed, []);
});

test('DockerManager beim Beenden: docker-cleanup aus -> kein docker rm, auch nicht claude-runner', async () => {
  const logger = recordingLogger();
  const policy = createStartupPolicy({}, { logger });
  const exec = fakeExec('');
  const manager = new DockerManager({ policy, execAsync: exec, logger, pythonPath: 'python' });

  const result = await manager.stopAllContainers();

  assert.deepEqual(exec.calls, []);
  assert.deepEqual(result, { stopped: [], skipped: ['claude-runner'] });
  assert.ok(logger.lines.includes(
    'log [Startprofil] docker-cleanup uebersprungen – haette: beim Beenden docker rm -f claude-runner'));
});

test('DockerManager beim Beenden: docker-cleanup erlaubt -> claude-runner wird entfernt', async () => {
  const policy = createStartupPolicy({ VIBEMIND_STARTUP_ALLOW: 'docker-cleanup' }, { logger: recordingLogger() });
  const exec = fakeExec('');
  const manager = new DockerManager({ policy, execAsync: exec, logger: recordingLogger(), pythonPath: 'python' });

  const result = await manager.stopAllContainers();

  assert.deepEqual(exec.calls, ['docker rm -f claude-runner']);
  assert.deepEqual(result, { stopped: ['claude-runner'], skipped: [] });
});
