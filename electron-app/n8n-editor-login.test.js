const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const { editorLogin, isN8nPage, targetPath, signIn, limitToN8n, openEditor } = require('./n8n-editor');

const read = (file) => fs.readFileSync(path.join(__dirname, file), 'utf8');
const BASE = 'http://n8n.example.test:15678';
const ACCOUNT = { N8N_UI_EMAIL: ' ich@example.test ', N8N_UI_PASSWORD: 'geheim-zum-test' };

// main.js cannot be loaded outside Electron, so these read its source.
function handler(name) {
    const main = read('main.js');
    const start = main.indexOf(`ipcMain.handle('${name}'`);
    assert.ok(start > 0, `${name} is registered`);
    const next = main.indexOf('ipcMain.handle(', start + 1);
    return main.slice(start, next > 0 ? next : undefined);
}

/** Electron's net.request with a scripted answer; records what was sent. */
function fakeNet(answer) {
    const sent = [];
    return {
        sent,
        request(options) {
            const handlers = {};
            const req = {
                options, headers: {}, body: '',
                setHeader(k, v) { this.headers[k] = v; },
                on(name, fn) { handlers[name] = fn; },
                write(chunk) { this.body += chunk; },
                end() {
                    sent.push(this);
                    if (answer === 'network') return handlers.error && handlers.error(new Error('x'));
                    const res = { statusCode: answer, on(name, fn) { if (name === 'end') setImmediate(fn); } };
                    handlers.response(res);
                },
            };
            return req;
        },
    };
}

function fakeWindow() {
    const handlers = {};
    let openHandler = null;
    const loads = [];
    const contents = {
        session: { name: 'fenster-sitzung' },
        on(name, fn) { handlers[name] = fn; },
        setWindowOpenHandler(fn) { openHandler = fn; },
        loadURL(url) { loads.push(url); },
        executeJavaScript() { throw new Error('the account must not go into the page'); },
    };
    return {
        loads, contents, handlers, open: (url) => openHandler({ url }),
        win: { webContents: contents, loadURL: (url) => loads.push(url), isDestroyed: () => false },
    };
}

test('main.js and n8n-editor.js hand no written-in value over as a password or sign-in name', () => {
    // a key followed directly by a non-empty quoted string: a value in the code instead of from the
    // environment (an empty '' as "nothing set" is fine)
    const literal = /\b(password|passwort|passwd|pwd|emailOrLdapLoginId|N8N_UI_PASSWORD)\s*[:=]\s*(['"`])(?!\2)/gi;
    for (const file of ['main.js', 'n8n-editor.js']) {
        const source = read(file);
        const found = [...source.matchAll(literal)].map((m) => source.slice(0, m.index).split('\n').length);
        assert.deepEqual(found, [], `literal sign-in data in ${file} on line(s) ${found.join(', ')}`);
    }
});

test('the handler leaves signing in to n8n-editor.js and puts nothing into the page', () => {
    const body = handler('clawport:open-n8n-editor');
    assert.match(body, /require\('\.\/n8n-editor'\)/);
    assert.match(body, /editor\.openEditor\(\{/);
    assert.doesNotMatch(body, /executeJavaScript|emailOrLdapLoginId|N8N_UI_PASSWORD/);
    assert.doesNotMatch(read('n8n-editor.js'), /executeJavaScript/);
});

test('the account comes only from the environment, both halves or none', () => {
    assert.deepEqual(editorLogin(ACCOUNT), { email: 'ich@example.test', password: 'geheim-zum-test' });
    assert.equal(editorLogin({ N8N_UI_EMAIL: 'ich@example.test' }), null);
    assert.equal(editorLogin({ N8N_UI_PASSWORD: 'x' }), null);
    assert.equal(editorLogin({}), null);
});

test('signed in from the main process with the window session, then straight to the workflow', async () => {
    const net = fakeNet(200);
    const w = fakeWindow();
    const lines = [];
    const result = await openEditor({ win: w.win, base: BASE, workflowId: 'a b/c', env: ACCOUNT, net, shell: { openExternal() {} }, log: (l) => lines.push(l) });
    assert.deepEqual(result, { success: true, autoLogin: true });
    const [req] = net.sent;
    assert.equal(req.options.url, `${BASE}/rest/login`);
    assert.equal(req.options.method, 'POST');
    assert.equal(req.options.session, w.contents.session, 'the cookie lands in the window session');
    assert.equal(req.options.useSessionCookies, true);
    assert.deepEqual(JSON.parse(req.body), { emailOrLdapLoginId: 'ich@example.test', password: 'geheim-zum-test' });
    assert.deepEqual(w.loads, [`${BASE}/workflow/a%20b%2Fc`], 'no sign-in page in between');
    assert.doesNotMatch(JSON.stringify({ result, lines }), /geheim-zum-test|ich@example/, 'the account is neither returned nor logged');
});

test('no account: the sign-in page and a calm note, no request at all', async () => {
    const net = fakeNet(200);
    const w = fakeWindow();
    const result = await openEditor({ win: w.win, base: BASE, env: {}, net, shell: { openExternal() {} } });
    assert.equal(net.sent.length, 0);
    assert.deepEqual(w.loads, [`${BASE}/signin`]);
    assert.equal(result.autoLogin, false);
    assert.match(result.message, /anmelden/);
});

test('refused or unreachable: the sign-in page, a calm note, the account not repeated', async () => {
    for (const answer of [401, 429, 'network']) {
        const w = fakeWindow();
        const lines = [];
        const result = await openEditor({ win: w.win, base: BASE, env: ACCOUNT, net: fakeNet(answer), shell: { openExternal() {} }, log: (l) => lines.push(l) });
        assert.deepEqual(w.loads, [`${BASE}/signin`], String(answer));
        assert.equal(result.autoLogin, false);
        assert.match(result.message, /bitte dort anmelden/);
        assert.doesNotMatch(JSON.stringify({ result, lines }), /geheim-zum-test/);
    }
    const slow = { request: () => ({ setHeader() {}, on() {}, write() {}, end() {} }) };
    assert.deepEqual(await signIn({ net: slow, session: {}, base: BASE, login: { email: 'a', password: 'b' }, timeoutMs: 20 }), { ok: false, status: 0, reason: 'timeout' });
});

test('the window stays on n8n: other origins go to the system browser, n8n pages stay in it', () => {
    const w = fakeWindow();
    const external = [];
    limitToN8n(w.contents, BASE, { openExternal: (url) => external.push(url) });

    let stopped = false;
    w.handlers['will-navigate']({ preventDefault() { stopped = true; } }, `${BASE}/workflow/1`);
    assert.equal(stopped, false, 'inside n8n: let it go');
    w.handlers['will-navigate']({ preventDefault() { stopped = true; } }, 'https://anderswo.example.test/signin');
    assert.equal(stopped, true, 'a page elsewhere with /signin in it gets nothing');
    assert.deepEqual(external, ['https://anderswo.example.test/signin']);

    assert.deepEqual(w.open(`${BASE}/executions`), { action: 'deny' });
    assert.deepEqual(w.loads, [`${BASE}/executions`], 'an n8n page opens in this window');
    assert.deepEqual(w.open('https://docs.example.test/'), { action: 'deny' });
    assert.deepEqual(w.open('javascript:alert(1)'), { action: 'deny' });
    assert.deepEqual(external, ['https://anderswo.example.test/signin', 'https://docs.example.test/'], 'only http(s) goes out');

    assert.equal(isN8nPage(`${BASE}/x`, BASE), true);
    assert.equal(isN8nPage('http://n8n.example.test:15679/x', BASE), false, 'another port is another origin');
    assert.equal(isN8nPage('nichts', BASE), false);
    assert.equal(targetPath(), '/');
    assert.equal(targetPath(' 42 '), '/workflow/42');
});
