/**
 * Renderer side of the external spaces (see ../external-spaces.js).
 *
 * For every space the main process lists, this adds a tab to the navigation bar and a
 * place in the 3D scene: a standing gate in the colour of the space with its sign.
 * Arriving there shows the overlay, leaving hides it (hooks in multiverse.js look at
 * `space.external`).
 */
(function (root) {
    'use strict';

    /** The scene entry for one space; everything the rest of multiverse.js reads from `this.spaces[key]`. */
    function sceneEntry(THREE, space) {
        return {
            objects: [],
            position: new THREE.Vector3(space.position[0], space.position[1], space.position[2]),
            icon: space.icon,
            name: space.label,
            agent: space.agent,
            color: space.color,
            external: true,
            configured: space.configured,
        };
    }

    function signTexture(THREE, doc, space) {
        if (!doc || !doc.createElement) return null;
        const canvas = doc.createElement('canvas');
        canvas.width = 256;
        canvas.height = 256;
        const ctx = canvas.getContext && canvas.getContext('2d');
        if (!ctx) return null;
        const colour = '#' + space.color.toString(16).padStart(6, '0');
        const glow = ctx.createRadialGradient(128, 118, 10, 128, 118, 128);
        glow.addColorStop(0, colour + 'cc');
        glow.addColorStop(0.55, colour + '33');
        glow.addColorStop(1, colour + '00');
        ctx.fillStyle = glow;
        ctx.fillRect(0, 0, 256, 256);
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.font = '96px "Segoe UI Emoji", "Apple Color Emoji", sans-serif';
        ctx.fillText(space.icon, 128, 104);
        ctx.font = '600 30px system-ui, "Segoe UI", sans-serif';
        ctx.fillStyle = '#ffffff';
        ctx.fillText(space.label, 128, 196);
        return new THREE.CanvasTexture(canvas);
    }

    /** A standing gate: ring, glowing sign, small orbiting light, halo hull and base ring. */
    function buildGate(THREE, space, doc = root.document) {
        const group = new THREE.Group();
        group.position.set(space.position[0], space.position[1], space.position[2]);

        const ring = new THREE.Mesh(
            new THREE.TorusGeometry(1.5, 0.09, 16, 96),
            new THREE.MeshStandardMaterial({
                color: space.color, emissive: space.color, emissiveIntensity: 0.55, roughness: 0.3, metalness: 0.4,
            }),
        );
        ring.position.y = 1.7;
        ring.userData = { type: 'external-gate', space: space.id };

        const map = signTexture(THREE, doc, space);
        const sign = new THREE.Mesh(
            new THREE.CircleGeometry(1.42, 64),
            new THREE.MeshBasicMaterial({
                map, color: map ? 0xffffff : space.color, transparent: true, opacity: map ? 1 : 0.35,
                side: THREE.DoubleSide, depthWrite: false,
            }),
        );
        sign.position.y = 1.7;
        sign.userData = { type: 'external-sign', space: space.id };

        const hull = new THREE.Mesh(
            new THREE.IcosahedronGeometry(2.6, 2),
            new THREE.MeshBasicMaterial({ color: space.color, transparent: true, opacity: 0.07, side: THREE.BackSide }),
        );
        hull.position.y = 1.2;

        const base = new THREE.Mesh(
            new THREE.RingGeometry(2.5, 3, 32),
            new THREE.MeshBasicMaterial({ color: space.color, transparent: true, opacity: 0.3, side: THREE.DoubleSide }),
        );
        base.rotation.x = -Math.PI / 2;
        base.position.y = -2;

        group.add(ring, sign, hull, base);
        return { group, ring, sign };
    }

    function addTab(doc, space, onClick) {
        if (doc.getElementById('tab-' + space.id)) return null;
        const tab = doc.createElement('button');
        tab.className = 'space-tab';
        tab.id = 'tab-' + space.id;
        tab.dataset.space = space.id;
        const icon = doc.createElement('span');
        icon.className = 'space-icon';
        icon.textContent = space.icon;
        const label = doc.createElement('span');
        label.className = 'space-name';
        label.textContent = space.label;
        tab.append(icon, label);
        tab.title = space.configured ? space.label : space.label + ' (keine Adresse hinterlegt)';
        tab.onclick = onClick;
        const tabs = doc.querySelectorAll('.space-tab[data-space]');
        if (!tabs.length) return null;
        tabs[tabs.length - 1].after(tab);
        return tab;
    }

    async function install() {
        const bridge = root.vibemind;
        if (!bridge || !bridge.getExternalSpaces) return [];
        const list = await bridge.getExternalSpaces();
        // Wait for the scene: this script may run before the app object exists.
        for (let i = 0; i < 100 && !(root.multiverseApp && root.multiverseApp.scene); i++) {
            await new Promise((resolve) => setTimeout(resolve, 100));
        }
        const app = root.multiverseApp;
        if (!app || !app.scene) return [];
        const THREE = root.THREE;
        for (const space of list) {
            if (app.spaces[space.id]) continue;
            const entry = sceneEntry(THREE, space);
            // A space with its own base model (space-models.js) shows it; the others keep the gate.
            const model = root.VibeSpaceModels ? root.VibeSpaceModels.build(THREE, space) : null;
            const gate = model ? null : buildGate(THREE, space);
            entry.group = model ? model.group : gate.group;
            entry.gate = gate;
            entry.model = model;
            entry.objects.push(entry.group);
            app.spaces[space.id] = entry;
            app.scene.add(entry.group);
            if (root.VibeSceneKit) root.VibeSceneKit.polishObject(THREE, entry.group);
            addTab(root.document, space, () => {
                if (root.spaceNavigator) root.spaceNavigator.switchSpace(space.id, { quelle: 'tab' });
                else app.navigateToSpace(space.id, { quelle: 'tab' });
            });
        }
        // The gates turn slowly towards nothing in particular; a small sign of life.
        const turn = () => {
            root.requestAnimationFrame(turn);
            const t = app.clock ? app.clock.elapsedTime : 0;
            for (const space of list) {
                const entry = app.spaces[space.id];
                const gate = entry && entry.gate;
                if (gate) gate.ring.rotation.y = gate.sign.rotation.y = Math.sin(t * 0.25 + space.position[0]) * 0.5;
                else if (entry && entry.model) entry.model.tick(t);
            }
        };
        turn();
        return list;
    }

    const api = { sceneEntry, buildGate, addTab, install };
    if (typeof module !== 'undefined' && module.exports) {
        module.exports = api;
    } else {
        root.VibeExternalSpaces = api;
        const start = () => install().catch((err) => console.warn('[ExternalSpaces]', err));
        if (root.document.readyState === 'loading') root.document.addEventListener('DOMContentLoaded', start);
        else start();
    }
})(typeof window !== 'undefined' ? window : globalThis);
