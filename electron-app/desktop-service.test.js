const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const { PORT, launchSpec, createDesktopService } = require('./desktop-service');

const ENV = { DESKTOP_AUTOMATION_DIR: 'C:\\repo\\Automation_ui\\backend', VIBEMIND_PYTHON: 'C:\\repo\\.venv\\Scripts\\python.exe', LOCALAPPDATA: 'C:\\L' };
const all = () => true;

test('the service is started the way the launcher starts it, bound to this machine only', () => {
    const spec = launchSpec({ ...ENV, HOST: '0.0.0.0', PORT: '9999' }, all);

    assert.equal(spec.command, ENV.VIBEMIND_PYTHON);
    assert.deepEqual(spec.args, ['server.py']);
    assert.equal(spec.cwd, ENV.DESKTOP_AUTOMATION_DIR);
    assert.equal(spec.env.HOST, '127.0.0.1', 'it drives mouse and keyboard: never reachable from outside');
    assert.equal(spec.env.PORT, String(PORT));
    assert.equal(spec.log, path.join('C:\\L', 'VibeMind', 'logs', 'automation_ui', 'backend.log'));
});

test('the service gets the system environment only, not what the app loaded from its .env', () => {
    // Seen in the app on 2026-11-22: LOG_FILE from the app's .env reached the service and it crashed at start.
    const spec = launchSpec({
        ...ENV, Path: 'C:\\Windows', SystemRoot: 'C:\\Windows', USERPROFILE: 'C:\\U', TEMP: 'C:\\T',
        LOG_FILE: 'vibemind.log', OPENFANG_API_KEY: 'geheim', VIBEMIND_ENV_FILE: 'C:\\repo\\.env', ELECTRON_RUN_AS_NODE: '1',
    }, all);

    assert.deepEqual(Object.keys(spec.env).sort(), ['HOST', 'LOCALAPPDATA', 'PORT', 'Path', 'SystemRoot', 'TEMP', 'USERPROFILE']);
});

test('nothing is started when the place or the interpreter is unknown or missing', () => {
    assert.equal(launchSpec({}, all), null);
    assert.equal(launchSpec({ ...ENV, VIBEMIND_PYTHON: '' }, all), null);
    assert.equal(launchSpec(ENV, (file) => !file.endsWith('server.py')), null, 'module not loaded');
    assert.equal(launchSpec(ENV, (file) => !file.endsWith('python.exe')), null);
});

function harness({ healthy = false, spec = { command: 'py', args: ['server.py'], cwd: 'd', env: {}, log: 'l' } } = {}) {
    const spawned = [];
    const state = { healthy };
    const service = createDesktopService({
        spec: () => spec,
        probe: async () => state.healthy,
        spawn: (s) => { spawned.push(s); return { pid: 4711 }; },
        now: () => state.now || 0,
    });
    return { service, spawned, state };
}

test('a running service is left alone', async () => {
    const { service, spawned } = harness({ healthy: true });
    assert.deepEqual(await service.ensureRunning(), { state: 'laeuft' });
    assert.equal(spawned.length, 0);
});

test('a missing service is started once; opening the space again does not start a second one', async () => {
    const { service, spawned, state } = harness();

    assert.deepEqual(await service.ensureRunning(), { state: 'gestartet' });
    assert.deepEqual(await service.ensureRunning(), { state: 'startet' });
    state.now = 30 * 1000;
    assert.deepEqual(await service.ensureRunning(), { state: 'startet' });
    assert.equal(spawned.length, 1);

    state.now = 3 * 60 * 1000; // it never came up: try again
    assert.deepEqual(await service.ensureRunning(), { state: 'gestartet' });
    assert.equal(spawned.length, 2);
});

test('without a known place the answer says so instead of failing', async () => {
    const { service, spawned } = harness({ spec: null });
    assert.deepEqual(await service.ensureRunning(), { state: 'nicht eingerichtet' });
    assert.equal(spawned.length, 0);
});

test('a failing start is reported, not thrown', async () => {
    const service = createDesktopService({ spec: () => ({}), probe: async () => false, spawn: () => { throw new Error('EACCES'); }, now: () => 0 });
    assert.deepEqual(await service.ensureRunning(), { state: 'fehler' });
});

test('the main process answers the message the desktop space already sends', () => {
    const main = fs.readFileSync(path.join(__dirname, 'main.js'), 'utf8');
    assert.match(main, /message && message\.type === 'start_automation_ui'/);
    assert.match(main, /desktopService\.ensureRunning\(\)/);
    // Seen in the app on 2026-11-22: the space called `window.vibemind.send`, which the bridge
    // does not have, so the request was never sent. It must use a function the preload exposes.
    const space = fs.readFileSync(path.join(__dirname, 'renderer', 'multiverse.js'), 'utf8');
    const call = /window\.vibemind\.(\w+)\(\{ type: 'start_automation_ui' \}\)/.exec(space);
    assert.ok(call, 'the desktop space sends start_automation_ui');
    const preload = fs.readFileSync(path.join(__dirname, 'preload.js'), 'utf8');
    assert.match(preload, new RegExp(`${call[1]}: \\(message\\) => ipcRenderer\\.send\\('to-python', message\\)`));
});

test('camera moves into and out of a space do not depend on animation frames alone', async () => {
    // Seen in the app on 2026-11-22: with the window covered there are no animation frames, the
    // move into the desktop space never ended and the dashboard was never created.
    const space = fs.readFileSync(path.join(__dirname, 'renderer', 'multiverse.js'), 'utf8');
    assert.doesNotMatch(space, /requestAnimationFrame\(zoom(In|Out)\)/);
    assert.equal((space.match(/this\._cameraStep\(zoom(In|Out)\)/g) || []).length, 8);

    // The step itself: runs once, by timer when no frame comes, by frame when one does.
    const body = /_cameraStep\(step\) \{([\s\S]*?)\n    \}\n/.exec(space.replace(/\r\n/g, '\n'))[1];
    const make = (requestAnimationFrame) => new Function('requestAnimationFrame', 'cancelAnimationFrame', 'setTimeout', 'clearTimeout',
        `return function (step) {${body}};`)(requestAnimationFrame, () => {}, setTimeout, clearTimeout);

    let ran = 0;
    make(() => 0)(() => { ran += 1; });                      // a covered window: the frame never comes
    await new Promise((resolve) => setTimeout(resolve, 200));
    assert.equal(ran, 1);

    ran = 0;
    make((run) => { setImmediate(run); return 1; })(() => { ran += 1; }); // a visible window: frame first
    await new Promise((resolve) => setTimeout(resolve, 200));
    assert.equal(ran, 1, 'the timer must not run the step a second time');
});

test('health is asked where the running service answers it', () => {
    // /api/health alone is 404 on a healthy service; asking there would start a second instance.
    assert.equal(require('./desktop-service').HEALTH_PATH, '/api/health/health');
});
