// Marks of the clicks and the click on the picture in the Desktop space. Invented values only.
const test = require('node:test');
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const { EventEmitter } = require('node:events');

const { createDesktopKlicks, createClickWitness, registerDesktopKlicks, zeichen, brainPort, HEADER, WITNESS_MS } = require('./desktop-klicks');
const KM = require('./renderer/klick-marken');

const KEY = 'erfundener-schluessel-mit-mehr-als-32-zeichen';
const read = (...parts) => fs.readFileSync(path.join(__dirname, ...parts), 'utf8');

/** http.request stand-in: keeps what was asked, answers with `reply` ({ status, body }). */
function fakeRequest(reply) {
    const asked = [];
    const request = (options, onResponse) => {
        const req = new EventEmitter();
        const sent = [];
        req.write = (d) => sent.push(d);
        req.destroy = () => {};
        req.end = () => {
            asked.push({ ...options, body: sent.length ? JSON.parse(Buffer.concat(sent).toString('utf8')) : undefined });
            const answer = typeof reply === 'function' ? reply(options) : reply;
            if (answer === 'error') { setImmediate(() => req.emit('error', new Error('x'))); return; }
            if (answer === 'hold') return;
            const res = new EventEmitter();
            res.statusCode = answer.status;
            setImmediate(() => { onResponse(res); res.emit('data', Buffer.from(JSON.stringify(answer.body))); res.emit('end'); });
        };
        return req;
    };
    return { request, asked };
}

test('the sign has the form of the Brain: "<sec>.<hmac>" over "<sec>\\nhand-klick <x> <y>"', () => {
    const expected = crypto.createHmac('sha256', KEY).update('1795600000\nhand-klick 300 -400').digest('hex');
    assert.equal(zeichen(KEY, 300, -400, 1795600000.7), `1795600000.${expected}`);
    assert.equal(brainPort({}), 5000);
    assert.equal(brainPort({ BRAIN_PORT: '5123' }), 5123);
    assert.equal(brainPort({ BRAIN_PORT: 'x' }), 5000);
});

test('a hand click goes to the Brain from the main process: signed, no Origin, no Sec-Fetch-Site, its answer back', async () => {
    const fake = fakeRequest({ status: 200, body: { x: 300, y: 400, ok: true, echt: true, trocken: false, grund: null, task_id: 'dt-1', plan_id: 'hand-1' } });
    const api = createDesktopKlicks({ env: { VIBEMIND_EINGABE_SCHLUESSEL: KEY }, now: () => 1795600000, request: fake.request });
    const answer = await api.handKlick(300, 400);
    assert.equal(answer.ok, true);
    assert.equal(answer.task_id, 'dt-1');
    const call = fake.asked[0];
    assert.equal(call.host, '127.0.0.1');
    assert.equal(call.port, 5000);
    assert.equal(call.method, 'POST');
    assert.equal(call.path, '/api/desktop/hand-klick');
    assert.deepEqual(call.body, { x: 300, y: 400 });
    assert.equal(call.headers[HEADER], zeichen(KEY, 300, 400, 1795600000));
    const names = Object.keys(call.headers).map((n) => n.toLowerCase());
    assert.ok(!names.includes('origin') && !names.includes('sec-fetch-site'));
    assert.doesNotMatch(JSON.stringify(answer), new RegExp(KEY));
});

test('no click goes out without the key, with a bad place, or while one is running; a refusal keeps its reason', async () => {
    const fake = fakeRequest('hold');
    const none = createDesktopKlicks({ env: {}, request: fake.request });
    assert.deepEqual(await none.handKlick(1, 2), { ok: false, x: 1, y: 2, grund: 'nicht_belegt' });
    const short = createDesktopKlicks({ env: { VIBEMIND_EINGABE_SCHLUESSEL: 'kurz' }, request: fake.request });
    assert.equal((await short.handKlick(1, 2)).grund, 'nicht_belegt');
    const api = createDesktopKlicks({ env: { VIBEMIND_EINGABE_SCHLUESSEL: KEY }, request: fake.request });
    for (const [x, y] of [[1.5, 2], ['1', 2], [20001, 0], [0, -20001], [null, 1]]) {
        assert.equal((await api.handKlick(x, y)).grund, 'eingabe_ungueltig', `${x},${y}`);
    }
    assert.equal(fake.asked.length, 0);
    api.handKlick(5, 5);                                   // held by the fake: still running
    assert.equal((await api.handKlick(6, 6)).grund, 'klick_laeuft');
    assert.equal(fake.asked.length, 1);

    const refused = createDesktopKlicks({ env: { VIBEMIND_EINGABE_SCHLUESSEL: KEY }, request: fakeRequest({ status: 403, body: { grund: 'nicht_belegt' } }).request });
    assert.deepEqual(await refused.handKlick(7, 8), { ok: false, x: 7, y: 8, grund: 'nicht_belegt' });
    const gone = createDesktopKlicks({ env: { VIBEMIND_EINGABE_SCHLUESSEL: KEY }, request: fakeRequest('error').request });
    assert.equal((await gone.handKlick(7, 8)).grund, 'gehirn_nicht_erreichbar');
});

test('the clicks of the book are asked with seit, and a failure is an empty list', async () => {
    const fake = fakeRequest({ status: 200, body: { success: true, stopped: false, klicks: [{ x: 1, y: 2, zeit: 10, ok: true, quelle: 'agent' }] } });
    const api = createDesktopKlicks({ env: { BRAIN_PORT: '5001' }, request: fake.request });
    assert.equal((await api.klicks(1795599990.25)).klicks.length, 1);
    assert.equal(fake.asked[0].path, '/api/desktop/klicks?seit=1795599990.25');
    assert.equal(fake.asked[0].port, 5001);
    await api.klicks(NaN);
    assert.equal(fake.asked[1].path, '/api/desktop/klicks');
    const missing = createDesktopKlicks({ request: fakeRequest({ status: 200, body: { success: false, error: 'aufgabenbuch_fehlt', klicks: [] } }).request });
    assert.deepEqual((await missing.klicks()).klicks, []);
});

test('only the window of the app may ask, and a click is signed only after a real press at that place', async () => {
    const handlers = {};
    const ipcMain = { handle: (name, fn) => { handlers[name] = fn; } };
    const fake = fakeRequest({ status: 200, body: { ok: true } });
    let clock = 1000;
    const inputs = {};
    const own = { getZoomFactor: () => 1, on: (name, fn) => { inputs[name] = fn; } };
    const api = registerDesktopKlicks(ipcMain, (event) => event.sender === own,
        { env: { VIBEMIND_EINGABE_SCHLUESSEL: KEY }, request: fake.request, nowMs: () => clock, isShown: () => true });
    api.watch(own);
    const press = (x, y, extra = {}) => inputs['input-event']({}, { type: 'mouseDown', button: 'left', x, y, ...extra });
    const click = (clientX, clientY) => handlers['desktop:hand-klick']({ sender: own }, { x: 1, y: 2, clientX, clientY });

    assert.deepEqual(Object.keys(handlers).sort(), ['desktop:hand-klick', 'desktop:klicks']);
    assert.deepEqual(await handlers['desktop:hand-klick']({ sender: {} }, { x: 1, y: 2 }), { ok: false, grund: 'fremd' });
    assert.equal((await handlers['desktop:klicks']({ sender: {} }, 0)).error, 'fremd');

    // a script in the renderer asks without a press: nothing is signed, nothing goes out
    assert.equal((await click(100, 200)).grund, 'kein_echter_klick');
    press(100, 200);
    assert.equal((await click(160, 200)).grund, 'kein_echter_klick', 'the press was elsewhere');
    assert.equal((await click(102, 199)).ok, true, 'a real press at the place: signed and sent');
    assert.equal((await click(102, 199)).grund, 'kein_echter_klick', 'each press is used once');
    press(300, 300);
    clock += WITNESS_MS + 1;
    assert.equal((await click(300, 300)).grund, 'kein_echter_klick', 'a stale press counts no more');
    press(300, 300, { button: 'right' });
    assert.equal((await click(300, 300)).grund, 'kein_echter_klick', 'a right press is no click');
    inputs['input-event']({}, { type: 'mouseUp', button: 'left', x: 300, y: 300 });
    assert.equal((await click(300, 300)).grund, 'kein_echter_klick');
    assert.equal(fake.asked.length, 1);
});

test('a click is signed only while the main process holds the Desktop space in front', async () => {
    const handlers = {};
    const ipcMain = { handle: (name, fn) => { handlers[name] = fn; } };
    const fake = fakeRequest({ status: 200, body: { ok: true } });
    const inputs = {};
    const own = { getZoomFactor: () => 1, on: (name, fn) => { inputs[name] = fn; } };
    let shown = false;
    const api = registerDesktopKlicks(ipcMain, (event) => event.sender === own,
        { env: { VIBEMIND_EINGABE_SCHLUESSEL: KEY }, request: fake.request, nowMs: () => 0, isShown: () => shown });
    api.watch(own);
    const pressAndClick = () => {
        inputs['input-event']({}, { type: 'mouseDown', button: 'left', x: 50, y: 60 });
        return handlers['desktop:hand-klick']({ sender: own }, { x: 7, y: 8, clientX: 50, clientY: 60 });
    };
    assert.deepEqual(await pressAndClick(), { ok: false, x: 7, y: 8, grund: 'desktop_nicht_sichtbar' });
    assert.equal(fake.asked.length, 0, 'another space in front: nothing goes out, even after a real press');
    shown = true;
    assert.equal((await pressAndClick()).ok, true);
    assert.equal(fake.asked.length, 1);

    const without = {};
    registerDesktopKlicks({ handle: (name, fn) => { without[name] = fn; } }, () => true, { env: { VIBEMIND_EINGABE_SCHLUESSEL: KEY }, request: fake.request });
    assert.equal((await without['desktop:hand-klick']({ sender: own }, { x: 1, y: 1, clientX: 0, clientY: 0 })).grund, 'desktop_nicht_sichtbar', 'without the state: refused');
    assert.equal(KM.reasonText('desktop_nicht_sichtbar'), 'Desktop nicht im Vordergrund');
});

test('the main process knows by itself whether the Desktop space is in front', () => {
    const main = read('main.js');
    assert.match(main, /registerDesktopKlicks\([\s\S]{0,200}\{ isShown: desktopPictureInFront \}\)/);
    const fn = main.slice(main.indexOf('function desktopPictureInFront()'));
    const body = fn.slice(0, fn.indexOf('\n}\n'));
    assert.match(body, /if \(currentSpace !== 'desktop'\) return false;/);
    assert.match(body, /isMinimized\(\)/);
    for (const view of ['dashboardManager', 'rowboatManager', 'externalSpaces', 'videoManager', 'flowzenManager']) assert.match(body, new RegExp(view));
});

test('the witness compares window pixels: client coordinates times the zoom', () => {
    const w = createClickWitness(() => 0);
    w.record({ type: 'mouseDown', button: 'left', x: 300, y: 150 });
    assert.equal(w.take(200, 100, 1.5), true);
    assert.equal(w.take(Number.NaN, 1), false);
});

test('a mark: colour by source, refused red with its reason, dry run as outline, fading over 30 s', () => {
    const agent = KM.markOf({ x: 10, y: 20, zeit: 100, ok: true, quelle: 'agent', task_id: 'dt-a' });
    const hand = KM.markOf({ x: 10, y: 20, zeit: 100, ok: true, quelle: 'hand', hand: true });
    const dry = KM.markOf({ x: 10, y: 20, zeit: 100, ok: true, quelle: 'trocken', hand: true });
    const refused = KM.markOf({ x: 10, y: 20, zeit: 100, ok: false, quelle: 'hand', grund: 'gesperrt' });
    assert.equal(KM.styleOf(agent, 100).rgb, KM.COLORS.agent);
    assert.equal(KM.styleOf(agent, 100).filled, true);
    assert.equal(KM.styleOf(hand, 100).rgb, KM.COLORS.hand);
    assert.deepEqual([KM.styleOf(dry, 100).filled, KM.styleOf(dry, 100).dashed], [false, true]);
    assert.equal(KM.styleOf(refused, 100).rgb, KM.COLORS.abgelehnt);
    assert.equal(KM.styleOf(refused, 100).text, 'gesperrtes Fenster');
    assert.equal(KM.reasonText('not_aus'), 'Not-Aus');
    assert.equal(KM.reasonText('aufgabe_laeuft'), 'Agent arbeitet');
    assert.equal(KM.reasonText('etwas Fremdes'), 'abgelehnt', 'an unknown reason is never shown as it came');
    assert.ok(Math.abs(KM.styleOf(agent, 115).alpha - 0.5) < 1e-9);
    assert.equal(KM.styleOf(agent, 130), null);
    assert.ok(KM.styleOf(KM.markOf({ x: 1, y: 1, zeit: 100, ok: null, quelle: 'agent' }), 100).alpha < 1, 'running: half strong');
    assert.equal(KM.markOf({ x: 'a', y: 1 }), null);
});

test('a desktop point lands on its monitor, shifted by the monitor offset and the letterbox', () => {
    const monitors = [
        { offsetX: 0, offsetY: 0, width: 1920, height: 1080, boxW: 960, boxH: 540, name: 'eins' },
        { offsetX: 1920, offsetY: 0, width: 1920, height: 1080, boxW: 960, boxH: 640, name: 'zwei' },
    ];
    const one = KM.placeOf(monitors, 960, 540);
    assert.equal(one.monitor.name, 'eins');
    assert.deepEqual([one.cx, one.cy], [480, 270]);
    const two = KM.placeOf(monitors, 1920 + 1920, 1080 - 1);
    assert.equal(two, null, 'outside every monitor');
    const second = KM.placeOf(monitors, 1920 + 960, 540);
    assert.equal(second.monitor.name, 'zwei');
    assert.deepEqual([second.cx, second.cy], [480, 320], 'bars of 50 px above and below');
});

function fakeWindow(answers) {
    const timers = [];
    const asked = [];
    const win = {
        Date: { now: () => 100000 },
        setTimeout: (fn, ms) => { const t = { fn, ms }; timers.push(t); return t; },
        clearTimeout: (t) => { const i = timers.indexOf(t); if (i >= 0) timers.splice(i, 1); },
        setInterval: () => 'zeichnen', clearInterval: () => {},
        vibemind: { desktopKlicks: (seit) => { asked.push(seit); return Promise.resolve(answers.shift() || { klicks: [] }); } },
    };
    return { win, timers, asked };
}

test('while shown the book is asked with the newest zeit; stop ends it; the book entry replaces the answer mark', async () => {
    const { win, timers, asked } = fakeWindow([
        { success: true, stopped: true, klicks: [{ x: 1, y: 2, zeit: 99.5, ok: true, quelle: 'agent', task_id: 'dt-a' }] },
        { success: true, stopped: false, klicks: [{ x: 3, y: 4, zeit: 99.8, ok: false, quelle: 'hand', hand: true, grund: 'gesperrt', task_id: 'dt-h' }] },
    ]);
    const marks = KM.create(win, { getElementById: () => null });
    const answerMark = marks.add({ x: 3, y: 4, ok: false, grund: 'gesperrt', task_id: 'dt-h' });
    assert.equal(answerMark.quelle, 'hand');
    assert.equal(marks.marks.size, 1);

    marks.start(null);
    await new Promise((r) => setImmediate(r));
    assert.deepEqual(asked, [undefined], 'the first time without seit: the last two minutes');
    assert.equal(marks.stopped(), true);
    timers.shift().fn();
    await new Promise((r) => setImmediate(r));
    assert.deepEqual(asked, [undefined, 99.5]);
    assert.equal(marks.marks.size, 2, 'the answer mark was replaced by the book entry of the same click');
    assert.equal(marks.stopped(), false);

    marks.stop();
    assert.equal(timers.length, 0);
    assert.equal(marks.isActive(), false);
});

test('the Desktop view sends the click through the Brain and stops asking when the space is left', () => {
    const scene = read('renderer', 'multiverse.js');
    assert.doesNotMatch(scene, /8007\/api\/automation\/click/, 'the old route that clicks without block list is gone');
    assert.match(scene, /await window\.vibemind\.handKlick\(realX, realY, e\.clientX, e\.clientY\)/);
    assert.match(scene, /marks\.add\(\{ x: realX, y: realY,/);
    assert.match(scene, /markCanvas\.className = 'klick-marken-canvas';/);
    assert.match(scene, /if \(this\.currentSpace === 'desktop' && targetSpace !== 'desktop'\) \{\s*\/\/[^\n]*\n\s*if \(this\._desktopStream\) this\._desktopStream\.stop\(\);/);
    assert.match(scene, /exitDesktopDashboard\(\) \{\s*if \(!this\._insideDesktopDashboard\) return;\s*if \(this\._desktopStream\) this\._desktopStream\.stop\(\);/);
    assert.match(scene, /if \(this\._desktopStream\) this\._desktopStream\.start\(\);/);
    assert.match(scene, /if \(!_desktopStreamActive \|\| gen !== _desktopStreamGen\) return;/);

    const preload = read('preload.js');
    assert.match(preload, /desktopKlicks: \(seit\) => ipcRenderer\.invoke\('desktop:klicks', seit\)/);
    assert.match(preload, /handKlick: \(x, y, clientX, clientY\) => ipcRenderer\.invoke\('desktop:hand-klick', \{ x, y, clientX, clientY \}\)/);
    assert.doesNotMatch(preload, /EINGABE_SCHLUESSEL/, 'the key never reaches the renderer');
    const main = read('main.js');
    assert.match(main, /registerDesktopKlicks\(ipcMain, \(event\) => Boolean\(mainWindow\) && !mainWindow\.isDestroyed\(\) && event\.sender === mainWindow\.webContents,/);
    assert.match(main, /mainWindow = new BrowserWindow\(\{[\s\S]*?\n    \}\);\s*\n\s*\/\/[^\n]*\n\s*if \(desktopKlicks\) desktopKlicks\.watch\(mainWindow\.webContents\);/, 'the window is watched as soon as it exists');
    const html = read('renderer', 'index.html');
    assert.ok(html.indexOf('src="klick-marken.js"') > html.indexOf('src="multiverse.js"'));
});
