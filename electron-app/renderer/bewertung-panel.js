/**
 * The evaluation panel of a bubble: one source, the last run of the Brain.
 *
 * It reads only ideas.metadata.bewertung_lauf (written by the fixed tool bubble_bewertung):
 *   { version, zeit, score, sichten: { coding|swe_design|research|rowboat|ideas: { punkte, urteil } },
 *     todos: [{ nr, sicht, titel, fehlt, karten[], punkte, art, erledigt, erledigt_zeit, erledigt_durch }],
 *     kartenstand, gekuerzt }
 * plus metadata.handwert (a score given by hand, shown apart) and metadata.eval_history (the course).
 *
 * The total is the sum of the five bars. Promoting is decided by the Brain alone (score against the
 * threshold VIBEMIND_BEFOERDERN_SCHWELLE, default 95, an up-to-date run and its sense check); there is
 * no way to read the threshold, so the panel names the default. "Up to date" in the Brain is a hash
 * over the content of cards and edges (kartenstand); the panel only sees change times, so a card
 * changed after the run is a hint to evaluate again, not a verdict. All text goes in with
 * textContent, never as HTML.
 */
(function (root, factory) {
    const api = factory();
    if (typeof module === 'object' && module.exports) module.exports = api;
    else root.VibeBewertung = api;
}(typeof self !== 'undefined' ? self : this, function () {
    'use strict';

    // The key rowboat stays (the Brain writes it); what it judges is the state of knowledge.
    const SICHTEN = Object.freeze([
        ['coding', 'Coding'],
        ['swe_design', 'SWE Design'],
        ['research', 'Research'],
        ['rowboat', 'Wissenslage'],
        ['ideas', 'Ideen'],
    ]);
    const MAX_SICHT = 25;
    const DEFAULT_SCHWELLE = 95;
    const LAUF_SATZ = 'Bewerte diese Bubble';
    const ARTEN = Object.freeze({
        karte_ergaenzen: 'Karte ergänzen',
        karte_fuellen: 'Karte füllen',
        verbindung: 'Verbindung',
        white_paper: 'White Paper',
        entscheidung: 'Entscheidung',
    });
    const ZUSTAENDE = Object.freeze({
        befoerderbar: 'Schwelle erreicht',
        unter_schwelle: 'Noch nicht beförderbar',
        veraltet: 'Karten geändert – neu bewerten',
    });
    // the Brain does these by hand, not by the model: no "Agent soll das erledigen"
    const VON_HAND = Object.freeze({
        white_paper: 'Von Hand: „Erstelle ein White Paper aus dieser Bubble“',
        entscheidung: 'Von Hand: diese Entscheidung selbst treffen',
    });
    const MAX_TODO_NR = 25;   // the Brain numbers the to-dos 1 to 25

    function objectOf(value) {
        if (value && typeof value === 'object' && !Array.isArray(value)) return value;
        if (typeof value === 'string') {
            try { return objectOf(JSON.parse(value)); } catch (_) { return {}; }
        }
        return {};
    }

    function number(value) {
        const n = Number(value);
        return Number.isFinite(n) ? n : null;
    }

    function timeOf(value) {
        const t = typeof value === 'string' || typeof value === 'number' ? Date.parse(value) : NaN;
        return Number.isFinite(t) ? t : null;
    }

    /** The sentence of a to-do button: the agent does it, or the person marks it done; '' for a bad number. */
    function todoSatz(nr, wie) {
        const n = Number(nr);
        if (!Number.isInteger(n) || n < 1 || n > MAX_TODO_NR) return '';
        if (wie === 'agent') return `Erledige To-do ${n}`;
        if (wie === 'hand') return `To-do ${n} erledigt`;
        return '';
    }

    function schwelleOf(value) {
        const n = number(value);
        return n !== null && n > 0 && n <= 100 ? n : null;
    }

    /**
     * What the panel shows for one bubble.
     * row: the ideas row ({ id, title, metadata }); cards: its cards ({ id, title, updated_at });
     * schwelle: the threshold the backend names (absent: the default 95).
     */
    function standOf({ row, cards, schwelle } = {}) {
        const meta = objectOf(row && row.metadata);
        const list = Array.isArray(cards) ? cards.filter((c) => c && c.id !== undefined && c.id !== null) : [];
        const byId = new Map(list.map((c) => [String(c.id), c]));
        const hand = objectOf(meta.handwert);
        const handwert = number(hand.score) === null ? null : { score: number(hand.score), zeit: hand.zeit || null };
        const verlauf = (Array.isArray(meta.eval_history) ? meta.eval_history : [])
            .filter((h) => h && typeof h === 'object' && number(h.score) !== null)
            .slice(-10)
            .map((h) => ({ zeit: h.zeit || null, score: number(h.score), art: h.art === 'hand' ? 'hand' : 'lauf' }));
        const given = schwelleOf(schwelle);
        const base = { titel: (row && row.title) || 'Bubble', handwert, verlauf,
            schwelle: given === null ? DEFAULT_SCHWELLE : given, schwelleVorgabe: given === null };

        const lauf = objectOf(meta.bewertung_lauf);
        if (!Object.keys(lauf).length) return { ...base, leer: true };

        const sichten = objectOf(lauf.sichten);
        const bars = SICHTEN.map(([key, label]) => {
            const s = objectOf(sichten[key]);
            const punkte = Math.min(MAX_SICHT, Math.max(0, Math.round(number(s.punkte) || 0)));
            return { key, label, punkte, urteil: typeof s.urteil === 'string' ? s.urteil : '' };
        });
        const score = bars.reduce((sum, b) => sum + b.punkte, 0);

        const zeit = timeOf(lauf.zeit);
        const geaendert = zeit === null ? [] : list.filter((c) => {
            const t = timeOf(c.updated_at);
            return t !== null && t > zeit;
        });
        const veraltet = geaendert.length > 0;

        const todos = (Array.isArray(lauf.todos) ? lauf.todos : [])
            .filter((t) => t && typeof t === 'object' && Number.isInteger(Number(t.nr)))
            .map((t) => ({
                nr: Number(t.nr),
                sicht: (SICHTEN.find(([k]) => k === t.sicht) || [null, ''])[1],
                titel: String(t.titel || ''),
                fehlt: String(t.fehlt || ''),
                art: ARTEN[t.art] ? t.art : '',
                artLabel: ARTEN[t.art] || '',
                punkte: Math.max(0, Math.round(number(t.punkte) || 0)),
                erledigt: t.erledigt === true,
                durch: t.erledigt_durch === 'agent' ? 'agent' : (t.erledigt === true ? 'hand' : null),
                karten: (Array.isArray(t.karten) ? t.karten : []).map((id) => {
                    const card = byId.get(String(id));
                    return card ? { id: String(card.id), title: card.title || String(card.id), gone: false }
                        : { id: String(id), title: '', gone: true };
                }),
            }))
            .sort((a, b) => (a.erledigt - b.erledigt) || (b.punkte - a.punkte) || (a.nr - b.nr));

        const zustand = veraltet ? 'veraltet' : (score >= base.schwelle ? 'befoerderbar' : 'unter_schwelle');
        return {
            ...base,
            leer: false,
            zeit: lauf.zeit || null,
            score,
            sichten: bars,
            todos,
            offen: todos.filter((t) => !t.erledigt).length,
            veraltet,
            geaendert: geaendert.length,
            gekuerzt: lauf.gekuerzt === true,
            zustand,
            zustandLabel: ZUSTAENDE[zustand],
        };
    }

    /** Green only when promotable; yellow when out of date or at least half way; red below. */
    function farbe(stand) {
        if (!stand || stand.leer) return '';
        if (stand.zustand === 'befoerderbar') return 'green';
        if (stand.zustand === 'veraltet' || stand.score >= stand.schwelle / 2) return 'yellow';
        return 'red';
    }

    function el(doc, tag, cls, text) {
        const node = doc.createElement(tag);
        if (cls) node.className = cls;
        if (text !== undefined && text !== null) node.textContent = String(text);
        return node;
    }

    function zeitText(value) {
        const t = timeOf(value);
        return t === null ? '' : new Date(t).toLocaleString('de-DE', { dateStyle: 'short', timeStyle: 'short' });
    }

    /**
     * Fills `box` with the panel. actions: { laeuft, onRun(button), onTodo(nr, wie, button), onCard(id) }.
     * The buttons that send a sentence carry it in data-satz; the preload knows the same sentences.
     */
    function render(doc, box, stand, actions = {}) {
        const parts = [];
        parts.push(el(doc, 'div', 'eval-title', stand.titel));

        const run = el(doc, 'button', 'bewertung-run', stand.leer ? 'Jetzt bewerten' : 'Neu bewerten');
        run.type = 'button';
        run.id = 'eval-rerun-btn';
        run.dataset.satz = LAUF_SATZ;
        run.disabled = !!actions.laeuft;
        run.addEventListener('click', (e) => { if (actions.onRun) actions.onRun(e); });
        if (actions.laeuft) parts.push(el(doc, 'div', 'bewertung-laeuft', 'Bewertung läuft … (die Antwort steht im Chat)'));

        if (stand.leer) {
            parts.push(el(doc, 'div', 'eval-empty', 'Noch keine Bewertung für diese Bubble.'));
            parts.push(run);
        } else {
            parts.push(el(doc, 'div', 'eval-subtitle', `Bewertet ${zeitText(stand.zeit)}${stand.gekuerzt ? ' · Karten gekürzt gelesen' : ''}`));
            const head = el(doc, 'div', 'score-display');
            head.append(el(doc, 'span', 'score-number', stand.score), el(doc, 'span', 'score-max', '/100'));
            parts.push(head);
            const bar = el(doc, 'div', 'score-bar');
            const fill = el(doc, 'div', 'score-bar-fill');
            fill.style.width = `${Math.min(100, stand.score)}%`;
            const mark = el(doc, 'div', 'score-bar-schwelle');
            mark.style.left = `${Math.min(100, stand.schwelle)}%`;
            bar.append(fill, mark);
            parts.push(bar);
            const zustand = el(doc, 'span', `score-prediction zustand-${stand.zustand}`, stand.zustandLabel);
            parts.push(zustand);
            parts.push(el(doc, 'div', 'bewertung-schwelle',
                `Schwelle zum Befördern: ${stand.schwelle}${stand.schwelleVorgabe ? ' (Vorgabe)' : ''}`));
            if (stand.veraltet) {
                parts.push(el(doc, 'div', 'bewertung-veraltet',
                    `Wohl veraltet: ${stand.geaendert === 1 ? 'eine Karte wurde' : `${stand.geaendert} Karten wurden`} nach der Bewertung geändert. Neu bewerten, bevor du beförderst.`));
            } else if (stand.zustand === 'befoerderbar') {
                parts.push(el(doc, 'div', 'bewertung-hinweis',
                    'Beförderbar, wenn seit der Bewertung keine Karte geändert wurde; beim Befördern prüft das Gehirn auch den Sinn.'));
            }
            parts.push(run);

            parts.push(el(doc, 'div', 'section-title', 'Sichten'));
            for (const s of stand.sichten) {
                const row = el(doc, 'div', 'agent-row');
                if (s.urteil) row.title = s.urteil.slice(0, 400);
                const track = el(doc, 'span', 'agent-bar');
                const f = el(doc, 'span', 'agent-bar-fill');
                f.style.width = `${(s.punkte / MAX_SICHT) * 100}%`;
                track.append(f);
                row.append(el(doc, 'span', 'agent-name', s.label), track, el(doc, 'span', 'agent-score', `${s.punkte}/${MAX_SICHT}`));
                parts.push(row);
            }

            const title = el(doc, 'div', 'section-title', 'To-dos');
            title.append(el(doc, 'span', 'todo-count', ` (${stand.offen} offen von ${stand.todos.length})`));
            parts.push(title);
            const list = el(doc, 'div', 'todo-list');
            for (const t of stand.todos) {
                const item = el(doc, 'div', `bewertung-todo${t.erledigt ? ' erledigt' : ''}`);
                item.dataset.nr = String(t.nr);
                const top = el(doc, 'div', 'bewertung-todo-kopf');
                top.append(el(doc, 'span', 'bewertung-todo-nr', `${t.nr}.`), el(doc, 'span', 'bewertung-todo-titel', t.titel),
                    el(doc, 'span', 'bewertung-todo-punkte', `+${t.punkte}`));
                item.append(top);
                if (t.fehlt) item.append(el(doc, 'div', 'bewertung-todo-fehlt', t.fehlt));
                const info = [t.sicht, t.artLabel].filter(Boolean).join(' · ');
                if (info) item.append(el(doc, 'div', 'bewertung-todo-art', info));
                if (t.karten.length) {
                    const links = el(doc, 'div', 'bewertung-todo-karten');
                    for (const card of t.karten) {
                        if (card.gone) { links.append(el(doc, 'span', 'bewertung-karte-weg', 'Karte gelöscht')); continue; }
                        const link = el(doc, 'button', 'bewertung-karte', card.title);
                        link.type = 'button';
                        link.dataset.cardId = card.id;
                        link.addEventListener('click', () => { if (actions.onCard) actions.onCard(card.id); });
                        links.append(link);
                    }
                    item.append(links);
                }
                if (t.erledigt) {
                    item.append(el(doc, 'div', 'bewertung-todo-erledigt', t.durch === 'agent' ? 'erledigt vom Agenten' : 'erledigt'));
                } else {
                    const row = el(doc, 'div', 'bewertung-todo-knoepfe');
                    const vonHand = VON_HAND[t.art];
                    if (vonHand) item.append(el(doc, 'div', 'bewertung-todo-art', vonHand));
                    const knoepfe = vonHand ? [['hand', 'erledigt']] : [['agent', 'Agent soll das erledigen'], ['hand', 'erledigt']];
                    for (const [wie, label] of knoepfe) {
                        const b = el(doc, 'button', 'bewertung-todo-btn', label);
                        b.type = 'button';
                        b.dataset.todoNr = String(t.nr);
                        b.dataset.todoWie = wie;
                        b.dataset.satz = todoSatz(t.nr, wie);
                        b.title = wie === 'agent'
                            ? 'Der Agent fragt im Chat nach; erst „Ja, erledigen“ startet den Auftrag'
                            : 'Markiert dieses To-do als erledigt, ohne Modell';
                        if (!b.dataset.satz) b.disabled = true;
                        b.addEventListener('click', (e) => { if (actions.onTodo) actions.onTodo(t.nr, wie, e); });
                        row.append(b);
                    }
                    item.append(row);
                }
                list.append(item);
            }
            if (!stand.todos.length) list.append(el(doc, 'div', 'eval-empty-hint', 'Keine To-dos.'));
            parts.push(list);
        }

        if (stand.handwert) {
            parts.push(el(doc, 'div', 'section-title', 'Handwert'));
            parts.push(el(doc, 'div', 'bewertung-handwert',
                `${Math.round(stand.handwert.score)} von Hand${stand.handwert.zeit ? ` · ${zeitText(stand.handwert.zeit)}` : ''} (zählt nicht fürs Befördern)`));
        }

        if (stand.verlauf.length) {
            parts.push(el(doc, 'div', 'section-title', 'Verlauf'));
            for (const h of stand.verlauf.slice().reverse()) {
                const row = el(doc, 'div', 'history-row');
                const track = el(doc, 'span', 'history-bar');
                const f = el(doc, 'span', 'history-bar-fill');
                f.style.width = `${Math.min(100, Math.max(0, h.score))}%`;
                track.append(f);
                row.append(el(doc, 'span', '', zeitText(h.zeit) || '?'), track,
                    el(doc, 'span', 'agent-score', `${Math.round(h.score)}${h.art === 'hand' ? ' Hand' : ''}`));
                parts.push(row);
            }
        }
        box.replaceChildren(...parts);
        return box;
    }

    return { SICHTEN, DEFAULT_SCHWELLE, LAUF_SATZ, ARTEN, ZUSTAENDE, MAX_TODO_NR, todoSatz, standOf, farbe, render };
}));
