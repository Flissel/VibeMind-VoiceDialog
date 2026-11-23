/**
 * Karten im Ideas-Canvas: lesbar zugeklappt, gross aufgeklappt.
 *
 * Die Regeln, was eine Karte zeigt, sind die der Kartenansicht im Ideas-Space
 * (spaces/ideas/KARTEN.md, Funktionen _card_short/_card_read). Die Huelle liest
 * canvas_nodes direkt, darum stehen sie hier noch einmal; card-view.test.js
 * prueft sie gegen dieselben Beispiele wie test_kartenansicht.py.
 *
 * Regel: nichts Technisches in dem, was ein Mensch liest (keine Feldnamen,
 * kein rohes Markdown oder JSON, keine Kennungen).
 */
(function (root, factory) {
    const api = factory();
    if (typeof module === 'object' && module.exports) module.exports = api;
    if (root) root.CardView = api;
})(typeof window !== 'undefined' ? window : null, function () {
    'use strict';

    const FORMAT_NAMES = {
        note: 'Notiz', table: 'Tabelle', action_list: 'Aufgabenliste', pros_cons: 'Pro und Contra',
        hierarchy: 'Gliederung', technical_specs: 'Anforderungen', kanban: 'Kanban', mindmap: 'Mindmap',
        swot: 'SWOT-Analyse', user_story: 'Nutzergeschichten', flowchart: 'Ablauf',
        comparison_table: 'Vergleich', research: 'Recherche',
        zusammenfassung: 'Zusammenfassung', white_paper: 'White Paper',
    };
    // Dokument-Karten (idea_document): node_type "dokument", die Art steht in metadata.art.
    const DOCUMENT_KINDS = new Set(['zusammenfassung', 'white_paper']);
    const FORMAT_ALIASES = { pros_cons_table: 'pros_cons' };
    // Vorlagentext der alten Formatier-Agenten: sieht aus wie Inhalt, sagt aber nichts.
    const TEMPLATE_TEXTS = new Set([
        'Konkrete Anforderung', 'Betroffene Komponente', 'Was analysiert wird', 'Technische Spezifikation',
        'Gesamtbewertung der aktuellen Situation', 'SWOT Analyse', 'Mind Map', 'User Stories', 'Gliederung',
    ]);
    const CARD_LINES = 3;          // so viele Zeilen zeigt die Karte zugeklappt
    const CARD_LINE_CHARS = 120;   // so lang darf eine Zeile auf der Karte sein
    // (Art der Kante, liegt die gelesene Karte am Anfang?) -> was die andere Karte fuer sie ist.
    const EDGE_NAMES = {
        'parent_child|true': 'Unterpunkt', 'parent_child|false': 'Oberpunkt',
        'expanded_from|true': 'Weiterentwicklung', 'expanded_from|false': 'Ausgangspunkt',
    };
    const MD_PREFIX = /^\s*(?:#{1,6}\s+|>\s*|[-*+]\s+)/;  // Nummern bleiben: sie tragen die Reihenfolge
    const MD_MARKS = /(\*\*|__|`|~~)/g;
    const MD_HEADING = /^(#{1,6})\s+(.*)$/;
    // Wiki form, as it stands in the data: "== Titel ==" (== is the first level below the title)
    const WIKI_HEADING = /^(={1,7})\s*([^=].*?)\s*\1$/;

    /** A heading in Markdown or wiki form: its level (1 = top) and text, or null. */
    function headingOf(line) {
        const md = MD_HEADING.exec(line);
        if (md) return { level: md[1].length, text: md[2] };
        const wiki = WIKI_HEADING.exec(line);
        if (wiki) return { level: Math.min(Math.max(wiki[1].length - 1, 1), 6), text: wiki[2] };
        return null;
    }
    const RESEARCH_TITLE = /^Research:\s*(.*?)\s*(\d{4})-(\d{2})-(\d{2})(?:\s+[\d:]+)?\s*$/;
    const SUMMARY_HEAD = /summary|zusammenfassung|kurzfassung|fazit/i;
    const RULE_CHARS = new Set('-|: =*_');

    const isMap = (value) => value !== null && typeof value === 'object' && !Array.isArray(value);
    const isText = (value) => typeof value === 'string';
    const chars = (text) => Array.from(text);
    const words = (text) => text.split(/\s+/).filter(Boolean).join(' ');
    const items = (value) => (Array.isArray(value) ? value : []);

    /** Eine Zeile aus der Datenbank, wie immer sie ankam (Eintritt, Abfrage, Echtzeit). */
    function rowOf(node) {
        if (!isMap(node)) return {};
        const content = node.content;
        const parsed = (value) => {
            if (!isText(value)) return value;
            try { return JSON.parse(value); } catch (_) { return null; }
        };
        const structured = parsed(node.content_json);
        const previous = parsed(node.previous_content_json);
        return {
            id: node.id != null ? String(node.id) : (node.db_id != null ? String(node.db_id) : null),
            title: isText(node.title) ? node.title : (isMap(content) && isText(content.title) ? content.title : null),
            content: isText(content) ? content : (isMap(content) && isText(content.text) ? content.text : null),
            node_type: node.node_type || node.type || null,
            content_json: structured === undefined ? null : structured,
            // what the card held before it was formatted: the Brain's format writes only text (often just the title)
            previous_content_json: isMap(previous) ? previous : null,
            format_schema: node.format_schema || null,
            metadata: isMap(node.metadata) ? node.metadata : {},
            // where the card lies on the canvas: grouping puts a group under its heading card (same x)
            x: Number.isFinite(Number(node.x ?? (isMap(node.position) ? node.position.x : NaN))) ? Number(node.x ?? node.position.x) : null,
            y: Number.isFinite(Number(node.y ?? (isMap(node.position) ? node.position.y : NaN))) ? Number(node.y ?? node.position.y) : null,
        };
    }

    /** A heading card that grouping by theme laid above a column (metadata.gruppen_kopf). */
    function isGroupHead(row) {
        return isMap(row) && isMap(row.metadata) && row.metadata.gruppen_kopf === true;
    }

    /**
     * The cards in the order of their groups: each heading, then the cards of its column (same x,
     * top to bottom), then the cards in no group. Without headings the order stays as it is.
     * Returns [{ head, cards }]; head is null for the cards in no group.
     */
    function grouped(rows) {
        const heads = rows.filter(isGroupHead).filter((h) => h.x !== null)
            .sort((a, b) => a.x - b.x);
        if (!heads.length) return [{ head: null, cards: rows.filter((r) => !isGroupHead(r)) }];
        const taken = new Set();
        const groups = heads.map((head) => {
            const cards = rows.filter((r) => !isGroupHead(r) && r.x === head.x && (r.y === null || head.y === null || r.y > head.y))
                .sort((a, b) => (a.y ?? 0) - (b.y ?? 0));
            cards.forEach((c) => taken.add(c.id));
            return { head, cards };
        });
        const rest = rows.filter((r) => !isGroupHead(r) && !taken.has(r.id));
        if (rest.length) groups.push({ head: null, cards: rest });
        return groups;
    }

    /** Das Format der Karte, wie gespeichert: content_json.type, sonst die Konstante des Schemas. */
    function cardFormat(row) {
        const structured = row.content_json;
        let fmt = isMap(structured) ? structured.type : null;
        if (!isText(fmt) || !fmt) {
            const schema = row.format_schema;
            if (isMap(schema)) {
                const properties = schema.properties;
                const kind = isMap(properties) ? properties.type : null;
                fmt = isMap(kind) ? kind.const : null;
                if (!isText(fmt) || !fmt) fmt = schema.type !== 'object' ? schema.type : null;
            }
        }
        if ((!isText(fmt) || !fmt) && row.node_type === 'research') fmt = 'research';
        const art = isMap(row.metadata) ? row.metadata.art : null;
        if ((!isText(fmt) || !fmt) && row.node_type === 'dokument' && DOCUMENT_KINDS.has(art)) fmt = art;
        fmt = isText(fmt) ? (FORMAT_ALIASES[fmt] || fmt) : null;
        return fmt || 'note';
    }

    /** Eine Zeile fuer Menschen: ohne Markdown-Zeichen, ohne Vorlagentext, mit Auslassung gekuerzt. */
    function plain(value, limit = CARD_LINE_CHARS) {
        if (!isText(value)) return '';
        const wiki = WIKI_HEADING.exec(value.trim());
        let text = words((wiki ? wiki[2] : value).replace(MD_PREFIX, '').replace(MD_MARKS, '').trim());
        if (!text || TEMPLATE_TEXTS.has(text)) return '';
        if (limit != null && chars(text).length > limit) text = chars(text).slice(0, limit - 1).join('').trimEnd() + '…';
        return text;
    }

    const count = (number, one, many) => `${number} ${number === 1 ? one : many}`;

    function cardTitle(row) {
        let title = isText(row.title) ? row.title : '';
        const research = RESEARCH_TITLE.exec(title);
        if (research) title = `Recherche: ${research[1]}`;
        title = words(title.replace(/_/g, ' '));
        return title || 'Ohne Titel';
    }

    /** Woher die Karte kommt, in einem kurzen Satz; null fuer eine von Hand notierte Karte. */
    function cardSource(row) {
        const metadata = isMap(row.metadata) ? row.metadata : {};
        const title = isText(row.title) ? row.title : '';
        const research = RESEARCH_TITLE.exec(title);
        if (research || row.node_type === 'research') {
            const parts = ['Recherche'];
            if (research) parts[0] += ` vom ${research[4]}.${research[3]}.${research[2]}`;
            const n = metadata.citation_count;
            if (Number.isInteger(n) && n > 0) parts.push(count(n, 'Quelle', 'Quellen'));
            return parts.join(' · ');
        }
        if (row.node_type === 'dokument') {
            const n = Array.isArray(metadata.quellen) ? metadata.quellen.length : 0;
            return n ? `aus ${count(n, 'Karte', 'Karten')}` : null;
        }
        if (metadata.ai_generated) {
            const origin = plain(metadata.source_title);
            return origin ? `Vorschlag aus „${origin.replace(/_/g, ' ')}“` : 'Vorschlag';
        }
        return null;
    }

    function field(item, ...names) {
        if (isText(item)) return item;
        if (isMap(item)) for (const name of names) if (item[name]) return item[name];
        return null;
    }

    /** Markdown oder Text nach Ueberschriften geteilt; ein Text, der nur den Titel wiederholt, sagt nichts. */
    function textSections(text, title, limit) {
        if (!text.trim() || text.trim() === title.trim()) return [];
        const sections = [[null, []]];
        for (const raw of text.split(/\r\n|\r|\n/)) {
            const heading = headingOf(raw.trim());
            if (heading) { sections.push([plain(heading.text, limit) || null, []]); continue; }
            let stripped = raw.trim();
            if (!stripped || chars(stripped).every((c) => RULE_CHARS.has(c))) continue;
            if (stripped.startsWith('|')) {
                stripped = stripped.replace(/^\|+|\|+$/g, '').split('|').map((c) => c.trim()).filter(Boolean).join(' · ');
            }
            const line = plain(stripped, limit);
            if (line) sections[sections.length - 1][1].push(line);
        }
        return sections.filter(([head, lines]) => lines.length || head);
    }

    /** Abschnitte und eine kurze Zahl je bekanntem Format; unbekannte Formen ergeben nichts. */
    function structuredSections(fmt, data, limit) {
        const lines = (list, ...names) => items(list).map((item) => plain(field(item, ...names), limit)).filter(Boolean);
        const get = (obj, key) => (isMap(obj) ? obj[key] : undefined);
        if (fmt === 'pros_cons') {
            const pros = lines(data.pros, 'point');
            const cons = lines(data.cons, 'point');
            return [[['Pro', pros], ['Contra', cons]], `${pros.length} Pro · ${cons.length} Contra`];
        }
        if (fmt === 'swot') {
            const parts = [['Stärken', 'Stärke', 'strengths'], ['Schwächen', 'Schwäche', 'weaknesses'],
                ['Chancen', 'Chance', 'opportunities'], ['Risiken', 'Risiko', 'threats']];
            const found = parts.map(([name, one, key]) => [name, one, lines(data[key], 'point')]);
            const said = found.filter(([, , list]) => list.length).map(([name, one, list]) => count(list.length, one, name)).join(' · ');
            return [found.map(([name, , list]) => [name, list]), said || null];
        }
        if (fmt === 'technical_specs') {
            const found = lines(data.specifications, 'requirement');
            return [[['Anforderungen', found]], found.length ? count(found.length, 'Anforderung', 'Anforderungen') : null];
        }
        if (fmt === 'user_story') {
            const stories = [];
            for (const story of items(data.stories)) {
                if (!isMap(story)) continue;
                const line = plain([story.role, story.want].filter(isText).join(' '), limit);
                if (line) stories.push(line);
            }
            return [[['Nutzergeschichten', stories]], stories.length ? count(stories.length, 'Geschichte', 'Geschichten') : null];
        }
        if (fmt === 'flowchart') {
            const steps = items(data.nodes)
                .filter((node) => isMap(node) && node.type !== 'start' && node.type !== 'end')
                .map((node) => plain(field(node, 'label'), limit)).filter(Boolean);
            return [[['Schritte', steps]], steps.length ? count(steps.length, 'Schritt', 'Schritte') : null];
        }
        if (fmt === 'mindmap') {
            const sections = [];
            for (const branch of items(data.branches)) {
                const head = plain(field(branch, 'label'), limit);
                if (head) sections.push([head, lines(get(branch, 'children'), 'label')]);
            }
            const middle = plain(field(data.center, 'description', 'label'), limit);
            if (middle) sections.unshift([null, [middle]]);
            const heads = sections.filter(([head]) => head).length;
            return [sections, heads ? count(heads, 'Zweig', 'Zweige') : null];
        }
        if (fmt === 'hierarchy') {
            const sections = [];
            for (const level of items(data.levels)) {
                for (const item of items(get(level, 'items'))) {
                    const head = plain(field(item, 'name'), limit);
                    if (head) sections.push([head, lines(get(item, 'children'), 'name')]);
                }
            }
            return [sections, sections.length ? count(sections.length, 'Punkt', 'Punkte') : null];
        }
        if (fmt === 'table') {
            const headers = items(data.headers).map((cell) => plain(cell, limit));
            const rows = items(data.rows).filter(Array.isArray)
                .map((row) => row.map((cell) => plain(cell, limit)).filter(Boolean).join(' · ')).filter(Boolean);
            const head = headers.filter(Boolean).join(' · ') || null;
            return [[[head, rows]], rows.length ? count(rows.length, 'Zeile', 'Zeilen') : null];
        }
        if (fmt === 'action_list') {
            const states = { completed: ' (erledigt)', in_progress: ' (in Arbeit)', blocked: ' (blockiert)' };
            const tasks = [];
            let done = 0;
            for (const item of items(data.items)) {
                const task = plain(field(item, 'task'), limit);
                if (!task) continue;
                const status = get(item, 'status');
                if (status === 'completed') done += 1;
                tasks.push(task + (states[status] || ''));
            }
            return [[['Aufgaben', tasks]], tasks.length ? `${done} von ${tasks.length} erledigt` : null];
        }
        if (fmt === 'kanban') {
            const sections = [];
            for (const column of items(data.columns)) {
                const head = plain(field(column, 'name', 'title', 'label'), limit);
                const cards = get(column, 'cards') !== undefined ? get(column, 'cards') : get(column, 'items');
                if (head) sections.push([head, lines(cards, 'title', 'text', 'name')]);
            }
            // the other shape of the same format (format-renderer.js): todo / doing / done
            for (const [key, head] of [['todo', 'Offen'], ['doing', 'In Arbeit'], ['done', 'Erledigt']]) {
                if (Array.isArray(data[key])) sections.push([head, lines(data[key], 'title', 'text', 'point')]);
            }
            const cards = sections.reduce((sum, [, list]) => sum + list.length, 0);
            return [sections, sections.length ? `${count(cards, 'Karte', 'Karten')} in ${count(sections.length, 'Spalte', 'Spalten')}` : null];
        }
        if (fmt === 'comparison_table') {
            const options = lines(data.options, 'name');
            return [[['Optionen', options]], options.length ? count(options.length, 'Option', 'Optionen') : null];
        }
        return [[], null];
    }

    /** [Format, Abschnitte, Umfang, ist Text] einer Karte; Abschnitte halten nur lesbare Zeilen. */
    function cardParts(row, limit) {
        const fmt = cardFormat(row);
        const title = isText(row.title) ? row.title : '';
        const structured = isMap(row.content_json) ? row.content_json : {};
        let [sections, said] = structuredSections(fmt, structured, limit);
        sections = sections.filter(([, found]) => found.length);
        if (sections.length) return [fmt, sections, said, false];
        sections = textSections(cardText(row), title, limit);
        if (!sections.some(([, found]) => found.length)) {
            // formatted by the Brain: the new content_json carries only the title, the content stayed in the one before
            const before = row.previous_content_json;
            if (isMap(before)) {
                const beforeFmt = isText(before.type) ? (FORMAT_ALIASES[before.type] || before.type) : 'note';
                let [found, beforeSaid] = structuredSections(beforeFmt, before, limit);
                found = found.filter(([, list]) => list.length);
                if (found.length) return [fmt, found, beforeSaid, false];
            }
        }
        const headings = sections.filter(([head]) => head).length;
        return [fmt, sections, headings > 1 ? `${headings} Abschnitte` : null, true];
    }

    /** The text of a card: the text of its format if it says more than the title, else the stored text. */
    function cardText(row) {
        const structured = isMap(row.content_json) ? row.content_json : {};
        const title = isText(row.title) ? row.title.trim() : '';
        const said = (value) => isText(value) && value.trim() && value.trim() !== title;
        if (said(structured.text)) return structured.text;
        if (said(row.content)) return row.content;
        const before = row.previous_content_json;
        if (isMap(before) && said(before.text)) return before.text;
        return isText(structured.text) ? structured.text : (isText(row.content) ? row.content : '');
    }

    /** Die zugeklappte Karte: Titel, Art, bis zu drei lesbare Zeilen, Umfang, Herkunft. */
    function cardShort(input) {
        const row = rowOf(input);
        const [fmt, sections, said, text] = cardParts(row, CARD_LINE_CHARS);
        const labelled = fmt === 'pros_cons' || fmt === 'swot' || fmt === 'kanban';
        let shown;
        if (text) {
            let summary = sections.find(([head]) => head && SUMMARY_HEAD.test(head));
            if (summary) summary = summary[1];
            else {
                const telling = sections.find(([, found]) => found.length && !found.every((line) => chars(line).slice(0, 40).includes(':')));
                const any = sections.find(([, found]) => found.length);
                summary = telling ? telling[1] : (any ? any[1] : []);
            }
            shown = summary.slice(0, CARD_LINES);
        } else {
            shown = [];
            for (const [head, found] of sections) for (const line of found) shown.push(labelled && head ? `${head}: ${line}` : line);
            shown = shown.slice(0, CARD_LINES);
        }
        // A Kanban shows its columns side by side, each with its first cards (Lauf 8: one list
        // "In Arbeit: …", the columns were not to be seen).
        const spalten = fmt === 'kanban' && !text
            ? sections.map(([head, found]) => ({ name: head, zeilen: found.slice(0, CARD_LINES) })) : null;
        return {
            titel: cardTitle(row),
            art: FORMAT_NAMES[fmt] || 'Notiz',
            zeilen: shown,
            ...(spalten ? { spalten } : {}),
            umfang: said,
            quelle: cardSource(row),
            leer: !shown.length,
        };
    }

    function ratingOf(row) {
        const rating = isMap(row.metadata) ? row.metadata.bewertung : null;
        const value = isMap(rating) ? rating.wert : null;
        return typeof value === 'number' && Number.isFinite(value) ? value : null;
    }

    /** Die Verbindungen einer Karte nach Titel; Kanten zu Karten, die es nicht mehr gibt, zeigen nichts. */
    function cardLinks(id, edges, titles) {
        const links = [];
        for (const edge of items(edges)) {
            if (!isMap(edge)) continue;
            const from = edge.from_node_id != null ? String(edge.from_node_id) : null;
            const to = edge.to_node_id != null ? String(edge.to_node_id) : null;
            if (from !== id && to !== id) continue;
            const startsHere = from === id;
            const other = startsHere ? to : from;
            const known = titles instanceof Map ? titles.get(other) : (titles || {})[other];
            if (other && other !== id && isText(known)) {
                const kind = edge.edge_type || edge.type;
                links.push({ id: other, titel: known, art: EDGE_NAMES[`${kind}|${startsHere}`] || 'verwandt' });
            }
        }
        return links;
    }

    /** The cards a summary or white paper was written from (metadata.quellen), by title; unknown ids show nothing. */
    function cardSources(row, titles) {
        const metadata = isMap(row.metadata) ? row.metadata : {};
        const found = [];
        for (const id of items(metadata.quellen)) {
            const key = id != null ? String(id) : null;
            const known = titles instanceof Map ? titles.get(key) : (titles || {})[key];
            if (key && key !== row.id && isText(known) && !found.some((s) => s.id === key)) found.push({ id: key, titel: known });
        }
        return found;
    }

    /**
     * A card named in the text („Titel“) becomes a jump to that card in the same reader.
     * html is built from escaped text; only whole quoted titles of other cards of this bubble are touched.
     */
    function linkMentions(html, titles, ownId) {
        const known = titles instanceof Map ? [...titles.entries()] : Object.entries(titles || {});
        const byTitle = new Map();
        for (const [id, title] of known) {
            if (id !== ownId && isText(title) && title.trim() && !byTitle.has(title.trim())) byTitle.set(title.trim(), id);
        }
        if (!byTitle.size) return html;
        // typographic quotes only: a plain " is escaped in text and stands only in attributes
        return html.replace(/([„“])([^„“”<>\n]{1,200})([“”])/g, (whole, open, inner, shut) => {
            const id = byTitle.get(unescapeHtml(inner).trim());
            if (!id) return whole;
            return `${open}<span class="kv-jump" role="link" tabindex="0" data-card-id="${escapeHtml(id)}" title="Karte öffnen">${inner}</span>${shut}`;
        });
    }

    /** Die aufgeklappte Karte: alles Lesbare, Abschnitte der Reihe nach, Verbindungen nach Titel. */
    function cardRead(input, edges, titles) {
        const row = rowOf(input);
        const [fmt, sections, said, isTextCard] = cardParts(row, null);
        let text = null;
        if (isTextCard) {
            const raw = cardText(row);
            const title = isText(row.title) ? row.title : '';
            text = isText(raw) && raw.trim() && raw.trim() !== title.trim() ? raw : null;
        }
        return {
            id: row.id,
            titel: cardTitle(row),
            art: FORMAT_NAMES[fmt] || 'Notiz',
            umfang: said,
            quelle: cardSource(row),
            bewertung: ratingOf(row),
            abschnitte: sections.map(([head, found]) => ({ ueberschrift: head, zeilen: found })),
            text,
            verbindungen: cardLinks(row.id, edges, titles),
            quellen: cardSources(row, titles),
            leer: !sections.some(([, found]) => found.length),
        };
    }

    // ------------------------------------------------------------------
    // Markdown zum Lesen: erst alles maskieren, dann wenige sichere Formen.
    // Adressen (nur http/https) werden Links; ein Klick oeffnet sie im Browser
    // des Systems (window.vibemind.openExternal), nie in der App selbst.
    // ------------------------------------------------------------------

    function escapeHtml(text) {
        return String(text).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
    }

    const unescapeHtml = (html) => html.replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"')
        .replace(/&#39;/g, "'").replace(/&amp;/g, '&');

    /** The address as it may be opened: http or https with a host, nothing else. */
    function safeUrl(value) {
        if (!isText(value)) return null;
        const text = value.trim();
        if (!text || text.length > 2048 || /[\s\u0000-\u001f]/.test(text)) return null;
        let url;
        try { url = new URL(text); } catch (_) { return null; }
        if ((url.protocol !== 'http:' && url.protocol !== 'https:') || !url.hostname || url.username || url.password) return null;
        return url.href;
    }

    /** escaped address -> link; label is escaped HTML already */
    function linkHtml(escapedHref, label) {
        const url = safeUrl(unescapeHtml(escapedHref));
        if (!url) return label;
        const attr = escapeHtml(url);
        return `<span class="kv-link" role="link" tabindex="0" data-url="${attr}" title="${attr} (öffnet im Browser)">${label}</span>`;
    }

    function inline(text) {
        let html = escapeHtml(text);
        const codes = [];
        html = html.replace(/`([^`]+)`/g, (_, code) => { codes.push(code); return `\u0000${codes.length - 1}\u0000`; });
        const links = [];
        const keep = (made) => { links.push(made); return `\u0001${links.length - 1}\u0001`; };
        html = html.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, (_, label, href) => keep(linkHtml(href, label)));
        // bare addresses, also in <…> and after "Abgerufen von"; trailing punctuation stays text
        html = html.replace(/(^|[\s(\[:]|&lt;)(https?:\/\/[^\s<>"\u0001]+)/g, (_, lead, found) => {
            let href = found;
            let tail = '';
            for (;;) {
                const end = /(&gt;|&quot;|&#39;|[.,;:!?)\]])$/.exec(href);
                if (!end || (end[1] === ')' && (href.match(/\(/g) || []).length >= (href.match(/\)/g) || []).length)) break;
                tail = end[1] + tail;
                href = href.slice(0, -end[1].length);
            }
            return lead + keep(linkHtml(href, href)) + tail;
        });
        html = html.replace(/\*\*([^*]+)\*\*|__([^_]+)__/g, (_, a, b) => `<strong>${a || b}</strong>`);
        html = html.replace(/(^|[^*])\*([^*\s][^*]*)\*/g, (_, lead, body) => `${lead}<em>${body}</em>`);
        html = html.replace(/~~([^~]+)~~/g, '<del>$1</del>');
        html = html.replace(/\u0000(\d+)\u0000/g, (_, i) => `<code>${codes[Number(i)]}</code>`);
        html = html.replace(/\u0001(\d+)\u0001/g, (_, i) => links[Number(i)]);
        return html;
    }

    const cells = (line) => line.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map((c) => c.trim());
    const isTableRule = (line) => /^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$/.test(line);

    /** Markdown als HTML zum Lesen, dazu die Ueberschriften fuer die Inhaltsuebersicht. */
    function renderMarkdown(text) {
        const lines = isText(text) ? text.split(/\r\n|\r|\n/) : [];
        const out = [];
        const headings = [];
        let list = null;      // 'ul' | 'ol'
        let para = [];
        const flushPara = () => { if (para.length) { out.push(`<p>${para.map(inline).join('<br>')}</p>`); para = []; } };
        const closeList = () => { if (list) { out.push(`</${list}>`); list = null; } };
        for (let i = 0; i < lines.length; i++) {
            const raw = lines[i];
            const line = raw.trim();
            if (!line) { flushPara(); closeList(); continue; }
            const heading = headingOf(line);
            if (heading) {
                flushPara(); closeList();
                const level = Math.min(heading.level + 1, 6);
                const anchor = `kv-h-${headings.length}`;
                headings.push({ level: heading.level, text: plain(heading.text, null), anchor });
                out.push(`<h${level} id="${anchor}">${inline(heading.text)}</h${level}>`);
                continue;
            }
            if (/^(-{3,}|\*{3,}|_{3,})$/.test(line)) { flushPara(); closeList(); out.push('<hr>'); continue; }
            if (line.startsWith('|') && i + 1 < lines.length && isTableRule(lines[i + 1])) {
                flushPara(); closeList();
                const head = cells(line);
                const body = [];
                i += 2;
                while (i < lines.length && lines[i].trim().startsWith('|')) { body.push(cells(lines[i])); i += 1; }
                i -= 1;
                out.push('<div class="kv-table-wrap"><table><thead><tr>' + head.map((c) => `<th>${inline(c)}</th>`).join('')
                    + '</tr></thead><tbody>' + body.map((r) => '<tr>' + r.map((c) => `<td>${inline(c)}</td>`).join('') + '</tr>').join('')
                    + '</tbody></table></div>');
                continue;
            }
            const bullet = /^[-*+]\s+(.*)$/.exec(line);
            const numbered = /^\d+[.)]\s+(.*)$/.exec(line);
            if (bullet || numbered) {
                flushPara();
                const kind = bullet ? 'ul' : 'ol';
                if (list !== kind) { closeList(); out.push(`<${kind}>`); list = kind; }
                out.push(`<li>${inline((bullet || numbered)[1])}</li>`);
                continue;
            }
            if (line.startsWith('>')) { flushPara(); closeList(); out.push(`<blockquote>${inline(line.replace(/^>\s*/, ''))}</blockquote>`); continue; }
            closeList();
            para.push(line);
        }
        flushPara(); closeList();
        return { html: out.join('\n'), headings };
    }

    /** Fuer die Suche: Kleinbuchstaben, Umlaute und Unterstriche gleichgesetzt. */
    function searchKey(text) {
        return String(text || '').toLowerCase().replace(/_/g, ' ')
            .replace(/ä/g, 'ae').replace(/ö/g, 'oe').replace(/ü/g, 'ue').replace(/ß/g, 'ss');
    }

    function matches(title, query) {
        const q = searchKey(query).trim();
        return !q || searchKey(title).includes(q);
    }

    // ------------------------------------------------------------------
    // Ansicht: Raster der Karten mit Suche und Groesse, Leser fuer eine Karte.
    // ------------------------------------------------------------------

    const SIZES = [200, 240, 290, 350, 430];   // Breite einer Karte je Zoomstufe
    const DEFAULT_SIZE = 2;
    const LONG_TEXT = 1500;                    // ab hier bekommt der Leser eine Inhaltsuebersicht

    function remember(doc, key, value) {
        try {
            const store = doc.defaultView && doc.defaultView.localStorage;
            if (!store) return null;
            if (value === undefined) return store.getItem(key);
            store.setItem(key, String(value));
        } catch (_) { /* ohne Speicher geht es auch */ }
        return null;
    }

    /**
     * Ein Raster aller Karten einer Bubble. update() kommt alle paar Sekunden (Abfrage des Canvas);
     * Suche, Groesse, Scrollstand und eine offene Karte bleiben dabei, wie sie sind.
     */
    function board(doc, options = {}) {
        const el = (tag, className, text) => {
            const node = doc.createElement(tag);
            if (className) node.className = className;
            if (text != null) node.textContent = text;
            return node;
        };
        const rootEl = el('div', 'kv-board');
        const bar = el('div', 'kv-bar');
        const search = el('input', 'kv-search');
        search.type = 'search';
        search.placeholder = 'Karte nach Titel suchen …';
        search.setAttribute('aria-label', 'Karte nach Titel suchen');
        const countEl = el('span', 'kv-count');
        const smaller = el('button', 'kv-btn', '−');
        smaller.type = 'button';
        smaller.title = 'Karten kleiner';
        const bigger = el('button', 'kv-btn', '+');
        bigger.type = 'button';
        bigger.title = 'Karten größer';
        const graph = el('button', 'kv-btn kv-wide', 'Verbindungsbild');
        graph.type = 'button';
        graph.title = 'Karten als Verbindungsbild zeigen';
        bar.append(search, countEl, smaller, bigger);
        if (typeof options.onGraph === 'function') bar.append(graph);
        const grid = el('div', 'kv-grid');
        const none = el('div', 'kv-none');
        none.hidden = true;
        const reader = el('div', 'kv-reader');
        reader.hidden = true;
        reader.setAttribute('role', 'dialog');
        reader.setAttribute('aria-modal', 'true');
        // the grid scrolls inside its own box: as a scrolling flex child its rows were squeezed to the minimum
        const scroller = el('div', 'kv-scroll');
        scroller.append(grid, none);
        rootEl.append(bar, scroller, reader);

        let rows = [];
        let edges = [];
        let titles = new Map();
        let signature = '';
        let openId = null;
        let rootId = null;   // the root set for the bubble (ideas.metadata.wurzel), marked on its card
        // nichts gespeichert: die Standardgroesse (Number(null) waere 0, die kleinste Stufe)
        const stored = remember(doc, 'vibemind.karten.groesse');
        let size = stored === null || stored === '' ? NaN : Number(stored);
        if (!Number.isInteger(size) || size < 0 || size >= SIZES.length) size = DEFAULT_SIZE;

        const applySize = () => {
            rootEl.style.setProperty('--kv-w', SIZES[size] + 'px');
            smaller.disabled = size === 0;
            bigger.disabled = size === SIZES.length - 1;
        };
        applySize();

        function linkCount(id) {
            let n = 0;
            for (const edge of edges) {
                const from = String(edge.from_node_id);
                const to = String(edge.to_node_id);
                if ((from === id) !== (to === id) && titles.has(from === id ? to : from)) n += 1;
            }
            return n;
        }

        function rootMark() {
            const mark = el('span', 'kv-wurzel', 'Wurzel');
            mark.title = 'Die Wurzel dieser Bubble';
            return mark;
        }

        function cardEl(row) {
            const short = cardShort(row);
            const card = el('article', 'kv-card' + (short.leer ? ' kv-leer' : ''));
            card.tabIndex = 0;
            card.dataset.cardId = row.id || '';
            const top = el('div', 'kv-top');
            top.append(el('span', 'kv-art', short.art));
            if (rootId && row.id === rootId) top.append(rootMark());
            const rating = ratingOf(row);
            if (rating != null) {
                const chip = el('span', 'kv-wert', String(rating));
                chip.title = 'Bewertung';
                top.append(chip);
            }
            card.append(top, el('h3', 'kv-title', short.titel));
            if (short.leer) card.append(el('p', 'kv-empty', 'Noch ohne Inhalt'));
            else if (short.spalten) {
                const board = el('div', 'kv-spalten');
                for (const column of short.spalten) {
                    const box = el('div', 'kv-spalte');
                    box.append(el('div', 'kv-spalte-kopf', column.name));
                    const ul = el('ul', 'kv-lines');
                    for (const line of column.zeilen) ul.append(el('li', null, line));
                    box.append(ul);
                    board.append(box);
                }
                card.append(board);
            } else {
                const ul = el('ul', 'kv-lines');
                for (const line of short.zeilen) ul.append(el('li', null, line));
                card.append(ul);
            }
            const foot = [];
            if (short.umfang) foot.push(short.umfang);
            const links = linkCount(row.id);
            if (links) foot.push(links === 1 ? '1 Verbindung' : `${links} Verbindungen`);
            if (short.quelle) foot.push(short.quelle);
            if (foot.length) card.append(el('div', 'kv-foot', foot.join(' · ')));
            card.addEventListener('click', () => open(row.id));
            card.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); e.stopPropagation(); open(row.id); }
            });
            return card;
        }

        /** A heading of a group across the whole row of the grid: the column head of grouping by theme. */
        function headEl(head, count) {
            const bar = el('div', 'kv-gruppe');
            bar.dataset.cardId = head.id || '';
            bar.append(el('h2', 'kv-gruppe-titel', cardTitle(head)), el('span', 'kv-gruppe-zahl', count === 1 ? '1 Karte' : `${count} Karten`));
            return bar;
        }

        function renderGrid() {
            const query = search.value;
            const shown = rows.filter((row) => !isGroupHead(row) && matches(cardTitle(row), query));
            const parts = [];
            // grouped by theme and no search: the headings stand over their cards
            const groups = query.trim() ? [{ head: null, cards: shown }] : grouped(rows);
            for (const group of groups) {
                if (group.head) parts.push(headEl(group.head, group.cards.length));
                else if (groups.length > 1) parts.push(el('div', 'kv-gruppe kv-gruppe-ohne', 'Ohne Gruppe'));
                parts.push(...group.cards.map(cardEl));
            }
            grid.replaceChildren(...parts);
            const total = rows.filter((row) => !isGroupHead(row)).length;   // headings are no cards
            countEl.textContent = query.trim()
                ? `${shown.length} von ${total} Karten`
                : (total === 1 ? '1 Karte' : `${total} Karten`);
            none.hidden = shown.length > 0;
            none.textContent = total === 0
                ? 'Noch keine Notizen in dieser Bubble. Tippe rechts im Chat, um die erste festzuhalten.'
                : (query.trim() ? `Keine Karte mit „${query.trim()}“ im Titel` : '');
        }

        function section(head, lines) {
            const box = el('section', 'kv-section');
            if (head) box.append(el('h3', null, head));
            const ul = el('ul');
            for (const line of lines) {
                const li = el('li');
                li.innerHTML = inline(line);   // maskiert; Adressen werden Links
                ul.append(li);
            }
            box.append(ul);
            return box;
        }

        function tableOf(row) {
            const data = isMap(row.content_json) ? row.content_json : {};
            const headers = items(data.headers).map((c) => plain(c, null));
            const body = items(data.rows).filter(Array.isArray);
            if (!body.length) return null;
            const wrap = el('div', 'kv-table-wrap');
            const table = el('table');
            if (headers.some(Boolean)) {
                const tr = el('tr');
                for (const h of headers) tr.append(el('th', null, h));
                const thead = el('thead');
                thead.append(tr);
                table.append(thead);
            }
            const tbody = el('tbody');
            for (const r of body) {
                const tr = el('tr');
                for (const c of r) tr.append(el('td', null, plain(String(c == null ? '' : c), null)));
                tbody.append(tr);
            }
            table.append(tbody);
            wrap.append(table);
            return wrap;
        }

        function renderReader() {
            const row = rows.find((r) => r.id === openId);
            if (!row) { close(); return; }
            const view = cardRead(row, edges, titles);
            const scroll = reader.querySelector('.kv-read-body');
            const keep = scroll ? scroll.scrollTop : 0;
            const sameCard = reader.dataset.cardId === openId;

            const panel = el('div', 'kv-read');
            const head = el('header', 'kv-read-head');
            const art = view.quelle && view.quelle.startsWith(view.art) ? null : view.art;   // "Recherche vom …" says it already
            const meta = [art, view.umfang, view.quelle].filter(Boolean).join(' · ');
            const titleBox = el('div', 'kv-read-titles');
            titleBox.append(el('div', 'kv-read-meta', meta), el('h2', 'kv-read-title', view.titel));
            head.append(titleBox);
            if (rootId && row.id === rootId) head.append(rootMark());
            if (view.bewertung != null) {
                const chip = el('span', 'kv-wert kv-wert-gross', String(view.bewertung));
                chip.title = 'Bewertung';
                head.append(chip);
            }
            const shut = el('button', 'kv-btn kv-close', 'Schließen');
            shut.type = 'button';
            shut.title = 'Schließen (Esc)';
            shut.addEventListener('click', close);
            head.append(shut);

            const body = el('div', 'kv-read-body');
            const content = el('div', 'kv-read-content');
            let toc = [];
            if (view.leer) content.append(el('p', 'kv-empty', 'Noch ohne Inhalt'));
            else if (view.text) {
                const md = renderMarkdown(view.text);
                content.innerHTML = linkMentions(md.html, titles, row.id);   // aus maskiertem Text gebaut (renderMarkdown)
                content.classList.add('kv-md');
                toc = md.headings;
            } else if (cardFormat(row) === 'table' && tableOf(row)) {
                content.append(tableOf(row));
            } else {
                for (const part of view.abschnitte) content.append(section(part.ueberschrift, part.zeilen));
                // a Kanban: its columns next to each other, as on a board
                if (cardFormat(row) === 'kanban') content.classList.add('kv-kanban');
            }
            if (view.quellen.length) {
                const box = el('section', 'kv-section kv-links kv-quellen');
                box.append(el('h3', null, view.quellen.length === 1 ? 'Geschrieben aus dieser Karte' : `Geschrieben aus diesen Karten (${view.quellen.length})`));
                const list = el('div', 'kv-link-list');
                for (const source of view.quellen) {
                    const go = el('button', 'kv-link-btn', source.titel);
                    go.type = 'button';
                    go.title = 'Karte öffnen';
                    go.addEventListener('click', () => open(source.id));
                    list.append(go);
                }
                box.append(list);
                content.append(box);
            }
            if (view.verbindungen.length) {
                const box = el('section', 'kv-section kv-links');
                box.append(el('h3', null, view.verbindungen.length === 1 ? 'Verbindung' : `Verbindungen (${view.verbindungen.length})`));
                const list = el('div', 'kv-link-list');
                for (const link of view.verbindungen) {
                    const go = el('button', 'kv-link-btn');
                    go.type = 'button';
                    go.append(el('span', 'kv-link-art', link.art), el('span', null, link.titel));
                    go.addEventListener('click', () => open(link.id));
                    list.append(go);
                }
                box.append(list);
                content.append(box);
            }
            const long = (view.text && view.text.length > LONG_TEXT) || toc.length >= 3;
            if (long && toc.length >= 2) {
                const nav = el('nav', 'kv-toc');
                nav.append(el('div', 'kv-toc-head', 'Inhalt'));
                for (const h of toc) {
                    const jump = el('button', 'kv-toc-item kv-toc-' + Math.min(h.level, 3), h.text);
                    jump.type = 'button';
                    jump.addEventListener('click', () => {
                        const target = content.querySelector('#' + h.anchor);
                        if (target) body.scrollTop = target.offsetTop - content.offsetTop;
                    });
                    nav.append(jump);
                }
                body.append(nav);
                body.classList.add('kv-with-toc');
            }
            body.append(content);
            panel.append(head, body);
            reader.replaceChildren(panel);
            reader.dataset.cardId = openId;
            if (sameCard) body.scrollTop = keep;
        }

        function open(id) {
            if (!id || !rows.some((r) => r.id === id)) return false;
            const first = reader.hidden;
            openId = id;
            reader.dataset.cardId = '';
            reader.hidden = false;
            renderReader();
            if (first) {
                const shut = reader.querySelector('.kv-close');
                if (shut && shut.focus) shut.focus();
            }
            return true;
        }

        function close() {
            const was = openId;
            openId = null;
            reader.hidden = true;
            reader.replaceChildren();
            reader.dataset.cardId = '';
            const card = was && grid.querySelector(`[data-card-id="${was.replace(/"/g, '')}"]`);
            if (card && card.focus) card.focus();
        }

        reader.addEventListener('click', (e) => { if (e.target === reader) close(); });
        // Links: im Browser des Systems, nie in der App (preload: vibemind.openExternal, main prueft erneut)
        const openUrl = typeof options.openUrl === 'function' ? options.openUrl : (url) => {
            const win = doc.defaultView || (typeof window !== 'undefined' ? window : null);
            const api = win && win.vibemind;
            if (api && typeof api.openExternal === 'function') api.openExternal(url);
        };
        const followLink = (e) => {
            const target = e.target && typeof e.target.closest === 'function' ? e.target.closest('.kv-link[data-url]') : null;
            if (!target) return;
            if (e.type === 'keydown' && e.key !== 'Enter') return;
            e.preventDefault();
            e.stopPropagation();
            const url = safeUrl(target.getAttribute('data-url'));
            if (url) openUrl(url);
        };
        reader.addEventListener('click', followLink);
        reader.addEventListener('keydown', followLink);
        // a card named in the text opens in the same reader
        const followMention = (e) => {
            const target = e.target && typeof e.target.closest === 'function' ? e.target.closest('.kv-jump[data-card-id]') : null;
            if (!target) return;
            if (e.type === 'keydown' && e.key !== 'Enter') return;
            e.preventDefault();
            e.stopPropagation();
            open(target.getAttribute('data-card-id'));
        };
        reader.addEventListener('click', followMention);
        reader.addEventListener('keydown', followMention);
        // Esc schliesst die Karte und nur die Karte: die App darf dabei die Bubble nicht verlassen.
        const onKey = (e) => {
            if (e.key !== 'Escape' || reader.hidden || !rootEl.isConnected) return;
            e.preventDefault();
            e.stopImmediatePropagation();
            close();
        };
        doc.addEventListener('keydown', onKey, true);
        // Tippen in der Suche steuert nicht die 3D-Welt (Pfeile wechseln dort den Space).
        search.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && search.value) { search.value = ''; renderGrid(); }
            e.stopPropagation();
        });
        search.addEventListener('input', renderGrid);
        // step -1 kleiner, +1 groesser; die feste Leiste der Bubble (bubble-bar.js) ruft das auch
        const zoom = (step) => {
            const next = Math.max(0, Math.min(SIZES.length - 1, size + (step < 0 ? -1 : 1)));
            if (next === size) return false;
            size = next;
            applySize();
            remember(doc, 'vibemind.karten.groesse', size);
            return true;
        };
        smaller.addEventListener('click', () => zoom(-1));
        bigger.addEventListener('click', () => zoom(1));
        graph.addEventListener('click', () => options.onGraph());
        // Wheel und Ziehen gehoeren dem Raster, nicht dem Canvas darunter.
        rootEl.addEventListener('wheel', (e) => e.stopPropagation(), { passive: true });
        rootEl.addEventListener('mousedown', (e) => e.stopPropagation());

        return {
            element: rootEl,
            mount(container) {
                if (rootEl.parentNode !== container) { container.innerHTML = ''; container.append(rootEl); }
            },
            update(nodes, newEdges) {
                const next = items(nodes).map(rowOf).filter((r) => r.id);
                const sig = JSON.stringify([next, items(newEdges)]);
                if (sig === signature) return false;
                signature = sig;
                rows = next.slice().sort((a, b) => cardTitle(a).localeCompare(cardTitle(b), 'de'));
                edges = items(newEdges).filter(isMap);
                titles = new Map(rows.map((r) => [r.id, cardTitle(r)]));
                renderGrid();
                if (openId) renderReader();
                return true;
            },
            open,
            close,
            /** The root of the bubble (metadata.wurzel); null clears it. Redraws only on a change. */
            setRoot(id) {
                const next = id != null && String(id) ? String(id) : null;
                if (next === rootId) return false;
                rootId = next;
                renderGrid();
                if (openId) renderReader();
                return true;
            },
            get rootId() { return rootId; },
            get openId() { return openId; },
            get count() { return rows.length; },
            get query() { return search.value; },
            /** Was die feste Leiste der Bubble zeigt: Anzahl, Treffer der Suche, Zoomgrenzen. */
            get state() {
                const shown = rows.filter((row) => matches(cardTitle(row), search.value)).length;
                return { count: rows.length, shown, query: search.value, smaller: size > 0, bigger: size < SIZES.length - 1 };
            },
            zoom,
            setQuery(text) { search.value = text; renderGrid(); },
            destroy() { doc.removeEventListener('keydown', onKey, true); rootEl.remove(); },
        };
    }

    return {
        FORMAT_NAMES, CARD_LINES, CARD_LINE_CHARS, SIZES,
        rowOf, cardFormat, plain, cardTitle, cardSource, cardShort, cardRead, cardLinks, cardSources, linkMentions,
        renderMarkdown, escapeHtml, safeUrl, headingOf, searchKey, matches, board, isGroupHead, grouped,
    };
});
