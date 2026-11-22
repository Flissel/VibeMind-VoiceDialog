const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const THREE = require('./renderer/lib/three.min.js');
const { buildSun } = require('./renderer/sun');

function sequence() {
    let i = 0;
    return () => ((i++ * 0.37) % 1);
}

test('the sun keeps the contract the rest of the app relies on', () => {
    const sun = buildSun(THREE, { document: null, random: sequence() });

    // Click target and hand tracking (multiverse.js reads/writes these).
    assert.equal(sun.planet.userData.type, 'planet');
    for (const name of ['u_time', 'u_pulse', 'u_color', 'u_handPos', 'u_intensity']) {
        assert.ok(sun.planet.material.uniforms[name], `planet uniform ${name}`);
    }
    // animate() rotates the Points objects of the desktop space.
    assert.equal(sun.particles.type, 'Points');
    assert.equal(sun.parts.includes(sun.planet), true);
    assert.equal(sun.parts.includes(sun.particles), true);
});

test('every animated part follows the one time value the render loop sets on the planet', () => {
    const sun = buildSun(THREE, { document: null, random: sequence() });
    const animated = [sun.planet, sun.corona, sun.ring, ...sun.flares];

    sun.planet.material.uniforms.u_time.value = 12.5;

    assert.equal(sun.flares.length, 3);
    for (const part of animated) {
        assert.equal(part.material.uniforms.u_time.value, 12.5, part.userData.type);
    }
});

test('the star is a round sphere and the see-through parts never write depth', () => {
    const sun = buildSun(THREE, { document: null, random: sequence() });

    assert.equal(sun.planet.geometry.type, 'SphereGeometry');
    assert.equal(sun.planet.material.transparent, false);
    for (const part of [sun.corona, sun.ring, sun.particles, ...sun.flares]) {
        assert.equal(part.material.transparent, true, part.userData.type);
        assert.equal(part.material.depthWrite, false, part.userData.type);
    }
    // The corona must reach beyond the star, and the ring must start outside it.
    const radius = sun.planet.geometry.parameters.radius;
    assert.ok(sun.corona.geometry.parameters.radius > radius * 1.5);
    assert.ok(sun.ring.geometry.parameters.innerRadius > radius);
});

test('the dust works without a canvas and keeps its particle count', () => {
    const sun = buildSun(THREE, { document: null, random: sequence(), particleCount: 120 });

    assert.equal(sun.particles.geometry.getAttribute('position').count, 120);
    assert.equal(sun.particles.geometry.getAttribute('color').count, 120);
    assert.equal(sun.particles.material.map, null);
});

test('the scene builds the sun from sun.js and loads it before multiverse.js', () => {
    const renderer = path.join(__dirname, 'renderer');
    const html = fs.readFileSync(path.join(renderer, 'index.html'), 'utf8');
    const scene = fs.readFileSync(path.join(renderer, 'multiverse.js'), 'utf8');

    assert.ok(html.indexOf('src="sun.js"') > -1, 'sun.js is loaded');
    assert.ok(html.indexOf('src="sun.js"') < html.indexOf('src="multiverse.js"'), 'before multiverse.js');
    assert.match(scene, /window\.VibeSun\.buildSun\(THREE\)/);
    assert.match(scene, /this\.spaces\.desktop\.planet = sun\.planet/);
});
