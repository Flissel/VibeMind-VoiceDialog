/**
 * Every space stays reachable at any window width. The tab strip (11 spaces of the app and the
 * external ones, 1764 px measured) did not fit a 1400 px window: the last tabs lay outside and
 * could not be reached. Now the strip scrolls sideways: arrows ‹ › at its ends (only when it does
 * not fit), the mouse wheel scrolls it, and the active tab is always scrolled into view.
 */
(function (root, factory) {
    const api = factory();
    if (typeof module === 'object' && module.exports) module.exports = api;
    if (root) root.VibeTabScroll = api;
})(typeof window !== 'undefined' ? window : null, function () {
    'use strict';

    const EDGE = 2;          // px of tolerance at the ends (subpixel widths)

    /** Which arrows are needed and usable, from the strip's scroll numbers. */
    function arrowState(scrollLeft, clientWidth, scrollWidth) {
        const overflow = scrollWidth - clientWidth > EDGE;
        return {
            overflow,
            back: overflow && scrollLeft > EDGE,
            forward: overflow && scrollLeft + clientWidth < scrollWidth - EDGE,
        };
    }

    /** How far one arrow click scrolls: most of the visible width, so a tab is never skipped. */
    function step(clientWidth) {
        return Math.max(120, Math.round(clientWidth * 0.8));
    }

    /** The scroll position that shows a tab fully (left, width relative to the strip's content). */
    function scrollFor(tabLeft, tabWidth, scrollLeft, clientWidth) {
        if (tabLeft < scrollLeft) return Math.max(0, tabLeft - 8);
        if (tabLeft + tabWidth > scrollLeft + clientWidth) return tabLeft + tabWidth - clientWidth + 8;
        return scrollLeft;
    }

    function install(doc, win) {
        const strip = doc.querySelector('.space-nav-tabs');
        if (!strip || strip.dataset.scrolls) return null;
        strip.dataset.scrolls = '1';
        const arrow = (dir, text, label) => {
            const b = doc.createElement('button');
            b.type = 'button';
            b.className = 'space-tabs-arrow space-tabs-' + dir;
            b.textContent = text;
            b.title = label;
            b.setAttribute('aria-label', label);
            return b;
        };
        const back = arrow('back', '‹', 'Weitere Spaces links');
        const forward = arrow('forward', '›', 'Weitere Spaces rechts');
        const frame = doc.createElement('div');
        frame.className = 'space-tabs-frame';
        strip.parentNode.insertBefore(frame, strip);
        frame.append(back, strip, forward);

        const update = () => {
            const s = arrowState(strip.scrollLeft, strip.clientWidth, strip.scrollWidth);
            frame.classList.toggle('overflowing', s.overflow);
            back.disabled = !s.back;
            forward.disabled = !s.forward;
            return s;
        };
        const scrollTo = (left) => {
            if (typeof strip.scrollTo === 'function') strip.scrollTo({ left, behavior: 'smooth' });
            else strip.scrollLeft = left;
        };
        back.addEventListener('click', () => scrollTo(strip.scrollLeft - step(strip.clientWidth)));
        forward.addEventListener('click', () => scrollTo(strip.scrollLeft + step(strip.clientWidth)));
        strip.addEventListener('scroll', update, { passive: true });
        // a vertical wheel scrolls the strip sideways
        strip.addEventListener('wheel', (e) => {
            if (!update().overflow || Math.abs(e.deltaY) <= Math.abs(e.deltaX)) return;
            e.preventDefault();
            strip.scrollLeft += e.deltaY;
        }, { passive: false });

        const showActive = () => {
            const tab = strip.querySelector('.space-tab.active');
            if (tab) {
                const left = scrollFor(tab.offsetLeft - strip.offsetLeft, tab.offsetWidth, strip.scrollLeft, strip.clientWidth);
                if (left !== strip.scrollLeft) scrollTo(left);
            }
            update();
        };
        // tabs are added later (external spaces) and change state: follow them
        if (typeof win.MutationObserver === 'function') {
            new win.MutationObserver(showActive).observe(strip, { childList: true, subtree: true, attributes: true, attributeFilter: ['class'] });
        }
        if (typeof win.addEventListener === 'function') win.addEventListener('resize', showActive);
        showActive();
        return { frame, back, forward, update, showActive };
    }

    if (typeof document !== 'undefined' && typeof window !== 'undefined') {
        const start = () => { window.__tabScroll = install(document, window); };
        if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
        else start();
    }

    return { arrowState, step, scrollFor, install };
});
