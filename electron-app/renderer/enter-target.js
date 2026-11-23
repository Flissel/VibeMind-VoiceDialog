/**
 * Which bubble the enter button opens, and when hovering may change that.
 *
 * Rule: the selected (clicked) bubble always wins. Hovering another bubble never replaces a
 * selected or pinned tooltip and never decides what the button opens. With nothing selected the
 * button opens the bubble whose tooltip is shown; it names that bubble ("Öffnen: <Titel>"), so
 * what it opens is always visible before the click.
 *
 * Used by multiverse.js (tooltip on hover) and bubble-navigation.js (the button).
 */
(function (root, factory) {
    const api = factory();
    if (typeof module === 'object' && module.exports) module.exports = api;
    if (root) root.VibeEnterTarget = api;
})(typeof window !== 'undefined' ? window : null, function () {
    'use strict';

    function known(id) {
        return id !== null && id !== undefined && id !== '';
    }

    /**
     * @param {{selectedIndex?: number, selectedId?: unknown, tooltipId?: unknown}} state
     * @returns {unknown} the id to open, or null (the button does nothing)
     */
    function target(state) {
        const s = state || {};
        // selectedId alone is not enough: it stays behind after an entry (only the index is reset)
        if (s.selectedIndex >= 0 && known(s.selectedId)) return s.selectedId;
        return known(s.tooltipId) ? s.tooltipId : null;
    }

    /**
     * May the bubble under the mouse take over the tooltip (and with it the button)?
     * @param {{selectedIndex?: number, pinned?: boolean}} state
     */
    function hoverMayReplace(state) {
        const s = state || {};
        return !(s.selectedIndex >= 0) && !s.pinned;
    }

    /** Text of the button: what it opens. */
    function label(title) {
        const name = String(title || '').trim() || 'Bubble';
        return '▶ Öffnen: ' + name;
    }

    return { target, hoverMayReplace, label };
});
