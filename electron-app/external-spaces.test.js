const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const THREE = require('./renderer/lib/three.min.js');
const {
    EXTERNAL_SPACES, resolveSpaces, describeForRenderer, authFor, fromOwnPage, withAuthorization, pathTarget, parsePaths, ExternalSpaceManager,
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
                setWindowOpenHandler() {}, isDestroyed: () => false,
                handlers: {}, on(name, fn) { this.handlers[name] = fn; },
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
    electron.made[0].hooks[0].handler({ requestHeaders: {}, resourceType: 'mainFrame' }, (result) => { sent = result; });   // the first load
    assert.equal(sent.requestHeaders.Authorization, 'Bearer geheim-123');

    manager.hideAll();
    assert.equal(electron.window.view, null);
    assert.equal(manager.getIsVisible(), false);
});

test('a path names a place inside the space and nothing else', () => {
    const base = 'https://space.example.test/';
    const pages = ['/', '/liste', '/eintrag'];
    assert.equal(pathTarget(base, '/liste#nr-12', pages), 'https://space.example.test/liste#nr-12');
    assert.equal(pathTarget(base, '/eintrag/42', pages), 'https://space.example.test/eintrag/42');
    assert.equal(pathTarget(base, '/', pages), base);
    for (const bad of ['//evil.example/x', 'https://evil.example/', '/\\evil.example', 'liste', 'javascript:alert(1)', '', null, '/a b',
        '/logout', '/api/senden', '/liste?senden=1', '/eintrag/../logout', '/eintrag/%2e%2e/logout', '/eintragX', '/liste/./x/../../logout']) {
        assert.equal(pathTarget(base, bad, pages), '', String(bad));
    }
    assert.equal(pathTarget('', '/liste', pages), '', 'a space without an address has no paths');
    assert.equal(pathTarget(base, '/liste'), '', 'a space without listed pages takes none');
    assert.equal(pathTarget(base, '/liste', []), '');
});

test('the pages of a space come from the environment, not from this repository', () => {
    assert.deepEqual(parsePaths(' /, /liste ,/eintrag/alt,,//evil.example,/a/../b,kein-pfad,/x?y=1 '), ['/', '/liste', '/eintrag/alt']);
    assert.deepEqual(parsePaths(undefined), []);

    const sales = (env) => resolveSpaces(env).find((s) => s.id === 'sales');
    assert.deepEqual(sales({}).paths, [], 'without the list no path is taken');
    assert.deepEqual(sales({ SALES_UI_PATHS: '/,/liste' }).paths, ['/', '/liste']);
    assert.equal(JSON.stringify(describeForRenderer({ SALES_UI_PATHS: '/geheim' })).includes('geheim'), false, 'the renderer does not learn them');

    const source = fs.readFileSync(path.join(__dirname, 'external-spaces.js'), 'utf8');
    assert.doesNotMatch(source, /paths: \[/, 'no page of a space is listed in the code');
});

function salesManager(electron, extra = {}) {
    return new ExternalSpaceManager(electron.window, {
        BrowserView: electron.BrowserView, shell: electron.shell, logger: { log() {} },
        env: { SALES_UI_URL: 'https://space.example.test/', SALES_UI_PATHS: '/,/liste,/eintrag', ...extra },
    });
}

test('an open space goes to a path in its own session; a closed one goes there when it is opened', () => {
    const electron = fakeElectron();
    const manager = salesManager(electron);
    const targets = [];
    manager._load = (id) => { targets.push(manager._targets(manager.spaces.get(id))[0].url); manager.views.get(id).result = { ok: true }; };

    assert.equal(manager.goTo('sales', '//evil.example/'), false);
    assert.equal(manager.goTo('orders', '/x'), false, 'a local page has no paths');
    assert.equal(manager.goTo('sales', '/logout'), false, 'only the listed pages of the space');
    assert.equal(manager.goTo('marketing', '/liste'), false, 'a space without listed pages takes none');
    assert.equal(manager.goTo('sales', '/liste'), true);
    manager.show('sales');
    assert.deepEqual(targets, ['https://space.example.test/liste']);

    const went = [];
    electron.made[0].webContents.loadURL = (url) => went.push(url);
    manager.goTo('sales', '/eintrag/42');
    assert.deepEqual(went, ['https://space.example.test/eintrag/42']);
    assert.equal(electron.made[0].options.webPreferences.partition, 'persist:space-sales', 'same session, the sign-in stays');
    manager.show('sales');
    assert.equal(targets.length, 1, 'opening it again does not reload');
});

test('a path that ends on the sign-in page is loaded once more after the sign-in', () => {
    const electron = fakeElectron();
    const manager = salesManager(electron);
    manager._load = (id) => { manager.views.get(id).result = { ok: true }; };
    manager.show('sales');
    const went = [];
    electron.made[0].webContents.loadURL = (url) => went.push(url);
    const arrive = (url) => manager._navigated('sales', url);

    manager.goTo('sales', '/liste#nr-12');
    arrive('https://space.example.test/anmelden');          // the sign-in ran out
    arrive('https://space.example.test/anmelden');          // a wrong password: still there
    assert.equal(went.length, 1);
    arrive('https://space.example.test/');                  // signed in, the page went to its start
    assert.deepEqual(went, ['https://space.example.test/liste#nr-12', 'https://space.example.test/liste#nr-12']);
    arrive('https://space.example.test/liste');
    arrive('https://space.example.test/anderswo');
    assert.equal(went.length, 2, 'only once');

    manager.goTo('sales', '/eintrag/7');
    arrive('https://space.example.test/eintrag/7');         // arrived directly: nothing is repeated
    arrive('https://space.example.test/');
    assert.equal(went.length, 3);
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

test('Marketing sends its key to its own address only; without the variable nothing is sent', async () => {
    const env = { MARKETING_UI_URL: 'https://marketing.example.test:8460/mockup/', MARKETING_UI_KEY: ' erfunden-456 ' };
    const marketing = resolveSpaces(env).find((s) => s.id === 'marketing');
    assert.equal(marketing.bearerEnv, 'MARKETING_UI_KEY');

    const auth = authFor(marketing, env);
    assert.equal(auth.header, 'Bearer erfunden-456');
    assert.deepEqual(auth.urls, ['https://marketing.example.test:8460/*', 'wss://marketing.example.test:8460/*']);
    for (const other of ['https://sales.example.test/', 'https://marketing.example.test/', 'http://marketing.example.test:8460/']) {
        assert.ok(!auth.urls.some((pattern) => other.startsWith(pattern.slice(0, -1))), other);
    }
    assert.equal(authFor(marketing, { MARKETING_UI_URL: env.MARKETING_UI_URL }), null, 'no key in the environment');
    assert.equal(authFor(marketing, { ...env, MARKETING_UI_KEY: '   ' }), null, 'an empty key counts as none');
    for (const id of ['sales', 'learning', 'events']) {
        assert.equal(authFor(resolveSpaces({ ...env, SALES_UI_URL: 'https://sales.example.test/', LEARNING_UI_URL: 'https://l.example.test/', EVENT_UI_URL: 'https://e.example.test/' }).find((s) => s.id === id), env), null, id);
    }

    // the view gets the hook for its own address, and the check before loading sends the key
    // too (else it would see the 401 and show the status card); the page never sees the value
    const electron = fakeElectron();
    const checks = [];
    const manager = new ExternalSpaceManager(electron.window, {
        BrowserView: electron.BrowserView, shell: electron.shell, logger: { log() {} }, env,
    });
    manager._load = (id) => { checks.push(manager._targets(manager.spaces.get(id))); manager.views.get(id).result = { ok: true }; };
    manager.show('marketing');
    assert.equal(electron.made[0].hooks.length, 1);
    assert.deepEqual(electron.made[0].hooks[0].filter.urls, auth.urls);
    assert.equal(checks[0][0].url, 'https://marketing.example.test:8460/mockup/');
    assert.equal(checks[0][0].headers.Authorization, 'Bearer erfunden-456');
    assert.doesNotMatch(JSON.stringify(describeForRenderer(env)), /erfunden-456|MARKETING_UI_KEY/);

    const bare = new ExternalSpaceManager(electron.window, {
        BrowserView: electron.BrowserView, shell: electron.shell, logger: { log() {} }, env: { MARKETING_UI_URL: env.MARKETING_UI_URL },
    });
    const target = bare._targets(bare.spaces.get('marketing'))[0];
    assert.equal(target.headers, undefined, 'without the variable no header at all');
});

test('the key goes only with requests of the space\'s own page; a view with a key does not leave its origin', () => {
    const origins = ['https://marketing.example.test:8460'];
    const own = 'https://marketing.example.test:8460/mockup/';
    const page = (url) => ({ getURL: () => url });
    // the first load and a reload from the status card are the app's own
    assert.equal(fromOwnPage({ resourceType: 'mainFrame', webContents: page('') }, origins), true);
    assert.equal(fromOwnPage({ resourceType: 'mainFrame', webContents: page('data:text/html,karte') }, origins), true);
    // the space's own page: its navigations and its requests
    assert.equal(fromOwnPage({ resourceType: 'mainFrame', webContents: page(own) }, origins), true);
    assert.equal(fromOwnPage({ resourceType: 'xhr', webContents: page(own), frame: { url: own } }, origins), true);
    // a foreign page in the view, or a foreign iframe inside the space: no key
    assert.equal(fromOwnPage({ resourceType: 'xhr', webContents: page('https://fremd.example.test/') }, origins), false);
    assert.equal(fromOwnPage({ resourceType: 'mainFrame', webContents: page('https://fremd.example.test/') }, origins), false);
    assert.equal(fromOwnPage({ resourceType: 'xhr', webContents: page(own), frame: { url: 'https://fremd.example.test/w' } }, origins), false);
    assert.equal(fromOwnPage({ resourceType: 'xhr', webContents: page('') }, origins), false, 'a request without a page is not the space\'s');

    const env = { MARKETING_UI_URL: own, MARKETING_UI_KEY: 'erfunden-456' };
    const electron = fakeElectron();
    const opened = [];
    const manager = new ExternalSpaceManager(electron.window, {
        BrowserView: electron.BrowserView, shell: { openExternal: (url) => opened.push(url) }, logger: { log() {} }, env,
    });
    manager._load = (id) => { manager.views.get(id).result = { ok: true }; };
    manager.show('marketing');
    const view = electron.made[0];
    let sent;
    view.hooks[0].handler({ requestHeaders: { Accept: '*/*' }, resourceType: 'xhr', webContents: page('https://fremd.example.test/') }, (r) => { sent = r; });
    assert.deepEqual(sent.requestHeaders, { Accept: '*/*' }, 'a foreign page gets no key');
    view.hooks[0].handler({ requestHeaders: {}, resourceType: 'xhr', webContents: page(own), frame: { url: own } }, (r) => { sent = r; });
    assert.equal(sent.requestHeaders.Authorization, 'Bearer erfunden-456');

    const go = (url) => { let stopped = false; view.webContents.handlers['will-navigate']({ preventDefault: () => { stopped = true; } }, url); return stopped; };
    assert.equal(go('https://marketing.example.test:8460/kampagnen'), false, 'inside the space: stays');
    assert.equal(go('https://fremd.example.test/'), true, 'another origin: not in the view');
    assert.equal(go('javascript:alert(1)'), true);
    assert.deepEqual(opened, ['https://fremd.example.test/'], 'it opens in the browser instead');

    // a space without a key keeps its free navigation (sign-in pages of other hosts)
    const salesView = new ExternalSpaceManager(electron.window, {
        BrowserView: electron.BrowserView, shell: electron.shell, logger: { log() {} }, env: { SALES_UI_URL: 'https://sales.example.test/' },
    });
    salesView._load = (id) => { salesView.views.get(id).result = { ok: true }; };
    salesView.show('sales');
    assert.equal(electron.made[1].webContents.handlers['will-navigate'], undefined);
});
