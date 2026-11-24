const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const THREE = require('./renderer/lib/three.min.js');
const { build, triangles } = require('./renderer/space-models');
const { describeForRenderer } = require('./external-spaces');
const { sceneEntry } = require('./renderer/external-spaces');
const { polishObject } = require('./renderer/scene-kit');
const { pickSpace } = require('./renderer/space-pick');

// The space as the renderer gets it from the main process (no address configured).
const sales = () => describeForRenderer({}).find((s) => s.id === 'sales');

test('Sales gets the disco: built at its place, with a name the scene can be searched by', () => {
    const model = build(THREE, sales());
    assert.ok(model, 'Sales has a model');
    assert.equal(model.group.name, 'raum-modell-sales');
    assert.deepEqual(model.group.userData, { type: 'space-model', space: 'sales' });
    assert.deepEqual(model.group.position.toArray(), sales().position);
    for (const part of ['disco-kugel', 'disco-strahlen', 'disco-tanzflaeche', 'disco-lichtflecken']) {
        assert.ok(model.group.getObjectByName(part), part);
    }
});

test('the other external spaces keep their gate until they get a model', () => {
    for (const space of describeForRenderer({}).filter((s) => s.id !== 'sales')) {
        assert.equal(build(THREE, space), null, space.id);
    }
});

test('the disco costs no visible frames: about 1600 triangles in the scene, few draw calls, no light of its own', () => {
    const model = build(THREE, sales());
    polishObject(THREE, model.group, null);
    const count = triangles(model.group);
    assert.ok(count > 1500 && count < 1700, `triangles ${count}`);
    assert.ok(count < 3572, 'fewer than the gate it replaces');

    let drawCalls = 0;
    let lights = 0;
    model.group.traverse((o) => { if (o.isMesh) drawCalls++; if (o.isLight) lights++; });
    assert.ok(drawCalls <= 18, `draw calls ${drawCalls}`);
    assert.equal(lights, 0, 'a light more would recompile every material of the scene');

    // one frame of its movement: well under a tenth of a millisecond
    const runs = 2000;
    const start = process.hrtime.bigint();
    for (let i = 0; i < runs; i++) model.tick(i / 60);
    const perFrameMs = Number(process.hrtime.bigint() - start) / 1e6 / runs;
    assert.ok(perFrameMs < 0.1, `tick ${perFrameMs.toFixed(4)} ms`);
});

test('it moves: the ball turns, the beams sweep, the floor lights up in turn', () => {
    const model = build(THREE, sales());
    const ball = model.group.getObjectByName('disco-kugel');
    const beams = model.group.getObjectByName('disco-strahlen');
    const floor = model.group.getObjectByName('disco-tanzflaeche');
    model.tick(0);
    const before = [ball.rotation.y, beams.rotation.y, floor.children.map((s) => s.material.emissiveIntensity)];
    model.tick(1.3);
    assert.notEqual(ball.rotation.y, before[0]);
    assert.notEqual(beams.rotation.y, before[1]);
    assert.notDeepEqual(floor.children.map((s) => s.material.emissiveIntensity), before[2]);
});

test('it cleans up: every geometry and material is freed and it leaves the scene', () => {
    const scene = new THREE.Scene();
    const model = build(THREE, sales());
    scene.add(model.group);
    let freed = 0;
    let parts = 0;
    model.group.traverse((o) => {
        for (const part of [o.geometry, o.material].filter(Boolean)) {
            parts++;
            part.addEventListener('dispose', () => { freed++; });
        }
    });
    model.dispose();
    assert.equal(model.group.parent, null);
    assert.ok(freed > 0);
    assert.ok(freed <= parts, 'shared parts are freed once');
    assert.equal(scene.children.length, 0);
});

test('the halo hull stays its click target, as for the gate', () => {
    const space = sales();
    const entry = sceneEntry(THREE, space);
    entry.group = build(THREE, space).group;
    entry.group.updateMatrixWorld(true);
    const from = new THREE.Vector3(space.position[0], space.position[1] + 1, space.position[2] + 12);
    const ray = new THREE.Raycaster(from, new THREE.Vector3(0, 0, -1));
    assert.equal(pickSpace(ray, { sales: entry }, 'ideas'), 'sales');
});

test('the scene uses the model instead of the gate and moves it; the page loads it first', () => {
    const read = (...parts) => fs.readFileSync(path.join(__dirname, ...parts), 'utf8');
    const scene = read('renderer', 'external-spaces.js');
    assert.match(scene, /const model = root\.VibeSpaceModels \? root\.VibeSpaceModels\.build\(THREE, space\) : null;/);
    assert.match(scene, /const gate = model \? null : buildGate\(THREE, space\);/);
    assert.match(scene, /else if \(entry && entry\.model\) entry\.model\.tick\(t\);/);
    const page = read('renderer', 'index.html');
    assert.ok(page.indexOf('src="space-models.js"') > 0 && page.indexOf('src="space-models.js"') < page.indexOf('src="external-spaces.js"'));
    const models = read('renderer', 'space-models.js');
    assert.doesNotMatch(models, /Math\.random|PointLight|SpotLight|TextureLoader|GLTFLoader/);
});
