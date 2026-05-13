/**
 * Cytoscape-based auto-layout for canvas nodes.
 *
 * Loads cytoscape + cytoscape-fcose from UMD bundles in lib/.
 * Exposes window.computeCytoscapeLayout(nodes, edges, opts).
 *
 * Returns a Promise<Map<nodeId, {x,y}>>.
 *
 * Why Cytoscape: Rowboat uses it with fCoSE for the same radial-cluster
 * layout we want — production-tuned, never produces overlap, knows about
 * real rendered box sizes.
 */
(function () {
    let _registered = false;

    function _ensureFcose() {
        if (_registered) return;
        if (typeof cytoscape === 'undefined') {
            throw new Error('cytoscape not loaded (check lib/cytoscape.umd.js)');
        }
        if (typeof cytoscapeFcose === 'undefined') {
            throw new Error('cytoscape-fcose not loaded (check lib/cytoscape-fcose.js)');
        }
        cytoscape.use(cytoscapeFcose);
        _registered = true;
    }

    /**
     * @param {Array<{id}>} nodes
     * @param {Array<{from_node_id, to_node_id}>} edges
     * @param {object} opts
     *   - nodeWidth, nodeHeight: real DOM box-size (default 240x100)
     *   - idealEdgeLength: target spring length (default 220)
     *   - nodeSeparation: extra gap (default 80)
     *   - quality: 'draft'|'default'|'proof' (default 'default')
     *
     * @returns {Promise<Map<string, {x, y}>>}
     */
    async function computeCytoscapeLayout(nodes, edges, opts = {}) {
        _ensureFcose();
        if (!nodes || nodes.length === 0) return new Map();

        const W = opts.nodeWidth ?? 260;
        const H = opts.nodeHeight ?? 110;
        const IDEAL = opts.idealEdgeLength ?? 600;  // V3 — much bigger so 43 nodes spread out properly
        const SEP = opts.nodeSeparation ?? 150;     // V3 — wider min-gap
        const QUALITY = opts.quality ?? 'default';

        const elements = [];
        for (const n of nodes) {
            elements.push({ group: 'nodes', data: { id: String(n.id) } });
        }
        for (const e of edges) {
            const src = String(e.from_node_id ?? e.source ?? '');
            const tgt = String(e.to_node_id ?? e.target ?? '');
            if (!src || !tgt) continue;
            elements.push({
                group: 'edges',
                data: { id: `e-${src}-${tgt}`, source: src, target: tgt },
            });
        }

        const cy = cytoscape({
            headless: true,
            elements,
            styleEnabled: false,
        });

        cy.nodes().forEach((n) => {
            n.style({ width: W, height: H });
        });

        return new Promise((resolve) => {
            // Phase 11.U.H — radial config: stronger gravity centers the
            // graph + repulsion spreads items apart + longer ideal edges
            // produce the "hub + spokes" look from Rowboat.
            // Phase 11.U.H — radial config tuned for headless cytoscape.
            // nodeRepulsion needs to be LARGE because Cytoscape's force-units
            // are independent of screen pixels — too small produces tiny dense
            // clusters. fCoSE default is 4500; we go to 50000 for clear spread.
            // V3 — much higher repulsion + much lower edge stiffness so the
            // graph SPREADS rather than compresses to a tiny cluster.
            const layout = cy.layout({
                name: 'fcose',
                quality: QUALITY,
                randomize: true,
                animate: false,
                nodeSeparation: SEP,            // V3 default 150
                idealEdgeLength: IDEAL,         // V3 default 600
                nodeRepulsion: 200000,          // V3 — 4x higher
                edgeElasticity: 0.02,           // V3 — 5x softer springs
                gravity: 0.05,                  // V3 — barely pull to center
                gravityRange: 4.0,
                gravityCompound: 0.5,
                gravityRangeCompound: 2.0,
                numIter: 8000,
                tile: true,
                tilingPaddingVertical: 40,
                tilingPaddingHorizontal: 40,
                packComponents: true,
                nodeDimensionsIncludeLabels: false,
                stop: () => {
                    const positions = new Map();
                    let minX = Infinity, minY = Infinity;
                    let maxX = -Infinity, maxY = -Infinity;
                    cy.nodes().forEach((n) => {
                        const p = n.position();
                        if (p.x < minX) minX = p.x;
                        if (p.y < minY) minY = p.y;
                        if (p.x > maxX) maxX = p.x;
                        if (p.y > maxY) maxY = p.y;
                    });
                    console.log(`[cytoscape-layout] fCoSE raw output bbox: x[${Math.round(minX)}, ${Math.round(maxX)}] (spread ${Math.round(maxX-minX)}), y[${Math.round(minY)}, ${Math.round(maxY)}] (spread ${Math.round(maxY-minY)})`);
                    const shiftX = 50 - minX;
                    const shiftY = 50 - minY;
                    cy.nodes().forEach((n) => {
                        const p = n.position();
                        positions.set(n.id(), {
                            x: Math.round(p.x + shiftX),
                            y: Math.round(p.y + shiftY),
                        });
                    });
                    cy.destroy();
                    resolve(positions);
                },
            });
            layout.run();
        });
    }

    window.computeCytoscapeLayout = computeCytoscapeLayout;
    console.log('[cytoscape-layout] window.computeCytoscapeLayout registered (v11.U.H rev3 repulsion=200000 ideal=600)');
})();
