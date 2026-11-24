/**
 * One fixed bar for every open bubble, the same in an empty and in a full one, always at the same
 * place: a row of its own below the header of the bubble, so it covers nothing.
 *
 *   Suche · − + · Verbindungsbild | Zusammenfassung · White Paper · Bewerten | Sprache · Chat
 *
 * Before, each view brought its own controls (the bar of the cards, the zoom of the diagram, the
 * English toolbar of the old canvas) and the floating buttons Summaries, White Paper, EVAL and
 * Start Voice were moved around or hidden; in a bubble with cards some were gone. Now those old
 * controls are hidden inside a bubble (styles/bubble-bar.css) and this bar works them.
 *
 * What a button cannot do right now is shown switched off, with the reason as its title, never
 * removed. Zusammenfassung and White Paper send a sentence to the Brain like a typed one; the
 * sentence is fixed in the preload (SENTENCE_BUTTONS), which also vouches for the click.
 */
(function (root, factory) {
    const api = factory();
    if (typeof module === 'object' && module.exports) module.exports = api;
    if (root) root.VibeBubbleBar = api;
})(typeof window !== 'undefined' ? window : null, function () {
    'use strict';

    const BAR_ID = 'bubble-bar';

    /** The voice button from the state of the voice panel (index.html keeps it there). */
    function voiceState({ available, indicator, status }) {
        if (!available) return { label: 'Sprache starten', disabled: true, state: 'aus', title: 'Sprachdienst nicht verfügbar' };
        if (indicator === 'active') return { label: 'Sprache stoppen', disabled: false, state: 'an', title: 'Sprache läuft – klicken zum Stoppen' };
        if (indicator === 'connecting') return { label: 'Verbinde …', disabled: true, state: 'verbindet', title: 'Sprache verbindet' };
        const failed = /error|fehler|timeout/i.test(String(status || ''));
        return { label: 'Sprache starten', disabled: false, state: failed ? 'fehler' : 'bereit',
            title: failed ? 'Der letzte Start ging nicht – erneut versuchen' : 'Sprache starten' };
    }

    /** Count text of the cards as the bar shows it. */
    function countText(state) {
        if (!state) return '';
        if (state.query && state.query.trim()) return `${state.shown} von ${state.count}`;
        return state.count === 1 ? '1 Karte' : `${state.count} Karten`;
    }

    /** What every button shows, from what the page offers now. Pure, so it is tested without a page. */
    function plan(env) {
        const cards = env.cards;                  // null: the diagram is shown
        const graph = env.view === 'graph';
        const sentences = env.sentences || {};
        const canSend = typeof env.submit === 'function';
        const empty = !cards ? env.cardCount === 0 : cards.count === 0;
        const send = (sentence) => {
            if (!sentence || !canSend) return { disabled: true, title: 'Gehirn-Chat nicht verfügbar' };
            if (empty) return { disabled: true, title: 'Noch keine Karten in dieser Bubble' };
            return { disabled: false, title: `Schickt „${sentence}“ an das Gehirn` };
        };
        return {
            search: graph ? { disabled: true, title: 'Suche gilt den Karten – erst „Karten“ wählen' }
                : { disabled: !cards, title: 'Karte nach Titel suchen' },
            count: countText(cards),
            smaller: { disabled: cards ? !cards.smaller : !graph, title: graph ? 'Verbindungsbild verkleinern' : 'Karten kleiner' },
            bigger: { disabled: cards ? !cards.bigger : !graph, title: graph ? 'Verbindungsbild vergrößern' : 'Karten größer' },
            view: { label: graph ? 'Karten' : 'Verbindungsbild', disabled: !env.canSwitch || (empty && !graph),
                title: graph ? 'Alle Karten lesbar als Raster zeigen'
                    : (empty ? 'Noch keine Karten in dieser Bubble' : 'Karten als Verbindungsbild zeigen') },
            summary: send(sentences.summary),
            whitepaper: send(sentences.whitepaper),
            evaluate: typeof env.toggleEval === 'function'
                ? { disabled: false, label: env.score ? `Bewerten · ${env.score}` : 'Bewerten', pressed: !!env.evalOpen,
                    title: env.score ? `Bewertung dieser Bubble: ${env.score}` : 'Bewertung dieser Bubble ansehen' }
                : { disabled: true, label: 'Bewerten', pressed: false, title: 'Bewertung nicht verfügbar' },
            voice: voiceState(env.voice || {}),
            chat: typeof env.fold === 'function'
                ? { disabled: false, label: env.folded ? 'Chat einblenden' : 'Chat ausblenden', pressed: !env.folded,
                    title: env.folded ? 'Chat rechts aufklappen' : 'Chat einklappen, die Karten bekommen die Breite' }
                : { disabled: true, label: 'Chat', pressed: false, title: 'Chat nur im Ideen-Bereich' },
        };
    }

    function create(doc, win) {
        let bar = null;
        const els = {};

        function button(id, text, className) {
            const b = doc.createElement('button');
            b.type = 'button';
            b.id = id;
            b.className = 'bb-btn' + (className ? ' ' + className : '');
            b.textContent = text;
            return b;
        }

        function build() {
            bar = doc.createElement('div');
            bar.id = BAR_ID;
            bar.setAttribute('role', 'toolbar');
            bar.setAttribute('aria-label', 'Werkzeuge der Bubble');
            const group = (...children) => {
                const g = doc.createElement('div');
                g.className = 'bb-group';
                g.append(...children);
                return g;
            };
            const search = doc.createElement('input');
            search.type = 'search';
            search.id = 'bubble-search';
            search.className = 'bb-search';
            search.placeholder = 'Karte suchen …';
            search.setAttribute('aria-label', 'Karte nach Titel suchen');
            const count = doc.createElement('span');
            count.id = 'bubble-count';
            count.className = 'bb-count';
            const voiceDot = doc.createElement('span');
            voiceDot.className = 'bb-dot';
            const voice = button('bubble-voice-btn', 'Sprache starten', 'bb-voice');
            Object.assign(els, {
                search, count,
                smaller: button('bubble-zoom-out', '−', 'bb-icon'),
                bigger: button('bubble-zoom-in', '+', 'bb-icon'),
                view: button('bubble-view-btn', 'Verbindungsbild'),
                summary: button('bubble-summary-btn', 'Zusammenfassung'),
                whitepaper: button('bubble-whitepaper-btn', 'White Paper'),
                evaluate: button('bubble-eval-btn', 'Bewerten'),
                voice, voiceDot,
                chat: button('bubble-chat-btn', 'Chat ausblenden'),
            });
            els.smaller.setAttribute('aria-label', 'Kleiner');
            els.bigger.setAttribute('aria-label', 'Größer');
            const spacer = doc.createElement('span');
            spacer.className = 'bb-spacer';
            bar.append(
                group(search, count, els.smaller, els.bigger, els.view),
                spacer,
                group(els.summary, els.whitepaper, els.evaluate),
                group(voiceDot, voice, els.chat),
            );

            const canvas = () => win.spaceCanvas || null;
            const chat = () => win.VibeIdeasChat || null;
            // keys typed in the search must not reach the shortcuts of the 3D scene
            search.addEventListener('keydown', (e) => {
                if (e.key === 'Escape' && search.value) { search.value = ''; if (canvas()) canvas().searchCards(''); render(); }
                e.stopPropagation();
            });
            search.addEventListener('input', () => { if (canvas() && canvas().searchCards) canvas().searchCards(search.value); render(); });
            els.smaller.addEventListener('click', () => { if (canvas() && canvas().zoomBy) canvas().zoomBy(-1); render(); });
            els.bigger.addEventListener('click', () => { if (canvas() && canvas().zoomBy) canvas().zoomBy(1); render(); });
            els.view.addEventListener('click', () => {
                const c = canvas();
                if (!c || typeof c.showView !== 'function') return;
                c.showView(c.currentView() === 'graph' ? 'karten' : 'graph');
                render();
            });
            const sendSentence = (key) => (e) => {
                const sentence = win.vibemind && win.vibemind.bubbleSentences && win.vibemind.bubbleSentences[key];
                const c = chat();
                if (!sentence || !c || typeof c.submit !== 'function' || e.currentTarget.disabled) return;
                // the answer comes in the chat: a folded chat opens, or the press seems to do nothing (Lauf 23)
                if (typeof c.folded === 'function' && c.folded() && typeof c.fold === 'function') { c.fold(false); render(); }
                // typed: only a click of the person; the preload checks it against what it saw
                c.submit(sentence, { typed: e.isTrusted === true });
            };
            els.summary.addEventListener('click', sendSentence('summary'));
            els.whitepaper.addEventListener('click', sendSentence('whitepaper'));
            els.evaluate.addEventListener('click', () => { if (typeof win.toggleEvalPanel === 'function') win.toggleEvalPanel(); render(); });
            els.voice.addEventListener('click', () => {
                const old = doc.getElementById('voice-btn');   // index.html keeps the voice state on it
                if (old && typeof old.click === 'function') old.click();
                render();
            });
            els.chat.addEventListener('click', () => {
                const c = chat();
                if (c && typeof c.fold === 'function') c.fold(!c.folded());
                render();
            });
            return bar;
        }

        /** Put the bar below the header of the bubble (once) and mark the view. */
        function mount() {
            const header = doc.getElementById('space-header');
            const view = doc.getElementById('space-view');
            if (!header || !view) return null;
            if (!bar) build();
            if (bar.parentNode !== header.parentNode) header.parentNode.insertBefore(bar, header.nextSibling);
            // only when missing: classList.add writes the attribute even when the class is there,
            // and the observer on this very attribute (watch) would call mount again, without end
            if (!view.classList.contains('with-bar')) view.classList.add('with-bar');
            render();
            return bar;
        }

        function env() {
            const c = win.spaceCanvas || null;
            const chat = win.VibeIdeasChat || null;
            const indicator = doc.getElementById('voice-indicator');
            const status = doc.getElementById('voice-status');
            const score = doc.getElementById('eval-toggle-score');
            const scoreText = score ? String(score.textContent || '').trim() : '';
            const panel = doc.getElementById('eval-panel');
            const view = c && typeof c.currentView === 'function' ? c.currentView() : 'karten';
            return {
                view,
                cards: c && typeof c.cardsState === 'function' ? c.cardsState() : null,
                cardCount: c && Array.isArray(c.lastNodes) ? c.lastNodes.length : 0,
                canSwitch: !!(c && typeof c.showView === 'function'),
                sentences: win.vibemind && win.vibemind.bubbleSentences,
                submit: chat && chat.submit,
                toggleEval: win.toggleEvalPanel,
                score: scoreText && scoreText !== '—' ? scoreText : '',
                evalOpen: !!(panel && panel.classList.contains('open')),
                voice: {
                    available: !!(win.vibemind && typeof win.vibemind.startVoice === 'function'),
                    indicator: indicator ? indicator.className : '',
                    status: status ? status.textContent : '',
                },
                fold: chat && chat.fold,
                folded: chat && typeof chat.folded === 'function' ? chat.folded() : false,
            };
        }

        const apply = (el, s) => {
            el.disabled = !!s.disabled;
            if (s.title) { el.title = s.title; }
            if (s.label !== undefined) el.textContent = s.label;
            if (s.pressed !== undefined) el.setAttribute('aria-pressed', s.pressed ? 'true' : 'false');
        };

        /** Show what every button can do now. */
        function render() {
            if (!bar) return null;
            const p = plan(env());
            apply(els.search, p.search);
            // the canvas clears the search on another bubble: the field follows, unless the person types
            const c = win.spaceCanvas;
            const state = c && typeof c.cardsState === 'function' ? c.cardsState() : null;
            if (state && doc.activeElement !== els.search && els.search.value !== state.query) els.search.value = state.query;
            els.count.textContent = p.count;
            for (const key of ['smaller', 'bigger', 'view', 'summary', 'whitepaper', 'evaluate', 'chat']) apply(els[key], p[key]);
            apply(els.voice, p.voice);
            els.voiceDot.dataset.state = p.voice.state;
            return p;
        }

        /** Follow the view, the cards, the voice panel and the evaluation, so the bar never lies. */
        function watch(Observer) {
            const view = doc.getElementById('space-view');
            const sync = () => {
                if (view && !view.classList.contains('hidden')) {
                    mount();
                    if (doc.body && doc.body.classList && !doc.body.classList.contains('bubble-open')) doc.body.classList.add('bubble-open');
                } else if (doc.body && doc.body.classList && doc.body.classList.contains('bubble-open')) {
                    doc.body.classList.remove('bubble-open');
                }
            };
            if (typeof Observer === 'function') {
                if (view) new Observer(sync).observe(view, { attributes: true, attributeFilter: ['class'] });
                for (const id of ['voice-panel', 'eval-toggle', 'eval-panel']) {
                    const el = doc.getElementById(id);
                    if (el) new Observer(() => render()).observe(el, { attributes: true, childList: true, characterData: true, subtree: true });
                }
            }
            if (typeof win.addEventListener === 'function') {
                // announced at the start of loadNodes, before the cards are drawn: show them after it
                win.addEventListener('vibemind:canvas-loaded', () => { Promise.resolve().then(render); });
            }
            sync();
        }

        return { mount, render, watch, get element() { return bar; }, buttons: els };
    }

    if (typeof document !== 'undefined' && typeof window !== 'undefined' && typeof MutationObserver === 'function') {
        const start = () => { const shared = create(document, window); shared.watch(MutationObserver); window.__bubbleBar = shared; };
        if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
        else start();
    }

    return { BAR_ID, plan, voiceState, countText, create };
});
