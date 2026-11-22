const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const { keyFile, readAccessKey, mintToken, accessCookie } = require('./learning-access');

const KEY = 'beispiel-schluessel-nur-fuer-den-test-0123456789';
// Produced by the learning space's own code (spaces/learning/huelle/zugang.py, token_erzeugen(KEY, 1800000000)).
const TOKEN = 'MTgwMjU5MjAwMC45ZWY1N2U4MDU4MjYwM2E1YmEzYTJlODI3NDdlM2M5ZGJhMWVkMzlhMTA4NWNmZWNkN2MyMGNlNjlmODkxOWQ4';

test('the token is the one the learning space itself would issue', () => {
    assert.equal(mintToken(KEY, 1800000000 * 1000), TOKEN);
});

test('the key file is the one on this machine unless the environment names another', () => {
    assert.equal(keyFile({ LOCALAPPDATA: 'C:\\X' }), path.join('C:\\X', 'VibeMind', 'learning-huelle', 'huelle.env'));
    assert.equal(keyFile({ LOCALAPPDATA: 'C:\\X', LEARNING_HUELLE_ENV: ' D:\\a\\h.env ' }), 'D:\\a\\h.env');
    assert.equal(keyFile({}), '');
});

test('the access key is read from the file; the service key only stands in when there is no own key', () => {
    const file = (text) => () => text;
    assert.equal(readAccessKey('x', file(`A=1\r\nLEARNING_HUELLE_ZUGANG_SCHLUESSEL= "${KEY}" \r\nLEARNHOUSE_LEARNING_SERVICE_KEY=dienst\r\n`)), KEY);
    assert.equal(readAccessKey('x', file('LEARNHOUSE_LEARNING_SERVICE_KEY=dienst-schluessel\n')), 'dienst-schluessel');
    assert.equal(readAccessKey('x', file('# LEARNING_HUELLE_ZUGANG_SCHLUESSEL=auskommentiert\n')), '');
    assert.equal(readAccessKey('x', () => { throw new Error('ENOENT'); }), '', 'a missing file is no key');
    assert.equal(readAccessKey('', file(`LEARNING_HUELLE_ZUGANG_SCHLUESSEL=${KEY}`)), '', 'no path, no read');
});

test('the cookie carries the attributes the learning space sets itself', () => {
    const cookie = accessCookie('https://lernen.example.test:8450/lernen/', KEY, 1800000000 * 1000);

    assert.deepEqual(cookie, {
        url: 'https://lernen.example.test:8450/',
        name: 'huelle_zugang',
        value: TOKEN,
        path: '/',
        httpOnly: true,
        secure: true,
        sameSite: 'strict',
        expirationDate: 1800000000 + 30 * 24 * 3600,
    });
});

test('no cookie without a key, and none for an address that is not https', () => {
    assert.equal(accessCookie('https://lernen.example.test/lernen/', '', 1), null);
    assert.equal(accessCookie('http://lernen.example.test/lernen/', KEY, 1), null, 'the cookie is Secure');
    assert.equal(accessCookie('kein url', KEY, 1), null);
});

test('the learning entry asks for the access cookie and gets it before the page loads', async () => {
    const { EXTERNAL_SPACES, ExternalSpaceManager } = require('./external-spaces');
    assert.equal(EXTERNAL_SPACES.find((space) => space.id === 'learning').access, 'learning-huelle');
    assert.equal(EXTERNAL_SPACES.filter((space) => space.access).length, 1, 'only the learning space');

    const order = [];
    const session = { cookies: { set: async (cookie) => { order.push(`cookie:${cookie.name}`); } }, webRequest: { onBeforeSendHeaders() {} } };
    class View { constructor() { this.webContents = { session, setWindowOpenHandler() {}, on() {} }; } setBounds() {} }
    const manager = new ExternalSpaceManager(null, {
        BrowserView: View, shell: {}, logger: { log() {} },
        env: { LEARNING_UI_URL: 'https://lernen.example.test:8450/lernen/' },
        accessCookies: { 'learning-huelle': (url) => ({ url, name: 'huelle_zugang', value: 'x' }) },
    });
    manager._load = (id) => { order.push(`load:${id}`); };
    manager._create('learning');
    await manager.ready('learning');

    assert.deepEqual(order, ['cookie:huelle_zugang', 'load:learning']);

    // The check before loading runs outside the view's session. Seen in the app on 2026-11-22:
    // cookie set, check without it, card "HTTP 403". The check must carry the same cookie.
    const [target] = manager._targets(manager.spaces.get('learning'));
    assert.deepEqual(target.headers, { Cookie: 'huelle_zugang=x' });
    const { checkOverlayTarget } = require('./overlay-status');
    const seen = [];
    const result = await checkOverlayTarget(target, {
        fetchImpl: async (url, options) => {
            seen.push(options.headers);
            return { ok: Boolean(options.headers && options.headers.Cookie), status: 403, body: { cancel: async () => {} } };
        },
    });
    assert.deepEqual(seen, [{ Cookie: 'huelle_zugang=x' }]);
    assert.equal(result.ok, true);
});

test('a space without an access cookie is checked without extra headers', () => {
    const { ExternalSpaceManager } = require('./external-spaces');
    const manager = new ExternalSpaceManager(null, {
        BrowserView: class {}, shell: {}, logger: { log() {} },
        env: { SALES_UI_URL: 'https://sales.example.test/', LEARNING_UI_URL: 'https://lernen.example.test/lernen/' },
    });
    assert.equal('headers' in manager._targets(manager.spaces.get('sales'))[0], false);
    assert.equal('headers' in manager._targets(manager.spaces.get('learning'))[0], false, 'nothing issued yet');
});

test('a failing cookie store still loads the page (it then shows its own refusal)', async () => {
    const { ExternalSpaceManager } = require('./external-spaces');
    const order = [];
    const session = { cookies: { set: async () => { throw new Error('store'); } }, webRequest: { onBeforeSendHeaders() {} } };
    class View { constructor() { this.webContents = { session, setWindowOpenHandler() {}, on() {} }; } setBounds() {} }
    const manager = new ExternalSpaceManager(null, {
        BrowserView: View, shell: {}, logger: { log() {} },
        env: { LEARNING_UI_URL: 'https://lernen.example.test:8450/lernen/' },
        accessCookies: { 'learning-huelle': (url) => ({ url, name: 'huelle_zugang', value: 'x' }) },
    });
    manager._load = (id) => { order.push(`load:${id}`); };
    manager._create('learning');
    await manager.ready('learning');

    assert.deepEqual(order, ['load:learning']);
});

test('the key never reaches the renderer or the log', () => {
    const source = fs.readFileSync(path.join(__dirname, 'external-spaces.js'), 'utf8');
    assert.doesNotMatch(source, /log\([^)]*cookie\.value/);
    assert.doesNotMatch(fs.readFileSync(path.join(__dirname, 'preload.js'), 'utf8'), /huelle|learning-access/);
});
