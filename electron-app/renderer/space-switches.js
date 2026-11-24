/**
 * Renderer side of the space switches (see ../space-switches.js): a space switched off loses its
 * tab and its place in the scene and is marked `hidden`, which navigateToSpace (multiverse.js)
 * and the click target (space-pick.js) respect. Its objects are kept, only taken out of the scene.
 */
(function (root) {
    'use strict';

    function apply(app, doc, hidden) {
        const done = [];
        for (const id of hidden || []) {
            const space = app && app.spaces && app.spaces[id];
            if (!space) continue;
            space.hidden = true;
            const parts = space.group ? [space.group] : (space.objects || []);
            for (const obj of parts) if (obj && obj.parent) obj.parent.remove(obj);
            const tab = doc && doc.getElementById('tab-' + id);
            if (tab) {
                tab.hidden = true;
                tab.setAttribute('aria-hidden', 'true');
                // `hidden` alone loses against `.space-tab { display: flex }`; an inline important
                // display wins against every stylesheet rule.
                tab.style.setProperty('display', 'none', 'important');
            }
            done.push(id);
        }
        return done;
    }

    async function install() {
        const bridge = root.vibemind;
        if (!bridge || !bridge.getSpaceSwitches) return [];
        const hidden = await bridge.getSpaceSwitches();
        for (let i = 0; i < 100 && !(root.multiverseApp && root.multiverseApp.scene); i++) {
            await new Promise((resolve) => setTimeout(resolve, 100));
        }
        return apply(root.multiverseApp, root.document, hidden);
    }

    const api = { apply, install };
    if (typeof module !== 'undefined' && module.exports) {
        module.exports = api;
    } else {
        root.VibeSpaceSwitches = api;
        const start = () => install().catch((err) => console.warn('[SpaceSwitches]', err));
        if (root.document.readyState === 'loading') root.document.addEventListener('DOMContentLoaded', start);
        else start();
    }
})(typeof window !== 'undefined' ? window : globalThis);
