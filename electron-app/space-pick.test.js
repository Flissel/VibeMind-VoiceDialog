const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const THREE = require('./renderer/lib/three.min.js');
const { pickSpace } = require('./renderer/space-pick');

function box(z, size = 2) {
    const mesh = new THREE.Mesh(new THREE.BoxGeometry(size, size, size), new THREE.MeshBasicMaterial());
    mesh.position.z = z;
    return mesh;
}

function space(...children) {
    const group = new THREE.Group();
    group.add(...children);
    group.updateMatrixWorld(true);
    return { group, objects: [group] };
}

/** Looks from z = +30 towards -z along the axis all test objects sit on. */
function rayDownTheAxis() {
    return new THREE.Raycaster(new THREE.Vector3(0, 0, 30), new THREE.Vector3(0, 0, -1));
}

test('the nearest space wins, not the first in the list', () => {
    // clawport comes before video in the old fixed order, but stands behind it here.
    const spaces = { clawport: space(box(0)), video: space(box(12)) };

    assert.equal(pickSpace(rayDownTheAxis(), spaces, 'ideas'), 'video');
});

test('a single space on the sight line is picked as before', () => {
    assert.equal(pickSpace(rayDownTheAxis(), { thebrain: space(box(0)) }, 'ideas'), 'thebrain');
    assert.equal(pickSpace(rayDownTheAxis(), { thebrain: space(box(0)) }, 'thebrain'), null, 'not the space you are in');
});

test('the space you are in is skipped, so the one behind it can be reached', () => {
    const spaces = { clawport: space(box(0)), video: space(box(12)) };

    assert.equal(pickSpace(rayDownTheAxis(), spaces, 'video'), 'clawport');
});

test('a click into empty space picks nothing', () => {
    const ray = new THREE.Raycaster(new THREE.Vector3(50, 0, 30), new THREE.Vector3(0, 0, -1));

    assert.equal(pickSpace(ray, { video: space(box(12)) }, 'ideas'), null);
});

test('an idea bubble in front of a space keeps its own click', () => {
    const spaces = { agentfarm: space(box(0)) };
    const bubble = box(20, 1);
    bubble.updateMatrixWorld(true);
    const behind = box(-20, 1);
    behind.updateMatrixWorld(true);

    assert.equal(pickSpace(rayDownTheAxis(), spaces, 'ideas', [bubble]), null, 'bubble is nearer');
    assert.equal(pickSpace(rayDownTheAxis(), spaces, 'ideas', [behind]), 'agentfarm', 'bubble is behind the space');
});

test('the same objects count as click target as in the old handler', () => {
    // Factory and boat: only direct meshes. A mesh inside a child group must not count for them,
    // but does count for the dashboard.
    const nested = new THREE.Group();
    nested.add(box(0));
    assert.equal(pickSpace(rayDownTheAxis(), { swedesign: space(nested) }, 'ideas'), null);
    const nestedAgain = new THREE.Group();
    nestedAgain.add(box(0));
    assert.equal(pickSpace(rayDownTheAxis(), { clawport: space(nestedAgain) }, 'ideas'), 'clawport');
    // MiroFish keeps its group in objects[0] and has no .group.
    const fish = space(box(0));
    assert.equal(pickSpace(rayDownTheAxis(), { mirofish: { objects: fish.objects } }, 'ideas'), 'mirofish');
});

test('the click handler asks pickSpace and no longer walks the spaces in a fixed order', () => {
    const renderer = path.join(__dirname, 'renderer');
    const html = fs.readFileSync(path.join(renderer, 'index.html'), 'utf8');
    const scene = fs.readFileSync(path.join(renderer, 'multiverse.js'), 'utf8');

    assert.ok(html.indexOf('src="space-pick.js"') > -1);
    assert.ok(html.indexOf('src="space-pick.js"') < html.indexOf('src="multiverse.js"'));
    assert.match(scene, /window\.VibeSpacePick\.pickSpace\(raycaster, this\.spaces, this\.currentSpace/);
    assert.doesNotMatch(scene, /const factoryHit = raycaster\.intersectObjects/);
});
