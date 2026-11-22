const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const http = require('node:http');
const path = require('node:path');

const { remoteTarget, forwardRemoteLaura } = require('./laura-local-forward');
const quiet = { log() {} };

test('only an http service on another machine needs the forward', () => {
    assert.deepEqual(remoteTarget({ LAURA_URL: 'http://laura.example.test:8765' }), { host: 'laura.example.test', port: 8765 });
    assert.deepEqual(remoteTarget({ LAURA_URL: ' http://10.0.0.5 ' }), { host: '10.0.0.5', port: 80 });
    for (const local of ['http://127.0.0.1:8765', 'http://localhost:9000', 'http://[::1]:8765']) {
        assert.equal(remoteTarget({ LAURA_URL: local }), null, local);
    }
    assert.equal(remoteTarget({}), null);
    assert.equal(remoteTarget({ LAURA_URL: 'kein url' }), null);
    assert.equal(remoteTarget({ LAURA_URL: 'https://laura.example.test' }), null, 'TLS is not forwarded blindly');
});

test('the forward carries a request, header included, to the service behind it', async (t) => {
    const { startForward } = require('./laura-local-forward');
    const seen = [];
    const service = http.createServer((req, res) => {
        seen.push({ url: req.url, token: req.headers['x-laura-token'] });
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end('{"ok":true}');
    });
    await new Promise((resolve) => service.listen(0, '127.0.0.1', resolve));
    const forward = await startForward({ host: '127.0.0.1', port: service.address().port }, { preferredPort: 0, logger: quiet });
    t.after(async () => { await forward.close(); service.close(); });

    assert.notEqual(forward.port, service.address().port);
    assert.match(forward.url, /^http:\/\/127\.0\.0\.1:\d+$/);
    const response = await fetch(`${forward.url}/projects`, { headers: { 'X-Laura-Token': 'abc' } });

    assert.equal(response.status, 200);
    assert.deepEqual(await response.json(), { ok: true });
    assert.deepEqual(seen, [{ url: '/projects', token: 'abc' }]);
});

test('a busy preferred port does not stop the forward', async (t) => {
    const { startForward } = require('./laura-local-forward');
    const busy = http.createServer(() => {});
    await new Promise((resolve) => busy.listen(0, '127.0.0.1', resolve));
    const forward = await startForward({ host: '127.0.0.1', port: 9 }, { preferredPort: busy.address().port, logger: quiet });
    t.after(async () => { await forward.close(); busy.close(); });

    assert.notEqual(forward.port, busy.address().port);
});
test('a local or missing LAURA_URL is left alone', async () => {
    const env = { LAURA_URL: 'http://127.0.0.1:8765' };
    assert.equal(await forwardRemoteLaura(env, { logger: quiet }), null);
    assert.equal(env.LAURA_URL, 'http://127.0.0.1:8765');
    assert.equal(await forwardRemoteLaura({}, { logger: quiet }), null);
});

test('the main process starts the forward before the video overlay is built', () => {
    const main = fs.readFileSync(path.join(__dirname, 'main.js'), 'utf8');

    assert.match(main, /forwardRemoteLaura\(process\.env\)/);
    assert.ok(main.indexOf('forwardRemoteLaura(process.env)') < main.indexOf('videoManager = new VideoManager'),
        'forward first, then the overlay reads LAURA_URL');
});
