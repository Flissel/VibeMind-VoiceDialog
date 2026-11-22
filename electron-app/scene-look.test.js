const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const THREE = require('./renderer/lib/three.min.js');
const kit = require('./renderer/scene-kit');
const refineApi = require('./renderer/scene-refine');

function hull(color = 0xff6633, opacity = 0.08) {
    return new THREE.Mesh(
        new THREE.IcosahedronGeometry(2.5, 2),
        new THREE.MeshBasicMaterial({ color, transparent: true, opacity, side: THREE.BackSide }),
    );
}

function baseRing() {
    const ring = new THREE.Mesh(
        new THREE.RingGeometry(2.5, 3, 32),
        new THREE.MeshBasicMaterial({ color: 0x4488ff, transparent: true, opacity: 0.3, side: THREE.DoubleSide }),
    );
    ring.rotation.x = -Math.PI / 2;
    ring.position.y = -2;
    return ring;
}

function points() {
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.BufferAttribute(new Float32Array(9), 3));
    return new THREE.Points(geometry, new THREE.PointsMaterial({ size: 0.05, color: 0xffffff }));
}

test('polish turns hulls into halos and base rings into round rings, on the same objects', () => {
    const group = new THREE.Group();
    const h = hull();
    const r = baseRing();
    const p = points();
    const tilted = baseRing();
    tilted.position.y = 0; // a ring that is part of an object, not a base ring
    group.add(h, r, p, tilted);

    const done = kit.polishObject(THREE, group, null);

    assert.deepEqual(done, { halos: 1, rings: 1, points: 1 });
    assert.equal(group.children[0], h, 'the hull mesh itself stays: it is a click target');
    assert.equal(h.material.type, 'ShaderMaterial');
    assert.equal(h.material.side, THREE.BackSide);
    assert.equal(h.material.depthWrite, false);
    assert.equal(h.material.uniforms.u_time, kit.time, 'follows the shared clock');
    assert.equal(r.geometry.parameters.thetaSegments, 128);
    assert.equal(r.material.uniforms.u_color.value.getHex(), 0x4488ff);
    assert.equal(tilted.material.type, 'MeshBasicMaterial', 'other rings are left alone');
});

test('polish is safe to run twice', () => {
    const group = new THREE.Group();
    group.add(hull(), baseRing(), points());
    kit.polishObject(THREE, group, null);

    assert.deepEqual(kit.polishObject(THREE, group, null), { halos: 0, rings: 0, points: 0 });
});

test('the brain surface has folds and a furrow between the halves', () => {
    const { brainRadius, brainGeometry } = refineApi;

    assert.ok(brainRadius(0, 0.6, 0.8) < brainRadius(0.3, 0.6, 0.74) - 0.05, 'deep in the middle');
    assert.equal(brainRadius(0.3, 0.2, 0.9), brainRadius(0.3, 0.2, 0.9), 'same on every start');
    const samples = [];
    for (let i = 0; i < 40; i++) samples.push(brainRadius(Math.cos(i) * 0.8, 0.3, Math.sin(i) * 0.8));
    assert.ok(Math.max(...samples) - Math.min(...samples) > 0.04, 'not a plain ball');

    const geometry = brainGeometry(THREE);
    assert.ok(geometry.getAttribute('position').count > 5000);
    assert.ok(geometry.getAttribute('normal'), 'smooth normals');
});

function fakeApp() {
    const spaces = {};
    const make = (key) => { spaces[key] = { group: new THREE.Group(), objects: [] }; return spaces[key]; };

    const ideas = make('ideas');
    const bubble = new THREE.Mesh(new THREE.SphereGeometry(0.7, 8, 6), new THREE.MeshPhongMaterial({ color: 0x4488ff }));
    bubble.userData = { type: 'bubble' };
    ideas.group.add(bubble);

    const factory = make('swedesign');
    factory.building = new THREE.Mesh(new THREE.BoxGeometry(2.4, 1.8, 1.6),
        new THREE.MeshPhongMaterial({ color: 0xff6633, transparent: true, opacity: 0.35, emissive: 0xff6633, emissiveIntensity: 0.2 }));
    const torus = new THREE.TorusGeometry(0.4, 0.08, 8, 12);
    const gearMaterial = new THREE.MeshPhongMaterial({ color: 0xffcc44 });
    factory.gear1 = new THREE.Mesh(torus, gearMaterial);
    factory.gear2 = new THREE.Mesh(torus, gearMaterial);
    const chimney = new THREE.Mesh(new THREE.CylinderGeometry(0.15, 0.18, 1.2, 8), new THREE.MeshPhongMaterial({ color: 0x884422 }));
    factory.group.add(factory.building, factory.gear1, factory.gear2, chimney);

    const brain = make('thebrain');
    brain.brainGroup = new THREE.Group();
    brain.brain = new THREE.Mesh(new THREE.IcosahedronGeometry(1.2, 3), new THREE.MeshPhongMaterial({ color: 0xee8899 }));
    brain.brainGroup.add(brain.brain);
    brain.synapses = [0, 1, 2].map(() => new THREE.Line(new THREE.BufferGeometry(), new THREE.LineBasicMaterial({ transparent: true, opacity: 0.2 })));
    brain.thoughtBubbles = [];
    brain.group.add(brain.brainGroup, ...brain.synapses);

    return { spaces, scene: new THREE.Scene(), renderer: null, bubble, chimney };
}

test('refine keeps every reference the render loop uses and leaves the idea bubbles alone', () => {
    const app = fakeApp();
    const { building, gear1, gear2 } = app.spaces.swedesign;
    const { brain, synapses } = app.spaces.thebrain;

    const report = refineApi.refine(app, THREE, null);

    assert.deepEqual(report.objects, ['thebrain', 'swedesign']);
    assert.equal(app.spaces.swedesign.building, building);
    assert.equal(building.material.type, 'MeshStandardMaterial');
    assert.equal(building.material.emissiveIntensity, 0.2, 'the loop breathes this value');
    assert.equal(gear1.geometry.type, 'ExtrudeGeometry');
    assert.equal(gear1.geometry, gear2.geometry, 'one toothed gear shape for both');
    assert.equal(app.chimney.geometry.parameters.radialSegments, 24);
    assert.ok(app.chimney.children.some((c) => c.userData.type === 'chimney-rim'));
    assert.equal(app.spaces.thebrain.brain, brain);
    assert.equal(brain.geometry.type, 'SphereGeometry');
    assert.equal(brain.material.type, 'MeshPhysicalMaterial');
    for (const line of synapses) assert.equal(line.geometry.getAttribute('position').count, 29, 'an arc, not a straight line');
    assert.equal(app.bubble.material.type, 'MeshPhongMaterial', 'bubbles untouched');
    assert.equal(app.bubble.geometry.parameters.widthSegments, 8, 'bubbles untouched');
});

test('refine runs once and works without a renderer or a canvas', () => {
    const app = fakeApp();

    const first = refineApi.refine(app, THREE, null);

    assert.equal(first.environment, false);
    assert.equal(refineApi.refine(app, THREE, null), null);
    assert.equal(app.scene.children.filter((c) => c.name === 'refine-sky-light').length, 1);
});

test('the scene loads both passes before multiverse.js and feeds the shared clock', () => {
    const renderer = path.join(__dirname, 'renderer');
    const html = fs.readFileSync(path.join(renderer, 'index.html'), 'utf8');
    const scene = fs.readFileSync(path.join(renderer, 'multiverse.js'), 'utf8');

    for (const file of ['scene-kit.js', 'scene-refine.js']) {
        assert.ok(html.indexOf(`src="${file}"`) > -1, file);
        assert.ok(html.indexOf(`src="${file}"`) < html.indexOf('src="multiverse.js"'), `${file} before multiverse.js`);
    }
    assert.match(scene, /window\.VibeSceneRefine\.refine\(this\)/);
    assert.match(scene, /window\.VibeSceneKit\.polish\(this\)/);
    assert.match(scene, /window\.VibeSceneKit\.time\.value = elapsed/);
});
