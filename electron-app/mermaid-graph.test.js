const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

/** mermaid-layout.js in a window stand-in; its graph text through window.VibeMermaidGraph. */
function load() {
    const window = {};
    vm.runInNewContext(fs.readFileSync(path.join(__dirname, 'renderer/mermaid-layout.js'), 'utf8'),
        { window, console: { log() {}, warn() {}, error() {} } });
    return window.VibeMermaidGraph;
}

// The form of a grouping as the brain writes it (renderer.log, node_added): a heading card with
// metadata.gruppen_kopf at the top of its column, its cards at the same x below it.
const card = (id, x, y, title, metadata = { width: 200, height: 100 }) =>
    ({ id, type: 'note', position: { x, y }, content: { title, text: '' }, title, metadata });
const head = (id, x, title) => card(id, x, 100, title, { width: 200, height: 100, gruppen_kopf: true });

const nodes = [
    head('0000abcd-0001', 480, 'Gruppe A'),
    head('0000abcd-0002', 720, 'Gruppe B'),
    card('0000abcd-0013', 480, 400, 'Karte 3'),
    card('0000abcd-0011', 480, 250, 'Karte 1'),
    card('0000abcd-0021', 720, 250, 'Karte 2'),
    card('0000abcd-0099', 960, 250, 'Karte 9'),   // no heading over it: stays on its own
];

test('grouped cards stand in columns under their heading, not all in one row', () => {
    const { graph } = load().build(nodes, []);
    const lines = graph.split('\n').map((l) => l.trim());
    assert.ok(lines.includes('class n_0000abcd_0001 groupHead'));
    assert.ok(lines.includes('class n_0000abcd_0002 groupHead'));
    // the column in order of y: heading, Karte 1 (y 250), Karte 3 (y 400)
    assert.ok(lines.includes('n_0000abcd_0001 ~~~ n_0000abcd_0011'));
    assert.ok(lines.includes('n_0000abcd_0011 ~~~ n_0000abcd_0013'));
    assert.ok(lines.includes('n_0000abcd_0002 ~~~ n_0000abcd_0021'));

    const hub = lines.filter((l) => l.startsWith('HUB -->')).map((l) => l.slice('HUB --> '.length));
    assert.deepEqual(hub, ['n_0000abcd_0001', 'n_0000abcd_0002', 'OHNE_GRUPPE'],
        'the top row: the headings, "Ohne Gruppe" last; no card');
});

// Lauf 11: the card without a group stood in the top row beside the headings and looked like one.
test('cards without a group stand in their own last column "Ohne Gruppe"; headings have no card frame', () => {
    const { graph, nodeToCluster } = load().build(nodes, []);
    const lines = graph.split('\n').map((l) => l.trim());
    assert.ok(lines.includes('OHNE_GRUPPE["Ohne Gruppe"]'));
    assert.ok(lines.includes('class OHNE_GRUPPE groupHead'));
    assert.ok(lines.includes('OHNE_GRUPPE ~~~ n_0000abcd_0099'));
    assert.ok(!lines.includes('class n_0000abcd_0099 rootNode'), 'the card is no root of the top row');
    assert.equal(nodeToCluster.get('n_0000abcd_0099'), nodeToCluster.get('OHNE_GRUPPE'), 'the column drags as one');
    const style = lines.find((l) => l.startsWith('classDef groupHead'));
    assert.match(style, /fill:transparent,stroke:transparent/);
    assert.match(style, /font-size:19px/);
});

test('a column drags as one: the members belong to the cluster of their heading', () => {
    const { clusters, nodeToCluster } = load().build(nodes, []);
    const a = nodeToCluster.get('n_0000abcd_0001');
    assert.equal(nodeToCluster.get('n_0000abcd_0011'), a);
    assert.equal(nodeToCluster.get('n_0000abcd_0013'), a);
    assert.notEqual(nodeToCluster.get('n_0000abcd_0021'), a);
    assert.ok(clusters.length >= 3);
});

test('without a heading nothing changes: x/y alone make no group', () => {
    const plain = nodes.filter((n) => !n.metadata.gruppen_kopf);
    const { graph } = load().build(plain, []);
    assert.doesNotMatch(graph, /~~~|class \S+ groupHead/);
});
