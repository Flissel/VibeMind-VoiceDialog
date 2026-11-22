/**
 * Detail pass over the objects of the multiverse scene.
 *
 * `refine(app)` runs once after the spaces are built. It keeps every object, its
 * place and every reference the render loop and the click handling use, and
 * replaces what made the scene look rough: flat low-polygon shapes, see-through
 * boxes, shading without reflections, objects standing in the dark.
 *
 *   all spaces  smoother round shapes, physically shaded surfaces with a soft
 *               studio reflection, one key light for the spaces that had none
 *   brain       folded surface with a central furrow instead of a faceted ball,
 *               synapses as glowing arcs that end in the neurons
 *   factory     solid building with lit windows, toothed gears, chimney rims
 *   farm        planked barn, braced door, grass ground, round silo and animals
 *   studio      clapper stripes, lit stage floor
 *
 * The idea bubbles are left exactly as they are.
 */
(function (root) {
    'use strict';

    // ── small deterministic helpers (no Math.random: the scene looks the same on every start) ──

    function seeded(seed) {
        let s = seed >>> 0;
        return () => {
            s = (s + 0x6d2b79f5) >>> 0;
            let t = Math.imul(s ^ (s >>> 15), 1 | s);
            t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
            return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
        };
    }

    function hash3(x, y, z) {
        let h = (Math.imul(x, 374761393) + Math.imul(y, 668265263) + Math.imul(z, 2147483647)) | 0;
        h = Math.imul(h ^ (h >>> 13), 1274126177);
        return ((h ^ (h >>> 16)) >>> 0) / 4294967296;
    }

    /** Smooth value noise in [0, 1]. */
    function noise3(x, y, z) {
        const xi = Math.floor(x), yi = Math.floor(y), zi = Math.floor(z);
        const fade = (t) => t * t * (3 - 2 * t);
        const u = fade(x - xi), v = fade(y - yi), w = fade(z - zi);
        const lerp = (a, b, t) => a + (b - a) * t;
        const c = (dx, dy, dz) => hash3(xi + dx, yi + dy, zi + dz);
        return lerp(
            lerp(lerp(c(0, 0, 0), c(1, 0, 0), u), lerp(c(0, 1, 0), c(1, 1, 0), u), v),
            lerp(lerp(c(0, 0, 1), c(1, 0, 1), u), lerp(c(0, 1, 1), c(1, 1, 1), u), v),
            w,
        );
    }

    /** Ridges in [0, 1]: 1 on a ridge line, falling off to both sides. Reads as folds. */
    function ridges(x, y, z) {
        return 1 - Math.abs(noise3(x, y, z) * 2 - 1);
    }

    /**
     * How far the brain surface stands out at direction (x, y, z) on the unit sphere:
     * folds everywhere, one deep furrow between the halves, a flatter underside.
     */
    function brainRadius(x, y, z) {
        const folds = ridges(x * 3.1 + 7, y * 3.1 + 3, z * 3.1 + 11) * 0.085
            + ridges(x * 6.4 + 1, y * 6.4 + 9, z * 6.4 + 5) * 0.035;
        const furrow = Math.exp(-((x / 0.075) ** 2)) * 0.15 * Math.max(0, Math.min(1, y * 1.4 + 0.75));
        const underside = y < -0.45 ? (y + 0.45) * 0.35 : 0;
        return 1 + folds - 0.06 - furrow + underside;
    }

    // ── three.js parts ──

    function canvasTexture(THREE, doc, width, height, draw) {
        if (!doc || !doc.createElement) return null;
        const canvas = doc.createElement('canvas');
        canvas.width = width;
        canvas.height = height;
        const ctx = canvas.getContext && canvas.getContext('2d');
        if (!ctx) return null;
        draw(ctx, width, height);
        const texture = new THREE.CanvasTexture(canvas);
        texture.anisotropy = 4;
        return texture;
    }

    /** A dim studio: dark gradient with three soft light panels. Gives surfaces something to reflect. */
    function buildEnvironment(THREE, renderer) {
        if (!renderer || !THREE.PMREMGenerator) return null;
        // Built-in materials only: the generator stores the result RGBE-encoded, and a
        // hand-written shader would skip that encoding (every reflection came out black).
        const scene = new THREE.Scene();
        const shellGeometry = new THREE.SphereGeometry(20, 24, 16);
        const position = shellGeometry.getAttribute('position');
        const colors = new Float32Array(position.count * 3);
        for (let i = 0; i < position.count; i++) {
            const t = Math.max(0, Math.min(1, (position.getY(i) / 20 + 0.4) / 1.3));
            colors.set([0.03 + 0.07 * t, 0.02 + 0.11 * t, 0.06 + 0.2 * t], i * 3);
        }
        shellGeometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
        const made = [shellGeometry];
        const shellMaterial = new THREE.MeshBasicMaterial({ vertexColors: true, side: THREE.BackSide });
        made.push(shellMaterial);
        scene.add(new THREE.Mesh(shellGeometry, shellMaterial));
        const panelGeometry = new THREE.SphereGeometry(1, 16, 12);
        made.push(panelGeometry);
        const panels = [
            { at: [9, 8, 9], size: 4.5, rgb: [3.0, 2.1, 1.3] },    // warm key
            { at: [-11, 5, -8], size: 5, rgb: [1.1, 1.6, 2.6] },   // cool fill
            { at: [0, 3, -14], size: 4, rgb: [2.0, 0.9, 1.8] },    // magenta rim
        ];
        for (const panel of panels) {
            const material = new THREE.MeshBasicMaterial({ toneMapped: false });
            material.color.setRGB(panel.rgb[0], panel.rgb[1], panel.rgb[2]);
            made.push(material);
            const mesh = new THREE.Mesh(panelGeometry, material);
            mesh.position.set(panel.at[0], panel.at[1], panel.at[2]);
            mesh.scale.setScalar(panel.size);
            scene.add(mesh);
        }
        const generator = new THREE.PMREMGenerator(renderer);
        const target = generator.fromScene(scene, 0.04);
        generator.dispose();
        for (const item of made) item.dispose();
        return target.texture;
    }

    function physical(THREE, env, color, options = {}) {
        return new THREE.MeshStandardMaterial({
            color, roughness: 0.6, metalness: 0.05, envMap: env, envMapIntensity: env ? 0.7 : 0, ...options,
        });
    }

    /** Swaps a Phong material for a physically shaded one and keeps what the render loop animates. */
    function upgradeMaterial(THREE, mesh, env, overrides = {}) {
        const old = mesh.material;
        if (!old || old.type !== 'MeshPhongMaterial') return false;
        mesh.material = physical(THREE, env, old.color.getHex(), {
            emissive: old.emissive.getHex(),
            emissiveIntensity: old.emissiveIntensity,
            transparent: old.transparent,
            opacity: old.opacity,
            side: old.side,
            ...overrides,
        });
        old.dispose();
        return true;
    }

    /** Rebuilds a coarse round shape with enough segments to look round. */
    function smoothGeometry(THREE, mesh) {
        const g = mesh.geometry;
        const p = g && g.parameters;
        if (!p) return false;
        let next = null;
        if (g.type === 'CylinderGeometry' && p.radialSegments < 20) {
            next = new THREE.CylinderGeometry(p.radiusTop, p.radiusBottom, p.height, 24, p.heightSegments, p.openEnded, p.thetaStart, p.thetaLength);
        } else if (g.type === 'SphereGeometry' && p.widthSegments < 20) {
            next = new THREE.SphereGeometry(p.radius, 24, 16, p.phiStart, p.phiLength, p.thetaStart, p.thetaLength);
        } else if (g.type === 'ConeGeometry' && p.radialSegments < 12) {
            next = new THREE.ConeGeometry(p.radius, p.height, 16, p.heightSegments, p.openEnded, p.thetaStart, p.thetaLength);
        } else if (g.type === 'CircleGeometry' && p.segments < 64) {
            next = new THREE.CircleGeometry(p.radius, 72, p.thetaStart, p.thetaLength);
        } else if (g.type === 'TorusGeometry' && p.tubularSegments < 32 && p.arc > 6) {
            next = new THREE.TorusGeometry(p.radius, p.tube, 12, 48, p.arc);
        }
        if (!next) return false;
        g.dispose();
        mesh.geometry = next;
        return true;
    }

    /** The general pass: every lit mesh of a space, except the idea bubbles and anything already custom. */
    function refineCommon(THREE, group, env) {
        const done = { materials: 0, shapes: 0 };
        group.traverse((obj) => {
            if (!obj.isMesh || (obj.userData && (obj.userData.type === 'bubble' || obj.userData.type === 'score_fill'))) return;
            if (smoothGeometry(THREE, obj)) done.shapes++;
            if (upgradeMaterial(THREE, obj, env)) done.materials++;
        });
        return done;
    }

    function addKeyLight(THREE, group, color, intensity = 1.15) {
        const light = new THREE.PointLight(color, intensity, 18, 1.6);
        light.position.set(2.6, 4.6, 3.6);
        light.userData = { type: 'key-light' };
        group.add(light);
        return light;
    }

    // ── brain ──

    function brainGeometry(THREE) {
        const geometry = new THREE.SphereGeometry(1.2, 112, 80);
        const position = geometry.getAttribute('position');
        const v = new THREE.Vector3();
        for (let i = 0; i < position.count; i++) {
            v.fromBufferAttribute(position, i).normalize();
            const r = 1.2 * brainRadius(v.x, v.y, v.z);
            // Longer front to back than wide, and lower than both.
            position.setXYZ(i, v.x * r * 0.98, v.y * r * 0.84, v.z * r * 1.16);
        }
        geometry.computeVertexNormals();
        return geometry;
    }

    function refineBrain(THREE, space, env) {
        const { brain, brainGroup, synapses = [], thoughtBubbles = [], neurons } = space;
        if (!brain || !brainGroup) return false;
        const random = seeded(4711);

        brain.geometry.dispose();
        brain.geometry = brainGeometry(THREE);
        brain.material.dispose();
        brain.material = new THREE.MeshPhysicalMaterial({
            color: 0xdc6f88, roughness: 0.5, metalness: 0.0, clearcoat: 0.45, clearcoatRoughness: 0.35,
            emissive: 0x4a1028, emissiveIntensity: 0.3, envMap: env, envMapIntensity: env ? 0.45 : 0,
        });
        // The old furrow was a thin box stuck through the ball; the furrow is in the surface now.
        for (const child of brainGroup.children) {
            if (child !== brain && child.geometry && child.geometry.type === 'BoxGeometry') child.visible = false;
        }

        // Synapses: arcs that leave the surface and end in a neuron.
        const centre = brainGroup.position.clone();
        const ends = [];
        const dir = new THREE.Vector3();
        const side = new THREE.Vector3();
        for (const line of synapses) {
            dir.set(random() * 2 - 1, random() * 1.4 - 0.35, random() * 2 - 1).normalize();
            side.set(random() - 0.5, random() - 0.5, random() - 0.5).multiplyScalar(1.3);
            const start = centre.clone().addScaledVector(dir, 1.12);
            const reach = 2.0 + random() * 1.5;
            const end = centre.clone().addScaledVector(dir, reach).add(side);
            const middle = centre.clone().addScaledVector(dir, reach * 0.62).addScaledVector(side, -0.55);
            middle.y += 0.5;
            const curve = new THREE.QuadraticBezierCurve3(start, middle, end);
            line.geometry.dispose();
            line.geometry = new THREE.BufferGeometry().setFromPoints(curve.getPoints(28));
            line.material.color.setHex(0xffb4ea);
            line.material.blending = THREE.AdditiveBlending;
            line.material.depthWrite = false;
            line.material.transparent = true;
            line.material.needsUpdate = true;
            ends.push(end);
        }
        if (neurons && neurons.geometry && ends.length) {
            const attribute = neurons.geometry.getAttribute('position');
            for (let i = 0; i < attribute.count && i < ends.length; i++) {
                attribute.setXYZ(i, ends[i].x, ends[i].y, ends[i].z);
            }
            attribute.needsUpdate = true;
        }
        for (const bubble of thoughtBubbles) {
            const old = bubble.material;
            bubble.material = new THREE.MeshStandardMaterial({
                color: 0xffc4e8, emissive: 0xff8fd0, emissiveIntensity: 0.7, roughness: 0.25,
                transparent: true, opacity: old.opacity, envMap: env, envMapIntensity: env ? 1 : 0,
            });
            old.dispose();
        }
        return true;
    }

    // ── factory ──

    function gearGeometry(THREE, radius = 0.42, teeth = 10) {
        const shape = new THREE.Shape();
        const steps = teeth * 4;
        for (let i = 0; i <= steps; i++) {
            const tooth = i % 4 < 2;
            const r = tooth ? radius * 1.18 : radius * 0.92;
            const angle = (i / steps) * Math.PI * 2;
            if (i === 0) shape.moveTo(Math.cos(angle) * r, Math.sin(angle) * r);
            else shape.lineTo(Math.cos(angle) * r, Math.sin(angle) * r);
        }
        const hole = new THREE.Path();
        hole.absarc(0, 0, radius * 0.36, 0, Math.PI * 2, true);
        shape.holes.push(hole);
        const geometry = new THREE.ExtrudeGeometry(shape, {
            depth: 0.12, bevelEnabled: true, bevelThickness: 0.015, bevelSize: 0.015, bevelSegments: 2, curveSegments: 20,
        });
        geometry.translate(0, 0, -0.06);
        return geometry;
    }

    function windowTexture(THREE, doc) {
        return canvasTexture(THREE, doc, 256, 192, (ctx, w, h) => {
            ctx.fillStyle = '#000';
            ctx.fillRect(0, 0, w, h);
            const random = seeded(99);
            for (let row = 0; row < 3; row++) {
                for (let col = 0; col < 6; col++) {
                    const lit = random() > 0.22;
                    ctx.fillStyle = lit ? `rgba(255, ${190 + Math.floor(random() * 50)}, 110, 1)` : 'rgba(70, 40, 25, 1)';
                    ctx.fillRect(18 + col * 38, 26 + row * 52, 24, 34);
                }
            }
        });
    }

    function refineFactory(THREE, space, env, doc) {
        const { building, gear1, gear2, smoke1, smoke2, group } = space;
        if (!building || !group) return false;

        const windows = windowTexture(THREE, doc);
        const intensity = building.material.emissiveIntensity;
        building.material.dispose();
        // The render loop breathes emissiveIntensity; with the map that is the light in the windows.
        building.material = physical(THREE, env, 0xc9552d, {
            roughness: 0.78, emissive: windows ? 0xffffff : 0xff6633, emissiveMap: windows, emissiveIntensity: intensity,
        });

        const gears = gearGeometry(THREE);
        for (const gear of [gear1, gear2]) {
            if (!gear) continue;
            const old = gear.material;
            gear.geometry = gears; // the two shared one torus before; dispose once below
            gear.material = physical(THREE, env, 0xffb02e, { roughness: 0.45, metalness: 0.1, emissive: 0x6a3a00, emissiveIntensity: 0.35, envMapIntensity: env ? 0.5 : 0 });
            if (gear === gear2 || !gear2) old.dispose();
        }

        for (const child of [...group.children]) {
            const g = child.geometry;
            if (!child.isMesh || !g) continue;
            const m = child.material;
            if (m && m.transparent && m.type === 'MeshStandardMaterial' && child !== building) {
                m.transparent = false; // roof and conveyor were see-through boxes
                m.opacity = 1;
                m.roughness = 0.8;
            }
            if (g.type === 'CylinderGeometry' && g.parameters.height > 1 && !child.userData.rimAdded) {
                // Chimney: a glowing rim at the mouth.
                const rim = new THREE.Mesh(
                    new THREE.TorusGeometry(g.parameters.radiusTop, 0.03, 10, 32),
                    new THREE.MeshStandardMaterial({ color: 0x2a1408, emissive: 0xff7a2a, emissiveIntensity: 1.4 }),
                );
                rim.rotation.x = Math.PI / 2;
                rim.position.y = g.parameters.height / 2;
                rim.userData = { type: 'chimney-rim' };
                child.add(rim);
                child.userData = { ...child.userData, rimAdded: true };
            }
        }
        for (const smoke of [smoke1, smoke2]) {
            if (!smoke) continue;
            smoke.material.color.setHex(0xd8c2b4);
            smoke.material.size = Math.max(smoke.material.size, 0.34);
            smoke.material.opacity = 0.32;
        }
        return true;
    }

    // ── farm ──

    function plankTexture(THREE, doc) {
        return canvasTexture(THREE, doc, 256, 256, (ctx, w, h) => {
            ctx.fillStyle = '#b5402e';
            ctx.fillRect(0, 0, w, h);
            const random = seeded(7);
            for (let x = 0; x < w; x += 16) {
                ctx.fillStyle = `rgba(0,0,0,${0.05 + random() * 0.12})`;
                ctx.fillRect(x, 0, 16, h);
                ctx.fillStyle = 'rgba(40,10,5,0.55)';
                ctx.fillRect(x, 0, 1.5, h);
            }
            ctx.fillStyle = '#f1ece0';
            ctx.fillRect(0, 0, w, 7);
            ctx.fillRect(0, h - 7, w, 7);
        });
    }

    function doorTexture(THREE, doc) {
        return canvasTexture(THREE, doc, 128, 192, (ctx, w, h) => {
            ctx.fillStyle = '#7b2b20';
            ctx.fillRect(0, 0, w, h);
            ctx.strokeStyle = '#f1ece0';
            ctx.lineWidth = 9;
            ctx.strokeRect(5, 5, w - 10, h - 10);
            ctx.beginPath();
            ctx.moveTo(5, 5); ctx.lineTo(w - 5, h - 5);
            ctx.moveTo(w - 5, 5); ctx.lineTo(5, h - 5);
            ctx.stroke();
        });
    }

    function grassTexture(THREE, doc) {
        return canvasTexture(THREE, doc, 256, 256, (ctx, w, h) => {
            const gradient = ctx.createRadialGradient(w / 2, h / 2, 10, w / 2, h / 2, w / 2);
            gradient.addColorStop(0, '#6fa843');
            gradient.addColorStop(0.7, '#4d8232');
            gradient.addColorStop(1, '#2f5a22');
            ctx.fillStyle = gradient;
            ctx.fillRect(0, 0, w, h);
            const random = seeded(31);
            for (let i = 0; i < 900; i++) {
                ctx.fillStyle = random() > 0.5 ? 'rgba(150,200,90,0.35)' : 'rgba(30,70,25,0.35)';
                ctx.fillRect(random() * w, random() * h, 2, 3);
            }
        });
    }

    function refineFarm(THREE, space, env, doc) {
        const { barn, group, blades, animals = [] } = space;
        if (!barn || !group) return false;
        for (const child of barn.children) {
            const g = child.geometry;
            if (!g) continue;
            if (g.type === 'BoxGeometry') {
                const planks = plankTexture(THREE, doc);
                child.material.dispose();
                child.material = physical(THREE, env, planks ? 0xffffff : 0xb5402e, { map: planks, roughness: 0.85 });
            } else if (g.type === 'PlaneGeometry') {
                const door = doorTexture(THREE, doc);
                child.material.dispose();
                child.material = new THREE.MeshStandardMaterial({ color: door ? 0xffffff : 0x7b2b20, map: door, roughness: 0.8 });
            } else if (g.type === 'ExtrudeGeometry') {
                child.material.color.setHex(0x4a3226);
                child.material.roughness = 0.9;
            } else if (child.material && child.material.color.getHex() === 0x888888) {
                Object.assign(child.material, { roughness: 0.3, metalness: 0.7, envMapIntensity: env ? 1.2 : 0 });
                child.material.color.setHex(0xc2c7cf); // silo and its cap
            }
        }
        for (const child of group.children) {
            if (child.isMesh && child.geometry.type === 'CircleGeometry') {
                const grass = grassTexture(THREE, doc);
                child.material.dispose();
                child.material = new THREE.MeshStandardMaterial({ color: grass ? 0xffffff : 0x4d8232, map: grass, roughness: 0.95 });
            }
        }
        if (blades) {
            blades.traverse((obj) => {
                if (!obj.isMesh) return;
                const old = obj.material;
                obj.material = physical(THREE, env, 0xf4f0e6, { roughness: 0.55 });
                old.dispose();
            });
        }
        for (const animal of animals) {
            const body = animal.children[0];
            if (body && body.material) {
                body.material.emissiveIntensity = Math.min(body.material.emissiveIntensity, 0.18);
                body.material.roughness = 0.45;
            }
        }
        return true;
    }

    // ── studio ──

    function clapperTexture(THREE, doc) {
        return canvasTexture(THREE, doc, 256, 64, (ctx, w, h) => {
            ctx.fillStyle = '#111';
            ctx.fillRect(0, 0, w, h);
            ctx.fillStyle = '#f4f4f4';
            for (let x = -h; x < w; x += 44) {
                ctx.beginPath();
                ctx.moveTo(x, h); ctx.lineTo(x + 22, h); ctx.lineTo(x + 22 + h, 0); ctx.lineTo(x + h, 0);
                ctx.closePath();
                ctx.fill();
            }
        });
    }

    function refineStudio(THREE, space, env, doc) {
        const { clap, group } = space;
        if (!group) return false;
        if (clap) {
            const stripes = clapperTexture(THREE, doc);
            const old = clap.material;
            clap.material = new THREE.MeshStandardMaterial({ color: stripes ? 0xffffff : 0xee4466, map: stripes, roughness: 0.5 });
            old.dispose();
        }
        for (const child of group.children) {
            if (!child.isMesh || !child.material) continue;
            if (child.geometry.type === 'CircleGeometry') {
                Object.assign(child.material, { roughness: 0.25, metalness: 0.2, envMapIntensity: env ? 1.1 : 0 }); // a polished stage
            } else if (child.geometry.type === 'BoxGeometry' && child.material.transparent && child.material.opacity < 1) {
                child.material.transparent = false; // the studio hall was a see-through box
                child.material.opacity = 1;
                child.material.color.setHex(0x3a3a52);
            }
        }
        return true;
    }

    /**
     * Runs the whole detail pass once.
     * @returns {object|null} what was changed, or null when it already ran
     */
    function refine(app, THREE = root.THREE, doc = root.document) {
        if (!app || !app.spaces || app._sceneRefined) return null;
        app._sceneRefined = true;
        const env = buildEnvironment(THREE, app.renderer);
        const report = { environment: Boolean(env), materials: 0, shapes: 0, lights: 0, objects: [] };

        if (app.scene && !app.scene.getObjectByName('refine-sky-light')) {
            const sky = new THREE.HemisphereLight(0x9aa8ff, 0x1a1024, 0.45);
            sky.name = 'refine-sky-light';
            app.scene.add(sky);
        }
        for (const [key, space] of Object.entries(app.spaces)) {
            if (!space.group || key === 'ideas' || key === 'desktop') continue; // bubbles stay; the sun is built in sun.js
            const done = refineCommon(THREE, space.group, env);
            report.materials += done.materials;
            report.shapes += done.shapes;
        }
        const lit = { thebrain: 0xffd2e6, agentfarm: 0xffe2b0, video: 0xcfd6ff, clawport: 0xe8ffe0 };
        for (const [key, color] of Object.entries(lit)) {
            if (app.spaces[key] && app.spaces[key].group) { addKeyLight(THREE, app.spaces[key].group, color); report.lights++; }
        }
        const steps = [
            ['thebrain', refineBrain], ['swedesign', refineFactory], ['agentfarm', refineFarm], ['video', refineStudio],
        ];
        for (const [key, step] of steps) {
            try {
                if (app.spaces[key] && step(THREE, app.spaces[key], env, doc)) report.objects.push(key);
            } catch (err) {
                // One object failing must not take the scene down; it simply keeps its general polish.
                console.warn('[SceneRefine]', key, err);
            }
        }
        return report;
    }

    const api = { refine, buildEnvironment, brainRadius, brainGeometry, gearGeometry, noise3, ridges, seeded, smoothGeometry, upgradeMaterial };
    if (typeof module !== 'undefined' && module.exports) module.exports = api;
    else root.VibeSceneRefine = api;
})(typeof window !== 'undefined' ? window : globalThis);
