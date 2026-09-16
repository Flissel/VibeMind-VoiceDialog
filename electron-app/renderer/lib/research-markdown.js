'use strict';
/**
 * Markdown -> DOM fuer Research-Karten.
 *
 * Erzeugt an KEINER Stelle einen HTML-String. parseMarkdown liefert eine
 * Baumbeschreibung aus einfachen Objekten, buildInto uebersetzt sie mit
 * createElement/textContent in DOM-Knoten. Eingebettetes Markup im Report
 * ist dadurch strukturell nicht ausfuehrbar - es gibt keinen Parse-Schritt,
 * der es interpretieren koennte. Der Reporttext stammt aus fremden
 * Webseiten und ist der am wenigsten vertrauenswuerdige Inhalt im System.
 */

const SAFE_SCHEMES = ['http:', 'https:'];

function safeHref(raw) {
    try {
        const u = new URL(raw, 'https://invalid.local/');
        return SAFE_SCHEMES.includes(u.protocol) ? u.href : null;
    } catch {
        return null;
    }
}

const INLINE_RE = /(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`|\[[^\]]+\]\([^)\s]+\))/;

function parseInline(text) {
    const spans = [];
    let rest = String(text ?? '');
    while (rest.length) {
        const m = INLINE_RE.exec(rest);
        if (!m) { spans.push({ t: 'text', v: rest }); break; }
        if (m.index > 0) spans.push({ t: 'text', v: rest.slice(0, m.index) });
        const tok = m[0];
        if (tok.startsWith('**')) {
            spans.push({ t: 'strong', v: tok.slice(2, -2) });
        } else if (tok.startsWith('`')) {
            spans.push({ t: 'code', v: tok.slice(1, -1) });
        } else if (tok.startsWith('[')) {
            const cut = tok.indexOf('](');
            const label = tok.slice(1, cut);
            const href = safeHref(tok.slice(cut + 2, -1));
            // Kein erlaubtes Schema => der Link wird Text. Ein javascript:
            // in einem href ist derselbe Einbruch wie ein <script>.
            if (href) spans.push({ t: 'link', v: label, href });
            else spans.push({ t: 'text', v: tok });
        } else {
            spans.push({ t: 'em', v: tok.slice(1, -1) });
        }
        rest = rest.slice(m.index + tok.length);
    }
    return spans.length ? spans : [{ t: 'text', v: '' }];
}

function splitRow(line) {
    return line.replace(/^\||\|$/g, '').split('|').map(c => parseInline(c.trim()));
}

function parseMarkdown(text) {
    const lines = String(text ?? '').split(/\r?\n/);
    const blocks = [];
    let i = 0;

    while (i < lines.length) {
        const line = lines[i];

        if (!line.trim()) { i++; continue; }

        if (line.startsWith('```')) {
            const body = [];
            i++;
            while (i < lines.length && !lines[i].startsWith('```')) body.push(lines[i++]);
            i++; // schliessende Zeile
            blocks.push({ kind: 'code', text: body.join('\n') });
            continue;
        }

        const heading = /^(#{1,4})\s+(.*)$/.exec(line);
        if (heading) {
            blocks.push({ kind: 'heading', level: heading[1].length, spans: parseInline(heading[2]) });
            i++;
            continue;
        }

        if (/^>\s?/.test(line)) {
            blocks.push({ kind: 'quote', spans: parseInline(line.replace(/^>\s?/, '')) });
            i++;
            continue;
        }

        if (line.includes('|') && /^\s*\|/.test(line)) {
            const rows = [];
            while (i < lines.length && /^\s*\|/.test(lines[i])) {
                if (!/^\s*\|[\s:-]+\|/.test(lines[i])) rows.push(splitRow(lines[i].trim()));
                i++;
            }
            blocks.push({ kind: 'table', rows });
            continue;
        }

        const bullet = /^\s*([-*])\s+(.*)$/;
        const number = /^\s*\d+\.\s+(.*)$/;
        if (bullet.test(line) || number.test(line)) {
            const ordered = number.test(line);
            const items = [];
            while (i < lines.length) {
                const b = bullet.exec(lines[i]);
                const n = number.exec(lines[i]);
                if (ordered && n) items.push(parseInline(n[1]));
                else if (!ordered && b) items.push(parseInline(b[2]));
                else break;
                i++;
            }
            blocks.push({ kind: 'list', ordered, items });
            continue;
        }

        const para = [];
        while (i < lines.length && lines[i].trim() && !/^(#{1,4}\s|```|>|\s*\||\s*[-*]\s|\s*\d+\.\s)/.test(lines[i])) {
            para.push(lines[i++]);
        }
        if (para.length) blocks.push({ kind: 'paragraph', spans: parseInline(para.join(' ')) });
        else i++; // Zeile passte in kein Muster: weiter, nie haengenbleiben
    }
    return blocks;
}

function appendSpans(parent, spans, doc) {
    for (const s of spans) {
        if (s.t === 'link') {
            const a = doc.createElement('a');
            a.href = s.href;
            a.target = '_blank';
            a.rel = 'noopener noreferrer';
            a.textContent = s.v;
            parent.appendChild(a);
            continue;
        }
        const tag = s.t === 'strong' ? 'strong' : s.t === 'em' ? 'em' : s.t === 'code' ? 'code' : 'span';
        const el = doc.createElement(tag);
        el.textContent = s.v;
        parent.appendChild(el);
    }
}

function buildInto(el, blocks, doc) {
    for (const b of blocks) {
        if (b.kind === 'heading') {
            const h = doc.createElement('h' + b.level);
            appendSpans(h, b.spans, doc);
            el.appendChild(h);
        } else if (b.kind === 'code') {
            const pre = doc.createElement('pre');
            const code = doc.createElement('code');
            code.textContent = b.text;
            pre.appendChild(code);
            el.appendChild(pre);
        } else if (b.kind === 'list') {
            const list = doc.createElement(b.ordered ? 'ol' : 'ul');
            for (const item of b.items) {
                const li = doc.createElement('li');
                appendSpans(li, item, doc);
                list.appendChild(li);
            }
            el.appendChild(list);
        } else if (b.kind === 'table') {
            const table = doc.createElement('table');
            b.rows.forEach((row, idx) => {
                const tr = doc.createElement('tr');
                for (const cell of row) {
                    const td = doc.createElement(idx === 0 ? 'th' : 'td');
                    appendSpans(td, cell, doc);
                    tr.appendChild(td);
                }
                table.appendChild(tr);
            });
            el.appendChild(table);
        } else if (b.kind === 'quote') {
            const q = doc.createElement('blockquote');
            appendSpans(q, b.spans, doc);
            el.appendChild(q);
        } else {
            const p = doc.createElement('p');
            appendSpans(p, b.spans, doc);
            el.appendChild(p);
        }
    }
}

if (typeof module !== 'undefined' && module.exports) {
    module.exports = { parseMarkdown, buildInto, SAFE_SCHEMES };
}
