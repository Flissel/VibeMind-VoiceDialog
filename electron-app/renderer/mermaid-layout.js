/**
 * Mermaid-based DIRECT renderer for canvas nodes.
 *
 * Phase 11.U.I rev2 — Direct-SVG mode. We render Mermaid's SVG straight
 * into the canvas container, ditching our DOM-positioned nodes. This
 * mirrors Rowboat's AgentGraphVisualizer.tsx exactly. Read-only — drag
 * and inline-edit are not supported in this mode, but the radial-hub
 * dagre layout is finally what the user actually wants.
 *
 * Public:
 *   window.computeMermaidLayout(nodes, edges, opts) -> Promise<Map> (legacy)
 *   window.renderMermaidIntoContainer(container, nodes, edges, opts) -> Promise<boolean>
 */
(function () {
    let _initialized = false;

    function _ensureMermaid() {
        if (_initialized) return;
        if (typeof window.mermaid === 'undefined') {
            throw new Error('mermaid not loaded (check lib/mermaid.min.js)');
        }
        window.mermaid.initialize({
            startOnLoad: false,
            securityLevel: 'loose',
            theme: 'dark',
            themeVariables: {
                background: '#0a0a0a',
                primaryColor: '#1e293b',
                primaryBorderColor: '#a78bfa',
                primaryTextColor: '#fff',
                lineColor: '#a78bfa',
                fontSize: '14px',
                nodeTextColor: '#fff',
            },
            flowchart: {
                curve: 'basis',
                nodeSpacing: 30,        // tighter vertical stacking inside a rank
                rankSpacing: 70,        // tighter horizontal spacing between ranks
                useMaxWidth: false,
                // Phase 11.U.L rev2 — htmlLabels:true caused nodes to render
                // empty/transparent. Reverted. We use plain text labels with
                // Mermaid's newline-syntax `\n` instead of <br/>.
                htmlLabels: false,
                padding: 8,
            },
        });
        _initialized = true;
    }

    function _sanitizeId(s) {
        return 'n_' + String(s).replace(/[^a-zA-Z0-9_]/g, '_');
    }

    function _truncate(s, n) {
        if (!s) return '?';
        s = String(s);
        return s.length > n ? s.slice(0, n - 1) + '…' : s;
    }

    // Phase 11.U.L — voice-first UI signal. Show which ideas are formatted
    // (SWOT, kanban, mindmap, etc.) right in the Mermaid node label so a
    // user can SEE the state without speaking. Icons are plain ASCII to
    // avoid Mermaid label-parsing issues with multi-byte emoji.
    const _FORMAT_ICONS = {
        note: '',                  // default — don't show icon
        table: '[T]',
        simple_table: '[T]',
        action_list: '[A]',
        pros_cons: '[+/-]',
        pros_cons_table: '[+/-]',
        hierarchy: '[H]',
        specs: '[S]',
        technical_specs: '[S]',
        kanban: '[K]',
        mindmap: '[M]',
        swot: '[SWOT]',
        user_story: '[US]',
        flowchart: '[F]',
    };

    function _formatBadge(node) {
        const cj = node.content_json;
        const fmt = (cj && cj.type) || node.format_type;
        if (!fmt || fmt === 'note') return '';
        const icon = _FORMAT_ICONS[fmt] || '✨';
        // Phase 11.U.L rev3 — plain space-separated badge to avoid \n
        // line-break inside the Mermaid label which sometimes breaks the
        // shape geometry. Just append the icon + abbrev.
        const tag = fmt.replace(/_/g, ' ').toUpperCase();
        return ` ${icon} ${tag}`;
    }

    function _buildGraph(nodes, edges) {
        // Phase 11.U.I rev4 — TD (top-down) instead of LR.
        // With LR + many disjoint clusters, Mermaid stacks them in vertical
        // columns (very narrow, very tall). TD puts all roots side-by-side
        // at the top with children hanging below → wider diagram that fits
        // browser viewport aspect ratios much better.
        const lines = [
            'graph TD',
            '    classDef ideaNode fill:#1e293b,stroke:#a78bfa,stroke-width:2px,color:#fff,font-size:14px,radius:8px',
            '    classDef rootNode fill:#312e81,stroke:#f59e0b,stroke-width:3px,color:#fff,font-size:16px,radius:10px',
            // Phase 11.U.M — formatted node = green border + slightly stronger fill
            '    classDef formattedNode fill:#1e293b,stroke:#10b981,stroke-width:3px,color:#fff,font-size:14px,radius:8px',
            '    classDef formattedRoot fill:#312e81,stroke:#10b981,stroke-width:3px,color:#fff,font-size:16px,radius:10px',
            '    classDef hubNode fill:transparent,stroke:transparent,color:transparent',
        ];
        const nodeIdSet = new Set(nodes.map(n => String(n.id)));

        // Build incoming + outgoing adjacency. Roots = no incoming edges.
        const incoming = new Map();
        const outgoing = new Map();
        for (const e of edges) {
            const src = String(e.from_node_id ?? e.source ?? '');
            const tgt = String(e.to_node_id ?? e.target ?? '');
            if (!nodeIdSet.has(src) || !nodeIdSet.has(tgt)) continue;
            incoming.set(tgt, (incoming.get(tgt) || 0) + 1);
            if (!outgoing.has(src)) outgoing.set(src, []);
            outgoing.get(src).push(tgt);
        }

        // Cluster: each root + its direct children (one level only).
        // Maps sanitized-id → cluster_index (so SVG-traversal can find membership).
        const clusters = [];  // [{root: origId, members: Set<sanitizedId>}]
        const nodeToCluster = new Map();  // sanitizedId → clusterIndex
        for (const n of nodes) {
            const origId = String(n.id);
            const sid = _sanitizeId(origId);
            if (!incoming.get(origId)) {
                // It's a root — make a cluster
                const members = new Set([sid]);
                const children = outgoing.get(origId) || [];
                for (const c of children) {
                    members.add(_sanitizeId(c));
                }
                const idx = clusters.length;
                clusters.push({ root: origId, members });
                for (const m of members) {
                    // First-cluster wins for nodes that are children of multiple roots
                    if (!nodeToCluster.has(m)) nodeToCluster.set(m, idx);
                }
            }
        }
        // Any node that didn't get assigned (deep grandchildren or isolated)
        // becomes its own single-node cluster so it's still dragable.
        for (const n of nodes) {
            const sid = _sanitizeId(String(n.id));
            if (!nodeToCluster.has(sid)) {
                const idx = clusters.length;
                clusters.push({ root: String(n.id), members: new Set([sid]) });
                nodeToCluster.set(sid, idx);
            }
        }

        // Collect roots for hub-wiring below + sidToNodeData for click-handler
        const rootSids = [];
        const sidToNodeData = new Map();   // sanitized-id → original node dict
        for (const n of nodes) {
            const sid = _sanitizeId(n.id);
            sidToNodeData.set(sid, n);
            const rawTitle = (n.content && (n.content.title || n.content.text)) || n.title || String(n.id);
            const title = _truncate(rawTitle, 32).replace(/["\\]/g, ' ');
            const badge = _formatBadge(n);
            const labelText = (title + badge).replace(/"/g, "'");
            lines.push(`    ${sid}["${labelText}"]`);
            const cj = n.content_json;
            const isFormatted = !!(cj && cj.type && cj.type !== 'note');
            const isRoot = !incoming.get(String(n.id));
            if (isRoot) {
                lines.push(`    class ${sid} ${isFormatted ? 'formattedRoot' : 'rootNode'}`);
                rootSids.push(sid);
            } else {
                lines.push(`    class ${sid} ${isFormatted ? 'formattedNode' : 'ideaNode'}`);
            }
        }

        let edgeCount = 0;
        const edgeList = [];   // for cluster-membership of edges
        for (const e of edges) {
            const src = String(e.from_node_id ?? e.source ?? '');
            const tgt = String(e.to_node_id ?? e.target ?? '');
            if (!nodeIdSet.has(src) || !nodeIdSet.has(tgt)) continue;
            const fid = _sanitizeId(src);
            const tid = _sanitizeId(tgt);
            lines.push(`    ${fid} --> ${tid}`);
            edgeList.push({ from: fid, to: tid });
            edgeCount++;
        }

        // Invisible hub forces all roots onto one rank. We use SOLID --> edges
        // (not dotted -.- which Mermaid sometimes ignores for layout) and
        // hide both the hub node + the hub-edges in post-render via display:none.
        if (rootSids.length > 1) {
            lines.push('    HUB[" "]');
            lines.push('    class HUB hubNode');
            for (const r of rootSids) {
                lines.push(`    HUB --> ${r}`);
            }
        }

        return { graph: lines.join('\n'), edgeCount, clusters, nodeToCluster, edgeList, sidToNodeData };
    }

    /**
     * PRIMARY ENTRY POINT — render Mermaid into the given container.
     * Replaces container.innerHTML with the SVG.
     *
     * @returns {Promise<boolean>} true on success, false on failure
     */
    async function renderMermaidIntoContainer(container, nodes, edges, opts = {}) {
        try {
            _ensureMermaid();
        } catch (err) {
            console.warn('[mermaid-layout] init failed:', err);
            return false;
        }
        if (!container || !nodes || nodes.length === 0) return false;

        const { graph, edgeCount, clusters, nodeToCluster, edgeList, sidToNodeData } = _buildGraph(nodes, edges);
        // Stash for click-handler + voice-show-format
        window._mermaidSidToNode = sidToNodeData;
        console.log(`[mermaid-layout] DIRECT render: ${nodes.length} nodes, ${edgeCount} edges, ${clusters.length} clusters`);
        // Phase 11.U.M debug — count formatted nodes + show first one
        const formatted = nodes.filter(n => n.content_json && n.content_json.type && n.content_json.type !== 'note');
        console.log(`[mermaid-layout] DEBUG formatted nodes: ${formatted.length}`);
        if (formatted.length > 0) {
            const f = formatted[0];
            console.log(`[mermaid-layout] DEBUG sample formatted: title="${f.title || f.content?.title}" content_json.type=${f.content_json.type}`);
        } else if (nodes.length > 0) {
            const n = nodes[0];
            console.log(`[mermaid-layout] DEBUG sample node keys: ${Object.keys(n).join(',')}`);
            console.log(`[mermaid-layout] DEBUG sample node.content_json=${JSON.stringify(n.content_json).slice(0,200)} format_type=${n.format_type}`);
        }

        const renderId = `_mermaid_${Date.now()}_${Math.floor(Math.random() * 1e6)}`;
        let svg = '';
        try {
            const result = await window.mermaid.render(renderId, graph);
            svg = result?.svg || '';
        } catch (err) {
            console.error('[mermaid-layout] render error:', err);
            return false;
        }
        if (!svg) return false;

        // Wipe container, insert SVG inside a pan/zoom wrapper.
        container.innerHTML = '';
        const wrap = document.createElement('div');
        wrap.className = 'mermaid-graph-wrap';
        wrap.style.cssText = [
            'position:relative',
            'width:100%',
            'height:100%',
            'overflow:hidden',
            'background:#0a0a0a',
            'cursor:grab',
        ].join(';');

        // Inner transformable layer — natural-size, scaled via CSS transform.
        // Phase 11.U.L rev7 — width:100%/height:100% caused the SVG to be
        // clipped to wrap-bounds even at scale<1 in Chromium. Auto sizing
        // lets the inner wrapper match the natural SVG geometry and the CSS
        // transform moves/scales the whole pack inside the wrap viewport.
        const inner = document.createElement('div');
        inner.className = 'mermaid-graph-inner';
        inner.style.cssText = [
            'position:absolute',
            'top:0',
            'left:0',
            'width:auto',
            'height:auto',
            'transform-origin:0 0',
            'will-change:transform',
            'overflow:visible',
        ].join(';');
        inner.innerHTML = svg;

        const svgEl = inner.querySelector('svg');
        if (svgEl) {
            // Strip any internal sizing so we can control it from CSS
            svgEl.removeAttribute('style');
            svgEl.style.display = 'block';
            svgEl.style.userSelect = 'none';

            // Phase 11.U.I rev7 — make the SVG act as an infinite canvas so
            // dragging clusters out of the initial bbox doesn't clip them.
            // CRITICAL: snapshot the original bbox to plain numbers BEFORE
            // mutating the viewBox attribute. `svgEl.viewBox.baseVal` is a
            // live SVGRect — reading .x/.width AFTER setAttribute returns the
            // new (expanded) values, which would zoom us out to nothing.
            // Phase 11.U.L rev3 — SIMPLIFIED. Don't expand viewBox or
            // width/height (the previous rev7 inflated to 25000×20000 which
            // some renderers refused to lay out, leaving the canvas blank).
            // Instead, the SVG stays at its natural size, AND we set
            // `overflow:visible` on it so any cluster dragged outside its
            // bbox is still drawn (SVG content outside viewBox renders fine
            // as long as overflow:visible).
            const vb = svgEl.viewBox?.baseVal;
            if (vb) {
                svgEl.dataset.contentX = String(vb.x);
                svgEl.dataset.contentY = String(vb.y);
                svgEl.dataset.contentW = String(vb.width);
                svgEl.dataset.contentH = String(vb.height);
                inner.dataset.svgPad = '0';   // no padding compensation needed now
            }
            svgEl.style.overflow = 'visible';

            // Hide the synthetic HUB node + its edges to the roots.
            // Mermaid IDs follow the pattern "flowchart-HUB-N" / "L_HUB_n_X_N".
            svgEl.querySelectorAll('g.node').forEach(g => {
                const id = g.getAttribute('id') || '';
                if (/^flowchart-HUB-\d+$/.test(id)) {
                    g.style.display = 'none';
                }
            });
            svgEl.querySelectorAll('path').forEach(p => {
                const id = p.getAttribute('id') || '';
                if (/^L_HUB_/.test(id) || /_HUB_\d+$/.test(id)) {
                    p.style.display = 'none';
                }
            });
        }

        // Phase 11.U.L rev6 — keep SVG at NATURAL size + use CSS transform on
        // inner to scale. width:100% scaling breaks Mermaid's <foreignObject>
        // labels in Chromium-based Electron (text/rect render off-position).
        // We compute the fit-scale here and apply it directly to the inner
        // wrapper.
        let initialScale = 1;
        let initialTx = 0;
        let initialTy = 0;
        if (svgEl) {
            const vbAttr = svgEl.getAttribute('viewBox') || '';
            const vbParts = vbAttr.split(/[\s,]+/).map(Number);
            const svgW = (vbParts.length >= 4 ? vbParts[2] : svgEl.clientWidth) || 1200;
            const svgH = (vbParts.length >= 4 ? vbParts[3] : svgEl.clientHeight) || 800;
            // SVG keeps its natural width/height from Mermaid — that's pixel-perfect
            svgEl.style.display = 'block';
            svgEl.style.userSelect = 'none';
            svgEl.style.overflow = 'visible';
            // Compute fit-to-wrap scale
            const wrapW = wrap.clientWidth || 1400;
            const wrapH = wrap.clientHeight || 800;
            const pad = 40;
            const sX = (wrapW - pad * 2) / svgW;
            const sY = (wrapH - pad * 2) / svgH;
            initialScale = Math.max(0.1, Math.min(2, Math.min(sX, sY)));
            initialTx = (wrapW - svgW * initialScale) / 2;
            initialTy = (wrapH - svgH * initialScale) / 2;
            console.log(`[mermaid-layout] rev6 fit: svg=${Math.round(svgW)}x${Math.round(svgH)} wrap=${wrapW}x${wrapH} scale=${initialScale.toFixed(3)} tx=${Math.round(initialTx)} ty=${Math.round(initialTy)}`);
        }
        // Apply the transform AFTER inner is built but BEFORE pan/zoom binding
        inner.dataset.initialScale = String(initialScale);
        inner.dataset.initialTx = String(initialTx);
        inner.dataset.initialTy = String(initialTy);
        inner.style.transform = `translate(${initialTx}px, ${initialTy}px) scale(${initialScale})`;

        wrap.appendChild(inner);
        container.appendChild(wrap);
        console.log(`[mermaid-layout] rendered to container (svg ${svgEl ? 'present' : 'missing'})`);


        // Wire up cluster-drag (per-cluster translation inside the SVG)
        // before pan/zoom so cluster-drag intercepts mousedown on nodes first.
        if (svgEl) {
            _initClusterDrag(svgEl, clusters, nodeToCluster, edgeList);
        }

        // Wire up pan/zoom + initial fit-to-viewport
        _initPanZoom(wrap, inner, svgEl);

        return true;
    }

    /**
     * Per-cluster drag — each root + its direct children translate together.
     * Edges entirely inside one cluster move with it; edges crossing clusters
     * re-route to keep their endpoints attached.
     */
    function _initClusterDrag(svgEl, clusters, nodeToCluster, edgeList) {
        // For each cluster, collect SVG <g.node> elements + edge <path>s
        // whose BOTH endpoints are in the cluster.
        const allNodeGs = svgEl.querySelectorAll('g.node');
        const sidToNodeG = new Map();
        allNodeGs.forEach(g => {
            const id = g.getAttribute('id') || '';
            // Mermaid v11 IDs: "flowchart-n_XYZ-NNN"
            const m = id.match(/flowchart-(n_[A-Za-z0-9_]+)-\d+$/);
            if (m) sidToNodeG.set(m[1], g);
        });

        // Edges: each path has data-id or id "L_<from>_<to>_<n>" or class
        // contains source/target sanitized ids. Mermaid v11 marks them with
        // classes like "edge-thickness-normal" + data-look. We rely on id.
        const edgePaths = Array.from(svgEl.querySelectorAll('path.flowchart-link, g.edgePaths path, g.edges path'));

        // Index edges by their from/to sids so we can find which cluster they belong to.
        // Mermaid v11 path id pattern: "L_n_FROM_n_TO_0" (or similar with separators).
        const edgeIndex = [];  // [{path, from, to}]
        edgePaths.forEach(p => {
            const id = p.getAttribute('id') || '';
            // Match patterns: L_<from>_<to>_<n>, with from/to potentially containing underscores.
            // Mermaid's actual format in v11 is e.g. L_n_abc_n_xyz_0
            const m = id.match(/^L_(n_[A-Za-z0-9_]+?)_(n_[A-Za-z0-9_]+?)_\d+$/);
            if (m) {
                edgeIndex.push({ path: p, from: m[1], to: m[2] });
            } else {
                // Fallback: leave it as a "shared" edge that always re-routes
                edgeIndex.push({ path: p, from: null, to: null });
            }
        });

        // Group nodes + intra-cluster edges by cluster index. Edges that cross
        // clusters stay as a global "crossing" set — they get re-routed each
        // drag instead of translated.
        const clusterGroups = clusters.map(() => ({ nodes: [], intraEdges: [] }));
        const crossingEdges = [];

        sidToNodeG.forEach((g, sid) => {
            const ci = nodeToCluster.get(sid);
            if (ci != null) clusterGroups[ci].nodes.push({ sid, g });
        });

        for (const e of edgeIndex) {
            if (!e.from || !e.to) { crossingEdges.push(e); continue; }
            const cf = nodeToCluster.get(e.from);
            const ct = nodeToCluster.get(e.to);
            if (cf === ct && cf != null) {
                clusterGroups[cf].intraEdges.push(e);
            } else {
                crossingEdges.push(e);
            }
        }

        // Per-cluster translation offset state
        const clusterTransforms = clusterGroups.map(() => ({ tx: 0, ty: 0 }));

        function applyClusterTransform(ci) {
            const { tx, ty } = clusterTransforms[ci];
            const tStr = `translate(${tx} ${ty})`;
            for (const { g } of clusterGroups[ci].nodes) {
                g.setAttribute('data-cluster-translate', tStr);
                _composeTransform(g);
            }
            for (const e of clusterGroups[ci].intraEdges) {
                e.path.setAttribute('data-cluster-translate', tStr);
                _composeTransform(e.path);
            }
            // Re-route crossing edges that touch this cluster
            for (const e of crossingEdges) {
                if (nodeToCluster.get(e.from) === ci || nodeToCluster.get(e.to) === ci) {
                    _rerouteCrossingEdge(e, sidToNodeG, clusterTransforms, nodeToCluster);
                }
            }
        }

        // Initialise: each cluster gets its own translate(0,0) so subsequent
        // drags just update it.
        clusterGroups.forEach((_, ci) => applyClusterTransform(ci));

        // Drag handlers — attach a mousedown to every node-g; on drag, move
        // the entire cluster. We bind on the node-g so panZoom (on the wrap)
        // doesn't fire when starting a drag on a node.
        let drag = null;
        const wrap = svgEl.closest('.mermaid-graph-wrap');
        sidToNodeG.forEach((g, sid) => {
            const ci = nodeToCluster.get(sid);
            if (ci == null) return;
            g.style.cursor = 'pointer';
            g.addEventListener('mousedown', (e) => {
                if (e.button !== 0) return;
                e.stopPropagation();   // don't trigger pan
                drag = {
                    ci,
                    startX: e.clientX,
                    startY: e.clientY,
                    origTx: clusterTransforms[ci].tx,
                    origTy: clusterTransforms[ci].ty,
                    moved: false,
                };
                if (wrap) wrap.setAttribute('data-dragging', 'true');
            });
            // Phase 11.U.N — click on a formatted node opens the format panel.
            // We detect "click vs drag" by checking if the mousemove moved
            // significantly. A small movement-tolerance prevents drag-cancel.
            g.addEventListener('click', (e) => {
                if (drag && drag.moved) return;   // it was a drag, not a click
                const nodeData = window._mermaidSidToNode?.get(sid);
                const cj = nodeData?.content_json;
                if (cj && cj.type && cj.type !== 'note' && typeof window.openFormatPanel === 'function') {
                    e.stopPropagation();
                    window.openFormatPanel(nodeData);
                }
            });
        });

        window.addEventListener('mousemove', (e) => {
            if (!drag) return;
            const scale = _currentPanZoomScale();
            const dx = (e.clientX - drag.startX) / scale;
            const dy = (e.clientY - drag.startY) / scale;
            // Only treat as drag if moved more than threshold (Phase 11.U.N)
            if (Math.abs(dx) > 4 || Math.abs(dy) > 4) drag.moved = true;
            clusterTransforms[drag.ci].tx = drag.origTx + dx;
            clusterTransforms[drag.ci].ty = drag.origTy + dy;
            applyClusterTransform(drag.ci);
        });

        window.addEventListener('mouseup', () => {
            if (drag && wrap) wrap.removeAttribute('data-dragging');
            drag = null;
        });

        console.log(`[mermaid-layout] cluster-drag wired: ${clusterGroups.length} clusters, ${crossingEdges.length} crossing edges`);
    }

    // Compose the existing Mermaid transform with our cluster-translate.
    // Mermaid stores its own transform on the node <g> (translate(x,y));
    // we prepend our cluster translate so the original stays correct.
    function _composeTransform(el) {
        const original = el.getAttribute('data-original-transform');
        let orig = original;
        if (orig == null) {
            orig = el.getAttribute('transform') || '';
            el.setAttribute('data-original-transform', orig);
        }
        const cluster = el.getAttribute('data-cluster-translate') || '';
        // Apply cluster first (outermost), then original — visually that's
        // "moved cluster + node-local position".
        const combined = `${cluster} ${orig}`.trim();
        el.setAttribute('transform', combined);
    }

    function _rerouteCrossingEdge(e, sidToNodeG, clusterTransforms, nodeToCluster) {
        // For crossing edges we redraw the path as a straight line between
        // current center positions of source + target nodes. We can't easily
        // reconstruct Mermaid's curved path — straight line is a reasonable
        // visual stand-in once the clusters have moved.
        const srcG = sidToNodeG.get(e.from);
        const tgtG = sidToNodeG.get(e.to);
        if (!srcG || !tgtG) return;

        const srcCenter = _gCenter(srcG, clusterTransforms[nodeToCluster.get(e.from)]);
        const tgtCenter = _gCenter(tgtG, clusterTransforms[nodeToCluster.get(e.to)]);
        e.path.setAttribute('d', `M${srcCenter.x},${srcCenter.y} L${tgtCenter.x},${tgtCenter.y}`);
        e.path.setAttribute('data-rerouted', 'true');
    }

    function _gCenter(g, clusterT) {
        // Extract translate(x,y) from data-original-transform (the Mermaid one)
        const orig = g.getAttribute('data-original-transform') || g.getAttribute('transform') || '';
        const m = orig.match(/translate\(\s*([-\d.]+)[\s,]+([-\d.]+)/);
        const baseX = m ? parseFloat(m[1]) : 0;
        const baseY = m ? parseFloat(m[2]) : 0;
        return {
            x: baseX + (clusterT?.tx || 0),
            y: baseY + (clusterT?.ty || 0),
        };
    }

    // Track current panZoom scale so drag-deltas are corrected for zoom level.
    // _initPanZoom sets _currentScale on a module-global; we read it here.
    let _currentScale = 1;
    function _currentPanZoomScale() { return _currentScale || 1; }

    function _initPanZoom(wrap, inner, svgEl) {
        const state = {
            scale: 1,
            panX: 0,
            panY: 0,
            isPanning: false,
            startX: 0,
            startY: 0,
            startPanX: 0,
            startPanY: 0,
            minScale: 0.1,
            maxScale: 5,
        };

        function applyTransform() {
            inner.style.transform = `translate(${state.panX}px, ${state.panY}px) scale(${state.scale})`;
            _currentScale = state.scale;  // expose to cluster-drag for delta correction
        }

        function fitToViewport() {
            if (!svgEl) return;
            // Phase 11.U.L rev6 — restore the initial fit-to-wrap transform
            // computed at render time (SVG at natural size + CSS scale).
            state.scale = parseFloat(inner.dataset.initialScale) || 1;
            state.panX = parseFloat(inner.dataset.initialTx) || 0;
            state.panY = parseFloat(inner.dataset.initialTy) || 0;
            applyTransform();
            console.log(`[mermaid-layout] fit-to-viewport: scale=${state.scale.toFixed(3)} pan=(${Math.round(state.panX)},${Math.round(state.panY)})`);
        }

        function _legacyFitToViewport() {
            // OLD math path — kept for reference; not called.
            let bboxX = 0, bboxY = 0, svgW = 1200, svgH = 800;
            if (svgEl.dataset.contentW) {
                bboxX = parseFloat(svgEl.dataset.contentX) || 0;
                bboxY = parseFloat(svgEl.dataset.contentY) || 0;
                svgW = parseFloat(svgEl.dataset.contentW) || 1200;
                svgH = parseFloat(svgEl.dataset.contentH) || 800;
            } else {
                let bbox;
                try { bbox = svgEl.getBBox(); } catch (_) { bbox = null; }
                bboxX = (bbox && bbox.x) || 0;
                bboxY = (bbox && bbox.y) || 0;
                svgW = (bbox && bbox.width) || svgEl.viewBox?.baseVal?.width || svgEl.clientWidth || 1200;
                svgH = (bbox && bbox.height) || svgEl.viewBox?.baseVal?.height || svgEl.clientHeight || 800;
            }
            const wrapRect = wrap.getBoundingClientRect();
            const padding = 40;

            // Phase 11.U.I rev6 — "show everything, center it" semantics.
            // User wants ALL clusters visible at once + vertically centered.
            // Trade-off: very wide diagrams render small. User can zoom in.
            //
            //   - scale = min(scaleX, scaleY) — pure fit, no min-clamp
            //   - both axes centered in viewport (no top-anchor weirdness)
            //   - zoom buttons / wheel let user enlarge
            const scaleX = (wrapRect.width - padding * 2) / svgW;
            const scaleY = (wrapRect.height - padding * 2) / svgH;
            const rawFit = Math.min(scaleX, scaleY);
            const CAP_MAX = 1.0;  // don't artificially upscale tiny graphs
            state.scale = Math.max(
                state.minScale,
                Math.min(state.maxScale, Math.min(CAP_MAX, rawFit)),
            );

            const scaledW = svgW * state.scale;
            const scaledH = svgH * state.scale;

            // Always center both axes — the user explicitly wants no empty band.
            const anchorX = (wrapRect.width - scaledW) / 2;
            const anchorY = (wrapRect.height - scaledH) / 2;
            // Account for the viewBox padding we added (rev7) so the content
            // origin (not the padded-svg-origin) lands at the anchor.
            const svgPad = parseFloat(inner.dataset.svgPad) || 0;
            state.panX = anchorX - bboxX * state.scale - svgPad * state.scale;
            state.panY = anchorY - bboxY * state.scale - svgPad * state.scale;

            applyTransform();
            console.log(`[mermaid-layout] fit-to-viewport: bbox=${Math.round(svgW)}x${Math.round(svgH)} @(${Math.round(bboxX)},${Math.round(bboxY)}) viewport=${Math.round(wrapRect.width)}x${Math.round(wrapRect.height)} rawFit=${rawFit.toFixed(3)} scale=${state.scale.toFixed(3)} pan=(${Math.round(state.panX)},${Math.round(state.panY)})`);
        }

        // Wheel zoom — zoom toward cursor position
        wrap.addEventListener('wheel', (e) => {
            e.preventDefault();
            const rect = wrap.getBoundingClientRect();
            const cx = e.clientX - rect.left;
            const cy = e.clientY - rect.top;
            const factor = e.deltaY > 0 ? 0.9 : 1.1;
            const newScale = Math.max(state.minScale, Math.min(state.maxScale, state.scale * factor));
            const ratio = newScale / state.scale;
            // Keep the point under the cursor stationary
            state.panX = cx - ratio * (cx - state.panX);
            state.panY = cy - ratio * (cy - state.panY);
            state.scale = newScale;
            applyTransform();
        }, { passive: false });

        // Drag pan
        wrap.addEventListener('mousedown', (e) => {
            if (e.button !== 0) return;
            state.isPanning = true;
            state.startX = e.clientX;
            state.startY = e.clientY;
            state.startPanX = state.panX;
            state.startPanY = state.panY;
            wrap.style.cursor = 'grabbing';
        });

        window.addEventListener('mousemove', (e) => {
            if (!state.isPanning) return;
            state.panX = state.startPanX + (e.clientX - state.startX);
            state.panY = state.startPanY + (e.clientY - state.startY);
            applyTransform();
        });

        window.addEventListener('mouseup', () => {
            if (!state.isPanning) return;
            state.isPanning = false;
            wrap.style.cursor = 'grab';
        });

        // Double-click resets to fit-to-viewport
        wrap.addEventListener('dblclick', () => {
            fitToViewport();
        });

        // Zoom controls overlay
        const controls = document.createElement('div');
        controls.className = 'mermaid-zoom-controls';
        controls.style.cssText = [
            'position:absolute',
            'bottom:12px',
            'right:12px',
            'display:flex',
            'gap:4px',
            'background:rgba(20,25,40,0.85)',
            'border:1px solid rgba(167,139,250,0.4)',
            'border-radius:6px',
            'padding:4px',
            'z-index:10',
        ].join(';');
        const mkBtn = (label, title, onClick) => {
            const b = document.createElement('button');
            b.textContent = label;
            b.title = title;
            b.style.cssText = [
                'width:28px', 'height:28px', 'background:transparent', 'color:#fff',
                'border:0', 'border-radius:4px', 'cursor:pointer', 'font-size:16px',
                'font-family:monospace', 'line-height:1',
            ].join(';');
            b.addEventListener('mouseenter', () => b.style.background = 'rgba(167,139,250,0.2)');
            b.addEventListener('mouseleave', () => b.style.background = 'transparent');
            b.addEventListener('click', onClick);
            return b;
        };
        const zoomAt = (factor) => {
            const rect = wrap.getBoundingClientRect();
            const cx = rect.width / 2;
            const cy = rect.height / 2;
            const newScale = Math.max(state.minScale, Math.min(state.maxScale, state.scale * factor));
            const ratio = newScale / state.scale;
            state.panX = cx - ratio * (cx - state.panX);
            state.panY = cy - ratio * (cy - state.panY);
            state.scale = newScale;
            applyTransform();
        };
        controls.appendChild(mkBtn('+', 'Zoom in', () => zoomAt(1.2)));
        controls.appendChild(mkBtn('−', 'Zoom out', () => zoomAt(0.8)));
        controls.appendChild(mkBtn('⟲', 'Reset (double-click also works)', fitToViewport));
        wrap.appendChild(controls);

        // Initial fit — wait one paint so getBBox returns real dimensions
        requestAnimationFrame(() => {
            requestAnimationFrame(fitToViewport);
        });
    }

    /**
     * LEGACY — kept for fallback callers that wanted positions.
     */
    async function computeMermaidLayout(nodes, edges, opts = {}) {
        // Kept stubbed for back-compat; not used in direct-render mode.
        return new Map();
    }

    window.renderMermaidIntoContainer = renderMermaidIntoContainer;
    window.computeMermaidLayout = computeMermaidLayout;
    console.log('[mermaid-layout] v11.U.I rev2 — direct-SVG mode registered');
})();
