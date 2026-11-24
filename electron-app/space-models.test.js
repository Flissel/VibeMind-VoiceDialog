const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const THREE = require('./renderer/lib/three.min.js');
const { build, triangles, FIGURES } = require('./renderer/space-models');
const { describeForRenderer } = require('./external-spaces');
const { sceneEntry } = require('./renderer/external-spaces');
const { polishObject } = require('./renderer/scene-kit');
const { pickSpace } = require('./renderer/space-pick');

// The spaces as the renderer gets them from the main process (no address configured).
const spaces = () => describeForRenderer({});
const space = (id) => spaces().find((s) => s.id === id);
const read = (...parts) => fs.readFileSync(path.join(__dirname, ...parts), 'utf8');

/**
 * What each figure must show, and what of it must move. `state` reads the moving parts; two
 * different times must give two different readings.
 */
const EXPECT = {
    disco: {
        space: 'sales',
        parts: ['disco-kugel', 'disco-strahlen', 'disco-tanzflaeche', 'disco-lichtflecken'],
        triangles: [1500, 1700],
        state: (g) => [g.getObjectByName('disco-kugel').rotation.y, g.getObjectByName('disco-strahlen').rotation.y,
            ...g.getObjectByName('disco-tanzflaeche').children.map((s) => s.material.emissiveIntensity)],
    },
    leuchtturm: {
        space: 'marketing',
        parts: ['leuchtturm-fels', 'leuchtturm-turm', 'leuchtturm-lampe', 'leuchtturm-strahl', 'leuchtturm-wellen'],
        triangles: [1600, 1800],
        state: (g) => [g.getObjectByName('leuchtturm-strahl').rotation.y, g.getObjectByName('leuchtturm-lampe').material.emissiveIntensity,
            ...g.getObjectByName('leuchtturm-wellen').instanceMatrix.array.slice(0, 1)],
    },
    buch: {
        space: 'learning',
        parts: ['buch-aufgeschlagen', 'buch-zeilen', 'buch-lichtpunkte'],
        triangles: [1900, 2100],
        state: (g) => [...g.getObjectByName('buch-lichtpunkte').instanceMatrix.array.slice(12, 15)],
    },
    buehne: {
        space: 'events',
        parts: ['buehne-boden', 'buehne-dach', 'buehne-wimpel', 'buehne-spots'],
        triangles: [600, 800],
        state: (g) => [...g.getObjectByName('buehne-wimpel').instanceMatrix.array.slice(0, 2),
            ...g.getObjectByName('buehne-spots').children.map((b) => b.rotation.z)],
    },
};

const GATE_TRIANGLES = 3572;   // what the gate with its emoji sign costs after the polish

test('the table names a figure file for every space in it, and only for known spaces', () => {
    const known = spaces().map((s) => s.id);
    for (const [id, name] of Object.entries(FIGURES)) {
        assert.ok(known.includes(id), `${id} is a space`);
        assert.ok(fs.existsSync(path.join(__dirname, 'renderer', 'space-figures', `${name}.js`)), `${name}.js`);
        assert.ok(EXPECT[name], `${name} is checked here`);
        assert.equal(EXPECT[name].space, id, `${name} stands for ${id}`);
    }
});

test('a space without a figure keeps its gate', () => {
    for (const s of spaces().filter((one) => !FIGURES[one.id])) assert.equal(build(THREE, s), null, s.id);
    assert.equal(build(THREE, { id: 'nirgends', color: 0xffffff, position: [0, 0, 0] }), null);
    assert.equal(build(THREE, null), null);
});

for (const [name, want] of Object.entries(EXPECT)) {
    const own = () => build(THREE, space(want.space));

    test(`${name}: built at the place of ${want.space}, with its parts and a name the scene can be searched by`, () => {
        const model = own();
        assert.ok(model, `${want.space} has a model`);
        assert.equal(model.group.name, `raum-modell-${want.space}`);
        assert.deepEqual(model.group.userData, { type: 'space-model', space: want.space, figure: name });
        assert.deepEqual(model.group.position.toArray(), space(want.space).position);
        for (const part of want.parts) assert.ok(model.group.getObjectByName(part), part);
    });

    test(`${name} costs no visible frames: fewer triangles than the gate, few draw calls, no light of its own`, () => {
        const model = own();
        polishObject(THREE, model.group, null);
        const count = triangles(model.group);
        assert.ok(count >= want.triangles[0] && count <= want.triangles[1], `triangles ${count}`);
        assert.ok(count < GATE_TRIANGLES, 'fewer than the gate it replaces');

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

    test(`${name} moves`, () => {
        const model = own();
        model.tick(0.4);
        const before = JSON.stringify(want.state(model.group));
        model.tick(2.9);
        assert.notEqual(JSON.stringify(want.state(model.group)), before);
    });

    test(`${name} cleans up: every geometry and material is freed and it leaves the scene`, () => {
        const scene = new THREE.Scene();
        const model = own();
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

    test(`${name}: the halo hull stays the click target of ${want.space}, as for the gate`, () => {
        const s = space(want.space);
        const entry = sceneEntry(THREE, s);
        entry.group = own().group;
        entry.group.updateMatrixWorld(true);
        const from = new THREE.Vector3(s.position[0], s.position[1] + 1, s.position[2] + 12);
        const ray = new THREE.Raycaster(from, new THREE.Vector3(0, 0, -1));
        assert.equal(pickSpace(ray, { [want.space]: entry }, 'ideas'), want.space);
    });
}

test('the scene uses the model instead of the gate and moves it; the page loads every figure before the scene', () => {
    const scene = read('renderer', 'external-spaces.js');
    assert.match(scene, /const model = root\.VibeSpaceModels \? root\.VibeSpaceModels\.build\(THREE, space\) : null;/);
    assert.match(scene, /const gate = model \? null : buildGate\(THREE, space\);/);
    assert.match(scene, /else if \(entry && entry\.model\) entry\.model\.tick\(t\);/);
    const page = read('renderer', 'index.html');
    const scenePos = page.indexOf('src="external-spaces.js"');
    const modelsPos = page.indexOf('src="space-models.js"');
    assert.ok(modelsPos > 0 && modelsPos < scenePos);
    for (const name of new Set(Object.values(FIGURES))) {
        const at = page.indexOf(`src="space-figures/${name}.js"`);
        assert.ok(at > 0 && at < scenePos, `${name}.js loaded before the scene`);
    }
});

test('figures stay plain geometry: no chance, no lights, no loaded files; each registers under its own name', () => {
    const dir = path.join(__dirname, 'renderer', 'space-figures');
    for (const file of ['space-models.js', ...fs.readdirSync(dir).map((f) => path.join('space-figures', f))]) {
        assert.doesNotMatch(read('renderer', file), /Math\.random|PointLight|SpotLight|TextureLoader|GLTFLoader/, file);
    }
    for (const name of fs.readdirSync(dir).map((f) => f.replace(/\.js$/, ''))) {
        assert.match(read('renderer', 'space-figures', `${name}.js`), new RegExp(`\\.VibeSpaceFigures \\|\\| \\{\\}\\)\\.${name} = ${name};`), name);
    }
});
