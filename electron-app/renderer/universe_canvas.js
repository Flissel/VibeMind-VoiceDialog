/**
 * VibeMind Universe Canvas
 *
 * DOM-based canvas for displaying and editing nodes inside a bubble.
 * Nodes are HTML divs, edges are SVG lines.
 */

class UniverseCanvas {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.nodes = new Map();      // nodeId -> {element, data}
        this.edges = [];             // [{fromId, toId, element}]
        this.bubbleId = null;
        this.svgOverlay = null;
        this.nodesContainer = null;
        this.selectedNode = null;
        this.dragState = null;
        this.nextLocalId = 1000;     // For optimistic local IDs

        // Zoom and pan state
        this.scale = 1;
        this.panX = 0;
        this.panY = 0;
        this.minScale = 0.1;
        this.maxScale = 5;
        this.isPanning = false;
        this.panStartX = 0;
        this.panStartY = 0;

        // Infinite canvas virtual size (very large)
        this.canvasSize = 20000;
        this.canvasCenter = this.canvasSize / 2;

        // Node sizing constants
        this.nodeWidth = 250;
        this.nodeHeight = 150;
        this.nodeMargin = 20;

        this.init();
    }

    init() {
        if (!this.container) {
            console.error('[UniverseCanvas] Container not found!');
            return;
        }

        // Clear container
        this.container.innerHTML = '';

        // Create transform wrapper for zoom/pan
        this.transformWrapper = document.createElement('div');
        this.transformWrapper.className = 'canvas-transform-wrapper';
        this.container.appendChild(this.transformWrapper);

        // Create SVG overlay for edges FIRST (below nodes)
        // Use fixed large dimensions for infinite canvas
        this.svgOverlay = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
        this.svgOverlay.setAttribute('class', 'canvas-edges');
        this.svgOverlay.setAttribute('width', this.canvasSize);
        this.svgOverlay.setAttribute('height', this.canvasSize);
        this.svgOverlay.setAttribute('viewBox', `0 0 ${this.canvasSize} ${this.canvasSize}`);
        this.svgOverlay.style.position = 'absolute';
        this.svgOverlay.style.top = '0';
        this.svgOverlay.style.left = '0';
        this.svgOverlay.style.pointerEvents = 'none';
        this.transformWrapper.appendChild(this.svgOverlay);

        // Create nodes container inside transform wrapper
        this.nodesContainer = document.createElement('div');
        this.nodesContainer.className = 'canvas-nodes';
        this.nodesContainer.style.width = this.canvasSize + 'px';
        this.nodesContainer.style.height = this.canvasSize + 'px';
        this.nodesContainer.style.position = 'relative';
        this.transformWrapper.appendChild(this.nodesContainer);

        // Create toolbar (outside transform wrapper)
        this.createToolbar();

        // Create zoom controls
        this.createZoomControls();

        // Bind methods for event listeners
        this.onDrag = this.onDrag.bind(this);
        this.endDrag = this.endDrag.bind(this);
        this.onWheel = this.onWheel.bind(this);
        this.onPanStart = this.onPanStart.bind(this);
        this.onPan = this.onPan.bind(this);
        this.onPanEnd = this.onPanEnd.bind(this);

        // Add zoom/pan event listeners
        this.container.addEventListener('wheel', this.onWheel, { passive: false });
        this.container.addEventListener('mousedown', this.onPanStart);
        document.addEventListener('mousemove', this.onPan);
        document.addEventListener('mouseup', this.onPanEnd);

        // Center the view initially
        this.centerView();

        console.log('[UniverseCanvas] Initialized with infinite canvas support');
    }

    /**
     * Center the view on the canvas origin (where new nodes appear)
     */
    centerView() {
        const rect = this.container.getBoundingClientRect();
        // Pan to show the center area of the canvas
        this.panX = rect.width / 2 - this.canvasCenter * this.scale;
        this.panY = rect.height / 2 - this.canvasCenter * this.scale;
        this.updateTransform();
    }

    createToolbar() {
        const toolbar = document.createElement('div');
        toolbar.className = 'canvas-toolbar';
        toolbar.innerHTML = `
            <div class="toolbar-section">
                <span class="toolbar-label">Create</span>
                <button data-action="add-note" title="Add Note">+ Note</button>
                <button data-action="add-link" title="Add Link">+ Link</button>
                <button data-action="add-image" title="Add Image">+ Image</button>
            </div>
            <div class="toolbar-section">
                <span class="toolbar-label">Format</span>
                <button data-action="format-table" title="Format as Table">Table</button>
                <button data-action="format-action-list" title="Format as Action List">Actions</button>
                <button data-action="format-pros-cons" title="Pros & Cons">Pro/Con</button>
                <button data-action="format-hierarchy" title="Hierarchy">Hierarchy</button>
                <button data-action="format-specs" title="Technical Specs">Specs</button>
            </div>
            <div class="toolbar-section">
                <span class="toolbar-label">AI Tools</span>
                <button data-action="summarize" title="Summarize">Summary</button>
                <button data-action="whitepaper" title="Generate White Paper">White Paper</button>
                <button data-action="expand" title="Expand Ideas">Expand</button>
                <button data-action="explain" title="Explain Idea">Explain</button>
                <button data-action="auto-link" title="Auto-Link Ideas">Auto Link</button>
                <button data-action="explore" title="Deep Exploration">Explore</button>
            </div>
            <div class="toolbar-section">
                <span class="toolbar-label">Layout</span>
                <button data-action="auto-layout" title="Auto Layout (Force-Directed)">Auto Layout</button>
            </div>
        `;

        toolbar.addEventListener('click', (e) => {
            const btn = e.target.closest('button');
            if (!btn) return;
            const action = btn.dataset.action;

            // Create actions
            if (action === 'add-note') this.addNode('note');
            if (action === 'add-link') this.addNode('link');
            if (action === 'add-image') this.addNode('image');

            // Layout actions
            if (action === 'auto-layout') {
                this.autoLayout();
                return;
            }

            // Tool actions - dispatch to Python backend via IPC
            const toolActions = {
                'format-table': 'idea.format_table',
                'format-action-list': 'idea.format_action_list',
                'format-pros-cons': 'idea.format_pros_cons',
                'format-hierarchy': 'idea.format_hierarchy',
                'format-specs': 'idea.format_specs',
                'summarize': 'idea.summarize',
                'whitepaper': 'idea.whitepaper',
                'expand': 'idea.expand',
                'explain': 'idea.explain',
                'auto-link': 'idea.auto_link',
                'explore': 'idea.explore.start',
            };

            if (toolActions[action]) {
                const eventType = toolActions[action];
                const payload = {};

                // If a node is selected, pass its name
                if (this.selectedNode) {
                    const nodeInfo = this.nodes.get(this.selectedNode);
                    if (nodeInfo) {
                        payload.idea_name = nodeInfo.data?.title || '';
                        payload.name = payload.idea_name;
                    }
                }

                // Send to Python backend
                if (window.vibemind?.sendToolAction) {
                    window.vibemind.sendToolAction(eventType, payload);
                } else {
                    console.log('[Toolbar] Tool action:', eventType, payload);
                    // Fallback: show transcript
                    const transcript = document.getElementById('transcript-content');
                    if (transcript) {
                        const msg = document.createElement('div');
                        msg.className = 'transcript-msg';
                        msg.textContent = `[Tool] ${eventType} triggered`;
                        transcript.appendChild(msg);
                    }
                }
            }
        });

        this.container.appendChild(toolbar);
    }

    loadBubble(bubbleId) {
        this.bubbleId = bubbleId;
        this.clear();
        console.log('[UniverseCanvas] Loading bubble:', bubbleId);
        // Backend will send nodes via entered_bubble message
    }

    loadNodes(nodes, edges = []) {
        console.log('[UniverseCanvas] Loading nodes:', nodes?.length || 0, 'edges:', edges?.length || 0);
        this._showBanner(`loadNodes: ${nodes?.length || 0} nodes, ${edges?.length || 0} edges`, '#666');

        if (!nodes || !Array.isArray(nodes) || nodes.length === 0) {
            this._stopMermaidPoll();
            this.clear();
            return;
        }

        // Phase 11.U.I rev2 — MERMAID DIRECT-RENDER MODE.
        // Rather than positioning our DOM nodes via fCoSE/dagre output, we
        // hand the whole container over to Mermaid and render its SVG straight
        // — 1:1 Rowboat AgentGraphVisualizer pattern. Read-only (no drag/edit),
        // but the radial-hub dagre layout is finally correct.
        if (typeof window.renderMermaidIntoContainer === 'function' && typeof window.mermaid !== 'undefined') {
            this._showBanner(`Rendering Mermaid (${nodes.length} nodes / ${edges.length} edges)...`, '#37c');
            this._loadGen = (this._loadGen || 0) + 1;
            const gen = this._loadGen;
            window.renderMermaidIntoContainer(this.container, nodes, edges).then(ok => {
                if (gen !== this._loadGen) return;
                if (ok) {
                    this._showBanner(`Mermaid rendered ${nodes.length} nodes`, '#3a7');
                    // Phase 11.U.N rev5 — refresh any open format-card with fresh content_json
                    if (typeof window.refreshOpenFormatPanel === 'function') {
                        try { window.refreshOpenFormatPanel(); } catch (_) {}
                    }
                    this._mermaidMode = true;
                    this.nodes.clear();  // legacy state cleanup
                    this.edges = [];
                    // Phase 11.U.I rev8 — Supabase Realtime broadcasts for
                    // canvas_nodes/canvas_edges INSERT don't reliably reach
                    // the renderer (channel-subscribe is timing-sensitive
                    // and the MCP-tool-write-path may bypass voice-process
                    // broadcast). Fall back to a 5-second poll while in
                    // mermaid mode so user-driven creates show up promptly.
                    this._startMermaidPoll();
                } else {
                    this._showBanner('Mermaid render failed, falling back to DOM canvas', '#c80');
                    this._loadNodesFallback(nodes, edges);
                }
            }).catch(err => {
                if (gen !== this._loadGen) return;
                console.warn('[UniverseCanvas] mermaid render exception:', err);
                this._showBanner('Mermaid exception: ' + err.message, '#c33');
                this._loadNodesFallback(nodes, edges);
            });
            return;
        }

        // Fallback path (mermaid not loaded) — old fCoSE pipeline.
        this._loadNodesFallback(nodes, edges);
    }

    _loadNodesFallback(nodes, edges) {
        // Re-init DOM canvas if we were in mermaid mode previously
        if (this._mermaidMode) {
            this._stopMermaidPoll();
            this.container.innerHTML = '';
            this.init();
            this._mermaidMode = false;
        }
        this.clear();

        this._loadGen = (this._loadGen || 0) + 1;
        const gen = this._loadGen;
        const needs = this._layoutNeeded(nodes);
        if (needs) {
            this._runAutoLayout(nodes, edges).then(positions => {
                if (gen !== this._loadGen) {
                    console.log(`[UniverseCanvas] dropping stale layout (gen ${gen} != ${this._loadGen})`);
                    return;
                }
                this._applyPositionsAndRender(nodes, edges, positions);
            }).catch(err => {
                if (gen !== this._loadGen) return;
                console.warn('[UniverseCanvas] auto-layout failed:', err);
                this._applyPositionsAndRender(nodes, edges, null);
            });
        } else {
            this._applyPositionsAndRender(nodes, edges, null);
        }
    }

    _layoutNeeded(nodes) {
        // Check 1: any node missing a position
        for (const n of nodes) {
            const px = n.position?.x ?? n.x;
            const py = n.position?.y ?? n.y;
            if (px == null || py == null) return true;
        }
        // Check 2: bounding box too small (all clustered at default 100,100)
        // or any two nodes overlap (centre-to-centre < 200px)
        for (let i = 0; i < nodes.length; i++) {
            const a = nodes[i];
            const ax = a.position?.x ?? a.x;
            const ay = a.position?.y ?? a.y;
            for (let j = i + 1; j < nodes.length; j++) {
                const b = nodes[j];
                const bx = b.position?.x ?? b.x;
                const by = b.position?.y ?? b.y;
                if (Math.abs(ax - bx) < 240 && Math.abs(ay - by) < 110) {
                    return true;
                }
            }
        }
        return false;
    }

    _showBanner(msg, color = '#3a7') {
        // Phase 11.U.G — Visible status banner because DevTools sometimes
        // refuses to open. Shows the cytoscape-layout pipeline state right
        // at the top of the screen for 5 seconds.
        try {
            let b = document.getElementById('cy-debug-banner');
            if (!b) {
                b = document.createElement('div');
                b.id = 'cy-debug-banner';
                b.style.cssText = 'position:fixed;top:8px;left:50%;transform:translateX(-50%);' +
                    'z-index:99999;padding:6px 14px;font:12px monospace;color:#fff;' +
                    'border-radius:4px;pointer-events:none;box-shadow:0 2px 8px rgba(0,0,0,.5)';
                document.body.appendChild(b);
            }
            b.style.background = color;
            b.textContent = msg;
            clearTimeout(this.__bannerTimer);
            this.__bannerTimer = setTimeout(() => {
                if (b && b.parentNode) b.parentNode.removeChild(b);
            }, 5000);
        } catch (_) { /* ignore */ }
    }

    async _runAutoLayout(nodes, edges) {
        // Phase 11.U.I — PRIMARY: Mermaid `graph LR` (dagre tree-layout, Rowboat-style).
        // Falls back to Cytoscape fCoSE if Mermaid is unavailable. Mermaid produces
        // the hierarchical-radial look the user wants; fCoSE was making organic
        // clusters which looked wrong here.
        if (typeof window.computeMermaidLayout === 'function' && typeof window.mermaid !== 'undefined') {
            this._showBanner(`Running Mermaid on ${nodes.length} nodes / ${edges.length} edges...`, '#37c');
            console.log('[UniverseCanvas] running mermaid auto-layout (primary)...');
            const t0 = performance.now();
            try {
                const positions = await window.computeMermaidLayout(nodes, edges);
                const dt = (performance.now() - t0).toFixed(0);
                if (positions && positions.size > 0) {
                    this._showBanner(`Mermaid done: ${positions.size} positions in ${dt}ms`, '#3a7');
                    return positions;
                }
                console.warn('[UniverseCanvas] mermaid returned empty positions — falling back to fCoSE');
                this._showBanner('Mermaid returned empty positions — using fCoSE fallback', '#c80');
            } catch (err) {
                console.warn('[UniverseCanvas] mermaid layout failed:', err);
                this._showBanner('Mermaid failed: ' + err.message + ' — using fCoSE', '#c80');
            }
        } else {
            console.log('[UniverseCanvas] mermaid not loaded — using fCoSE fallback');
        }

        // Fallback: Cytoscape fCoSE (Phase 11.U.G)
        if (typeof window.cytoscape === 'undefined') {
            this._showBanner('cytoscape UMD not loaded (lib/cytoscape.umd.js missing?)', '#c33');
            console.warn('[UniverseCanvas] cytoscape UMD not loaded');
            return null;
        }
        if (typeof window.cytoscapeFcose === 'undefined') {
            this._showBanner('cytoscape-fcose not loaded', '#c33');
            return null;
        }
        if (typeof window.computeCytoscapeLayout !== 'function') {
            this._showBanner('computeCytoscapeLayout not registered', '#c33');
            return null;
        }
        this._showBanner(`Running fCoSE on ${nodes.length} nodes / ${edges.length} edges...`, '#37c');
        console.log('[UniverseCanvas] running cytoscape auto-layout...');
        const t0 = performance.now();
        try {
            const positions = await window.computeCytoscapeLayout(nodes, edges, {
                nodeWidth: 240, nodeHeight: 100,
                idealEdgeLength: 220, nodeSeparation: 80,
                quality: 'default',
            });
            const dt = (performance.now() - t0).toFixed(0);
            console.log(`[UniverseCanvas] layout computed in ${dt}ms`);
            this._showBanner(`fCoSE done: ${positions.size} positions in ${dt}ms`, '#3a7');
            return positions;
        } catch (err) {
            this._showBanner('fCoSE error: ' + err.message, '#c33');
            console.error('[UniverseCanvas] layout error:', err);
            return null;
        }
    }

    _applyPositionsAndRender(nodes, edges, positions) {
        // Overwrite positions with computed ones (when available)
        if (positions) {
            for (const n of nodes) {
                const p = positions.get(String(n.id));
                if (p) {
                    n.position = { x: p.x, y: p.y };
                }
            }
            // Persist computed positions back via IPC so they survive reload
            this._persistPositions(positions);
        }

        // Phase 11.U.H — render nodes first, edges second, then a final
        // redrawEdges pass to lock positions in. Edges keep their data in
        // this.edges even if endpoint nodes are temporarily missing.
        // Debug: log input positions before render
        if (nodes.length > 0) {
            const sample = nodes.slice(0, 3).map(n => `(${n.position?.x},${n.position?.y})`).join(' ');
            const allPos = nodes.map(n => ({x: n.position?.x ?? 0, y: n.position?.y ?? 0}));
            const minX = Math.min(...allPos.map(p => p.x));
            const maxX = Math.max(...allPos.map(p => p.x));
            const minY = Math.min(...allPos.map(p => p.y));
            const maxY = Math.max(...allPos.map(p => p.y));
            console.log(`[UniverseCanvas] _applyPositionsAndRender: nodes=${nodes.length} bbox=(${minX},${minY})→(${maxX},${maxY}) spread=${maxX-minX}x${maxY-minY} samples=${sample}`);
        }
        nodes.forEach(node => this.renderNode(node));
        // Phase 11.U.H DEBUG — log type of stored node-ids vs edge endpoints
        if (nodes.length > 0 && edges && edges.length > 0) {
            const firstNodeKey = Array.from(this.nodes.keys())[0];
            const firstEdge = edges[0];
            console.log(`[UniverseCanvas] DEBUG: nodes-map first key=${firstNodeKey} (typeof ${typeof firstNodeKey}); first-edge from=${firstEdge.from_node_id} (typeof ${typeof firstEdge.from_node_id}) to=${firstEdge.to_node_id} (typeof ${typeof firstEdge.to_node_id})`);
        }
        if (edges && Array.isArray(edges)) {
            edges.forEach(edge => this.createEdge(
                edge.from_node_id, edge.to_node_id,
                { label: edge.edge_type || 'related' },
            ));
        }
        // Recompute edge positions now that all node DOM-elements are in place
        this.redrawEdges();

        // Phase 11.U.H — Critical: fit the new layout into the visible
        // viewport. Without this, the freshly-rendered nodes sit at
        // (canvas-coord = 10050+), invisible because no pan/scale was set.
        // centerOnNodes() handles both pan AND auto-fit scale.
        if (positions || nodes.length > 0) {
            // Use a microtask so layout reflow + offsetWidth measurements
            // pick up the actual rendered widths
            requestAnimationFrame(() => {
                this.centerOnNodes();
                // One more pass after centering so edges follow the new transform
                this.redrawEdges();
            });
        }
    }

    async _persistPositions(positions) {
        // Phase 11.U.H — IDs are DB-UUIDs directly (post-H.1). Use map-keys
        // straight as PATCH targets. Throttle to 6 in-flight at once to
        // avoid ERR_INSUFFICIENT_RESOURCES.
        const SUPA = 'http://localhost:54321/rest/v1';
        const tasks = [];
        positions.forEach((pos, nodeId) => {
            // nodeId is already a Supabase UUID string after H.1
            if (!nodeId || typeof nodeId !== 'string' || nodeId.length < 4) return;
            tasks.push({ dbId: nodeId, pos });
        });
        const BATCH = 6;
        for (let i = 0; i < tasks.length; i += BATCH) {
            const slice = tasks.slice(i, i + BATCH);
            await Promise.allSettled(slice.map(t => {
                return fetch(`${SUPA}/canvas_nodes?id=eq.${encodeURIComponent(t.dbId)}`, {
                    method: 'PATCH',
                    headers: { 'apikey': 'anon', 'Content-Type': 'application/json' },
                    body: JSON.stringify({ x: t.pos.x, y: t.pos.y }),
                });
            }));
        }
        console.log(`[UniverseCanvas] persisted ${tasks.length} positions to Supabase`);
    }

    clear() {
        this.nodes.forEach(node => node.element.remove());
        this.nodes.clear();
        this.edges.forEach(edge => edge.element.remove());
        this.edges = [];
        this.selectedNode = null;
    }

    createZoomControls() {
        const controls = document.createElement('div');
        controls.className = 'zoom-controls';
        controls.innerHTML = `
            <button data-action="zoom-in" title="Zoom In">+</button>
            <span class="zoom-level">100%</span>
            <button data-action="zoom-out" title="Zoom Out">−</button>
            <button data-action="zoom-reset" title="Reset View">⟲</button>
        `;

        controls.addEventListener('click', (e) => {
            const action = e.target.dataset.action;
            if (action === 'zoom-in') this.zoom(1.2);
            if (action === 'zoom-out') this.zoom(0.8);
            if (action === 'zoom-reset') this.resetView();
        });

        this.zoomLevelDisplay = controls.querySelector('.zoom-level');
        this.container.appendChild(controls);
    }

    // ========================================================================
    // NODE RENDERING
    // ========================================================================

    renderNode(data) {
        const el = document.createElement('div');
        el.className = 'canvas-node';
        el.dataset.nodeId = data.id;
        el.dataset.nodeType = data.type || 'note';
        
        // Position nodes relative to canvas center
        const x = (data.position?.x || 100) + this.canvasCenter;
        const y = (data.position?.y || 100) + this.canvasCenter;
        el.style.left = x + 'px';
        el.style.top = y + 'px';

        // Header with drag handle and delete button
        const formatType = data.content_json?.type || data.format_type || null;
        const header = document.createElement('div');
        header.className = 'node-header';

        const iconSpan = document.createElement('span');
        iconSpan.className = 'node-type-icon';
        iconSpan.textContent = this.getTypeIcon(data.type, formatType);

        const titleSpan = document.createElement('span');
        titleSpan.className = 'node-title';
        titleSpan.textContent = this.getNodeTitle(data);

        const deleteBtn = document.createElement('button');
        deleteBtn.className = 'node-delete';
        deleteBtn.title = 'Delete';
        deleteBtn.textContent = '×';

        header.appendChild(iconSpan);
        header.appendChild(titleSpan);
        header.appendChild(deleteBtn);
        el.appendChild(header);

        // Content area (type-specific)
        const content = document.createElement('div');
        content.className = 'node-content';
        content.innerHTML = this.getNodeContent(data);
        el.appendChild(content);

        // Event handlers
        header.addEventListener('mousedown', (e) => {
            if (!e.target.classList.contains('node-delete')) {
                this.startDrag(e, data.id);
            }
        });

        deleteBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            this.deleteNode(data.id);
        });

        el.addEventListener('click', (e) => {
            if (!e.target.classList.contains('node-delete')) {
                this.selectNode(data.id);
            }
        });

        // Handle content changes for notes with auto-resize
        const textarea = content.querySelector('textarea');
        if (textarea) {
            this.setupAutoResize(textarea);
            
            textarea.addEventListener('input', (e) => {
                this.updateNodeContent(data.id, { text: e.target.value });
            });
        }

        this.nodesContainer.appendChild(el);
        this.nodes.set(data.id, { element: el, data: data });

        // Render structured content (content_json) if available from DB
        console.log('[UniverseCanvas] renderNode content_json:', data.id, data.content_json?.type, 'RichRenderer:', !!window.RichContentRenderer);
        if (data.content_json && data.content_json.type) {
            // Set format type for CSS targeting
            el.dataset.formatType = data.content_json.type;

            // Use RichContentRenderer if available
            if (window.RichContentRenderer) {
                const renderer = new window.RichContentRenderer(content);
                const contentType = data.content_json.type;
                if (renderer.contentTypes && renderer.contentTypes[contentType]) {
                    // Clear default content safely using DOM methods
                    while (content.firstChild) {
                        content.removeChild(content.firstChild);
                    }
                    const rendered = renderer.contentTypes[contentType](data.content_json);
                    if (rendered) {
                        rendered.classList.add('structured-content');
                        content.appendChild(rendered);
                    }
                }
            }
        }

        return el;
    }

    getTypeIcon(type, formatType) {
        // Check format type first (structured content type)
        const ft = formatType || type;
        switch (ft) {
            case 'action_list': return '☐';
            case 'table': return '📊';
            case 'simple_table': return '📊';
            case 'pros_cons_table': return '⚖️';
            case 'pros_cons': return '⚖️';
            case 'hierarchy': return '🌳';
            case 'kanban': return '📋';
            case 'mindmap': return '🧠';
            case 'swot': return '🔲';
            case 'user_story': return '👤';
            case 'flowchart': return '🔀';
            case 'technical_specs': return '🔧';
            case 'specs': return '🔧';
            default: break;
        }
        switch (type) {
            case 'note': return '✏️';
            case 'link': return '🔗';
            case 'image': return '🖼️';
            case 'idea': return '💡';
            case 'project': return '📁';
            case 'whitepaper': return '📄';
            case 'feature': return '⚙️';
            case 'feature_doc': return '📋';
            case 'feature_index': return '📑';
            default: return '📄';
        }
    }

    getNodeTitle(data) {
        if (data.content?.title) return data.content.title;
        switch (data.type) {
            case 'note': return 'Note';
            case 'link': return 'Link';
            case 'image': return 'Image';
            case 'whitepaper': return 'White Paper';
            case 'feature': return 'Feature';
            case 'feature_doc': return 'Feature Doc';
            case 'feature_index': return 'Feature Index';
            default: return data.type || 'Item';
        }
    }

    getNodeContent(data) {
        switch (data.type) {
            case 'note':
                return `<textarea placeholder="Enter your note...">${data.content?.text || ''}</textarea>`;
            case 'link':
                const url = data.content?.url || 'https://';
                return `
                    <input type="url" class="link-input" value="${url}" placeholder="https://...">
                    <a href="${url}" target="_blank" class="link-preview">${url}</a>
                `;
            case 'image':
                const imgUrl = data.content?.url || '';
                return imgUrl
                    ? `<img src="${imgUrl}" alt="${data.content?.caption || 'Image'}">`
                    : `<div class="image-placeholder">Drop image or paste URL</div>`;
            case 'whitepaper':
            case 'feature_doc':
            case 'feature_index':
                const wpText = data.content?.text || '';
                const preview = wpText.length > 1000000 ? wpText.slice(0, 1000000) + '...' : wpText;
                return `<div class="whitepaper-preview">${this.escapeHtml(preview)}</div>`;
            case 'feature':
                return `<div class="feature-content">${this.escapeHtml(data.content?.text || '')}</div>`;
            default:
                return `<div class="node-text">${data.content?.text || ''}</div>`;
        }
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // ========================================================================
    // DRAG AND DROP
    // ========================================================================

    startDrag(e, nodeId) {
        const node = this.nodes.get(nodeId);
        if (!node) return;

        e.preventDefault();
        node.element.classList.add('dragging');

        this.dragState = {
            nodeId: nodeId,
            startX: e.clientX,
            startY: e.clientY,
            nodeStartX: parseInt(node.element.style.left) || 0,
            nodeStartY: parseInt(node.element.style.top) || 0
        };

        document.addEventListener('mousemove', this.onDrag);
        document.addEventListener('mouseup', this.endDrag);
    }

    onDrag(e) {
        if (!this.dragState) return;

        const node = this.nodes.get(this.dragState.nodeId);
        if (!node) return;

        // FIX: Divide by scale to convert screen pixels to canvas coordinates
        const dx = (e.clientX - this.dragState.startX) / this.scale;
        const dy = (e.clientY - this.dragState.startY) / this.scale;
        const newX = Math.max(0, this.dragState.nodeStartX + dx);
        const newY = Math.max(0, this.dragState.nodeStartY + dy);

        node.element.style.left = newX + 'px';
        node.element.style.top = newY + 'px';

        this.redrawEdges();
    }

    endDrag(e) {
        if (!this.dragState) return;

        const node = this.nodes.get(this.dragState.nodeId);
        if (node) {
            node.element.classList.remove('dragging');

            // Phase 11.U.H — style.left/top INCLUDE canvasCenter offset.
            // The stored data.position must be canvas-relative (without
            // center) so renderNode can re-add canvasCenter on the next
            // load without drifting outward.
            const rawX = (parseInt(node.element.style.left) || 0) - this.canvasCenter;
            const rawY = (parseInt(node.element.style.top) || 0) - this.canvasCenter;
            const newPosition = { x: rawX, y: rawY };
            node.data.position = newPosition;

            // Sync with Python backend (will eventually PATCH Supabase via
            // _persistPositions OR via the update_canvas_node IPC path)
            if (window.vibemind) {
                window.vibemind.updateCanvasNode(
                    this.bubbleId,
                    this.dragState.nodeId,
                    { position: newPosition }
                );
            }
        }

        this.dragState = null;
        document.removeEventListener('mousemove', this.onDrag);
        document.removeEventListener('mouseup', this.endDrag);
    }

    // ========================================================================
    // ZOOM AND PAN
    // ========================================================================

    onWheel(e) {
        e.preventDefault();
        const delta = e.deltaY > 0 ? 0.9 : 1.1;
        this.zoom(delta, e.clientX, e.clientY);
    }

    zoom(factor, centerX = null, centerY = null) {
        const newScale = Math.min(this.maxScale, Math.max(this.minScale, this.scale * factor));
        
        if (newScale === this.scale) return;

        // Zoom toward cursor position if provided
        if (centerX !== null && centerY !== null) {
            const rect = this.container.getBoundingClientRect();
            const mouseX = centerX - rect.left;
            const mouseY = centerY - rect.top;

            // Adjust pan to keep point under cursor
            this.panX = mouseX - (mouseX - this.panX) * (newScale / this.scale);
            this.panY = mouseY - (mouseY - this.panY) * (newScale / this.scale);
        }

        this.scale = newScale;
        this.updateTransform();
    }

    onPanStart(e) {
        // Only pan on middle mouse button or when clicking empty space
        if (e.button === 1 || (e.button === 0 && e.target === this.container || e.target === this.transformWrapper)) {
            this.isPanning = true;
            this.panStartX = e.clientX - this.panX;
            this.panStartY = e.clientY - this.panY;
            this.container.classList.add('panning');
            e.preventDefault();
        }
    }

    onPan(e) {
        if (!this.isPanning) return;
        this.panX = e.clientX - this.panStartX;
        this.panY = e.clientY - this.panStartY;
        this.updateTransform();
    }

    onPanEnd(e) {
        if (this.isPanning) {
            this.isPanning = false;
            this.container.classList.remove('panning');
        }
    }

    updateTransform() {
        this.transformWrapper.style.transform = 
            `translate(${this.panX}px, ${this.panY}px) scale(${this.scale})`;
        
        if (this.zoomLevelDisplay) {
            this.zoomLevelDisplay.textContent = `${Math.round(this.scale * 100)}%`;
        }
    }

    resetView() {
        this.scale = 1;
        this.centerView();
    }

    // ========================================================================
    // EDGE RENDERING (SVG)
    // ========================================================================

    // Phase 11.U.H — Edge data lives in this.edges regardless of node-render state.
    // createEdge() always records the edge; redrawEdges() looks up DOM elements via
    // [data-node-id="<uuid>"] selector each time. If a node isn't currently rendered,
    // the edge is simply skipped this render pass — but stays in this.edges so a
    // later load/relayout can re-draw it.
    createEdge(fromNodeId, toNodeId, opts = {}) {
        // De-dup
        const exists = this.edges.some(e =>
            (e.fromId === fromNodeId && e.toId === toNodeId) ||
            (e.fromId === toNodeId && e.toId === fromNodeId)
        );
        if (exists) return;

        const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
        line.classList.add('canvas-edge');
        line.dataset.from = String(fromNodeId);
        line.dataset.to = String(toNodeId);
        if (opts.label) line.dataset.label = opts.label;
        this.svgOverlay.appendChild(line);

        const edge = {
            fromId: fromNodeId,
            toId: toNodeId,
            label: opts.label || 'related',
            element: line,
        };
        this.edges.push(edge);
        this._positionEdge(edge);  // initial position (may be hidden if nodes missing)
    }

    _findNodeElement(nodeId) {
        // Phase 11.U.H — first try the in-memory map (fast path), then
        // fall back to DOM querySelector for nodes that may have been
        // rendered but not yet inserted in the map (race-safe).
        const node = this.nodes.get(nodeId);
        if (node && node.element) return node.element;
        // querySelectorAll-escape the id (UUIDs are safe but be defensive)
        const safe = String(nodeId).replace(/"/g, '\\"');
        return this.nodesContainer.querySelector(`[data-node-id="${safe}"]`);
    }

    _positionEdge(edge) {
        const fromEl = this._findNodeElement(edge.fromId);
        const toEl = this._findNodeElement(edge.toId);
        if (!fromEl || !toEl) {
            // Hide the line until both endpoints exist
            // Phase 11.U.H — log mismatched ids so we can spot type bugs
            if (!this.__edgeWarnLogged) {
                this.__edgeWarnLogged = 0;
            }
            if (this.__edgeWarnLogged < 5) {
                console.warn(`[UniverseCanvas] edge endpoint(s) not found: fromId=${edge.fromId} (typeof ${typeof edge.fromId}) fromEl=${!!fromEl} toId=${edge.toId} (typeof ${typeof edge.toId}) toEl=${!!toEl}. Map sample key=${Array.from(this.nodes.keys()).slice(0,1)[0]} (typeof ${typeof Array.from(this.nodes.keys())[0]})`);
                this.__edgeWarnLogged++;
            }
            edge.element.setAttribute('x1', 0);
            edge.element.setAttribute('y1', 0);
            edge.element.setAttribute('x2', 0);
            edge.element.setAttribute('y2', 0);
            edge.element.style.visibility = 'hidden';
            return;
        }
        edge.element.style.visibility = '';
        const fromX = parseFloat(fromEl.style.left) || 0;
        const fromY = parseFloat(fromEl.style.top) || 0;
        const toX = parseFloat(toEl.style.left) || 0;
        const toY = parseFloat(toEl.style.top) || 0;
        const fromW = fromEl.offsetWidth || this.nodeWidth || 240;
        const fromH = fromEl.offsetHeight || this.nodeHeight || 100;
        const toW = toEl.offsetWidth || this.nodeWidth || 240;
        const toH = toEl.offsetHeight || this.nodeHeight || 100;
        edge.element.setAttribute('x1', fromX + fromW / 2);
        edge.element.setAttribute('y1', fromY + fromH / 2);
        edge.element.setAttribute('x2', toX + toW / 2);
        edge.element.setAttribute('y2', toY + toH / 2);
    }

    // Back-compat shim — old callers used updateEdgePosition(line, fromEl, toEl)
    updateEdgePosition(line, fromEl, toEl) {
        const fromX = parseFloat(fromEl.style.left) || 0;
        const fromY = parseFloat(fromEl.style.top) || 0;
        const toX = parseFloat(toEl.style.left) || 0;
        const toY = parseFloat(toEl.style.top) || 0;
        const fromW = fromEl.offsetWidth || this.nodeWidth || 240;
        const fromH = fromEl.offsetHeight || this.nodeHeight || 100;
        const toW = toEl.offsetWidth || this.nodeWidth || 240;
        const toH = toEl.offsetHeight || this.nodeHeight || 100;
        line.setAttribute('x1', fromX + fromW / 2);
        line.setAttribute('y1', fromY + fromH / 2);
        line.setAttribute('x2', toX + toW / 2);
        line.setAttribute('y2', toY + toH / 2);
    }

    redrawEdges() {
        this.edges.forEach(edge => this._positionEdge(edge));
    }

    // ========================================================================
    // COLLISION DETECTION FOR NODE PLACEMENT
    // ========================================================================

    /**
     * Find a free position for a new node that doesn't overlap existing nodes
     */
    findFreePosition(preferredX = null, preferredY = null) {
        // Positions are relative to canvas center (0,0 is center)
        const startX = preferredX ?? 100;
        const startY = preferredY ?? 100;
        
        // Get all existing node positions (convert from canvas coords to local coords)
        const existingPositions = Array.from(this.nodes.values()).map(n => ({
            x: (parseInt(n.element.style.left) || 0) - this.canvasCenter,
            y: (parseInt(n.element.style.top) || 0) - this.canvasCenter,
            width: n.element.offsetWidth || this.nodeWidth,
            height: n.element.offsetHeight || this.nodeHeight
        }));

        // Check if position collides with any existing node
        const collides = (x, y) => {
            for (const pos of existingPositions) {
                if (x < pos.x + pos.width + this.nodeMargin &&
                    x + this.nodeWidth + this.nodeMargin > pos.x &&
                    y < pos.y + pos.height + this.nodeMargin &&
                    y + this.nodeHeight + this.nodeMargin > pos.y) {
                    return true;
                }
            }
            return false;
        };

        // If preferred position is free, use it
        if (!collides(startX, startY)) {
            return { x: startX, y: startY };
        }

        // Spiral search for free position
        const stepSize = this.nodeWidth + this.nodeMargin;
        let radius = 1;
        
        while (radius < 20) { // Max 20 spiral steps
            for (let angle = 0; angle < Math.PI * 2; angle += Math.PI / 4) {
                const x = startX + Math.cos(angle) * radius * stepSize;
                const y = startY + Math.sin(angle) * radius * stepSize;
                
                if (x >= 0 && y >= 0 && !collides(x, y)) {
                    return { x: Math.round(x), y: Math.round(y) };
                }
            }
            radius++;
        }

        // Fallback: place below all existing nodes
        const maxY = existingPositions.reduce((max, p) => Math.max(max, p.y + p.height), 0);
        return { x: startX, y: maxY + this.nodeMargin };
    }

    // ========================================================================
    // FORCE-DIRECTED AUTO LAYOUT
    // ========================================================================

    /**
     * Auto-layout nodes using a force-directed algorithm.
     * Connected nodes attract, all nodes repel, edges act as springs.
     */
    /**
     * Phase 11.U.G — Cytoscape (fCoSE) based auto-layout.
     * Replaces the old hand-rolled force simulation. fCoSE is what
     * Rowboat uses and produces clean radial-cluster layouts without
     * overlap, using real DOM box dimensions.
     */
    async autoLayout() {
        const nodeIds = Array.from(this.nodes.keys());
        if (nodeIds.length < 2) return;

        // Phase 11.U.H — sample up to 10 nodes for an average box size.
        // CSS allows .canvas-node width to range 200-350 px depending on
        // title length; a single sample can mislead the layout.
        let boxW = 260, boxH = 110;
        try {
            const samples = nodeIds.slice(0, Math.min(10, nodeIds.length))
                .map(id => this.nodes.get(id).element.getBoundingClientRect())
                .filter(r => r.width > 0 && r.height > 0);
            if (samples.length > 0) {
                const maxW = Math.max(...samples.map(r => r.width));
                const maxH = Math.max(...samples.map(r => r.height));
                boxW = maxW;
                boxH = maxH;
            }
        } catch (_) { /* keep defaults */ }
        // Generous breathing space — fCoSE doesn't know about CSS box-shadow / hover
        boxW = Math.max(240, boxW + 40);
        boxH = Math.max(110, boxH + 30);

        // Convert edges to fCoSE format
        const edgeList = this.edges.map(e => ({
            from_node_id: e.fromId, to_node_id: e.toId,
        }));
        const nodeList = nodeIds.map(id => ({ id }));

        this._showBanner(`Auto Layout (fCoSE): ${nodeIds.length} nodes, ${edgeList.length} edges...`, '#37c');

        // Run Cytoscape fCoSE if available, fall back to old simulation otherwise
        let positions;
        if (typeof window.computeCytoscapeLayout === 'function') {
            try {
                positions = await window.computeCytoscapeLayout(nodeList, edgeList, {
                    nodeWidth: boxW, nodeHeight: boxH,
                    idealEdgeLength: Math.max(280, boxW + 80),
                    nodeSeparation: Math.max(80, boxW * 0.4),
                    quality: 'proof', // 'proof' = best quality, slower
                });
                this._showBanner(`fCoSE done: ${positions.size} positioned`, '#3a7');
            } catch (err) {
                this._showBanner('fCoSE error: ' + err.message, '#c33');
                console.error('[UniverseCanvas] fCoSE error:', err);
                return;
            }
        } else {
            this._showBanner('cytoscape not loaded', '#c33');
            console.warn('[UniverseCanvas] window.computeCytoscapeLayout missing');
            return;
        }

        // Apply final positions with animation
        nodeIds.forEach(id => {
            const node = this.nodes.get(id);
            const p = positions.get(String(id));
            if (!p) return;
            const el = node.element;
            el.style.transition = 'left 0.5s ease, top 0.5s ease';
            // canvasCenter is added because renderNode does `+ this.canvasCenter`
            el.style.left = (p.x + this.canvasCenter) + 'px';
            el.style.top = (p.y + this.canvasCenter) + 'px';
            // Also update data so future redraw/persist sees them
            if (node.data) {
                node.data.position = { x: p.x, y: p.y };
            }
            setTimeout(() => { el.style.transition = ''; }, 600);
        });

        // Persist to Supabase so the layout survives reload
        this._persistPositions(positions);

        // Phase 11.U.H — redraw edges throughout the 500ms transition so
        // they animate along with the nodes. Final pass at 600ms locks in
        // the resting positions.
        for (const t of [0, 100, 200, 300, 400, 500, 600]) {
            setTimeout(() => this.redrawEdges(), t);
        }
        this.centerOnNodes();
    }

    /**
     * Center the viewport on all nodes.
     */
    centerOnNodes() {
        if (this.nodes.size === 0) return;

        let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
        this.nodes.forEach(node => {
            const x = parseInt(node.element.style.left) || 0;
            const y = parseInt(node.element.style.top) || 0;
            minX = Math.min(minX, x);
            minY = Math.min(minY, y);
            maxX = Math.max(maxX, x + (node.element.offsetWidth || this.nodeWidth));
            maxY = Math.max(maxY, y + (node.element.offsetHeight || this.nodeHeight));
        });

        const centerX = (minX + maxX) / 2;
        const centerY = (minY + maxY) / 2;
        const rect = this.container.getBoundingClientRect();
        const bboxW = maxX - minX;
        const bboxH = maxY - minY;

        // Phase 11.U.H — auto-fit-to-viewport: compute scale so the entire
        // bbox fits with 10% margin around it. Clamp to [minScale, maxScale].
        // Without this, large-spread fCoSE outputs render tiny because the
        // default scale is 1 and the bbox blows past the viewport.
        if (bboxW > 0 && bboxH > 0) {
            const margin = 0.85; // 15% padding
            const scaleX = (rect.width * margin) / bboxW;
            const scaleY = (rect.height * margin) / bboxH;
            const newScale = Math.min(scaleX, scaleY);
            this.scale = Math.min(
                this.maxScale || 3,
                Math.max(this.minScale || 0.05, newScale),
            );
            console.log(`[UniverseCanvas] auto-fit: bbox ${Math.round(bboxW)}x${Math.round(bboxH)} → scale ${this.scale.toFixed(3)}`);
            if (this.zoomLevelDisplay) {
                this.zoomLevelDisplay.textContent = `${Math.round(this.scale * 100)}%`;
            }
        }

        this.panX = rect.width / 2 - centerX * this.scale;
        this.panY = rect.height / 2 - centerY * this.scale;
        this.updateTransform();
    }

    // ========================================================================
    // AUTO-RESIZE TEXTAREA
    // ========================================================================

    /**
     * Auto-resize a textarea to fit its content
     */
    autoResizeTextarea(textarea) {
        if (!textarea) return;
        
        // Reset height to get accurate scrollHeight
        textarea.style.height = 'auto';
        
        // Set new height based on content
        const newHeight = Math.max(60, Math.min(400, textarea.scrollHeight));
        textarea.style.height = newHeight + 'px';
    }

    /**
     * Setup auto-resize for a textarea
     */
    setupAutoResize(textarea) {
        if (!textarea) return;
        
        // Initial resize
        this.autoResizeTextarea(textarea);
        
        // Resize on input
        textarea.addEventListener('input', () => {
            this.autoResizeTextarea(textarea);
        });
        
        // Resize on focus (in case content was set programmatically)
        textarea.addEventListener('focus', () => {
            this.autoResizeTextarea(textarea);
        });
    }

    // ========================================================================
    // CRUD OPERATIONS
    // ========================================================================

    addNode(type, position = null) {
        if (!this.bubbleId) {
            console.warn('[UniverseCanvas] No bubble loaded');
            return;
        }

        // Use collision detection to find free position
        const freePosition = this.findFreePosition(
            position?.x ?? 100 + Math.random() * 100,
            position?.y ?? 100 + Math.random() * 100
        );

        const nodeData = {
            type: type,
            position: freePosition,
            content: this.getDefaultContent(type)
        };

        // Optimistic local render
        const localId = this.nextLocalId++;
        const tempNode = { ...nodeData, id: localId };
        this.renderNode(tempNode);

        // Send to backend
        if (window.vibemind) {
            window.vibemind.addCanvasNode(this.bubbleId, nodeData);
        }
    }

    getDefaultContent(type) {
        switch (type) {
            case 'note': return { title: 'New Note', text: '' };
            case 'link': return { title: 'New Link', url: 'https://' };
            case 'image': return { caption: 'Image', url: '' };
            default: return {};
        }
    }

    updateNodeContent(nodeId, contentUpdates) {
        const node = this.nodes.get(nodeId);
        if (!node) return;

        // Merge content updates
        node.data.content = { ...node.data.content, ...contentUpdates };

        // Debounced sync with backend (don't spam on every keystroke)
        clearTimeout(node.updateTimeout);
        node.updateTimeout = setTimeout(() => {
            if (window.vibemind) {
                window.vibemind.updateCanvasNode(
                    this.bubbleId,
                    nodeId,
                    { content: node.data.content }
                );
            }
        }, 500);
    }

    deleteNode(nodeId) {
        const node = this.nodes.get(nodeId);
        if (node) {
            node.element.remove();
            this.nodes.delete(nodeId);
        }

        // Remove connected edges
        this.edges = this.edges.filter(edge => {
            if (edge.fromId === nodeId || edge.toId === nodeId) {
                edge.element.remove();
                return false;
            }
            return true;
        });

        // Sync with backend
        if (window.vibemind) {
            window.vibemind.deleteCanvasNode(this.bubbleId, nodeId);
        }
    }

    selectNode(nodeId) {
        // Deselect previous
        if (this.selectedNode) {
            const prev = this.nodes.get(this.selectedNode);
            if (prev) prev.element.classList.remove('selected');
        }

        // Select new
        this.selectedNode = nodeId;
        const node = this.nodes.get(nodeId);
        if (node) {
            node.element.classList.add('selected');
        }
    }

    // ========================================================================
    // BACKEND MESSAGE HANDLERS
    // ========================================================================

    /**
     * Find a node by ID, supporting both integer and UUID string keys.
     * This is needed because Python tools send UUIDs while Electron uses integers.
     */
    findNodeById(nodeId) {
        // First try direct lookup (fastest)
        if (this.nodes.has(nodeId)) {
            return this.nodes.get(nodeId);
        }
        
        // Try string conversion (in case nodeId is number but key is string or vice versa)
        const nodeIdStr = String(nodeId);
        const nodeIdNum = parseInt(nodeId, 10);
        
        if (this.nodes.has(nodeIdStr)) {
            return this.nodes.get(nodeIdStr);
        }
        if (!isNaN(nodeIdNum) && this.nodes.has(nodeIdNum)) {
            return this.nodes.get(nodeIdNum);
        }
        
        // Search through all nodes for UUID match (for Python tool events)
        // This is O(n) but necessary for cross-system compatibility
        for (const [key, nodeData] of this.nodes) {
            // Check if the node's data contains a db_id or uuid field matching
            if (nodeData.data && nodeData.data.db_id === nodeId) {
                return nodeData;
            }
            // Check if the nodeId contains this node's key (partial match for UUID prefix)
            if (typeof nodeId === 'string' && nodeId.length > 8) {
                // Compare short prefix as fallback
                const prefix = nodeId.substring(0, 8);
                if (String(key).includes(prefix) || (nodeData.data && String(nodeData.data.id).includes(prefix))) {
                    console.log('[UniverseCanvas] Found node by UUID prefix:', nodeId, '->', key);
                    return nodeData;
                }
            }
        }
        
        return null;
    }

    onNodeAdded(node) {
        // In Mermaid mode, re-render the whole diagram (cheap for small graphs)
        if (this._mermaidMode) { this._scheduleMermaidRefresh(); return; }
        // If we already have a temp node, replace it
        // Otherwise just render
        this.renderNode(node);
    }

    _scheduleMermaidRefresh() {
        // Debounce — rapid backend bursts (e.g. 10× node_added within 1s)
        // shouldn't trigger 10 enterBubble round-trips.
        if (this._mermaidRefreshTimer) return;
        this._mermaidRefreshTimer = setTimeout(() => {
            this._mermaidRefreshTimer = null;
            this.refresh();
        }, 300);
    }

    _startMermaidPoll() {
        if (this._mermaidPollTimer) return;
        // 5-second poll: re-fetches the bubble via enterBubble. The voice
        // backend's enter_bubble reads canvas_nodes + canvas_edges fresh
        // from Supabase, so we always see the latest state. Skipped if
        // the user is mid-cluster-drag (state.isPanning on the SVG wrap
        // OR the per-cluster drag is active).
        this._mermaidPollTimer = setInterval(() => {
            // Skip if user is actively dragging — don't yank the diagram
            // out from under them
            const dragging = !!document.querySelector('.mermaid-graph-wrap')?.matches('[data-dragging="true"]');
            if (dragging) return;
            this.refresh();
        }, 5000);
        console.log('[UniverseCanvas] mermaid auto-poll started (5s interval)');
    }

    _stopMermaidPoll() {
        if (this._mermaidPollTimer) {
            clearInterval(this._mermaidPollTimer);
            this._mermaidPollTimer = null;
            console.log('[UniverseCanvas] mermaid auto-poll stopped');
        }
    }

    onNodeUpdated(nodeId, updates) {
        if (this._mermaidMode) { this._scheduleMermaidRefresh(); return; }
        // Use findNodeById for cross-system ID compatibility
        const node = this.findNodeById(nodeId);
        if (!node) {
            console.warn('[UniverseCanvas] Node not found for update:', nodeId);
            return;
        }

        // Ensure content is always an object (fix "Cannot create property on string" error)
        if (typeof node.data.content !== 'object' || node.data.content === null) {
            // Convert string content to object format
            const oldContent = node.data.content;
            node.data.content = { text: typeof oldContent === 'string' ? oldContent : '' };
        }

        // Update data model
        Object.assign(node.data, updates);

        // Update DOM position
        // Phase 11.U.H rev4 — renderNode() positions elements at
        // (data.position.x + canvasCenter, ...). Updates coming via realtime
        // carry RAW DB coords, so we must re-add canvasCenter here. Without
        // this, positions like (1115, 950) end up at the top-left of the
        // 20000×20000 canvas — looks like all items collapsed into a corner.
        if (updates.position) {
            const x = (updates.position.x || 100) + this.canvasCenter;
            const y = (updates.position.y || 100) + this.canvasCenter;
            node.element.style.left = x + 'px';
            node.element.style.top = y + 'px';
            // Keep node.data.position in raw-DB shape (consistent with how
            // renderNode reads data.position.x for the next render). Object.assign
            // above already stamped updates.position into node.data — which is
            // the right shape (raw, no center-offset).
            this.redrawEdges();
        }

        // Update DOM title
        if (updates.title) {
            const titleEl = node.element.querySelector('.node-title');
            if (titleEl) {
                titleEl.textContent = updates.title;
            }
            node.data.content.title = updates.title;
        }

        // Update DOM content - handle both string and object formats
        if (updates.content !== undefined) {
            let newText = '';
            let newTitle = null;

            if (typeof updates.content === 'string') {
                // Content is a string directly
                newText = updates.content;
            } else if (typeof updates.content === 'object' && updates.content !== null) {
                // Content is an object with text/title properties
                newText = updates.content.text || updates.content.content || '';
                newTitle = updates.content.title;
            }

            // Update textarea if present
            const textarea = node.element.querySelector('textarea');
            if (textarea && newText !== textarea.value) {
                textarea.value = newText;
            }

            // Update node-text div if present (for non-note types)
            const textDiv = node.element.querySelector('.node-text');
            if (textDiv) {
                textDiv.textContent = newText;
            }

            // Store in data model
            node.data.content.text = newText;

            // Update title if provided in content object
            if (newTitle) {
                const titleEl = node.element.querySelector('.node-title');
                if (titleEl) {
                    titleEl.textContent = newTitle;
                }
                node.data.content.title = newTitle;
            }
        }

        // Flash animation for visual feedback
        node.element.classList.add('updated');
        setTimeout(() => node.element.classList.remove('updated'), 500);

        console.log('[UniverseCanvas] Node updated:', nodeId, updates);
    }

    onNodeDeleted(nodeId) {
        if (this._mermaidMode) { this._scheduleMermaidRefresh(); return; }
        const node = this.nodes.get(nodeId);
        if (node) {
            node.element.remove();
            this.nodes.delete(nodeId);
        }
    }

    /**
     * Handle structured content update (tables, formatted content)
     * Called when format_idea_as_table or similar tools update node content
     */
    onNodeStructuredUpdate(nodeId, structuredContent) {
        const node = this.findNodeById(nodeId);
        if (!node) {
            console.warn('[UniverseCanvas] Node not found for structured update:', nodeId);
            return;
        }

        console.log('[UniverseCanvas] Structured content update:', nodeId, structuredContent);

        // Find or create the content container
        let contentContainer = node.element.querySelector('.node-body, .node-content');
        if (!contentContainer) {
            contentContainer = node.element;
        }

        // Check if we have a RichContentRenderer available
        if (window.RichContentRenderer) {
            const renderer = new window.RichContentRenderer(contentContainer);
            const contentType = structuredContent.type;

            // Use RichContentRenderer for all supported content types
            if (renderer.contentTypes && renderer.contentTypes[contentType]) {
                // Clear existing structured content
                const existing = contentContainer.querySelector('.structured-content, .rich-content, .table-content, .action-list');
                if (existing) existing.remove();

                const rendered = renderer.contentTypes[contentType](structuredContent);
                if (rendered) {
                    rendered.classList.add('structured-content');
                    const titleEl = contentContainer.querySelector('.node-title');
                    if (titleEl && titleEl.nextSibling) {
                        contentContainer.insertBefore(rendered, titleEl.nextSibling);
                    } else {
                        contentContainer.appendChild(rendered);
                    }
                }
                console.log(`[UniverseCanvas] Rendered ${contentType} via RichContentRenderer`);
            } else if (structuredContent.type === 'table' || (structuredContent.headers && structuredContent.rows)) {
                // Fallback for table-like data
                const existingTable = contentContainer.querySelector('.table-content');
                if (existingTable) existingTable.remove();

                const tableElement = renderer.renderTable({
                    headers: structuredContent.headers || structuredContent.columns,
                    rows: structuredContent.rows || structuredContent.data
                });

                const titleEl = contentContainer.querySelector('.node-title');
                if (titleEl && titleEl.nextSibling) {
                    contentContainer.insertBefore(tableElement, titleEl.nextSibling);
                } else {
                    contentContainer.appendChild(tableElement);
                }
            } else {
                // Generic fallback - render as formatted text
                const textDiv = contentContainer.querySelector('.node-text, textarea');
                if (textDiv) {
                    textDiv.textContent = JSON.stringify(structuredContent, null, 2);
                }
            }
        } else {
            // Fallback: Simple table rendering without RichContentRenderer
            if (structuredContent.headers && structuredContent.rows) {
                const existingTable = contentContainer.querySelector('table');
                if (existingTable) {
                    existingTable.remove();
                }

                const table = document.createElement('table');
                table.className = 'structured-table';
                table.style.cssText = 'width:100%;border-collapse:collapse;font-size:12px;margin-top:8px;';

                // Header
                const thead = document.createElement('thead');
                const headerRow = document.createElement('tr');
                structuredContent.headers.forEach(h => {
                    const th = document.createElement('th');
                    th.textContent = h;
                    th.style.cssText = 'border:1px solid #444;padding:4px 6px;background:#2a2a2a;text-align:left;';
                    headerRow.appendChild(th);
                });
                thead.appendChild(headerRow);
                table.appendChild(thead);

                // Rows
                const tbody = document.createElement('tbody');
                structuredContent.rows.forEach(row => {
                    const tr = document.createElement('tr');
                    row.forEach(cell => {
                        const td = document.createElement('td');
                        td.textContent = cell;
                        td.style.cssText = 'border:1px solid #444;padding:4px 6px;';
                        tr.appendChild(td);
                    });
                    tbody.appendChild(tr);
                });
                table.appendChild(tbody);

                contentContainer.appendChild(table);
            }
        }

        // Set format type as data attribute for CSS targeting
        if (structuredContent.type) {
            node.element.dataset.formatType = structuredContent.type;
            // Update icon to match new format
            const iconEl = node.element.querySelector('.node-type-icon');
            if (iconEl) {
                iconEl.textContent = this.getTypeIcon(node.data.type, structuredContent.type);
            }
        }

        // Store structured content in data model
        if (typeof node.data.content !== 'object') {
            node.data.content = { text: node.data.content || '' };
        }
        node.data.content.structured = structuredContent;

        // Flash animation for visual feedback
        node.element.classList.add('updated');
        setTimeout(() => node.element.classList.remove('updated'), 500);
    }

    /**
     * Handle edge added from backend (voice command linking)
     * BUG FIX: Visual feedback when linking ideas
     */
    onEdgeAdded(edge) {
        if (this._mermaidMode) { this._scheduleMermaidRefresh(); return; }
        const fromNodeId = edge.from_node_id;
        const toNodeId = edge.to_node_id;

        console.log('[UniverseCanvas] Edge added:', fromNodeId, '->', toNodeId);

        // Check if edge already exists
        const exists = this.edges.some(e =>
            (e.fromId === fromNodeId && e.toId === toNodeId) ||
            (e.fromId === toNodeId && e.toId === fromNodeId)
        );
        
        if (!exists) {
            this.createEdge(fromNodeId, toNodeId);
            
            // Flash connected nodes for visual feedback
            const fromNode = this.nodes.get(fromNodeId);
            const toNode = this.nodes.get(toNodeId);
            if (fromNode) {
                fromNode.element.classList.add('linked');
                setTimeout(() => fromNode.element.classList.remove('linked'), 1000);
            }
            if (toNode) {
                toNode.element.classList.add('linked');
                setTimeout(() => toNode.element.classList.remove('linked'), 1000);
            }
        }
    }

    onEdgeRemoved(payload) {
        if (this._mermaidMode) { this._scheduleMermaidRefresh(); return; }
        const edgeId = payload && (payload.edge_id || (payload.edge && payload.edge.id));
        const fromId = payload && (payload.from_node_id || (payload.edge && payload.edge.from_node_id));
        const toId = payload && (payload.to_node_id || (payload.edge && payload.edge.to_node_id));
        const before = this.edges.length;
        this.edges = this.edges.filter(e => {
            if (edgeId && e.id === edgeId) { if (e.element) e.element.remove(); return false; }
            if (fromId && toId && ((e.fromId === fromId && e.toId === toId) || (e.fromId === toId && e.toId === fromId))) {
                if (e.element) e.element.remove();
                return false;
            }
            return true;
        });
        console.log(`[UniverseCanvas] Edge removed (${before - this.edges.length} dropped)`);
    }

    /**
     * Refresh canvas - request nodes from backend again.
     * Called when voice tools modify the canvas.
     */
    refresh() {
        if (this.bubbleId && window.vibemind) {
            // Re-request the current bubble (triggers entered_bubble with fresh data)
            window.vibemind.enterBubble(this.bubbleId);
        }
    }

    /**
     * Get node position in local coordinates (relative to canvas center)
     */
    getNodeLocalPosition(element) {
        const canvasX = parseInt(element.style.left) || 0;
        const canvasY = parseInt(element.style.top) || 0;
        return {
            x: canvasX - this.canvasCenter,
            y: canvasY - this.canvasCenter
        };
    }

    /**
     * Convert local position to canvas position
     */
    localToCanvas(x, y) {
        return {
            x: x + this.canvasCenter,
            y: y + this.canvasCenter
        };
    }

    /**
     * Update node title elements to show voice index numbers.
     * Called when ideas_listed message is received.
     * @param {Array} indexedIdeas - Array of {index, id, title} objects
     */
    updateNodeIndices(indexedIdeas) {
        if (!indexedIdeas || !Array.isArray(indexedIdeas)) {
            console.warn('[UniverseCanvas] updateNodeIndices: Invalid data');
            return;
        }

        console.log('[UniverseCanvas] Updating node indices for', indexedIdeas.length, 'ideas');

        // Create a map of id -> index for quick lookup
        const indexMap = new Map();
        indexedIdeas.forEach(idea => {
            indexMap.set(idea.id, idea.index);
        });

        // Update each node's title display
        this.nodes.forEach((nodeInfo, nodeId) => {
            const voiceIndex = indexMap.get(nodeId);
            if (voiceIndex !== undefined) {
                const titleEl = nodeInfo.element.querySelector('.node-title');
                if (titleEl) {
                    const originalTitle = nodeInfo.data.content?.title || this.getNodeTitle(nodeInfo.data);
                    // Add index badge before the title
                    titleEl.innerHTML = `<span class="voice-index">${voiceIndex}</span> ${originalTitle}`;
                    // Store the index in data for later reference
                    nodeInfo.data.voice_index = voiceIndex;
                }
            }
        });
    }

    /**
     * Clear voice index badges from all nodes.
     */
    clearNodeIndices() {
        this.nodes.forEach((nodeInfo) => {
            const titleEl = nodeInfo.element.querySelector('.node-title');
            if (titleEl && nodeInfo.data.voice_index !== undefined) {
                const originalTitle = nodeInfo.data.content?.title || this.getNodeTitle(nodeInfo.data);
                titleEl.textContent = originalTitle;
                delete nodeInfo.data.voice_index;
            }
        });
    }
}

// Global instance (created when entering a bubble)
window.UniverseCanvas = UniverseCanvas;
console.log('[UniverseCanvas] Module loaded');
