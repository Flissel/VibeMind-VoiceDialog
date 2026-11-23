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
    const KEEP_MS = 90000;      // a finished task stays visible this long

    /** What to do with a task that belongs to `space`. */
    function decide({ space, currentSpace, knownSpaces, lastInputAt, now, insideBubble }) {
        if (!space || !knownSpaces.includes(space)) return 'ignore';
        if (space === currentSpace) return 'ignore';
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
        const state = message.state === 'done' || message.state === 'failed' ? message.state : 'running';
        const count = message.total > 1 ? ` (${Math.min(message.done + (state === 'running' ? 1 : 0), message.total)}/${message.total})` : '';
        const arrow = away ? ' →' : '';
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
        const result = message.result ? ` — ${message.result}` : '';
        return {
            state,
            text: `✓ ${label}: fertig${took ? ' in ' + took : ''}${result}${arrow}`,
            title: [message.result, message.result_ref].filter(Boolean).join('\n'),
        };
    }

    function install() {
        const doc = root.document;
        let lastInputAt = 0;
        let current = null;      // last task_status message
        let keepTimer = null;
        let pending = null;      // { space, tries } a jump waiting for a camera move to end
        let followed = '';       // the space the app is jumping to because of a task
        for (const type of ['pointerdown', 'keydown', 'wheel']) {
            root.addEventListener(type, () => { lastInputAt = Date.now(); }, { capture: true, passive: true });
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
            if (!current || !current.space) {
                el.hidden = true;
                markTab('', '');
                return;
            }
            const app = root.multiverseApp;
            const away = Boolean(app && app.currentSpace !== current.space);
            const line = describe(current, labelFor(current.space, app && app.spaces), away);
            el.textContent = line.text;
            el.title = line.title;
            el.dataset.state = line.state;
            el.dataset.space = current.space;
            el.hidden = false;
            markTab(current.space, line.state);
        }

        function clear() {
            current = null;
            render();
        }

        function handleStatus(message) {
            if (!message || !message.space) return 'ignore';
            current = message;
            root.dispatchEvent(new root.CustomEvent('vibemind:task-status', { detail: message }));
            root.clearTimeout(keepTimer);
            if (message.state === 'done' || message.state === 'failed') keepTimer = root.setTimeout(clear, KEEP_MS);
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
            // 'note' needs nothing here: the status that follows says where the task runs.
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
            render(); // the arrow at the end of the line depends on the space on screen
        });

        return function handle(message) {
            if (message && message.type === 'task_status') return handleStatus(message);
            return handleNavigate(message);
        };
    }

    const api = { decide, describe, labelFor, BUSY_MS };
    if (typeof module !== 'undefined' && module.exports) {
        module.exports = api;
    } else {
        root.VibeTaskNav = { ...api, handle: install() };
    }
})(typeof window !== 'undefined' ? window : globalThis);
