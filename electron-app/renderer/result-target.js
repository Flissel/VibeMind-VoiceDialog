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

    /** A ziel as the app uses it, or null: plain ids only, node_id may be null. */
    function zielOf(value) {
        if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
        const id = (x) => (typeof x === 'number' && Number.isInteger(x) ? String(x) : x);
        const bubble = id(value.bubble_id);
        const node = id(value.node_id);
        if (typeof value.space !== 'string' || !/^[a-z_]{1,32}$/.test(value.space)) return null;
        if (typeof bubble !== 'string' || !PLAIN_ID.test(bubble)) return null;
        return { space: value.space, bubble_id: bubble, node_id: typeof node === 'string' && PLAIN_ID.test(node) ? node : null };
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
                if (win.spaceNavigator && win.spaceNavigator.switchSpace) win.spaceNavigator.switchSpace(ziel.space);
                else app.navigateToSpace(ziel.space);
                return false;
            }
            if (ziel.space !== 'ideas') return true;          // only Ideas has bubbles to enter
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

        /** Go to the place of a result. `value` is a ziel of the Brain; anything else is ignored. */
        function follow(value) {
            const ziel = zielOf(value);
            if (!ziel) return false;
            if (target && target.ziel.bubble_id === ziel.bubble_id && target.ziel.node_id === ziel.node_id) return true;
            if (timer) win.clearTimeout(timer);
            target = { ziel, tries: 0 };
            look();
            return true;
        }

        /** The bubble of this ziel is open now. */
        function opens(value) {
            const ziel = zielOf(value);
            const app = win.multiverseApp;
            return !!ziel && !!app && insideTarget(app, ziel);
        }

        return { follow, opens, pending: () => (target ? target.ziel : null) };
    }

    return { zielOf, create, STEP_MS, TRIES, MARK_MS, MARK };
});
