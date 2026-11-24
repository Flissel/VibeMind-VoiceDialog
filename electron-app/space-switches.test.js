const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const THREE = require('./renderer/lib/three.min.js');
const { hiddenSpaces } = require('./space-switches');
const { apply } = require('./renderer/space-switches');
const { pickSpace } = require('./renderer/space-pick');

const read = (...parts) => fs.readFileSync(path.join(__dirname, ...parts), 'utf8');

test('the Dashboard is off by default; the switch brings it back', () => {
    assert.deepEqual(hiddenSpaces({}), ['clawport']);
    for (const value of ['an', 'ein', 'on', 'true', '1', 'JA', ' an ']) {
        assert.deepEqual(hiddenSpaces({ VIBEMIND_DASHBOARD_SPACE: value }), [], value);
    }
    assert.deepEqual(hiddenSpaces({ VIBEMIND_DASHBOARD_SPACE: 'aus' }), ['clawport']);
    assert.deepEqual(hiddenSpaces({ VIBEMIND_DASHBOARD_SPACE: 'vielleicht' }), ['clawport'], 'unknown value: the default');
});

function fakeDoc(ids) {
    const tabs = Object.fromEntries(ids.map((id) => [id, { id: 'tab-' + id, hidden: false, attrs: {}, setAttribute(k, v) { this.attrs[k] = v; } }]));
    return { tabs, getElementById: (name) => Object.values(tabs).find((t) => t.id === name) || null };
}

test('switched off: no tab, out of the scene, objects kept, not clickable', () => {
    const scene = new THREE.Scene();
    const board = new THREE.Group();
    const face = new THREE.Mesh(new THREE.BoxGeometry(2, 2, 0.2), new THREE.MeshBasicMaterial());
    const inner = new THREE.Group();
    inner.add(face);
    board.add(inner);
    board.position.set(-8, 0, 12);
    scene.add(board);
    const app = { scene, spaces: { ideas: { objects: [] }, clawport: { group: board, objects: [board] } } };
    const doc = fakeDoc(['ideas', 'clawport']);

    // before: the board is the click target of the Dashboard
    board.updateMatrixWorld(true);
    const ray = new THREE.Raycaster(new THREE.Vector3(-8, 0, 30), new THREE.Vector3(0, 0, -1));
    assert.equal(pickSpace(ray, app.spaces, 'ideas'), 'clawport');

    assert.deepEqual(apply(app, doc, ['clawport', 'gibt-es-nicht']), ['clawport']);
    assert.equal(app.spaces.clawport.hidden, true);
    assert.equal(board.parent, null, 'out of the scene');
    assert.equal(app.spaces.clawport.group, board, 'kept, nothing deleted');
    assert.equal(doc.tabs.clawport.hidden, true);
    assert.equal(doc.tabs.clawport.attrs['aria-hidden'], 'true');
    assert.equal(doc.tabs.ideas.hidden, false);
    assert.equal(pickSpace(ray, app.spaces, 'ideas'), null, 'no click opens it');
});

test('the scene does not enter a space switched off, by any way; key cycling skips it', () => {
    const scene = read('renderer', 'multiverse.js');
    assert.match(scene, /navigateToSpace\(targetSpace\) \{\s*if \(this\.isNavigating \|\| targetSpace === this\.currentSpace\) \{\s*return false;\s*\}\s*\/\/[^\n]*\n\s*if \(this\.spaces\[targetSpace\] && this\.spaces\[targetSpace\]\.hidden\) \{\s*return false;/);
    const cycling = scene.match(/const spaceKeys = Object\.keys\(this\.spaces\)\.filter\(\(key\) => !this\.spaces\[key\]\.hidden \|\| key === this\.currentSpace\);/g);
    assert.equal(cycling && cycling.length, 2, 'previous and next');
});

test('main, preload and page are wired; the Dashboard code stays', () => {
    assert.match(read('main.js'), /ipcMain\.handle\('get-space-switches', \(\) => require\('\.\/space-switches'\)\.hiddenSpaces\(process\.env\)\)/);
    assert.match(read('preload.js'), /getSpaceSwitches: \(\) => ipcRenderer\.invoke\('get-space-switches'\)/);
    const page = read('renderer', 'index.html');
    assert.match(page, /<script defer src="space-switches\.js"><\/script>/);
    assert.match(page, /id="tab-clawport"/, 'the tab is hidden, not removed');
    assert.ok(fs.existsSync(path.join(__dirname, 'clawport-manager.js')));
    assert.match(read('main.js'), /ipcMain\.handle\('clawport:chat-text-input'/);
});
