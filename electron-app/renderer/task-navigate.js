/**
 * Renderer side of task navigation: follow a task into its space and show where it stands.
 *
 * Messages from the main process (task-navigation.js):
 *   { type: 'task_navigate', space, registry_space, capability, description }
 *   { type: 'task_status', state: 'running' | 'done' | 'failed', space, step, done, total,
 *     result, error, elapsed_s, plan_id }
 *
 * The jump is skipped while the user is in the middle of something; the status line then
 * says where the task runs and a click on it goes there.
 *
 * The status is shown in the title bar and as a dot on the tab of the working space. Both
 * sit above the pages of the spaces, which cover everything below the tab bar.
 */
(function (root) {
    'use strict';

    const BUSY_MS = 4000;       // an input this recent means: the user is working here
    const RETRY_MS = 250;       // a camera move is running: try again
    const RETRY_LIMIT = 24;     // ... for six seconds at most
    const KEEP_MS = 30000;      // a finished task stays visible this long

    /**
     * Spaces a plan never jumps to. They work in the background; their result is shown in the
     * status line all the same, and their tab still opens them by hand. Desktop: the eyes of the
     * Brain, not a place to look at (2026-11-23).
     */
    const NO_JUMP = Object.freeze(['desktop']);

    /** What to do with a task that belongs to `space`. */
    function decide({ space, currentSpace, knownSpaces, lastInputAt, now, insideBubble }) {
        if (!space || !knownSpaces.includes(space)) return 'ignore';
        if (space === currentSpace) return 'ignore';
        if (NO_JUMP.includes(space)) return 'stay';
        if (insideBubble) return 'note';                      // do not pull the user out of an open bubble
        if (now - lastInputAt < BUSY_MS) return 'note';
        return 'navigate';
    }

    const LABELS = {
        ideas: 'Ideas', projects: 'Project Space', desktop: 'Desktop', roarboot: 'Rowboat', agentfarm: 'Agent Farm',
        video: 'Video Studio', flowzen: 'Blue Rose', mirofish: 'MiroFish', swedesign: 'SWE Design',
        clawport: 'Dashboard', thebrain: 'The Brain',
    };

    /** Name of a space: the fixed ones from the list, the external ones from the scene entry. */
    function labelFor(space, spaces) {
        return LABELS[space] || (spaces && spaces[space] && spaces[space].name) || space;
    }

    function seconds(value) {
        return typeof value === 'number' && Number.isFinite(value)
            ? value.toFixed(1).replace('.', ',') + ' s' : '';
    }

    /**
     * The status line for a `task_status` message: { text, title, state }.
     * `away` = the task runs in another space than the one on screen.
     */
    function describe(message, label, away) {
        const state = message.state === 'done' || message.state === 'failed' || message.state === 'accepted' ? message.state : 'running';
        const count = message.total > 1 ? ` (${Math.min(message.done + (state === 'running' ? 1 : 0), message.total)}/${message.total})` : '';
        const arrow = away ? ' →' : '';
        // The Brain took the order, a model works on it; the result comes later at the card. Never "fehlgeschlagen".
        // Past ACCEPTED_STALE_MS without an end the line stops pretending to work and says so plainly.
        if (state === 'accepted' && message.stale) {
            const nr = orderNumber(message.orders);
            return { state: 'stale', text: `${label}: noch in Arbeit${nr ? ', Nr. ' + nr : ''}${arrow}`,
                title: 'Kein Abschluss gemeldet. Das Ergebnis erscheint an der Karte, sobald es da ist.' };
        }
        if (state === 'accepted' || (state === 'running' && message.accepted)) {
            return { state: 'accepted', text: `● ${label}: ${ACCEPTED_TEXT.slice(2)}${arrow}`, title: message.step || '' };
        }
        if (state === 'running') {
            // A pipeline names its stage; it comes before the step.
            // With its position the short form of the pipelines: "Stufe 3 von 6, Requirements".
            const name = message.stage_label || message.stage;
            const stage = message.stage_nr && message.stage_total
                ? `Stufe ${message.stage_nr} von ${message.stage_total}${name ? ', ' + name : ''}` : name;
            const what = stage && message.stage_nr ? stage : [stage, message.step].filter(Boolean).join(' · ');
            const step = what ? `: ${what}` : '';
            return { state, text: `● ${label}${step}${count}${arrow}`, title: message.result || message.step || '' };
        }
        const took = seconds(message.elapsed_s);
        if (state === 'failed') {
            const why = message.error ? ` — ${message.error}` : '';
            return { state, text: `✕ ${label}: fehlgeschlagen${why}${arrow}`, title: message.error || '' };
        }
        // Raw data of a tool ("{'_meta': …}") is never shown; then the line just says "fertig".
        const result = message.result && !isRaw(message.result) ? ` — ${message.result}` : '';
        return {
            state,
            text: `✓ ${label}: fertig${took ? ' in ' + took : ''}${result}${arrow}`,
            title: [message.result, message.result_ref].filter(Boolean).join('\n'),
        };
    }

    const LINE_MAX = 240;
    const WAIT_MS = 60000;                       // a sentence that never gets an answer: the neutral line goes
    const ANSWER_GRACE_MS = 2000;                // answered before the plan reported: wait this long for it
    const ANSWER_WAIT_MS = 5000;                 // plan done before the answer came: wait this long for it
    const WAITING_TEXT = '\u25CF arbeitet \u2026';
    const ACCEPTED_TEXT = '\u25CF arbeitet \u2026 (Auftrag angenommen)';
    const ACCEPTED_MAX_MS = 20 * 60 * 1000;      // an accepted order whose result never shows: the line goes
    const ACCEPTED_STALE_MS = 3 * 60 * 1000;     // ... before that it says "noch in Arbeit, Nr. …" instead of "arbeitet"

    /** The number of an order as the Brain's receipt names it: the first 8 characters of its id. */
    function orderNumber(orders) {
        const first = Array.isArray(orders) ? orders.find((id) => typeof id === 'string' && id.trim()) : '';
        return first ? first.trim().slice(0, 8) : '';
    }

    /** How many reasons the bubble holds (`metadata.bewertungen`); null when the row does not say. */
    function reasonCount(row) {
        const list = row && row.metadata && typeof row.metadata === 'object' ? row.metadata.bewertungen : null;
        return Array.isArray(list) ? list.length : null;
    }

    /** What changes in a card row when a model writes its result into it. */
    function cardPrint(node) {
        if (!node || typeof node !== 'object') return '';
        const content = node.content;
        return JSON.stringify([node.updated_at || null, node.title || '', content && typeof content === 'object' ? content : String(content == null ? '' : content),
            node.content_json || null, node.format_schema || null, node.summary || null]);
    }

    /** id -> fingerprint of every card in the list. */
    function snapshot(nodes) {
        const map = new Map();
        for (const node of Array.isArray(nodes) ? nodes : []) if (node && node.id != null) map.set(String(node.id), cardPrint(node));
        return map;
    }

    /**
     * Has the result of an accepted order arrived? The id of the card it changed, or null.
     * With `targets` (the cards the Brain named) only those count. Without them any card of the
     * bubble that changed or came counts: the app cannot tell the order's card from another then.
     */
    function resultArrived(before, nodes, targets) {
        const now = snapshot(nodes);
        const base = before instanceof Map ? before : new Map();
        const ids = Array.isArray(targets) && targets.length ? targets.map(String) : [...now.keys()];
        return ids.find((id) => now.has(id) && base.get(id) !== now.get(id)) || null;
    }

    /** One line of at most 240 characters out of any text. */
    function shorten(text) {
        const line = typeof text === 'string' ? text.replace(/\s+/g, ' ').trim() : '';
        return line.length > LINE_MAX ? line.slice(0, LINE_MAX - 1) + '…' : line;
    }

    /** Data of a tool rather than a sentence for a person: a dict, list or call, or its meta field. */
    function isRaw(text) {
        return typeof text === 'string' && (/^\s*[[{(<]/.test(text) || /['"]_meta['"]/.test(text));
    }

    const finished = (message) => Boolean(message) && (message.state === 'done' || message.state === 'failed');

    /**
     * How much of a status is shown while onScreen is the space on screen:
     *   'line'  the line in the title bar and the dot on the tab
     *   'dot'   only the dot on the tab of its space
     *   'none'
     * A running task is always named. A finished one is named only in its own space: an old
     * result or error of another space must not stand above the space the user is in.
     */
    function shows(message, onScreen) {
        if (!message || !message.space) return 'none';
        if (!finished(message)) return 'line';
        // A space without jump is never on screen by itself: its result stands wherever the user is.
        return message.space === onScreen || NO_JUMP.includes(message.space) ? 'line' : 'dot';
    }

    function install() {
        const doc = root.document;
        let lastInputAt = 0;
        let current = null;      // last task_status message
        let keepTimer = null;
        let pending = null;      // { space, tries } a jump waiting for a camera move to end
        let followed = '';       // the space the app is jumping to because of a task
        let answer = '';         // the answer to the sentence last sent, once it is there
        let refusal = '';        // ... or the Brain's sentence on why it did not work
        let awaiting = false;    // a sentence of the app was sent and its answer is not there yet
        let answerTimer = null;  // ... how long a finished plan waits for that answer
        let watch = null;        // an accepted order: { before, bubbleId } the cards as they were when it was taken
        let acceptedTimer = null;
        let staleTimer = null;
        let lastRow = null;      // the last row of the open bubble (vibemind:bubble-row)
        let lastPlanId = '';     // the plan the last status was about
        for (const type of ['pointerdown', 'keydown', 'wheel']) {
            root.addEventListener(type, () => {
                lastInputAt = Date.now();
                // A navigation by the Brain counts once per plan, and only until the person acts:
                // a jump still waiting for a camera move is dropped.
                pending = null;
                followed = '';
            }, { capture: true, passive: true });
        }

        function go(space) {
            const app = root.multiverseApp;
            if (!app) return false;
            if (app.currentSpace === space) return true;
            if (app.isNavigating) return false;
            if (root.spaceNavigator && root.spaceNavigator.switchSpace) root.spaceNavigator.switchSpace(space);
            else app.navigateToSpace(space);
            return true;
        }

        /** Jump now, or as soon as the running camera move has ended. */
        function jump(space) {
            pending = { space, tries: 0 };
            const attempt = () => {
                if (!pending || pending.space !== space) return; // a newer jump took over
                if (go(space) || ++pending.tries >= RETRY_LIMIT) { pending = null; return; }
                root.setTimeout(attempt, RETRY_MS);
            };
            attempt();
        }

        function statusElement() {
            let el = doc.getElementById('task-status');
            if (el) return el;
            const anchor = doc.getElementById('titlebar-space');
            if (!anchor || !anchor.parentNode) return null;
            el = doc.createElement('button');
            el.id = 'task-status';
            el.className = 'task-status';
            el.hidden = true;
            anchor.parentNode.insertBefore(el, anchor.nextSibling);
            el.addEventListener('click', () => {
                if (current && current.space) jump(current.space);
            });
            return el;
        }

        function markTab(space, state) {
            for (const tab of doc.querySelectorAll('.space-tab[data-task]')) {
                if (tab.dataset.space !== space || !state) delete tab.dataset.task;
            }
            const tab = space && state ? doc.getElementById('tab-' + space) : null;
            if (tab) tab.dataset.task = state;
        }

        function render() {
            const el = statusElement();
            if (!el) return;
            if (current && current.waiting) {
                el.textContent = WAITING_TEXT;
                el.title = '';
                el.dataset.state = 'running';
                el.dataset.space = '';
                el.hidden = false;
                markTab('', '');
                return;
            }
            if (!current || !current.space) {
                el.hidden = true;
                markTab('', '');
                return;
            }
            const app = root.multiverseApp;
            // While the app is on its way into the space of the task, that space counts as on
            // screen: a result arriving during the camera move was hidden until the arrival
            // (line empty for 0.5 to 0.7 s, measured 2026-11-23).
            const arriving = followed !== '' && followed === current.space;
            const onScreen = arriving || !app ? current.space : app.currentSpace;
            // The plan is done but the answer to the sentence is not there yet: its last step only
            // has raw data of a tool. The neutral line stays until the sentence for the person comes.
            if (current.state === 'done' && awaiting && !answer) {
                el.textContent = WAITING_TEXT;
                el.title = '';
                el.dataset.state = 'running';
                el.dataset.space = current.space;
                el.hidden = false;
                markTab(current.space, 'running');
                return;
            }
            const line = describe(current, labelFor(current.space, app && app.spaces), onScreen !== current.space);
            el.textContent = line.text;
            el.title = line.title;
            el.dataset.state = line.state;
            el.dataset.space = current.space;
            el.hidden = shows(current, onScreen) !== 'line';
            if (!el.hidden && finished(current)) current.seen = true; // the user had it in front of them
            markTab(current.space, line.state);
        }

        function clear() {
            current = null;
            render();
        }

        /** A new sentence was sent, or a new plan began: what an earlier task ended with is no longer the news. */
        function fresh() {
            if (finished(current)) clear();
        }
        root.addEventListener('vibemind:sentence-sent', () => {
            // The key or click that sent the sentence is no sign that the user works here: they asked
            // for the task and want to see it. Counting it as such kept every typed sentence from
            // jumping (the Enter came 0 s before the plan; only sends without a key event jumped).
            // Input after the send still holds the jump back.
            lastInputAt = 0;
            answer = '';
            refusal = '';
            awaiting = true;
            root.clearTimeout(answerTimer);
            fresh();
            // The first thing to see after a sentence, before the Brain has said anything: a neutral
            // line. The first event of the plan replaces it; an answer without a plan removes it.
            if (!current) {
                current = { state: 'running', space: '', waiting: true };
                root.clearTimeout(keepTimer);
                keepTimer = root.setTimeout(() => { if (current && current.waiting) clear(); }, WAIT_MS);
                render();
            }
        });

        // The answer to the sentence is the plan's own summary, written for the user. It is what a
        // finished task shows; the result of its last step (raw data of a tool) is only the fallback.
        // Answer and end of the plan arrive in either order.
        root.addEventListener('vibemind:sentence-answered', (event) => {
            const detail = (event && event.detail) || {};
            awaiting = false;
            root.clearTimeout(answerTimer);
            // The Brain took the order; a model works on it (answer { ok: true, pending: true }).
            // The line says so until the result is at the card, never "fehlgeschlagen".
            if (detail.accepted) {
                answer = '';
                refusal = '';
                if (!current || current.waiting || current.state === 'accepted' || finished(current)) {
                    current = { state: 'accepted', space: detail.space || (current && current.space) || 'ideas',
                        step: '', done: 0, total: 0, targets: Array.isArray(detail.targets) ? detail.targets.map(String) : [],
                        orders: Array.isArray(detail.orders) ? detail.orders.map(String) : [],
                        // the plan that took the order: its "done" is the acceptance, not the result
                        plan_id: (current && current.plan_id) || lastPlanId };
                    root.clearTimeout(keepTimer);
                    startAccepted();
                    root.dispatchEvent(new root.CustomEvent('vibemind:task-status', { detail: current }));
                }
                render();
                return;
            }
            answer = detail.success === false ? '' : shorten(detail.text);
            // A tool refused or failed: the Brain's sentence says why, in words for the user.
            refusal = detail.success === false ? shorten(detail.text) : '';
            // Answered before any event of the plan: the events of the plan come on another way and
            // often a moment later. Clearing now made the line vanish and come back a moment later
            // as "fertig" (flicker at about 1 s, measured 2026-11-23). The neutral line stays a
            // little; only an answer without a plan that has a place in the app removes it.
            if (current && current.waiting) {
                root.clearTimeout(keepTimer);
                keepTimer = root.setTimeout(() => { if (current && current.waiting) clear(); }, ANSWER_GRACE_MS);
            }
            if (current && current.state === 'done') {
                if (answer) current.result = answer;
                render(); // also ends the neutral line a finished plan kept while waiting for this answer
            }
            if (refusal && current && current.state === 'failed') {
                current.error = refusal;
                render();
            }
        });

        /**
         * An order was accepted: remember the cards as they are now. The 5-s reload of the canvas
         * (vibemind:canvas-loaded) then shows when its result has arrived at the card.
         */
        function startAccepted() {
            const canvas = root.spaceCanvas;
            const nodes = canvas && Array.isArray(canvas.lastNodes) ? canvas.lastNodes : [];
            const bubbleId = (canvas && canvas.bubbleId) || null;
            if (!watch) {
                watch = { before: nodes.length ? snapshot(nodes) : null, bubbleId,
                    // An assessment writes to the bubble (a new reason), not to a card.
                    reasons: lastRow && bubbleId && String(lastRow.id) === String(bubbleId) ? reasonCount(lastRow) : null };
            }
            root.clearTimeout(acceptedTimer);
            acceptedTimer = root.setTimeout(() => {
                if (current && current.state === 'accepted') { watch = null; clear(); }
            }, ACCEPTED_MAX_MS);
            // No end reported for a while: "noch in Arbeit, Nr. …", not an endless "arbeitet".
            root.clearTimeout(staleTimer);
            staleTimer = root.setTimeout(() => {
                if (current && current.state === 'accepted') {
                    current = { ...current, stale: true };
                    root.dispatchEvent(new root.CustomEvent('vibemind:task-status', { detail: current }));
                    render();
                }
            }, ACCEPTED_STALE_MS);
        }

        function stopAccepted() {
            watch = null;
            root.clearTimeout(acceptedTimer);
            root.clearTimeout(staleTimer);
        }

        /** The result is there: the line says so, the chat ends its "arbeitet". */
        function finishAccepted(title, where = 'card') {
            stopAccepted();
            const result = where === 'bubble' ? 'Einschätzung an der Bubble'
                : title ? `Ergebnis an der Karte „${shorten(title)}“` : 'Ergebnis an der Karte';
            current = { ...current, state: 'done', accepted: false, stale: false, result, error: '' };
            root.dispatchEvent(new root.CustomEvent('vibemind:task-status', { detail: current }));
            root.clearTimeout(keepTimer);
            keepTimer = root.setTimeout(clear, KEEP_MS);
            render();
        }

        root.addEventListener('vibemind:canvas-loaded', (event) => {
            if (!current || current.state !== 'accepted' || !watch) return;
            const detail = (event && event.detail) || {};
            const nodes = Array.isArray(detail.nodes) ? detail.nodes : [];
            const bubbleId = detail.bubbleId || null;
            // No picture of the cards from the moment of the order, or the cards of another bubble:
            // this load becomes the picture to compare with.
            if (!watch.before || (bubbleId && watch.bubbleId && bubbleId !== watch.bubbleId)) {
                watch = { before: snapshot(nodes), bubbleId };
                return;
            }
            if (!watch.bubbleId) watch.bubbleId = bubbleId;
            const id = resultArrived(watch.before, nodes, current.targets);
            if (!id) return;
            const node = nodes.find((item) => item && String(item.id) === id);
            finishAccepted(node ? String(node.title || '') : '');
        });

        // The row of the open bubble, loaded on open and every 5 s (universe_canvas.js). A new reason
        // there ends an accepted assessment: its result is at the bubble, no card changes.
        root.addEventListener('vibemind:bubble-row', (event) => {
            const row = event && event.detail ? event.detail.row : null;
            if (!row || row.id == null) return;
            lastRow = row;
            if (!current || current.state !== 'accepted' || !watch) return;
            if (watch.bubbleId && String(watch.bubbleId) !== String(row.id)) return;
            const count = reasonCount(row);
            if (count === null) return;
            if (watch.reasons === null || watch.reasons === undefined) { watch.reasons = count; return; }
            if (count > watch.reasons) finishAccepted('', 'bubble');
        });

        function handleStatus(message) {
            if (message && message.state === 'reset') { fresh(); return 'reset'; }
            if (!message || !message.space) return 'ignore';
            if (message.plan_id) lastPlanId = message.plan_id;
            // The status of the main process does not know the order numbers; the answer to the sentence did.
            if ((message.state === 'accepted' || message.accepted) && !Array.isArray(message.orders)
                && current && Array.isArray(current.orders) && current.orders.length) {
                message = { ...message, orders: current.orders };
            }
            if (message.state === 'done' && answer) message = { ...message, result: answer };
            if (message.state === 'failed' && refusal) message = { ...message, error: refusal };
            current = message;
            if (message.state === 'accepted' || message.accepted) startAccepted();
            else stopAccepted();
            root.dispatchEvent(new root.CustomEvent('vibemind:task-status', { detail: message }));
            root.clearTimeout(keepTimer);
            if (message.state === 'done' || message.state === 'failed') keepTimer = root.setTimeout(clear, KEEP_MS);
            // A finished plan waits a little for the answer to the sentence; then it shows "fertig" without it.
            if (message.state === 'done' && awaiting && !answer) {
                root.clearTimeout(answerTimer);
                answerTimer = root.setTimeout(() => { awaiting = false; render(); }, ANSWER_WAIT_MS);
            }
            // A finished task of an external space may name a path of its page ("/seite/7"): the page goes there.
            const app = root.multiverseApp;
            const external = app && app.spaces && app.spaces[message.space] && app.spaces[message.space].external;
            if (message.state === 'done' && external && typeof message.result_ref === 'string' && message.result_ref.startsWith('/')
                && root.vibemind && root.vibemind.externalSpacePath) {
                root.vibemind.externalSpacePath(message.space, message.result_ref);
            }
            render();
            return message.state;
        }

        function handleNavigate(message) {
            const app = root.multiverseApp;
            if (!app || !message) return 'ignore';
            const action = decide({
                space: message.space,
                currentSpace: app.currentSpace,
                knownSpaces: Object.keys(app.spaces || {}),
                lastInputAt,
                now: Date.now(),
                insideBubble: Boolean(app.isInsideBubble),
            });
            // 'note' and 'stay' need nothing here: the status that follows says where the task runs.
            if (action === 'navigate') {
                followed = message.space;
                jump(message.space);
            }
            return action;
        }

        root.addEventListener('vibemind:space-arrived', (event) => {
            const space = event && event.detail ? event.detail.space : '';
            // A task in the Desktop space is watched on its screen view, not in front of the sun.
            if (space === 'desktop' && followed === 'desktop') {
                const app = root.multiverseApp;
                if (app && app.enterDesktopDashboard) app.enterDesktopDashboard();
            }
            if (space === followed) followed = '';
            // A finished task the user has seen in its space goes when they move on.
            if (finished(current) && current.seen && space !== current.space) { clear(); return; }
            render(); // the arrow at the end of the line depends on the space on screen
        });

        return function handle(message) {
            if (message && message.type === 'task_status') return handleStatus(message);
            return handleNavigate(message);
        };
    }

    const api = { decide, describe, labelFor, shows, shorten, isRaw, snapshot, resultArrived, orderNumber, reasonCount, NO_JUMP, BUSY_MS, KEEP_MS, WAITING_TEXT, ACCEPTED_TEXT, ACCEPTED_MAX_MS, ACCEPTED_STALE_MS, ANSWER_GRACE_MS, ANSWER_WAIT_MS };
    if (typeof module !== 'undefined' && module.exports) {
        module.exports = api;
    } else {
        root.VibeTaskNav = { ...api, handle: install() };
    }
})(typeof window !== 'undefined' ? window : globalThis);
