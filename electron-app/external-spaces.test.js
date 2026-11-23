const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const THREE = require('./renderer/lib/three.min.js');
const {
    EXTERNAL_SPACES, resolveSpaces, describeForRenderer, authFor, withAuthorization, pathTarget, ExternalSpaceManager,
} = require('./external-spaces');
const { sceneEntry, buildGate } = require('./renderer/external-spaces');
const { pickSpace } = require('./renderer/space-pick');
const { appKeyForSpace } = require('./task-navigation');

test('the external spaces are listed once, each with its own place', () => {
    // OpenFang is not among them: it lives in the Agent Farm.
    assert.deepEqual(EXTERNAL_SPACES.map((s) => s.id), ['sales', 'marketing', 'learning', 'events', 'orders']);
    const places = new Set(EXTERNAL_SPACES.map((s) => s.position.join(',')));
    assert.equal(places.size, EXTERNAL_SPACES.length);
});

test('addresses come from the environment; private hosts are not written into the code', () => {
    const source = fs.readFileSync(path.join(__dirname, 'external-spaces.js'), 'utf8');
    assert.doesNotMatch(source, /ts\.net|100\.\d+\.\d+\.\d+/);

    const none = resolveSpaces({});
    assert.equal(none.find((s) => s.id === 'marketing').url, 'http://127.0.0.1:5510/mockup/');
    for (const id of ['sales', 'learning', 'events']) assert.equal(none.find((s) => s.id === id).url, '', id);

    const set = resolveSpaces({ SALES_UI_URL: ' https://sales.example.test:8445/ ', EVENT_UI_URL: 'javascript:alert(1)' });
    assert.equal(set.find((s) => s.id === 'sales').url, 'https://sales.example.test:8445/');
    assert.equal(set.find((s) => s.id === 'events').url, '', 'only http and https count');
});

test('the renderer learns neither addresses nor key names', () => {
    const list = describeForRenderer({ SALES_UI_URL: 'https://sales.example.test/' });
    const text = JSON.stringify(list);

    assert.doesNotMatch(text, /example\.test|urlEnv|bearerEnv|defaultUrl/);
    assert.equal(list.find((s) => s.id === 'sales').configured, true);
    assert.equal(list.find((s) => s.id === 'learning').configured, false);
});

test('a key is attached to the address of its own space only, and never overrides the page', () => {
    const env = { OPENFANG_API_KEY: ' geheim-123 ' };
    const openfang = { id: 'probe', label: 'Probe', bearerEnv: 'OPENFANG_API_KEY', url: 'http://127.0.0.1:4200/' };
    const sales = resolveSpaces({ SALES_UI_URL: 'https://sales.example.test/' }).find((s) => s.id === 'sales');

    const auth = authFor(openfang, env);
    assert.equal(auth.header, 'Bearer geheim-123');
    assert.deepEqual(auth.urls, [
        'http://127.0.0.1:4200/*', 'ws://127.0.0.1:4200/*', 'http://localhost:4200/*', 'ws://localhost:4200/*',
    ]);
    assert.equal(authFor(sales, env), null, 'a space without a key gets none');
    assert.equal(authFor(openfang, {}), null, 'no key in the environment: nothing is sent');

    assert.deepEqual(withAuthorization({ Accept: '*/*' }, 'Bearer x'), { Accept: '*/*', Authorization: 'Bearer x' });
    assert.deepEqual(withAuthorization({ authorization: 'Bearer eigen' }, 'Bearer x'), { authorization: 'Bearer eigen' });
});

function fakeElectron() {
    const made = [];
    class BrowserView {
        constructor(options) {
            this.options = options;
            this.bounds = null;
            this.hooks = [];
            this.webContents = {
                session: { webRequest: { onBeforeSendHeaders: (filter, handler) => this.hooks.push({ filter, handler }) } },
                setWindowOpenHandler() {}, on() {}, isDestroyed: () => false,
            };
            made.push(this);
        }
        setBounds(bounds) { this.bounds = bounds; }
    }
    const window = {
        view: undefined,
        on() {}, isDestroyed: () => false, webContents: { send() {} },
        setBrowserView(view) { this.view = view; },
        getContentBounds: () => ({ width: 1400, height: 900 }),
    };
    return { BrowserView, shell: { openExternal() {} }, window, made };
}

test('the manager shows one space at a time, each in its own session, and sends the key from the main process', async () => {
    const electron = fakeElectron();
    const loaded = [];
    const manager = new ExternalSpaceManager(electron.window, {
        BrowserView: electron.BrowserView, shell: electron.shell, logger: { log() {} },
        env: { OPENFANG_API_KEY: 'geheim-123', SALES_UI_URL: 'https://sales.example.test/' },
    });
    manager.spaces.set('openfang', { id: 'openfang', label: 'Probe mit Schluessel', bearerEnv: 'OPENFANG_API_KEY', url: 'http://127.0.0.1:4200/' });
    manager._load = (id) => { loaded.push(id); manager.views.get(id).result = { ok: true }; };

    assert.equal(manager.show('gibt-es-nicht'), false);
    assert.equal(manager.show('openfang'), true);
    assert.equal(manager.show('sales'), true);
    manager.show('openfang');

    assert.deepEqual(loaded, ['openfang', 'sales'], 'a view is created once and reused');
    assert.deepEqual(electron.made.map((v) => v.options.webPreferences.partition), ['persist:space-openfang', 'persist:space-sales']);
    assert.equal(electron.window.view, electron.made[0]);
    assert.deepEqual(electron.made[0].bounds, { x: 0, y: 75, width: 1400, height: 825 });
    assert.equal(electron.made[0].hooks.length, 1, 'requests of the space with a key get it');
    assert.equal(electron.made[1].hooks.length, 0, 'Sales requests do not');
    let sent;
    electron.made[0].hooks[0].handler({ requestHeaders: {} }, (result) => { sent = result; });
    assert.equal(sent.requestHeaders.Authorization, 'Bearer geheim-123');

    manager.hideAll();
    assert.equal(electron.window.view, null);
    assert.equal(manager.getIsVisible(), false);
});

test('a path names a place inside the space and nothing else', () => {
    const base = 'https://sales.example.test/';
    const pages = ['/', '/freigaben', '/kontakte'];
    assert.equal(pathTarget(base, '/freigaben#fg-12', pages), 'https://sales.example.test/freigaben#fg-12');
    assert.equal(pathTarget(base, '/kontakte/42', pages), 'https://sales.example.test/kontakte/42');
    assert.equal(pathTarget(base, '/', pages), base);
    for (const bad of ['//evil.example/x', 'https://evil.example/', '/\\evil.example', 'freigaben', 'javascript:alert(1)', '', null, '/a b',
        '/logout', '/api/senden', '/freigaben?senden=1', '/kontakte/../logout', '/kontakte/%2e%2e/logout', '/kontakteX', '/freigaben/./x/../../logout']) {
        assert.equal(pathTarget(base, bad, pages), '', String(bad));
    }
    assert.equal(pathTarget('', '/freigaben', pages), '', 'a space without an address has no paths');
    assert.equal(pathTarget(base, '/freigaben'), '', 'a space without listed pages takes none');
    assert.equal(pathTarget(base, '/freigaben', []), '');
});

test('an open space goes to a path in its own session; a closed one goes there when it is opened', () => {
    const electron = fakeElectron();
    const manager = new ExternalSpaceManager(electron.window, {
        BrowserView: electron.BrowserView, shell: electron.shell, logger: { log() {} },
        env: { SALES_UI_URL: 'https://sales.example.test/' },
    });
    const targets = [];
    manager._load = (id) => { targets.push(manager._targets(manager.spaces.get(id))[0].url); manager.views.get(id).result = { ok: true }; };

    assert.equal(manager.goTo('sales', '//evil.example/'), false);
    assert.equal(manager.goTo('orders', '/x'), false, 'a local page has no paths');
    assert.equal(manager.goTo('sales', '/logout'), false, 'only the listed pages of the space');
    assert.equal(manager.goTo('marketing', '/freigaben'), false, 'a space without listed pages takes none');
    assert.equal(manager.goTo('sales', '/freigaben'), true);
    manager.show('sales');
    assert.deepEqual(targets, ['https://sales.example.test/freigaben']);

    const went = [];
    electron.made[0].webContents.loadURL = (url) => went.push(url);
    manager.goTo('sales', '/kontakte/42');
    assert.deepEqual(went, ['https://sales.example.test/kontakte/42']);
    assert.equal(electron.made[0].options.webPreferences.partition, 'persist:space-sales', 'same session, the sign-in stays');
    manager.show('sales');
    assert.equal(targets.length, 1, 'opening it again does not reload');
});

test('a space that showed a status card is checked again when it is opened next', () => {
    const electron = fakeElectron();
    const loaded = [];
    const manager = new ExternalSpaceManager(electron.window, {
        BrowserView: electron.BrowserView, shell: electron.shell, logger: { log() {} }, env: {},
    });
    manager._load = (id) => { loaded.push(id); manager.views.get(id).result = { ok: false }; };

    manager.show('learning');
    manager.show('learning');

    assert.deepEqual(loaded, ['learning', 'learning']);
});

test('the gate of an external space is its click target and carries what the scene reads', () => {
    const space = describeForRenderer({}).find((s) => s.id === 'marketing');
    const entry = sceneEntry(THREE, space);
    const gate = buildGate(THREE, space, null);
    entry.group = gate.group;
    gate.group.updateMatrixWorld(true);

    assert.equal(entry.external, true);
    assert.equal(entry.name, 'Marketing');
    assert.deepEqual(entry.position.toArray(), space.position);
    const from = new THREE.Vector3(space.position[0], space.position[1] + 1.7, space.position[2] + 12);
    const ray = new THREE.Raycaster(from, new THREE.Vector3(0, 0, -1));
    assert.equal(pickSpace(ray, { marketing: entry }, 'ideas'), 'marketing');
    assert.equal(pickSpace(ray, { marketing: entry }, 'marketing'), null);
});

test('tasks of Lernen and Event-Management now have a place to go', () => {
    assert.equal(appKeyForSpace('learning'), 'learning');
    assert.equal(appKeyForSpace('event-management'), 'events');
    const ids = EXTERNAL_SPACES.map((s) => s.id);
    for (const key of ['learning', 'events']) assert.ok(ids.includes(key), key);
});

test('main process, preload, scene and page are wired to the one manager', () => {
    const read = (...parts) => fs.readFileSync(path.join(__dirname, ...parts), 'utf8');
    const main = read('main.js');

    assert.match(main, /externalSpaces = new ExternalSpaceManager\(mainWindow\)/);
    assert.match(main, /ipcMain\.handle\('get-external-spaces'/);
    assert.match(main, /ipcMain\.on\('show-external-space'/);
    // Every other overlay hides the external ones when it opens.
    assert.ok(main.split('if (externalSpaces) externalSpaces.hideAll();').length - 1 >= 9);
    const preload = read('preload.js');
    for (const name of ['getExternalSpaces', 'showExternalSpace', 'hideExternalSpaces']) assert.match(preload, new RegExp(name));
    const scene = read('renderer', 'multiverse.js');
    assert.match(scene, /this\.spaces\[targetSpace\]\?\.external/);
    assert.match(scene, /window\.vibemind\.hideExternalSpaces\(\)/);
    assert.ok(read('renderer', 'index.html').includes('src="external-spaces.js"'));
});
