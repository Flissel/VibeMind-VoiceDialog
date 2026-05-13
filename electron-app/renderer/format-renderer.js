/**
 * VibeMind format-renderer — turns content_json into Mermaid diagrams.
 *
 * Phase 11.U.N rev2 — Card-AT-Node mode (voice-first):
 *   click / voice "zeig X" → zoom to node → card opens at node position
 *   voice "schließen" / Esc → card closes → zoom restores to overview
 *
 * Public API:
 *   window.openFormatPanel(node)   — animate zoom + open card
 *   window.closeFormatPanel()      — close card + restore zoom
 */
(function () {
    let _card = null;
    let _renderId = 0;
    let _savedZoomState = null;   // {scale, panX, panY}

    function _escapeMermaid(s) {
        if (s == null) return '';
        return String(s).replace(/"/g, "'").replace(/\n/g, ' ').slice(0, 80);
    }

    // ===== Per-format builders =====
    function _buildSwot(cj) {
        const title = cj.subject || cj.title || 'SWOT';
        const lines = [
            'graph TB',
            `    SWOT["${_escapeMermaid(title)}"]`,
            '    classDef rootC fill:#312e81,stroke:#a78bfa,stroke-width:3px,color:#fff,font-size:15px',
            '    classDef strengthC fill:#064e3b,stroke:#10b981,stroke-width:2px,color:#fff',
            '    classDef weaknessC fill:#7c2d12,stroke:#f97316,stroke-width:2px,color:#fff',
            '    classDef opportunityC fill:#1e3a8a,stroke:#3b82f6,stroke-width:2px,color:#fff',
            '    classDef threatC fill:#7f1d1d,stroke:#ef4444,stroke-width:2px,color:#fff',
            '    class SWOT rootC',
        ];
        const quadrants = [
            { key: 'strengths', label: 'S — Strengths', cls: 'strengthC' },
            { key: 'weaknesses', label: 'W — Weaknesses', cls: 'weaknessC' },
            { key: 'opportunities', label: 'O — Opportunities', cls: 'opportunityC' },
            { key: 'threats', label: 'T — Threats', cls: 'threatC' },
        ];
        for (const q of quadrants) {
            const items = Array.isArray(cj[q.key]) ? cj[q.key] : [];
            const prefix = q.key.charAt(0).toUpperCase();
            const hubId = `H_${prefix}`;
            lines.push(`    ${hubId}["${_escapeMermaid(q.label)}"]`);
            lines.push(`    class ${hubId} ${q.cls}`);
            lines.push(`    SWOT --> ${hubId}`);
            items.forEach((it, i) => {
                const point = _escapeMermaid(it.point || it.text || '?');
                const nid = `${prefix}${i}`;
                lines.push(`    ${nid}["${point}"]`);
                lines.push(`    class ${nid} ${q.cls}`);
                lines.push(`    ${hubId} --> ${nid}`);
            });
        }
        return lines.join('\n');
    }

    function _buildKanban(cj) {
        const cols = ['todo', 'doing', 'done'];
        const lines = [
            'graph LR',
            '    classDef colC fill:#312e81,stroke:#a78bfa,stroke-width:2px,color:#fff',
            '    classDef cardC fill:#1e293b,stroke:#a78bfa,color:#fff',
        ];
        for (const col of cols) {
            const items = Array.isArray(cj[col]) ? cj[col] : [];
            const cid = `COL_${col}`;
            lines.push(`    ${cid}["${col.toUpperCase()} (${items.length})"]`);
            lines.push(`    class ${cid} colC`);
            items.forEach((it, i) => {
                const text = _escapeMermaid(it.title || it.text || it.point || '?');
                const nid = `${cid}_${i}`;
                lines.push(`    ${nid}["${text}"]`);
                lines.push(`    class ${nid} cardC`);
                lines.push(`    ${cid} --> ${nid}`);
            });
        }
        return lines.join('\n');
    }

    function _buildMindmap(cj) {
        const root = cj.root || cj.title || cj.subject || 'Mindmap';
        const branches = Array.isArray(cj.branches) ? cj.branches : [];
        const lines = ['mindmap', `  root((${_escapeMermaid(root)}))`];
        const walk = (items, indent) => {
            for (const it of items) {
                const text = _escapeMermaid(it.text || it.title || it.point || it.label || '?');
                lines.push(`${' '.repeat(indent)}${text}`);
                if (Array.isArray(it.children)) walk(it.children, indent + 2);
                if (Array.isArray(it.subbranches)) walk(it.subbranches, indent + 2);
            }
        };
        walk(branches, 4);
        return lines.join('\n');
    }

    function _buildTable(cj) {
        const cols = Array.isArray(cj.columns) ? cj.columns : [];
        const rows = Array.isArray(cj.rows) ? cj.rows : [];
        const lines = [
            'graph TD',
            '    classDef hdrC fill:#312e81,stroke:#a78bfa,stroke-width:2px,color:#fff',
            '    classDef cellC fill:#1e293b,stroke:#a78bfa,color:#fff',
        ];
        const hdrLabel = cols.length > 0 ? cols.join(' | ') : (cj.title || 'Table');
        lines.push(`    HDR["${_escapeMermaid(hdrLabel)}"]`);
        lines.push('    class HDR hdrC');
        rows.slice(0, 20).forEach((row, i) => {
            const cells = Array.isArray(row) ? row : (row.cells || Object.values(row));
            const rowText = (cells || []).join(' | ');
            const nid = `R${i}`;
            lines.push(`    ${nid}["${_escapeMermaid(rowText)}"]`);
            lines.push(`    class ${nid} cellC`);
            lines.push(`    HDR --> ${nid}`);
        });
        return lines.join('\n');
    }

    function _buildActionList(cj) {
        const tasks = Array.isArray(cj.tasks) ? cj.tasks : (Array.isArray(cj.actions) ? cj.actions : []);
        const lines = [
            'graph TD',
            '    classDef todoC fill:#1e293b,stroke:#a78bfa,stroke-width:2px,color:#fff',
            '    classDef doneC fill:#064e3b,stroke:#10b981,stroke-width:2px,color:#fff',
        ];
        lines.push(`    LIST["Actions (${tasks.length})"]`);
        lines.push('    class LIST todoC');
        tasks.forEach((t, i) => {
            const text = _escapeMermaid(t.title || t.text || t.task || '?');
            const checked = (t.checked || t.done) ? '✓ ' : '○ ';
            const nid = `T${i}`;
            lines.push(`    ${nid}["${checked}${text}"]`);
            lines.push(`    class ${nid} ${(t.checked || t.done) ? 'doneC' : 'todoC'}`);
            lines.push(`    LIST --> ${nid}`);
        });
        return lines.join('\n');
    }

    function _buildProsCons(cj) {
        const pros = Array.isArray(cj.pros) ? cj.pros : [];
        const cons = Array.isArray(cj.cons) ? cj.cons : [];
        const lines = [
            'graph LR',
            '    classDef proC fill:#064e3b,stroke:#10b981,stroke-width:2px,color:#fff',
            '    classDef conC fill:#7f1d1d,stroke:#ef4444,stroke-width:2px,color:#fff',
            '    classDef rootC fill:#312e81,stroke:#a78bfa,stroke-width:3px,color:#fff',
        ];
        lines.push(`    ROOT["${_escapeMermaid(cj.title || 'Pros & Cons')}"]`);
        lines.push('    class ROOT rootC');
        lines.push('    PROS["Pros"]'); lines.push('    class PROS proC');
        lines.push('    CONS["Cons"]'); lines.push('    class CONS conC');
        lines.push('    ROOT --> PROS'); lines.push('    ROOT --> CONS');
        pros.forEach((p, i) => {
            const text = _escapeMermaid(p.text || p.point || p);
            lines.push(`    P${i}["${text}"]`);
            lines.push(`    class P${i} proC`);
            lines.push(`    PROS --> P${i}`);
        });
        cons.forEach((c, i) => {
            const text = _escapeMermaid(c.text || c.point || c);
            lines.push(`    C${i}["${text}"]`);
            lines.push(`    class C${i} conC`);
            lines.push(`    CONS --> C${i}`);
        });
        return lines.join('\n');
    }

    function _buildHierarchy(cj) {
        const root = cj.root || cj.title || 'Hierarchy';
        const lines = ['graph TD', '    classDef nC fill:#1e293b,stroke:#a78bfa,color:#fff'];
        let counter = 0;
        const walk = (items, parentId) => {
            for (const it of items) {
                const text = _escapeMermaid(it.text || it.title || it.label || '?');
                const id = `N${counter++}`;
                lines.push(`    ${id}["${text}"]`);
                lines.push(`    class ${id} nC`);
                if (parentId) lines.push(`    ${parentId} --> ${id}`);
                if (Array.isArray(it.children)) walk(it.children, id);
            }
        };
        const rootId = `N${counter++}`;
        lines.push(`    ${rootId}["${_escapeMermaid(root)}"]`);
        lines.push(`    class ${rootId} nC`);
        walk(Array.isArray(cj.children) ? cj.children : [], rootId);
        return lines.join('\n');
    }

    function _buildFlowchart(cj) {
        // Two possible schemas:
        //   A) {steps: [{text}, ...]} — linear
        //   B) {nodes: [{id, type, label}], edges: [{from, to, label}]} — DAG (LLM-default)
        const lines = [
            'graph LR',
            '    classDef startC fill:#064e3b,stroke:#10b981,stroke-width:2px,color:#fff',
            '    classDef endC fill:#7f1d1d,stroke:#ef4444,stroke-width:2px,color:#fff',
            '    classDef processC fill:#1e293b,stroke:#a78bfa,color:#fff',
            '    classDef decisionC fill:#312e81,stroke:#f59e0b,stroke-width:2px,color:#fff',
            '    classDef stepC fill:#1e293b,stroke:#a78bfa,color:#fff',
        ];
        if (Array.isArray(cj.nodes) && Array.isArray(cj.edges)) {
            const sid = (id) => 'N_' + String(id).replace(/[^a-zA-Z0-9_]/g, '_');
            for (const n of cj.nodes) {
                const label = _escapeMermaid(n.label || n.text || n.id);
                const t = (n.type || 'process').toLowerCase();
                const shape = t === 'decision' ? `{${label}}` : (t === 'start' || t === 'end' ? `([${label}])` : `[${label}]`);
                lines.push(`    ${sid(n.id)}${shape}`);
                const cls = t === 'start' ? 'startC' : t === 'end' ? 'endC' : t === 'decision' ? 'decisionC' : 'processC';
                lines.push(`    class ${sid(n.id)} ${cls}`);
            }
            for (const e of cj.edges) {
                const lbl = e.label ? `|${_escapeMermaid(e.label)}|` : '';
                lines.push(`    ${sid(e.from)} -->${lbl} ${sid(e.to)}`);
            }
            return lines.join('\n');
        }
        const steps = Array.isArray(cj.steps) ? cj.steps : [];
        steps.forEach((s, i) => {
            const text = _escapeMermaid(s.text || s.title || s.label || '?');
            lines.push(`    S${i}["${text}"]`);
            lines.push(`    class S${i} stepC`);
            if (i > 0) lines.push(`    S${i - 1} --> S${i}`);
        });
        return lines.join('\n');
    }

    function _buildSpecs(cj) {
        // LLM-default schema: {component, specifications:[{category, priority, requirement, acceptance_criteria}]}
        // Alt schema: {sections:[{title, items:[...]}]}
        const lines = [
            'graph TB',
            '    classDef rootC fill:#312e81,stroke:#a78bfa,stroke-width:3px,color:#fff,font-size:15px',
            '    classDef catC fill:#312e81,stroke:#a78bfa,stroke-width:2px,color:#fff',
            '    classDef mustC fill:#7f1d1d,stroke:#ef4444,stroke-width:2px,color:#fff',
            '    classDef shouldC fill:#7c2d12,stroke:#f97316,stroke-width:2px,color:#fff',
            '    classDef niceC fill:#064e3b,stroke:#10b981,stroke-width:2px,color:#fff',
            '    classDef iC fill:#1e293b,stroke:#a78bfa,color:#fff',
        ];
        if (Array.isArray(cj.specifications)) {
            const compName = cj.component || cj.title || 'Specs';
            lines.push(`    ROOT["${_escapeMermaid(compName)}"]`);
            lines.push('    class ROOT rootC');
            const byCat = {};
            cj.specifications.forEach((s, i) => {
                const cat = s.category || 'General';
                (byCat[cat] = byCat[cat] || []).push({ s, i });
            });
            let catIdx = 0;
            for (const [cat, items] of Object.entries(byCat)) {
                const cid = `C${catIdx++}`;
                lines.push(`    ${cid}["${_escapeMermaid(cat)}"]`);
                lines.push(`    class ${cid} catC`);
                lines.push(`    ROOT --> ${cid}`);
                items.forEach(({ s, i }) => {
                    const nid = `S${i}`;
                    const prio = (s.priority || '').toLowerCase();
                    const cls = prio.includes('must') ? 'mustC' : prio.includes('should') ? 'shouldC' : prio ? 'niceC' : 'iC';
                    lines.push(`    ${nid}["${_escapeMermaid(s.requirement || s.text || '?')}"]`);
                    lines.push(`    class ${nid} ${cls}`);
                    lines.push(`    ${cid} --> ${nid}`);
                });
            }
            return lines.join('\n');
        }
        // Old sections-schema fallback
        const sections = Array.isArray(cj.sections) ? cj.sections : [];
        sections.forEach((sec, i) => {
            const hid = `H${i}`;
            lines.push(`    ${hid}["${_escapeMermaid(sec.title || sec.name || `Section ${i+1}`)}"]`);
            lines.push(`    class ${hid} catC`);
            const items = Array.isArray(sec.items) ? sec.items : [];
            items.forEach((it, j) => {
                const text = _escapeMermaid(it.text || it.title || '?');
                const nid = `${hid}_${j}`;
                lines.push(`    ${nid}["${text}"]`);
                lines.push(`    class ${nid} iC`);
                lines.push(`    ${hid} --> ${nid}`);
            });
        });
        return lines.join('\n');
    }

    function _buildUserStory(cj) {
        const stories = Array.isArray(cj.stories) ? cj.stories : [];
        const lines = [
            'graph TB',
            '    classDef rootC fill:#312e81,stroke:#a78bfa,stroke-width:3px,color:#fff',
            '    classDef mustC fill:#7f1d1d,stroke:#ef4444,stroke-width:2px,color:#fff',
            '    classDef shouldC fill:#7c2d12,stroke:#f97316,stroke-width:2px,color:#fff',
            '    classDef niceC fill:#064e3b,stroke:#10b981,stroke-width:2px,color:#fff',
            '    classDef sC fill:#1e293b,stroke:#a78bfa,color:#fff',
        ];
        const epic = cj.epic || cj.title || 'User Stories';
        lines.push(`    EPIC["${_escapeMermaid(epic)}"]`);
        lines.push('    class EPIC rootC');
        stories.forEach((s, i) => {
            const role = s.role || s.as || '?';
            const want = s.want || s.action || '?';
            const so = s.so_that || s.benefit || s.value || '?';
            const text = _escapeMermaid(`${role} -- ${want} -- ${so}`);
            const prio = (s.priority || '').toLowerCase();
            const cls = prio.includes('must') ? 'mustC' : prio.includes('should') ? 'shouldC' : prio ? 'niceC' : 'sC';
            lines.push(`    US${i}["${text}"]`);
            lines.push(`    class US${i} ${cls}`);
            lines.push(`    EPIC --> US${i}`);
        });
        return lines.join('\n');
    }

    const _BUILDERS = {
        swot: _buildSwot,
        kanban: _buildKanban,
        mindmap: _buildMindmap,
        table: _buildTable,
        simple_table: _buildTable,
        comparison_table: _buildTable,
        action_list: _buildActionList,
        pros_cons: _buildProsCons,
        pros_cons_table: _buildProsCons,
        hierarchy: _buildHierarchy,
        flowchart: _buildFlowchart,
        specs: _buildSpecs,
        technical_specs: _buildSpecs,
        user_story: _buildUserStory,
    };

    function _ensureCard() {
        if (_card) return _card;
        const card = document.createElement('div');
        card.id = 'format-card';
        card.style.cssText = [
            'position:fixed',
            'top:50%',
            'left:50%',
            'transform:translate(-50%,-50%) scale(0.8)',
            'opacity:0',
            // Phase 11.U.N rev3 — larger card so the Mermaid sub-diagram is readable
            'width:min(1400px, 92vw)',
            'height:min(840px, 88vh)',
            'background:rgba(10,10,10,0.97)',
            'border:2px solid #10b981',
            'border-radius:12px',
            'box-shadow:0 0 60px rgba(16,185,129,0.4), 0 20px 60px rgba(0,0,0,0.7)',
            'z-index:9999',
            'display:none',
            'flex-direction:column',
            'color:#fff',
            'font-family:system-ui',
            'transition:transform 250ms ease-out, opacity 250ms ease-out',
        ].join(';');

        const header = document.createElement('div');
        header.style.cssText = 'display:flex;align-items:center;padding:12px 16px;border-bottom:1px solid rgba(16,185,129,0.3);background:rgba(20,25,40,0.95);border-radius:10px 10px 0 0';
        const title = document.createElement('span');
        title.id = 'format-card-title';
        title.style.cssText = 'flex:1;font-size:15px;font-weight:500;color:#10b981';
        title.textContent = 'Format Detail';
        const closeHint = document.createElement('span');
        closeHint.style.cssText = 'font-size:11px;color:#6b7280;margin-right:12px';
        closeHint.textContent = 'Esc / say "back"';
        const close = document.createElement('button');
        close.textContent = '×';
        close.style.cssText = 'background:transparent;border:0;color:#fff;font-size:22px;cursor:pointer;padding:0 8px;line-height:1';
        close.title = 'Close';
        close.onclick = () => closeFormatPanel();
        header.appendChild(title);
        header.appendChild(closeHint);
        header.appendChild(close);
        card.appendChild(header);

        const body = document.createElement('div');
        body.id = 'format-card-body';
        body.style.cssText = 'flex:1;display:flex;flex-direction:column;overflow:hidden;padding:18px;background:#0a0a0a;border-radius:0 0 10px 10px;min-height:0';
        card.appendChild(body);

        document.body.appendChild(card);
        _card = card;

        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && _card.style.display === 'flex') closeFormatPanel();
        });
        return card;
    }

    async function _renderInto(body, mermaidText, fmtName) {
        body.innerHTML = '<div style="color:#9ca3af;font-size:13px;padding:10px">Rendering…</div>';
        if (typeof window.mermaid === 'undefined') {
            body.innerHTML = '<div style="color:#ef4444">Mermaid not loaded</div>';
            return;
        }
        const id = `_fmtCard_${++_renderId}`;
        try {
            const result = await window.mermaid.render(id, mermaidText);
            body.innerHTML = `
                <div style="color:#10b981;font-size:12px;margin-bottom:12px;text-transform:uppercase;letter-spacing:0.08em;flex:0 0 auto">${fmtName}</div>
                <div class="format-card-svg-host" style="flex:1;background:#111827;border-radius:8px;padding:14px;display:flex;align-items:center;justify-content:center;overflow:auto;min-height:0">${result.svg}</div>
            `;
            // Phase 11.U.N rev3 — make the SVG fill its host so labels become readable.
            const svgEl = body.querySelector('.format-card-svg-host svg');
            if (svgEl) {
                svgEl.removeAttribute('width');
                svgEl.removeAttribute('height');
                svgEl.style.width = '100%';
                svgEl.style.height = '100%';
                svgEl.style.maxWidth = '100%';
                svgEl.style.maxHeight = '100%';
                svgEl.setAttribute('preserveAspectRatio', 'xMidYMid meet');
            }
        } catch (err) {
            console.error('[format-card] mermaid error:', err);
            body.innerHTML = `<div style="color:#ef4444;padding:10px">Mermaid render error: ${err.message}</div>`;
        }
    }

    /**
     * Zoom to the clicked node, then animate the card open at its position.
     * Saves the current pan/zoom state so closeFormatPanel can restore it.
     */
    function openFormatPanel(node, opts = {}) {
        const card = _ensureCard();
        const title = card.querySelector('#format-card-title');
        const body = card.querySelector('#format-card-body');
        const cj = node && node.content_json;
        const fmt = cj && cj.type;
        const nodeTitle = (node && (node.title || (node.content && node.content.title))) || node?.id || 'Node';
        const subject = (cj && (cj.subject || cj.title)) || nodeTitle;
        title.textContent = `${nodeTitle} · ${fmt || 'note'}`;

        // Phase 11.U.N rev2 — zoom into the clicked node in the main diagram
        // before opening the card. The card itself overlays center, but the
        // background pan-zoom is animated so the focus is on the formatted node.
        if (opts.zoom !== false) _zoomToNode(node);

        if (!cj || !fmt) {
            body.innerHTML = '<div style="color:#9ca3af;padding:10px">No structured content for this idea.</div>';
        } else {
            const builder = _BUILDERS[fmt];
            if (!builder) {
                body.innerHTML = `<div style="color:#f97316;padding:10px">No renderer for format "${fmt}". Raw JSON:</div><pre style="color:#9ca3af;font-size:11px;white-space:pre-wrap;background:#1f2937;padding:10px;border-radius:6px;margin-top:10px">${JSON.stringify(cj, null, 2)}</pre>`;
            } else {
                _renderInto(body, builder(cj), fmt);
            }
        }

        // Animate card in
        card.style.display = 'flex';
        // double-rAF to let display:flex apply before transitioning
        requestAnimationFrame(() => {
            requestAnimationFrame(() => {
                card.style.transform = 'translate(-50%,-50%) scale(1)';
                card.style.opacity = '1';
            });
        });
    }

    function closeFormatPanel() {
        if (!_card) return;
        _card.style.transform = 'translate(-50%,-50%) scale(0.8)';
        _card.style.opacity = '0';
        setTimeout(() => { if (_card) _card.style.display = 'none'; }, 250);
        // Restore background zoom
        _restoreZoom();
    }

    function _zoomToNode(node) {
        // Find the SVG node-group via the sanitized id
        const sid = 'n_' + String(node.id).replace(/[^a-zA-Z0-9_]/g, '_');
        const matches = document.querySelectorAll(`g.node[id*="${sid}"]`);
        if (!matches.length) return;
        const g = matches[0];

        const wrap = document.querySelector('.mermaid-graph-wrap');
        const inner = document.querySelector('.mermaid-graph-inner');
        if (!wrap || !inner) return;

        // Save current transform so we can restore on close
        const cur = inner.style.transform || '';
        const m = cur.match(/translate\(\s*([-\d.]+)px\s*,\s*([-\d.]+)px\s*\)\s*scale\(\s*([-\d.]+)\s*\)/);
        _savedZoomState = m ? {
            panX: parseFloat(m[1]),
            panY: parseFloat(m[2]),
            scale: parseFloat(m[3]),
        } : null;

        // Compute node center in SVG-coordinates
        const tr = g.getAttribute('transform') || '';
        const tm = tr.match(/translate\(\s*([-\d.]+)\s*[, ]\s*([-\d.]+)\s*\)/);
        if (!tm) return;
        const nodeX = parseFloat(tm[1]);
        const nodeY = parseFloat(tm[2]);

        // Target: scale so the node + card are visible together. Card opens
        // at viewport center, so we just need the node visible behind/around it.
        // Zoom to ~1.5x and pan so the node ends up roughly at left-of-center
        // (since the card is at center).
        const wrapRect = wrap.getBoundingClientRect();
        const newScale = 1.5;
        // We want the node at viewport coord (wrapW * 0.25, wrapH * 0.5)
        // panX + nodeX * newScale = wrapW * 0.25
        const targetX = wrapRect.width * 0.25 - nodeX * newScale;
        const targetY = wrapRect.height * 0.5 - nodeY * newScale;

        // Smooth animate via CSS transition
        inner.style.transition = 'transform 400ms ease-out';
        inner.style.transform = `translate(${targetX}px, ${targetY}px) scale(${newScale})`;
        setTimeout(() => { inner.style.transition = ''; }, 420);
    }

    function _restoreZoom() {
        const inner = document.querySelector('.mermaid-graph-inner');
        if (!inner) return;
        let target;
        if (_savedZoomState) {
            target = `translate(${_savedZoomState.panX}px, ${_savedZoomState.panY}px) scale(${_savedZoomState.scale})`;
        } else {
            // Fall back to initial fit from mermaid-layout
            const s = parseFloat(inner.dataset.initialScale) || 1;
            const tx = parseFloat(inner.dataset.initialTx) || 0;
            const ty = parseFloat(inner.dataset.initialTy) || 0;
            target = `translate(${tx}px, ${ty}px) scale(${s})`;
        }
        inner.style.transition = 'transform 400ms ease-out';
        inner.style.transform = target;
        setTimeout(() => { inner.style.transition = ''; _savedZoomState = null; }, 420);
    }

    // Phase 11.U.N rev5 — track the currently-open node so the mermaid auto-poll
    // can refresh the card content live when new format-data arrives via realtime.
    let _openedNodeId = null;
    const _origOpen = openFormatPanel;
    function _openWithTracking(node, opts) {
        _openedNodeId = node && node.id;
        _origOpen(node, opts);
    }
    const _origClose = closeFormatPanel;
    function _closeWithTracking() {
        _openedNodeId = null;
        _origClose();
    }
    function refreshOpenFormatPanel() {
        if (!_openedNodeId || !_card || _card.style.display === 'none') return;
        const data = window._mermaidSidToNode;
        if (!data) return;
        const sid = 'n_' + String(_openedNodeId).replace(/[^a-zA-Z0-9_]/g, '_');
        const fresh = data.get(sid);
        if (fresh) _origOpen(fresh, { zoom: false });   // re-render body, don't re-zoom
    }

    window.openFormatPanel = _openWithTracking;
    window.closeFormatPanel = _closeWithTracking;
    window.refreshOpenFormatPanel = refreshOpenFormatPanel;
    console.log('[format-renderer] rev5 — auto-refresh of open card on poll');
})();
