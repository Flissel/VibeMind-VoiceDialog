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
        this.clear();

        if (nodes && Array.isArray(nodes)) {
            nodes.forEach(node => this.renderNode(node));
        }

        if (edges && Array.isArray(edges)) {
            edges.forEach(edge => this.createEdge(edge.from_node_id, edge.to_node_id));
        }
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
        const header = document.createElement('div');
        header.className = 'node-header';
        header.innerHTML = `
            <span class="node-type-icon">${this.getTypeIcon(data.type)}</span>
            <span class="node-title">${this.getNodeTitle(data)}</span>
            <button class="node-delete" title="Delete">×</button>
        `;
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

        header.querySelector('.node-delete').addEventListener('click', (e) => {
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

        return el;
    }

    getTypeIcon(type) {
        switch (type) {
            case 'note': return '📝';
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

            // Save new position to backend
            const newPosition = {
                x: parseInt(node.element.style.left),
                y: parseInt(node.element.style.top)
            };
            node.data.position = newPosition;

            // Sync with Python backend
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

    createEdge(fromNodeId, toNodeId) {
        const fromNode = this.nodes.get(fromNodeId);
        const toNode = this.nodes.get(toNodeId);
        if (!fromNode || !toNode) return;

        const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
        line.classList.add('canvas-edge');
        line.dataset.from = fromNodeId;
        line.dataset.to = toNodeId;

        this.updateEdgePosition(line, fromNode.element, toNode.element);
        this.svgOverlay.appendChild(line);
        this.edges.push({ fromId: fromNodeId, toId: toNodeId, element: line });
    }

    updateEdgePosition(line, fromEl, toEl) {
        // FIX: Use canvas coordinates directly instead of getBoundingClientRect
        // getBoundingClientRect returns screen coordinates which are affected by zoom/transform
        // We need canvas coordinates (style.left/top) which are unaffected
        
        const fromX = parseInt(fromEl.style.left) || 0;
        const fromY = parseInt(fromEl.style.top) || 0;
        const toX = parseInt(toEl.style.left) || 0;
        const toY = parseInt(toEl.style.top) || 0;
        
        // Get node dimensions for center point calculation
        const fromWidth = fromEl.offsetWidth || this.nodeWidth;
        const fromHeight = fromEl.offsetHeight || this.nodeHeight;
        const toWidth = toEl.offsetWidth || this.nodeWidth;
        const toHeight = toEl.offsetHeight || this.nodeHeight;
        
        // Calculate center points in canvas coordinates
        const x1 = fromX + fromWidth / 2;
        const y1 = fromY + fromHeight / 2;
        const x2 = toX + toWidth / 2;
        const y2 = toY + toHeight / 2;

        line.setAttribute('x1', x1);
        line.setAttribute('y1', y1);
        line.setAttribute('x2', x2);
        line.setAttribute('y2', y2);
    }

    redrawEdges() {
        this.edges.forEach(edge => {
            const fromNode = this.nodes.get(edge.fromId);
            const toNode = this.nodes.get(edge.toId);
            if (fromNode && toNode) {
                this.updateEdgePosition(edge.element, fromNode.element, toNode.element);
            }
        });
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
    autoLayout() {
        const nodeIds = Array.from(this.nodes.keys());
        if (nodeIds.length < 2) return;

        // Build adjacency set for quick lookup
        const adjacency = new Map();
        nodeIds.forEach(id => adjacency.set(id, new Set()));
        this.edges.forEach(edge => {
            if (adjacency.has(edge.fromId) && adjacency.has(edge.toId)) {
                adjacency.get(edge.fromId).add(edge.toId);
                adjacency.get(edge.toId).add(edge.fromId);
            }
        });

        // Initialize positions from current node positions (canvas-relative)
        const positions = new Map();
        nodeIds.forEach(id => {
            const node = this.nodes.get(id);
            const el = node.element;
            positions.set(id, {
                x: (parseInt(el.style.left) || this.canvasCenter) - this.canvasCenter,
                y: (parseInt(el.style.top) || this.canvasCenter) - this.canvasCenter,
                vx: 0,
                vy: 0
            });
        });

        // Layout parameters
        const REPULSION = 80000;      // Repulsion force between all nodes
        const ATTRACTION = 0.005;     // Spring constant for connected nodes
        const IDEAL_LENGTH = 350;     // Ideal edge length
        const DAMPING = 0.85;         // Velocity damping
        const CENTER_PULL = 0.01;     // Pull towards center
        const ITERATIONS = 200;       // Simulation steps

        for (let iter = 0; iter < ITERATIONS; iter++) {
            const cooling = 1 - (iter / ITERATIONS) * 0.8; // Slow down over time

            // Calculate forces for each node
            nodeIds.forEach(id => {
                const p = positions.get(id);
                let fx = 0, fy = 0;

                // Repulsion from all other nodes (Coulomb's law)
                nodeIds.forEach(otherId => {
                    if (otherId === id) return;
                    const o = positions.get(otherId);
                    const dx = p.x - o.x;
                    const dy = p.y - o.y;
                    const dist = Math.max(Math.sqrt(dx * dx + dy * dy), 1);
                    const force = REPULSION / (dist * dist);
                    fx += (dx / dist) * force;
                    fy += (dy / dist) * force;
                });

                // Attraction along edges (Hooke's law)
                const neighbors = adjacency.get(id);
                if (neighbors) {
                    neighbors.forEach(neighborId => {
                        const o = positions.get(neighborId);
                        const dx = o.x - p.x;
                        const dy = o.y - p.y;
                        const dist = Math.sqrt(dx * dx + dy * dy);
                        const displacement = dist - IDEAL_LENGTH;
                        const force = ATTRACTION * displacement;
                        fx += (dx / Math.max(dist, 1)) * force;
                        fy += (dy / Math.max(dist, 1)) * force;
                    });
                }

                // Center gravity (prevent drift)
                fx -= p.x * CENTER_PULL;
                fy -= p.y * CENTER_PULL;

                // Update velocity with damping and cooling
                p.vx = (p.vx + fx) * DAMPING * cooling;
                p.vy = (p.vy + fy) * DAMPING * cooling;
            });

            // Apply velocities
            nodeIds.forEach(id => {
                const p = positions.get(id);
                p.x += p.vx;
                p.y += p.vy;
            });
        }

        // Apply final positions with animation
        nodeIds.forEach(id => {
            const node = this.nodes.get(id);
            const p = positions.get(id);
            const el = node.element;
            el.style.transition = 'left 0.5s ease, top 0.5s ease';
            el.style.left = (Math.round(p.x) + this.canvasCenter) + 'px';
            el.style.top = (Math.round(p.y) + this.canvasCenter) + 'px';

            // Remove transition after animation
            setTimeout(() => { el.style.transition = ''; }, 600);
        });

        // Redraw edges after layout
        setTimeout(() => this.redrawEdges(), 50);
        // Redraw again after animation completes
        setTimeout(() => this.redrawEdges(), 550);

        // Center the view on the laid-out nodes
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
        // If we already have a temp node, replace it
        // Otherwise just render
        this.renderNode(node);
    }

    onNodeUpdated(nodeId, updates) {
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
        if (updates.position) {
            node.element.style.left = updates.position.x + 'px';
            node.element.style.top = updates.position.y + 'px';
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
