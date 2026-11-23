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

    const MAX_CARDS = 500;      // cards sent with a sentence; beyond FULL_CARDS only id and title
    const FULL_CARDS = 100;     // the first cards go with format and score as well
    const SETTLE_MS = 15000;    // a pending card without an answer from the canvas goes after this

    /** Title of a canvas row as the canvas shows it. */
    function cardTitle(node) {
        if (!node) return '';
        const content = node.content && typeof node.content === 'object' ? node.content : null;
        return String((content && (content.title || content.text)) || node.title || '').trim().slice(0, 120);
    }

    /**
     * The whole title, for the context: the Brain resolves names against it, and a cut title made
     * two cards look alike. Only a card without any title falls back to the start of its text.
     */
    function fullTitle(node) {
        if (!node) return '';
        const content = node.content && typeof node.content === 'object' ? node.content : null;
        const title = String((content && content.title) || node.title || '').trim();
        // A long sentence noted as a card is stored with a cut title (its first 80 characters and
        // "…", by the Ideas server of the Brain) and the whole sentence as its text. Then the
        // context names the card by that sentence (measured 2026-11-23: a title ending "… und…").
        if (title.endsWith('…')) {
            const stem = title.slice(0, -1).trimEnd();
            const text = String((content && content.text) || (typeof node.content === 'string' ? node.content : '') || '').trim();
            const first = text.split('\n')[0].trim();
            if (stem && first.length > stem.length && first.startsWith(stem)) return first.slice(0, FULL_TITLE_MAX);
        }
        return title || cardTitle(node);
    }

    const FULL_TITLE_MAX = 500;   // a whole sentence, not a whole document

    function cardFormat(node) {
        return (node && ((node.content_json && node.content_json.type) || (node.format_schema && node.format_schema.type)
            || node.format_type)) || 'note';
    }

    /**
     * The context sent along with a sentence. Kept in one place: its form is agreed with
     * the Ideas space and may still change.
     */
    // Ids of the database come in three forms: 8 hex characters (most bubbles), 32 hex characters
    // (connections) and a UUID (newer rows, cards noted by the app). They are passed on unchanged.
    // The form only tells them from what is no database id at all: the local number of the
    // Python part ("1"), a title, an index.
    const DB_ID = /^[0-9a-f]{8}$|^[0-9a-f]{32}$|^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
    const isDbId = (value) => typeof value === 'string' && DB_ID.test(value);

    /**
     * The database id of the open bubble, unchanged, or null.
     * `candidates`: what the app holds about the bubble, in order of trust. A candidate in the
     * form of a database id is the id. Any other (the local number of the Python part, a title, an index) is only
     * used to look the bubble up (`lookup` returns the scene object) and to read its db_id.
     */
    function bubbleDbId(candidates, lookup) {
        const known = (Array.isArray(candidates) ? candidates : []).filter((value) => value != null && value !== '');
        const direct = known.find(isDbId);
        if (direct) return direct;
        for (const value of known) {
            const found = typeof lookup === 'function' ? lookup(value) : null;
            const data = (found && found.userData) || {};
            const id = [data.db_id, data.id, data.data && data.data.id].find(isDbId);
            if (id) return id;
        }
        return null;
    }

    function cardScore(node) {
        const value = node && node.metadata && node.metadata.bewertung ? Number(node.metadata.bewertung.wert) : NaN;
        return Number.isFinite(value) ? value : null;
    }

    function buildContext({ bubble, nodes, nodesBubbleId, bubbles, newId, selection, lastId } = {}) {
        const context = { space: 'ideas', bubble: null };
        if (bubble) {
            // The id is the database id of the bubble or null, never anything else: a wrong id made
            // every tool fail (the local number "1" was sent, measured 2026-11-23). With null and
            // the title the Brain can find the bubble or ask back.
            context.bubble = { id: isDbId(bubble.id) ? String(bubble.id) : null, title: String(bubble.title || '') };
            // Cards and bubble must be of the same bubble. Cards loaded for another one (the canvas
            // kept the cards of "Bubble A" in "Bubble B", measured 2026-11-23) would make the
            // Brain resolve names in the wrong bubble and write there: then no cards go at all.
            const ownCards = nodesBubbleId === undefined
                || (isDbId(String(nodesBubbleId)) && context.bubble.id === String(nodesBubbleId));
            const all = (ownCards && Array.isArray(nodes) ? nodes : []).filter((node) => node && node.id != null);
            if (!ownCards && Array.isArray(nodes) && nodes.length) context.cards_withheld = true;
            // Every card up to MAX_CARDS can be named: beyond the first FULL_CARDS with id and title only
            // (a bubble with 101 cards had its 101st out of reach).
            context.cards = all.slice(0, MAX_CARDS).map((node, index) => (index < FULL_CARDS
                ? { id: String(node.id), title: fullTitle(node), format: cardFormat(node), score: cardScore(node) }
                : { id: String(node.id), title: fullTitle(node) }));
            // Always: without the total a name looks unique that is not, once the list is cut.
            context.cards_total = all.length;
            const known = new Set(all.map((node) => String(node.id)));
            // Marked cards in the order of marking ("verbinde die beiden"), and the card last made or changed ("mach das zur Tabelle").
            context.selection = (Array.isArray(selection) ? selection : []).map(String).filter((id) => known.has(id));
            if (lastId != null && known.has(String(lastId))) context.last_id = String(lastId);
        }
        // Also with a bubble open: when its own id is not known (id null), the Brain finds it by
        // its title in this list.
        context.bubbles = (Array.isArray(bubbles) ? bubbles : []).slice(0, MAX_CARDS)
            // only bubbles whose database id is known: an index or a title is no id
            .filter((item) => item && isDbId(String(item.id)))
            .map((item) => ({ id: String(item.id), title: String(item.title || '') }));
        if (newId) context.new_id = newId;
        return context;
    }

    // A sentence that takes something back or removes it. Its answer reports no changed rows, so the
    // list of cards is loaded again once the answer is there.
    const REMOVES = /(zur(?:ü|ue)ck|r(?:ü|ue)ckg(?:ä|ae)ngig|\bundo\b|l(?:ö|oe)sch|entfern)/i;

    /** Whether the cards of the bubble have to be loaded again after the answer to this sentence. */
    function reloadsCards(sentence) {
        return typeof sentence === 'string' && REMOVES.test(sentence);
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

    const ACCEPTED_LINE = '● arbeitet … (Auftrag angenommen)';

    /** The Brain took the order and a model works on it: { ok: true, pending: true, status: 'angenommen' }. */
    function isAccepted(response) {
        return Boolean(response) && response.ok !== false && (response.pending === true || response.status === 'angenommen');
    }

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
            /** The plan failed: every card that was only noted in advance goes. */
            failAll() {
                for (const card of list()) if (card.state === 'pending') cards.delete(card.id);
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
        let nodesBubbleId = null; // ... and the bubble the canvas loaded them for
        let lastId = null;       // the card last made or changed
        let waiting = false;     // a sentence is on its way that made no card: the chat says "arbeitet"
        let planRuns = false;
        let busy = false;
        let acceptedKey = null;  // an order the Brain took and a model works on: the bubble it was asked in
        let staleKey = null;     // ... and the one whose "noch in Arbeit" the chat has already said

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
        // The chat can be folded to a narrow strip, so the cards get the whole width.
        const fold = el('button', 'ideas-chat-fold');
        fold.type = 'button';
        const setFolded = (folded) => {
            view.classList.toggle('chat-folded', folded);
            fold.textContent = folded ? '‹' : '›';
            fold.title = folded ? 'Chat aufklappen' : 'Chat einklappen';
            fold.setAttribute('aria-label', fold.title);
            try { root.localStorage && root.localStorage.setItem('vibemind.chat.eingeklappt', folded ? '1' : '0'); } catch (_) { /* none */ }
        };
        let foldedBefore = false;
        try { foldedBefore = !!root.localStorage && root.localStorage.getItem('vibemind.chat.eingeklappt') === '1'; } catch (_) { /* none */ }
        fold.addEventListener('click', () => setFolded(!view.classList.contains('chat-folded')));
        head.append(fold, headTitle, headState);
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
            if (canvas && typeof canvas.showCard === 'function' && canvas.showCard(id)) return true;  // cards view: open it big
            if (!canvas || canvas._mermaidMode || !canvas.nodes || !canvas.findNodeById) return false;
            const found = canvas.findNodeById(id);
            if (!found || !found.element) return false;
            canvas.selectNode(found.data.id);
            if (found.element.scrollIntoView) found.element.scrollIntoView({ block: 'center', inline: 'center' });
            return true;
        }

        function renderReasons() {
            const bubble = view.classList.contains('hidden') ? null : openBubble();
            // rows are kept under the database id; without it the row of the overview is looked up
            const row = bubble ? (bubble.id && rows.get(bubble.id)) || overviewRow(bubble.id || bubble.key) : null;
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
        setFolded(foldedBefore);

        const history = createHistory();
        let shownKey = null;     // the bubble whose history is in the log

        function line(entry) {
            return el('div', 'ideas-chat-msg ideas-chat-' + entry.kind, entry.text);
        }

        function bubbleKey() {
            const bubble = view.classList.contains('hidden') ? null : openBubble();
            return bubble ? bubble.key : '';
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
            const titleEl = doc.getElementById('space-title');
            const entered = root.__currentEvalBubble || {};
            // What the app knows about the open bubble, the database id first. __currentBubbleId is
            // the local number of the Python part; it only serves to look the bubble up.
            // canvas.bubbleId is not asked: the cards are checked against the bubble found here
            // (buildContext), so it must come from elsewhere than the canvas that loaded them.
            const candidates = [entered.dbId, app && app.selectedBubbleId,
                root.__currentBubbleId, entered.localId];
            const lookup = (value) => (app && app.getBubbleById ? app.getBubbleById(value) : null);
            const raw = candidates.find((value) => value != null && value !== '');
            if (raw == null) return null;
            return {
                id: bubbleDbId(candidates, lookup),      // null when the database id is not known
                key: String(bubbleDbId(candidates, lookup) || raw),
                title: titleEl ? titleEl.textContent : '',
            };
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
            return buildContext({ bubble: inside ? openBubble() : null, nodes, nodesBubbleId, bubbles: overviewBubbles(), newId, selection, lastId });
        }

        function showState() {
            headState.textContent = acceptedKey !== null ? ACCEPTED_LINE.slice(2) : (waiting || planRuns ? 'arbeitet \u2026' : '');
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

        /**
         * Load the cards of the open bubble again from the database (UniverseCanvas.refresh, in
         * place, no navigation). Its loadNodes() reports the new list as vibemind:canvas-loaded.
         */
        function reloadCards() {
            const canvas = root.spaceCanvas;
            if (view.classList.contains('hidden') || !canvas || typeof canvas.refresh !== 'function') return;
            // The canvas knows its bubble from the entry (setBubble). The chat never sets it: an id
            // set here outlived the bubble and the 5-s poll kept loading that bubble later.
            if (!canvas.bubbleId) return;
            Promise.resolve(canvas.refresh()).catch((error) => {
                if (root.vibemind && root.vibemind.writeLog) root.vibemind.writeLog('warn', '[IdeasChat] reload of cards failed', { error: String(error) });
            });
        }

        /**
         * Send a sentence. `typed` is true only when the person sent it from the chat field
         * (a trusted submit); a call from code, a repeat or a follow-up leaves it false.
         */
        async function submit(text, { typed = false } = {}) {
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
                const response = await root.vibemind.sendChatMessage(text, contextNow(newId), typed === true);
                // The Brain took the order, a model works on it; the result comes later at the card.
                const accepted = isAccepted(response);
                // Not understood or asked back (question, rueckfrage, verstanden: false): a calm question,
                // never a failure; the raw original of an error (`fehler`) is never shown.
                const asks = !accepted && !!response && (response.question === true || response.rueckfrage === true || response.verstanden === false);
                // A hint ("keine Spalten") is information for the user, not a failure.
                const hint = !accepted && !asks && !!response && response.hinweis === true;
                const failed = !accepted && !asks && !hint && (!response || response.success === false || response.ok === false);
                const message = (response && (response.message || response.final_text)) || (failed ? 'Keine Antwort' : asks ? 'Wie meinst du das?' : 'OK');
                const targets = accepted && Array.isArray(response.targets) ? response.targets.map(String) : [];
                root.dispatchEvent(new root.CustomEvent('vibemind:sentence-answered', { detail: {
                    text: (response && response.message) || '', success: !failed, note: asks ? 'rueckfrage' : hint ? 'hinweis' : '',
                    ...(accepted ? { accepted: true, space: 'ideas', targets, orders: Array.isArray(response.orders) ? response.orders.map(String) : [] } : {}),
                } }));
                if (failed && newId) store.reject(newId, message);
                // A question back stored nothing: the card noted in advance goes as well.
                if ((asks || hint) && newId) store.settle(newId);
                if (!failed) applyAnswer(accepted ? { ...response, working: true } : response, newId, note);
                if (!failed && reloadsCards(text)) reloadCards();
                if (accepted) {
                    acceptedKey = asked;
                    const said = response.message && response.message !== 'OK' ? ' — ' + response.message : '';
                    say(ACCEPTED_LINE + said, 'agent', asked);
                } else {
                    say(message, failed ? 'error' : asks ? 'rueckfrage' : hint ? 'hinweis' : 'agent', asked);
                }
            } catch (error) {
                if (newId) store.reject(newId, error.message);
                if (root.vibemind && root.vibemind.writeLog) root.vibemind.writeLog('warn', '[IdeasChat] sentence failed', { error: String(error && error.message) });
                say('Das hat nicht geklappt. Bitte noch einmal versuchen.', 'error', asked);
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
            // isTrusted: the browser itself raised the submit (Enter or click by the person), not a script.
            submit(text, { typed: event.isTrusted === true });
        });
        // Keys typed here must not reach the shortcuts of the scene.
        input.addEventListener('keydown', (event) => event.stopPropagation());

        root.addEventListener('vibemind:canvas-loaded', (event) => {
            nodes = (event.detail && Array.isArray(event.detail.nodes)) ? event.detail.nodes : [];
            nodesBubbleId = event.detail && event.detail.bubbleId ? String(event.detail.bubbleId) : null;
            store.matchLoaded(nodes);
            showHistory(); // the bubble is known for certain once its rows are loaded
            renderReasons();
            renderCards();
        });
        // The row of the open bubble from the database (UniverseCanvas._loadBubbleRow): its reasons.
        root.addEventListener('vibemind:bubble-row', (event) => bubbleRow(event.detail && event.detail.row));
        root.addEventListener('vibemind:canvas-node-added', (event) => {
            const node = event.detail && event.detail.node;
            if (!node) return;
            nodes = nodes.concat([node]);
            // The card is shown as soon as the database reports it; the text of the answer comes seconds later.
            if (node.id != null) { store.settle(node.id); lastId = String(node.id); }
            store.matchLoaded([node]);
            renderCards();
        });
        // A card deleted in the database is no longer one the Brain may be told about.
        root.addEventListener('vibemind:canvas-node-removed', (event) => {
            const id = event.detail && event.detail.id;
            if (id == null) return;
            nodes = nodes.filter((node) => !node || String(node.id) !== String(id));
            if (lastId === String(id)) lastId = null;
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
            // An accepted order still runs after its plan: a model works on it.
            planRuns = status.state === 'running' || status.state === 'accepted';
            if (status.state === 'accepted' && acceptedKey === null) acceptedKey = bubbleKey();
            // No end reported for minutes: the chat says so once, with the number of the order.
            if (status.state === 'accepted' && status.stale && acceptedKey !== null && staleKey !== acceptedKey) {
                staleKey = acceptedKey;
                const nr = Array.isArray(status.orders) && status.orders.length ? String(status.orders[0]).slice(0, 8) : '';
                say('● noch in Arbeit' + (nr ? ', Nr. ' + nr : '') + ' — das Ergebnis erscheint, sobald es da ist.', 'agent', acceptedKey);
            }
            // The result is at the card (task-navigate.js saw it arrive): the chat says so once.
            if (acceptedKey !== null && status.state !== 'accepted' && !(status.state === 'running' && status.accepted)) {
                const key = acceptedKey;
                acceptedKey = null;
                if (status.state === 'done') say('✓ fertig' + (status.result ? ' — ' + status.result : ''), 'agent', key);
            }
            showState();
            // The plan failed: nothing of it was stored. The cards noted in advance go, even when the
            // answer to the sentence is late or says something else; the chat names the reason.
            if (status.state === 'failed') store.failAll();
            if (!planRuns) { store.endWork(); renderCards(); }
        });

        // While a bubble is open this chat is the one place to type; the console below the scene rests.
        const sync = () => {
            const inside = !view.classList.contains('hidden');
            doc.body.classList.toggle('ideas-chat-open', inside);
            const titleEl = doc.getElementById('space-title');
            headTitle.textContent = inside && titleEl && titleEl.textContent ? 'Chat · ' + titleEl.textContent : 'Chat';
            if (!inside) { nodes = []; nodesBubbleId = null; lastId = null; }
            showHistory();
            renderReasons();
            renderCards();
        };
        new root.MutationObserver(sync).observe(view, { attributes: true, attributeFilter: ['class'] });
        const titleEl = doc.getElementById('space-title');
        if (titleEl) new root.MutationObserver(sync).observe(titleEl, { childList: true, characterData: true, subtree: true });
        sync();

        // fold / folded: the button "Chat" of the fixed bar of the bubble (bubble-bar.js)
        return { submit, contextNow, store, bubbleRow, fold: setFolded, folded: () => view.classList.contains('chat-folded') };
    }

    const api = { buildContext, reloadsCards, noteText, cardTitle, fullTitle, isAccepted, ACCEPTED_LINE, FULL_CARDS, createCardStore, createHistory, reasonsFor, bubbleDbId, MAX_CARDS, HISTORY_MAX, MAX_REASONS };
    if (typeof module !== 'undefined' && module.exports) {
        module.exports = api;
    } else {
        const start = () => { root.VibeIdeasChat = { ...api, ...(install() || {}) }; };
        if (root.document.readyState === 'loading') root.document.addEventListener('DOMContentLoaded', start);
        else start();
    }
})(typeof window !== 'undefined' ? window : globalThis);
