const test = require('node:test');
const assert = require('node:assert/strict');

const CONFIG_PATH = require.resolve('./supabase-config');

const ORIGINAL_URL = process.env.SUPABASE_URL;
const ORIGINAL_KEY = process.env.SUPABASE_ANON_KEY;

function freshRequire(env) {
    delete require.cache[CONFIG_PATH];
    if (env.url === undefined) delete process.env.SUPABASE_URL;
    else process.env.SUPABASE_URL = env.url;
    if (env.key === undefined) delete process.env.SUPABASE_ANON_KEY;
    else process.env.SUPABASE_ANON_KEY = env.key;
    return require('./supabase-config');
}

function restoreEnv() {
    delete require.cache[CONFIG_PATH];
    if (ORIGINAL_URL === undefined) delete process.env.SUPABASE_URL;
    else process.env.SUPABASE_URL = ORIGINAL_URL;
    if (ORIGINAL_KEY === undefined) delete process.env.SUPABASE_ANON_KEY;
    else process.env.SUPABASE_ANON_KEY = ORIGINAL_KEY;
}

test('supabase-config falls back to the known dev VM URL and JWT when no env vars are set', (t) => {
    t.after(restoreEnv);
    const { SUPABASE_URL, SUPABASE_ANON_KEY } = freshRequire({});

    assert.equal(SUPABASE_URL, 'http://127.0.0.1:54321');
    assert.match(SUPABASE_ANON_KEY, /^eyJ/, 'fallback key looks like a JWT');
});

test('supabase-config honors SUPABASE_URL / SUPABASE_ANON_KEY overrides', (t) => {
    t.after(restoreEnv);
    const { SUPABASE_URL, SUPABASE_ANON_KEY } = freshRequire({
        url: 'https://example.supabase.co',
        key: 'test-anon-key',
    });

    assert.equal(SUPABASE_URL, 'https://example.supabase.co');
    assert.equal(SUPABASE_ANON_KEY, 'test-anon-key');
});

test('supabase-client.js and preload.js both read from the same supabase-config module (single source of truth)', () => {
    const fs = require('node:fs');
    const path = require('node:path');

    const clientSource = fs.readFileSync(path.join(__dirname, 'supabase-client.js'), 'utf8');
    const preloadSource = fs.readFileSync(path.join(__dirname, 'preload.js'), 'utf8');

    assert.match(clientSource, /require\(['"]\.\/supabase-config['"]\)/);
    // Sandboxed preload cannot require local files: it gets the values via IPC from the main process.
    assert.doesNotMatch(preloadSource, /require\(['"]\.\//);
    assert.match(preloadSource, /sendSync\(['"]vibemind:supabase-config['"]\)/);

    // The fallback values must not be duplicated as literals in either
    // consumer — that duplication is exactly the drift this module exists
    // to remove.
    assert.doesNotMatch(clientSource, /192\.168\.178\.65/);
    assert.doesNotMatch(preloadSource, /192\.168\.178\.65/);
});

test('renderer/universe_canvas.js no longer hardcodes a Supabase URL or the "anon" placeholder key', () => {
    const fs = require('node:fs');
    const path = require('node:path');

    const rendererSource = fs.readFileSync(
        path.join(__dirname, 'renderer', 'universe_canvas.js'),
        'utf8',
    );

    assert.doesNotMatch(rendererSource, /192\.168\.178\.65/);
    assert.doesNotMatch(rendererSource, /'apikey':\s*'anon'/);
    assert.match(rendererSource, /window\.vibemind\s*&&\s*window\.vibemind\.supabase/);
});

test('buildRealtimeOptions hands the ws package to Realtime when the runtime has no global WebSocket (Electron main = Node 20)', () => {
    const { buildRealtimeOptions } = require('./supabase-config');
    const fakeWs = function FakeWebSocket() {};
    const options = buildRealtimeOptions({ nativeWebSocket: undefined, loadWs: () => fakeWs });

    assert.equal(options.transport, fakeWs);
    assert.deepEqual(options.params, { eventsPerSecond: 10 });
});

test('buildRealtimeOptions leaves the transport alone when a global WebSocket exists', () => {
    const { buildRealtimeOptions } = require('./supabase-config');
    let loaded = false;
    const options = buildRealtimeOptions({
        nativeWebSocket: function NativeWebSocket() {},
        loadWs: () => { loaded = true; return null; },
    });

    assert.equal('transport' in options, false);
    assert.equal(loaded, false, 'ws is not even loaded');
});

test('supabase-client.js builds its Realtime options through buildRealtimeOptions', () => {
    const fs = require('node:fs');
    const path = require('node:path');
    const clientSource = fs.readFileSync(path.join(__dirname, 'supabase-client.js'), 'utf8');

    assert.match(clientSource, /realtime:\s*buildRealtimeOptions\(\)/);
});