/**
 * A flag that cannot stay set for ever.
 *
 * The scene locks itself with `isNavigating` while a camera move runs, and entering a bubble is
 * marked with `window.isEnteringBubble`. Both are cleared by the code that ends the move. When
 * that code never runs (a move that got no animation frames, an exception in a callback), the
 * flag stayed set and every later change of space was refused: one stuck entry locked the whole
 * navigation (measured 2026-11-23).
 *
 * guardFlag() turns a property into one that clears itself after `ms` and reports it. The limit
 * is far above the longest regular move (1.5 s), so it only fires when something hangs.
 */
(function (root) {
    'use strict';

    const STUCK_MS = 6000;

    /**
     * @param {object} target        the object that carries the flag
     * @param {string} name          the name of the flag
     * @param {object} [options]
     * @param {number} [options.ms]
     * @param {(info: {flag: string, afterMs: number}) => void} [options.onStuck]
     * @param {{setTimeout: Function, clearTimeout: Function}} [options.timers]
     */
    function guardFlag(target, name, options = {}) {
        const ms = options.ms || STUCK_MS;
        const timers = options.timers || root;
        let value = Boolean(target[name]);
        let timer = null;

        const disarm = () => { if (timer !== null) { timers.clearTimeout(timer); timer = null; } };
        const arm = () => {
            disarm();
            timer = timers.setTimeout(() => {
                timer = null;
                if (!value) return;
                value = false;
                if (options.onStuck) options.onStuck({ flag: name, afterMs: ms });
            }, ms);
        };

        Object.defineProperty(target, name, {
            configurable: true,
            enumerable: true,
            get() { return value; },
            set(next) {
                const now = Boolean(next);
                // Setting it again while it is set does not push the limit further out:
                // a loop that keeps setting it must not keep it alive.
                if (now && !value) arm();
                if (!now) disarm();
                value = now;
            },
        });
        if (value) arm();
        return { release() { disarm(); value = false; } };
    }

    const api = { guardFlag, STUCK_MS };
    if (typeof module !== 'undefined' && module.exports) module.exports = api;
    else root.VibeNavigationGuard = api;
})(typeof window !== 'undefined' ? window : globalThis);
