/**
 * Renderer side of task navigation: follow a task into its space, unless the user is
 * in the middle of something. Then only a small note appears, which can be clicked.
 *
 * Message from the main process (task-navigation.js):
 *   { type: 'task_navigate', space, registry_space, capability, description }
 */
(function (root) {
    'use strict';

    const BUSY_MS = 4000;      // an input this recent means: the user is working here
    const NOTE_MS = 12000;

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

    function install() {
        let lastInputAt = 0;
        let note = null;
        let noteTimer = null;
        for (const type of ['pointerdown', 'keydown', 'wheel']) {
            root.addEventListener(type, () => { lastInputAt = Date.now(); }, { capture: true, passive: true });
        }

        function showNote(space, text) {
            if (!note) {
                note = root.document.createElement('button');
                note.id = 'task-nav-note';
                note.style.cssText = 'position:fixed;top:84px;right:18px;z-index:40;padding:8px 14px;border-radius:12px;'
                    + 'border:1px solid rgba(120,180,255,.6);background:rgba(16,22,44,.92);color:#e6eeff;cursor:pointer;'
                    + 'font:500 13px system-ui,sans-serif;box-shadow:0 0 16px rgba(86,156,255,.35);';
                root.document.body.appendChild(note);
            }
            note.textContent = text;
            note.onclick = () => {
                note.style.display = 'none';
                if (root.multiverseApp) root.multiverseApp.navigateToSpace(space);
            };
            note.style.display = '';
            clearTimeout(noteTimer);
            noteTimer = setTimeout(() => { note.style.display = 'none'; }, NOTE_MS);
        }

        return function handle(message) {
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
            if (action === 'navigate') app.navigateToSpace(message.space);
            else if (action === 'note') showNote(message.space, `Aufgabe läuft in ${LABELS[message.space] || message.space} →`);
            return action;
        };
    }

    const api = { decide, BUSY_MS };
    if (typeof module !== 'undefined' && module.exports) {
        module.exports = api;
    } else {
        root.VibeTaskNav = { ...api, handle: install() };
    }
})(typeof window !== 'undefined' ? window : globalThis);
