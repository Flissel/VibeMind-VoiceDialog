/**
 * The way to a result: the Brain names where a writing call put it (ziel = { space, bubble_id,
 * node_id }) in the answer to a sentence, in the end of its plan and at /stand of an order. The app
 * goes there: into the space, into the bubble (the same way as the enter button), and marks the card.
 * Without ziel nothing happens here; the jump into the space stays with task-navigate.js.
 *
 * One step at a time, looked at every STEP_MS: the camera moves and the cards load in their own time.
 * A new ziel replaces the one on the way; the same ziel again (answer and end of plan both name it)
 * does not start anew. After TRIES looks it gives up quietly.
 */
(function (root, factory) {
    const api = factory();
    if (typeof module === 'object' && module.exports) module.exports = api;
    else root.VibeResultTarget = api;
})(typeof self !== 'undefined' ? self : this, function () {
    const STEP_MS = 250;
    const TRIES = 48;              // twelve seconds: a camera move, the entry and the load of the cards
    const MARK_MS = 6000;          // how long the card stays marked
    const MARK = 'kv-ziel';
    const PLAIN_ID = /^[A-Za-z0-9-]{1,64}$/;

    /**
     * The names of the Brain (config/space_agent_registry.yml) where the app calls the space otherwise.
     * Bubbles and the research of the Brain write into bubbles of Ideas.
     */
    const ALIASES = Object.freeze({ rowboat: 'roarboot', coding: 'projects', bubbles: 'ideas', research: 'ideas', recherche: 'ideas', schedule: 'orders' });
    /** How the chat names a space the app has no place for. */
    const NAMES = Object.freeze({ minibook: 'Minibook', n8n: 'n8n' });

    /**
     * A ziel as the app uses it, or null: plain ids only. `space` is the space of the app, `named`
     * the name the Brain sent. A bubble is needed only to open one: without it the app goes to the
     * space (Sales, Rowboat, …), where the result is shown.
     */
    function zielOf(value) {
        if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
        const id = (x) => (typeof x === 'number' && Number.isInteger(x) ? String(x) : x);
        const bubble = id(value.bubble_id);
        const node = id(value.node_id);
        if (typeof value.space !== 'string' || !/^[a-z0-9_]{1,32}$/.test(value.space)) return null;
        if (bubble != null && bubble !== '' && (typeof bubble !== 'string' || !PLAIN_ID.test(bubble))) return null;
        const hasBubble = typeof bubble === 'string' && bubble !== '';
        return { space: ALIASES[value.space] || value.space, named: value.space, bubble_id: hasBubble ? bubble : null,
            node_id: hasBubble && typeof node === 'string' && PLAIN_ID.test(node) ? node : null };
    }

    /** The space as the chat names it: its label in the scene, else a plain name of the Brain's word. */
    function nameOf(ziel, app) {
        const space = app && app.spaces && app.spaces[ziel.space];
        if (space && typeof space.name === 'string' && space.name) return space.name;
        return NAMES[ziel.named] || ziel.named.charAt(0).toUpperCase() + ziel.named.slice(1);
    }

    function create(win, doc) {
        let target = null;     // { ziel, tries }
        let timer = null;

        /** The bubble of the overview with this id (local or database id), or null. */
        function bubbleOf(app, id) {
            const mesh = app && typeof app.getBubbleById === 'function'
                ? (app.getBubbleById(id) || app.getBubbleById(Number(id))) : null;
            return mesh && mesh.userData ? mesh.userData : null;
        }

        /** The bubble open now is the one of the ziel. */
        function insideTarget(app, ziel) {
            if (!app.isInsideBubble) return false;
            const open = win.spaceCanvas ? win.spaceCanvas.bubbleId : null;
            if (open == null) return false;
            if (String(open) === ziel.bubble_id) return true;
            const data = bubbleOf(app, ziel.bubble_id);
            return !!data && (String(data.id) === String(open) || String(data.db_id) === String(open));
        }

        /** Mark the card: scrolled into view, a ring for a while, selected on the canvas. */
        function mark(nodeId) {
            const card = doc.querySelector ? doc.querySelector(`[data-card-id="${nodeId}"]`) : null;
            if (win.spaceCanvas && typeof win.spaceCanvas.selectNode === 'function') win.spaceCanvas.selectNode(nodeId);
            if (!card) return false;
            card.classList.add(MARK);
            if (typeof card.scrollIntoView === 'function') card.scrollIntoView({ block: 'center', behavior: 'smooth' });
            win.setTimeout(() => card.classList.remove(MARK), MARK_MS);
            return true;
        }

        /** One step towards the ziel; true when there (or nothing more to do). */
        function step(ziel) {
            const app = win.multiverseApp;
            if (!app || app.isNavigating || win.isEnteringBubble) return false;
            if (app.currentSpace !== ziel.space) {
                const how = target && target.options ? target.options : undefined;
                if (win.spaceNavigator && win.spaceNavigator.switchSpace) win.spaceNavigator.switchSpace(ziel.space, how);
                else app.navigateToSpace(ziel.space, how);
                return false;
            }
            if (ziel.space !== 'ideas' || !ziel.bubble_id) return true;   // only Ideas has bubbles to enter
            if (!insideTarget(app, ziel)) {
                const nav = win.bubbleNavigation;
                if (!nav) return true;
                if (app.isInsideBubble) { nav.exitSpace(); return false; }   // another bubble is open
                const data = bubbleOf(app, ziel.bubble_id);
                if (!data) return false;                       // the overview has not loaded it yet
                const id = data.id != null ? data.id : ziel.bubble_id;
                if (win.vibemind && win.vibemind.enterBubble) win.vibemind.enterBubble(id);
                nav.enterSpace(id);
                return false;
            }
            return ziel.node_id === null || mark(ziel.node_id);
        }

        function look() {
            timer = null;
            if (!target) return;
            if (step(target.ziel) || ++target.tries >= TRIES) { target = null; return; }
            timer = win.setTimeout(look, STEP_MS);
        }

        /**
         * Go to the place of a result. `value` is a ziel of the Brain; anything else is ignored.
         * `options` go with the switch of space (space-navigator.js: quick, back).
         */
        function follow(value, options) {
            const ziel = zielOf(value);
            if (!ziel || !reachable(ziel)) return false;
            if (target && target.ziel.space === ziel.space && target.ziel.bubble_id === ziel.bubble_id
                && target.ziel.node_id === ziel.node_id) return true;
            if (timer) win.clearTimeout(timer);
            target = { ziel, tries: 0, options: options || null };
            look();
            return true;
        }

        /** The bubble of this ziel is open now. */
        function opens(value) {
            const ziel = zielOf(value);
            const app = win.multiverseApp;
            return !!ziel && !!ziel.bubble_id && !!app && insideTarget(app, ziel);
        }

        /** The app has this space and it is switched on. */
        function reachable(ziel) {
            const app = win.multiverseApp;
            const space = app && app.spaces ? app.spaces[ziel.space] : null;
            return !!space && !space.hidden;
        }

        /**
         * A ziel the app cannot go to (a space it does not have, or one switched off): the sentence
         * the chat says instead, calmly. '' for a ziel the app can follow or for no ziel at all.
         */
        function unreachable(value) {
            const ziel = zielOf(value);
            if (!ziel || reachable(ziel)) return '';
            return `Das Ergebnis liegt im Bereich „${nameOf(ziel, win.multiverseApp)}“. Dorthin kann die App nicht springen.`;
        }

        return { follow, opens, unreachable, pending: () => (target ? target.ziel : null) };
    }

    return { zielOf, create, ALIASES, STEP_MS, TRIES, MARK_MS, MARK };
});
