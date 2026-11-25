// A layout writes x/y only for the cards it moved (universe_canvas.js _persistPositions).
// Invented ids, no real data.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function canvasClass() {
    const calls = [];
    const window = { vibemind: { supabase: { url: 'http://db.invalid', anonKey: 'k' } } };
    const context = {
        window, console: { log() {}, warn() {} },
        fetch: (url, init) => { calls.push({ url, body: JSON.parse(init.body) }); return Promise.resolve({ ok: true }); },
    };
    vm.runInNewContext(fs.readFileSync(path.join(__dirname, 'renderer', 'universe_canvas.js'), 'utf8'), context);
    return { UniverseCanvas: window.UniverseCanvas, calls };
}

const A = 'aaaa-0001';
const B = 'bbbb-0002';
const C = 'cccc-0003';

test('a layout that leaves every card where it was writes nothing', async () => {
    const { UniverseCanvas, calls } = canvasClass();
    const positions = new Map([[A, { x: 10, y: 20 }], [B, { x: 300, y: 40 }]]);
    const before = new Map([[A, { x: 10, y: 20 }], [B, { x: 300.2, y: 39.9 }]]);
    await UniverseCanvas.prototype._persistPositions.call({}, positions, before);
    assert.deepEqual(calls, []);
});

test('only the moved card is written, and a card without an old place too', async () => {
    const { UniverseCanvas, calls } = canvasClass();
    const positions = new Map([[A, { x: 10, y: 20 }], [B, { x: 500, y: 40 }], [C, { x: 7, y: 8 }]]);
    const before = new Map([[A, { x: 10, y: 20 }], [B, { x: 300, y: 40 }]]);
    await UniverseCanvas.prototype._persistPositions.call({}, positions, before);
    assert.deepEqual(calls.map((c) => decodeURIComponent(c.url.split('id=eq.')[1])).sort(), [B, C]);
    assert.deepEqual(calls.find((c) => c.url.endsWith(B)).body, { x: 500, y: 40 });
});

test('without the old places (an older caller) every card is written as before', async () => {
    const { UniverseCanvas, calls } = canvasClass();
    await UniverseCanvas.prototype._persistPositions.call({}, new Map([[A, { x: 1, y: 2 }]]));
    assert.equal(calls.length, 1);
});

test('both layout paths hand the old places over', () => {
    const src = fs.readFileSync(path.join(__dirname, 'renderer', 'universe_canvas.js'), 'utf8');
    assert.equal((src.match(/this\._persistPositions\(positions, before\);/g) || []).length, 2);
    assert.doesNotMatch(src, /this\._persistPositions\(positions\);/);
});
