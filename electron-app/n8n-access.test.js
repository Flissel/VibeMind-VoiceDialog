const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const { n8nBaseUrl, n8nLogin, shouldRetryLogin, frameHeaderUrls } = require('./n8n-access');

test('the n8n address comes from N8N_API_URL and falls back to the local one', () => {
    assert.equal(n8nBaseUrl({}), 'http://localhost:15678');
    assert.equal(n8nBaseUrl({ N8N_API_URL: ' http://n8n.example.test:15678/ ' }), 'http://n8n.example.test:15678');
    assert.equal(n8nBaseUrl({ N8N_API_URL: 'https://n8n.example.test/rest' }), 'https://n8n.example.test');
    assert.equal(n8nBaseUrl({ N8N_API_URL: 'kein url' }), 'http://localhost:15678');
    assert.equal(n8nBaseUrl({ N8N_API_URL: 'file:///etc/passwd' }), 'http://localhost:15678');
});

test('a remote n8n over plain http is forwarded and then addressed as localhost', () => {
    const { forwardTarget } = require('./n8n-access');

    assert.deepEqual(forwardTarget({ N8N_API_URL: 'http://n8n.example.test:15678' }), { host: 'n8n.example.test', port: 15678 });
    assert.equal(forwardTarget({ N8N_API_URL: 'http://localhost:15678' }), null);
    assert.equal(forwardTarget({ N8N_API_URL: 'https://n8n.example.test' }), null, 'TLS needs no forward');
    assert.equal(forwardTarget({}), null);
    // After the forward the main process sets N8N_UI_URL; the UI then talks to localhost,
    // and the built-in "local" rules apply to the address, but the account still comes from the environment.
    const env = { N8N_API_URL: 'http://n8n.example.test:15678', N8N_UI_URL: 'http://localhost:15678', N8N_UI_EMAIL: 'ich@example.test', N8N_UI_PASSWORD: 'pw' };
    assert.equal(n8nBaseUrl(env), 'http://localhost:15678');
    assert.equal(n8nLogin(env).source, 'environment');
    const main = fs.readFileSync(path.join(__dirname, 'main.js'), 'utf8');
    assert.ok(main.indexOf("forwardTarget(process.env)") < main.indexOf('agentfarmManager = new AgentFarmManager('), 'forward before the manager is built');
});

test('sign-in data come from the environment', () => {
    const login = n8nLogin({ N8N_API_URL: 'http://n8n.example.test:15678', N8N_UI_EMAIL: ' ich@example.test ', N8N_UI_PASSWORD: 'pw' });

    assert.deepEqual(login, { email: 'ich@example.test', password: 'pw', source: 'environment' });
});

test('the built-in account is only tried against an n8n on this machine', () => {
    assert.equal(n8nLogin({}).source, 'local default');
    assert.equal(n8nLogin({ N8N_API_URL: 'http://127.0.0.1:15678' }).source, 'local default');
    assert.equal(n8nLogin({ N8N_API_URL: 'http://n8n.example.test:15678' }), null);
    assert.equal(n8nLogin({ N8N_API_URL: 'http://n8n.example.test:15678', N8N_UI_EMAIL: 'ich@example.test' }), null, 'half a login is none');
});

test('a refused sign-in is not repeated, a missing service is', () => {
    for (const refused of [401, 403, 429, 400, 404, 422]) assert.equal(shouldRetryLogin(refused), false, String(refused));
    for (const later of [500, 502, 503]) assert.equal(shouldRetryLogin(later), true, String(later));
});

test('the frame may show n8n wherever it runs', () => {
    assert.deepEqual(frameHeaderUrls({}), ['http://localhost:15678/*', 'http://localhost:4200/*']);
    assert.deepEqual(frameHeaderUrls({ N8N_API_URL: 'http://n8n.example.test:15678' }),
        ['http://localhost:15678/*', 'http://localhost:4200/*', 'http://n8n.example.test:15678/*']);
});

test('the session cookie is taken from the sign-in answer and merged into a request', () => {
    const { cookiePairs, mergeCookieHeader, sessionCookieUrls } = require('./n8n-access');
    const pairs = cookiePairs(['n8n-auth=abc.def; Path=/; HttpOnly; SameSite=Lax', 'kaputt', '=ohneName']);

    assert.deepEqual(pairs, ['n8n-auth=abc.def']);
    assert.equal(mergeCookieHeader(undefined, pairs), 'n8n-auth=abc.def');
    assert.equal(mergeCookieHeader('lang=de; n8n-auth=alt', pairs), 'lang=de; n8n-auth=abc.def', 'each name once, the session wins');
    assert.deepEqual(cookiePairs(undefined), []);
    assert.deepEqual(sessionCookieUrls({ N8N_API_URL: 'http://n8n.example.test:15678' }),
        ['http://n8n.example.test:15678/*', 'ws://n8n.example.test:15678/*']);
    assert.deepEqual(sessionCookieUrls({ N8N_API_URL: 'https://n8n.example.test' }),
        ['https://n8n.example.test/*', 'wss://n8n.example.test/*']);
});

test('manager, preload, main process and the Agent Farm page use the one address', () => {
    const read = (...parts) => fs.readFileSync(path.join(__dirname, ...parts), 'utf8');
    const manager = read('agentfarm-manager.js');

    assert.match(manager, /require\('\.\/n8n-access'\)/);
    assert.doesNotMatch(manager, /password: '/, 'no account written into the manager');
    assert.match(manager, /shouldRetryLogin\(res\.statusCode\)/);
    assert.match(read('agentfarm-preload.js'), /getN8nUrl/);
    assert.match(read('main.js'), /ipcMain\.handle\('agentfarm:n8n-url'/);
    const page = read('agentfarm', 'src', 'features', 'WorkflowBuilder.tsx');
    assert.doesNotMatch(page, /const n8nBaseUrl = 'http:\/\/localhost:15678'/);
    assert.match(page, /getN8nUrl/);
});
