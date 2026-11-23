/**
 * Ideas space: a chat next to the canvas of the open bubble, and the states of its cards.
 *
 * Canvas on the left, chat on the right. What is typed goes the existing way
 * (window.vibemind.sendChatMessage -> main -> Python -> process_intent); this file adds
 * no channel of its own. With every sentence it sends the context the Brain needs to
 * resolve names: the open bubble and the cards on screen (buildContext).
 *
 * Card states:
 *   pending    the sentence was sent, nothing is stored yet: the card is there at once, pale
 *   confirmed  the stored card arrived on the canvas: the pale one goes
 *   rejected   the tool reported an error: the card goes, the chat names the reason
 *   working    a model is still working on it: the card carries the mark "arbeitet"
 *
 * The canvas draws the stored cards itself (universe_canvas.js, at present as one diagram
 * that cannot take single cards). Cards that are not stored yet therefore sit in a small
 * stack above the canvas until the stored one arrives.
 */
(function (root) {
    'use strict';

    const MAX_CARDS = 100;      // the tools of the Ideas space work on up to 100 cards per bubble
    const SETTLE_MS = 15000;    // a pending card without an answer from the canvas goes after this

    /** Title of a canvas row as the canvas shows it. */
    function cardTitle(node) {
        if (!node) return '';
        const content = node.content && typeof node.content === 'object' ? node.content : null;
        return String((content && (content.title || content.text)) || node.title || '').trim().slice(0, 120);
    }

    function cardFormat(node) {
        return (node && ((node.content_json && node.content_json.type) || (node.format_schema && node.format_schema.type)
            || node.format_type)) || 'note';
    }

    /**
     * The context sent along with a sentence. Kept in one place: its form is agreed with
     * the Ideas space and may still change.
     */
    function cardScore(node) {
        const value = node && node.metadata && node.metadata.bewertung ? Number(node.metadata.bewertung.wert) : NaN;
        return Number.isFinite(value) ? value : null;
    }

    function buildContext({ bubble, nodes, bubbles, newId, selection, lastId } = {}) {
        const context = { space: 'ideas', bubble: null };
        if (bubble && bubble.id != null) {
            context.bubble = { id: String(bubble.id), title: String(bubble.title || '') };
            const all = (Array.isArray(nodes) ? nodes : []).filter((node) => node && node.id != null);
            context.cards = all.slice(0, MAX_CARDS)
                .map((node) => ({ id: String(node.id), title: cardTitle(node), format: cardFormat(node), score: cardScore(node) }));
            // Without the total a name looks unique that is not, once the list is cut.
            if (all.length > MAX_CARDS) context.cards_total = all.length;
            const known = new Set(all.map((node) => String(node.id)));
            // Marked cards in the order of marking ("verbinde die beiden"), and the card last made or changed ("mach das zur Tabelle").
            context.selection = (Array.isArray(selection) ? selection : []).map(String).filter((id) => known.has(id));
            if (lastId != null && known.has(String(lastId))) context.last_id = String(lastId);
        } else {
            context.bubbles = (Array.isArray(bubbles) ? bubbles : []).slice(0, MAX_CARDS)
                .filter((item) => item && item.id != null)
                .map((item) => ({ id: String(item.id), title: String(item.title || '') }));
        }
        if (newId) context.new_id = newId;
        return context;
    }

    // Only a plain opening at the start of the sentence makes a card at once; anything else would turn
    // questions into wrong cards. The list is the choice of the Ideas space; keep it in this one place.
    const NOTE = /^\s*(?:notiz\s*:|notiere\b|halte?\s+fest\b|schreibe?\s+auf\b|merke?\s+dir\b)\s*[:,\-]?\s*(.+)$/i;

    /** The text of a note when the sentence plainly asks to hold one, otherwise null. */
    function noteText(sentence) {
        const found = NOTE.exec(typeof sentence === 'string' ? sentence : '');
        const text = found ? found[1].trim() : '';
        return text || null;
    }

    const same = (a, b) => a.trim().toLowerCase() === b.trim().toLowerCase();

    /** The cards that are not stored yet, or still worked on. No DOM in here. */
    function createCardStore() {
        const cards = new Map(); // id -> { id, title, state, reason }
        const list = () => [...cards.values()];
        return {
            list,
            pending(id, title) {
                cards.set(id, { id, title, state: 'pending', reason: '' });
                return list();
            },
            working(id, title) {
                const card = cards.get(id);
                cards.set(id, { id, title: title || (card ? card.title : ''), state: 'working', reason: '' });
                return list();
            },
            /** The stored card is on the canvas (same id, or the same title): the pale one goes. */
            confirm(idOrTitle) {
                for (const card of list()) {
                    if (card.id === idOrTitle || same(card.title, String(idOrTitle))) cards.delete(card.id);
                }
                return list();
            },
            reject(id, reason) {
                const card = cards.get(id);
                cards.delete(id);
                return card ? { ...card, state: 'rejected', reason: reason || '' } : null;
            },
            /** After the canvas loaded its rows: everything that is stored now is confirmed. */
            matchLoaded(nodes) {
                for (const node of Array.isArray(nodes) ? nodes : []) {
                    if (!node) continue;
                    const title = cardTitle(node);
                    for (const card of list()) {
                        if (card.state !== 'pending') continue;
                        if (card.id === String(node.id) || (title && same(card.title, title))) cards.delete(card.id);
                    }
                }
                return list();
            },
            /** The database reported this card: whatever was noted or worked on for it is over. */
            settle(id) { cards.delete(String(id)); return list(); },
            /** A pending card that never got an answer from the canvas goes; a working one stays. */
            expire(id) {
                const card = cards.get(id);
                if (card && card.state === 'pending') cards.delete(id);
                return list();
            },
            /** The model has finished (or failed): nothing is worked on any more. */
            endWork() {
                for (const card of list()) if (card.state === 'working') cards.delete(card.id);
                return list();
            },
        };
    }

    const MAX_REASONS = 50;

    /**
     * The reasons given for ratings in a bubble, newest first: from the bubble row
     * (ideas.metadata.bewertungen[], each { id, text, karten: [card id], wert?, erstellt_am }).
     * Every card id becomes { id, title } or, when the card is gone, { id, gone: true }.
     */
    function reasonsFor(row, nodes) {
        const entries = row && row.metadata && Array.isArray(row.metadata.bewertungen) ? row.metadata.bewertungen : [];
        const titles = new Map((Array.isArray(nodes) ? nodes : []).filter((node) => node && node.id != null)
            .map((node) => [String(node.id), cardTitle(node)]));
        return entries
            .filter((entry) => entry && typeof entry.text === 'string' && entry.text.trim())
            .map((entry, index) => ({
                id: String(entry.id != null ? entry.id : index),
                text: entry.text.trim(),
                wert: Number.isFinite(Number(entry.wert)) && entry.wert !== null && entry.wert !== '' ? Number(entry.wert) : null,
                erstellt_am: typeof entry.erstellt_am === 'string' ? entry.erstellt_am : '',
                karten: (Array.isArray(entry.karten) ? entry.karten : []).map((id) => {
                    const key = String(id);
                    return titles.has(key) ? { id: key, title: titles.get(key) } : { id: key, gone: true };
                }),
            }))
            .sort((a, b) => (a.erstellt_am < b.erstellt_am ? 1 : a.erstellt_am > b.erstellt_am ? -1 : 0))
            .slice(0, MAX_REASONS);
    }

    const HISTORY_MAX = 200;

    /**
     * The chat history, one per bubble (key = id of the bubble). Kept in memory: it is gone when
     * the app restarts. Where it should be stored is not decided yet.
     */
    function createHistory() {
        const byBubble = new Map();
        return {
            add(key, entry) {
                const list = byBubble.get(key) || [];
                list.push(entry);
                if (list.length > HISTORY_MAX) list.splice(0, list.length - HISTORY_MAX);
                byBubble.set(key, list);
            },
            get(key) { return (byBubble.get(key) || []).slice(); },
        };
    }

    function install() {
        const doc = root.document;
        const view = doc.getElementById('space-view');
        if (!view) return null;
        const store = createCardStore();
        let nodes = [];          // rows of the open bubble as the canvas last loaded them
        let lastId = null;       // the card last made or changed
        let waiting = false;     // a sentence is on its way that made no card: the chat says "arbeitet"
        let planRuns = false;
        let busy = false;

        const el = (tag, className, text) => {
            const node = doc.createElement(tag);
            if (className) node.className = className;
            if (text != null) node.textContent = text;
            return node;
        };

        const panel = el('aside');
        panel.id = 'ideas-chat';
        const head = el('div', 'ideas-chat-head');
        const headTitle = el('span', 'ideas-chat-title', 'Chat');
        const headState = el('span', 'ideas-chat-state');
        head.append(headTitle, headState);
        const log = el('div', 'ideas-chat-log');
        log.id = 'ideas-chat-log';
        const row = el('form', 'ideas-chat-row');
        const input = el('input', 'ideas-chat-input');
        input.id = 'ideas-chat-input';
        input.type = 'text';
        input.autocomplete = 'off';
        input.placeholder = 'Notiz festhalten, formatieren, ordnen …';
        const send = el('button', 'ideas-chat-send', '▶');
        send.type = 'submit';
        row.append(input, send);
        // Reasons given for ratings of the open bubble: a list of their own, not on the cards.
        const reasons = el('details', 'ideas-reasons');
        reasons.id = 'ideas-reasons';
        reasons.hidden = true;
        const reasonsHead = el('summary', 'ideas-reasons-head', 'Begründungen');
        const reasonsList = el('div', 'ideas-reasons-list');
        reasons.append(reasonsHead, reasonsList);
        panel.append(head, reasons, log, row);

        const rows = new Map();  // bubble id -> its row as last reported (ideas table)

        /** Goes to a card and marks it, where the canvas can do that (not while it draws one diagram). */
        function showCard(id) {
            const canvas = root.spaceCanvas;
            if (!canvas || canvas._mermaidMode || !canvas.nodes || !canvas.findNodeById) return false;
            const found = canvas.findNodeById(id);
            if (!found || !found.element) return false;
            canvas.selectNode(found.data.id);
            if (found.element.scrollIntoView) found.element.scrollIntoView({ block: 'center', inline: 'center' });
            return true;
        }

        function renderReasons() {
            const bubble = view.classList.contains('hidden') ? null : openBubble();
            const row = bubble ? rows.get(String(bubble.id)) || overviewRow(bubble.id) : null;
            const list = reasonsFor(row, nodes);
            reasons.hidden = list.length === 0;
            reasonsHead.textContent = `Begründungen (${list.length})`;
            reasonsList.replaceChildren(...list.map((reason) => {
                const item = el('div', 'ideas-reason');
                item.dataset.reasonId = reason.id;
                if (reason.wert != null) item.append(el('span', 'ideas-reason-score', String(reason.wert)));
                item.append(el('span', 'ideas-reason-text', reason.text));
                const links = el('div', 'ideas-reason-cards');
                for (const card of reason.karten) {
                    if (card.gone) { links.append(el('span', 'ideas-reason-gone', 'Karte gelöscht')); continue; }
                    const link = el('button', 'ideas-reason-card', card.title || card.id);
                    link.type = 'button';
                    link.dataset.cardId = card.id;
                    link.addEventListener('click', () => { link.dataset.jump = String(showCard(card.id)); });
                    links.append(link);
                }
                if (reason.karten.length) item.append(links);
                return item;
            }));
        }

        function overviewRow(id) {
            const app = root.multiverseApp;
            const objects = (app && app.spaces && app.spaces.ideas && app.spaces.ideas.objects) || [];
            const found = objects.find((o) => o.userData && o.userData.type === 'bubble'
                && (String(o.userData.db_id) === String(id) || String(o.userData.id) === String(id)));
            return found ? found.userData.data : null;
        }

        /** The row of a bubble as the database (or an answer) reports it. A row without metadata tells nothing new. */
        function bubbleRow(row) {
            if (!row || row.id == null || !row.metadata || typeof row.metadata !== 'object') return;
            rows.set(String(row.id), row);
            renderReasons();
        }

        const stack = el('div');
        stack.id = 'ideas-pending';
        const hint = el('div', 'ideas-empty-hint', 'Tippe rechts, um die erste Notiz festzuhalten');
        hint.id = 'ideas-empty-hint';
        hint.hidden = true;
        view.append(stack, hint, panel);
        view.classList.add('with-chat');

        const history = createHistory();
        let shownKey = null;     // the bubble whose history is in the log

        function line(entry) {
            return el('div', 'ideas-chat-msg ideas-chat-' + entry.kind, entry.text);
        }

        function bubbleKey() {
            const bubble = view.classList.contains('hidden') ? null : openBubble();
            return bubble ? String(bubble.id) : '';
        }

        /** Each bubble has its own history; an answer goes to the bubble it was asked in. */
        function say(text, kind, key = bubbleKey()) {
            history.add(key, { text, kind });
            if (key !== shownKey) return;
            log.appendChild(line({ text, kind }));
            log.scrollTop = log.scrollHeight;
        }

        function showHistory() {
            const key = bubbleKey();
            if (key === shownKey) return;
            shownKey = key;
            log.replaceChildren(...history.get(key).map(line));
            log.scrollTop = log.scrollHeight;
        }

        function renderCards() {
            const cards = store.list();
            stack.replaceChildren(...cards.map((card) => {
                const item = el('div', 'ideas-card');
                item.dataset.cardId = card.id;
                item.dataset.cardState = card.state;
                item.append(el('span', 'ideas-card-title', card.title),
                    el('span', 'ideas-card-mark', card.state === 'working' ? 'arbeitet' : 'vorgemerkt'));
                return item;
            }));
            hint.hidden = !(nodes.length === 0 && cards.length === 0 && !view.classList.contains('hidden'));
        }

        function openBubble() {
            const app = root.multiverseApp;
            const canvas = root.spaceCanvas;
            const titleEl = doc.getElementById('space-title');
            const id = (canvas && canvas.bubbleId) || root.__currentBubbleId || (app && app.selectedBubbleId) || null;
            return id == null ? null : { id, title: titleEl ? titleEl.textContent : '' };
        }

        function overviewBubbles() {
            const app = root.multiverseApp;
            const objects = (app && app.spaces && app.spaces.ideas && app.spaces.ideas.objects) || [];
            return objects.filter((o) => o.userData && o.userData.type === 'bubble')
                .map((o) => ({ id: o.userData.db_id || o.userData.id, title: o.userData.title }));
        }

        /** Context for a sentence typed anywhere in the Ideas space (also used by the console below the overview). */
        function contextNow(newId) {
            const inside = !view.classList.contains('hidden');
            const canvas = root.spaceCanvas;
            // The canvas marks one card at a time; marking several in order is not there yet.
            const selection = canvas && canvas.selectedNode != null ? [canvas.selectedNode] : [];
            return buildContext({ bubble: inside ? openBubble() : null, nodes, bubbles: overviewBubbles(), newId, selection, lastId });
        }

        function showState() {
            headState.textContent = waiting || planRuns ? 'arbeitet \u2026' : '';
        }

        function titleOf(id) {
            const node = nodes.find((item) => item && String(item.id) === String(id));
            return node ? cardTitle(node) : (openBubble() || {}).title || '';
        }

        /** What the answer says was stored: { op, id, pending_id, row }, and the cards a model still works on. */
        function applyAnswer(response, newId, note) {
            for (const change of Array.isArray(response.changes) ? response.changes : []) {
                if (!change || change.id == null) continue;
                // An equal title in the bubble returns the card that is there: then id differs from pending_id.
                if (change.pending_id) store.settle(change.pending_id);
                store.settle(change.id);
                if (change.op === 'create' || change.op === 'update') lastId = String(change.id);
                // A new reason comes as an update of the bubble row.
                if (change.op === 'update' && change.row && change.row.metadata) bubbleRow(change.row);
            }
            if (!response.working) return;
            const targets = Array.isArray(response.targets) && response.targets.length ? response.targets : (newId ? [newId] : []);
            for (const id of targets) store.working(String(id), String(id) === newId ? note : titleOf(id));
        }

        async function submit(text) {
            if (!text || busy) return;
            busy = true;
            panel.dataset.busy = 'true';
            const asked = bubbleKey();
            root.dispatchEvent(new root.CustomEvent('vibemind:sentence-sent'));
            say(text, 'user', asked);
            const note = noteText(text);
            const newId = note && root.crypto && root.crypto.randomUUID ? root.crypto.randomUUID() : '';
            waiting = !newId;
            showState();
            if (newId) {
                store.pending(newId, note);
                renderCards();
                root.setTimeout(() => { store.expire(newId); renderCards(); }, SETTLE_MS);
            }
            try {
                const response = await root.vibemind.sendChatMessage(text, contextNow(newId));
                const failed = !response || response.success === false;
                const message = (response && response.message) || (failed ? 'Keine Antwort' : 'OK');
                if (failed && newId) store.reject(newId, message);
                if (!failed) applyAnswer(response, newId, note);
                say(message, failed ? 'error' : 'agent', asked);
            } catch (error) {
                if (newId) store.reject(newId, error.message);
                say('Fehler: ' + error.message, 'error', asked);
            } finally {
                busy = false;
                waiting = false;
                showState();
                delete panel.dataset.busy;
                renderCards();
            }
        }

        row.addEventListener('submit', (event) => {
            event.preventDefault();
            const text = input.value.trim();
            input.value = '';
            submit(text);
        });
        // Keys typed here must not reach the shortcuts of the scene.
        input.addEventListener('keydown', (event) => event.stopPropagation());

        root.addEventListener('vibemind:canvas-loaded', (event) => {
            nodes = (event.detail && Array.isArray(event.detail.nodes)) ? event.detail.nodes : [];
            store.matchLoaded(nodes);
            showHistory(); // the bubble is known for certain once its rows are loaded
            renderReasons();
            renderCards();
        });
        root.addEventListener('vibemind:canvas-node-added', (event) => {
            const node = event.detail && event.detail.node;
            if (!node) return;
            nodes = nodes.concat([node]);
            // The card is shown as soon as the database reports it; the text of the answer comes seconds later.
            if (node.id != null) { store.settle(node.id); lastId = String(node.id); }
            store.matchLoaded([node]);
            renderCards();
        });
        // A report of the database for a card ends the work on it.
        root.addEventListener('vibemind:canvas-node-updated', (event) => {
            const id = event.detail && event.detail.id;
            if (id == null) return;
            store.settle(id);
            lastId = String(id);
            renderCards();
        });
        // A plan of the Brain that runs in this space: the chat says so.
        root.addEventListener('vibemind:task-status', (event) => {
            const status = event.detail || {};
            if (status.space !== 'ideas') return;
            planRuns = status.state === 'running';
            showState();
            if (!planRuns) { store.endWork(); renderCards(); }
        });

        // While a bubble is open this chat is the one place to type; the console below the scene rests.
        const sync = () => {
            const inside = !view.classList.contains('hidden');
            doc.body.classList.toggle('ideas-chat-open', inside);
            const titleEl = doc.getElementById('space-title');
            headTitle.textContent = inside && titleEl && titleEl.textContent ? 'Chat · ' + titleEl.textContent : 'Chat';
            if (!inside) { nodes = []; lastId = null; }
            showHistory();
            renderReasons();
            renderCards();
        };
        new root.MutationObserver(sync).observe(view, { attributes: true, attributeFilter: ['class'] });
        const titleEl = doc.getElementById('space-title');
        if (titleEl) new root.MutationObserver(sync).observe(titleEl, { childList: true, characterData: true, subtree: true });
        sync();

        return { submit, contextNow, store, bubbleRow };
    }

    const api = { buildContext, noteText, cardTitle, createCardStore, createHistory, reasonsFor, MAX_CARDS, HISTORY_MAX, MAX_REASONS };
    if (typeof module !== 'undefined' && module.exports) {
        module.exports = api;
    } else {
        const start = () => { root.VibeIdeasChat = { ...api, ...(install() || {}) }; };
        if (root.document.readyState === 'loading') root.document.addEventListener('DOMContentLoaded', start);
        else start();
    }
})(typeof window !== 'undefined' ? window : globalThis);
