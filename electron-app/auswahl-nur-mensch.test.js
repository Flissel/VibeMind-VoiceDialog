// Run 37: after a note for two cards the Brain got selection = [the card made last], though nobody had
// marked anything. The app marks a card on its own (ideas-chat showCard after a jump, result-target mark
// after a result); that mark went out as the selection of the person. Now only a click of the person is
// a selection. Invented ids, no real data.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const read = (...parts) => fs.readFileSync(path.join(__dirname, ...parts), 'utf8');
const { buildContext } = require('./renderer/ideas-chat');

const BUBBLE = '00000000-0000-4000-8000-0000000000b1';
const NEW_CARD = '00000000-0000-4000-8000-0000000000c1';
const OLD_CARD = '00000000-0000-4000-8000-0000000000c2';

function canvas() {
    const window = { vibemind: {} };
    vm.runInNewContext(read('renderer', 'universe_canvas.js'), { window, console: { log() {}, warn() {} } });
    const card = () => ({ element: { classList: { add() {}, remove() {} } } });
    const self = { selectedNode: null, userSelectedNode: null, nodes: new Map([[NEW_CARD, card()], [OLD_CARD, card()]]) };
    const proto = window.UniverseCanvas.prototype;
    return {
        self,
        appMarks: (id) => proto.selectNode.call(self, id),
        personClicks: (id) => proto.selectNode.call(self, id, { byUser: true }),
    };
}

test('a card the app marks is shown as marked but is no selection of the person', () => {
    const c = canvas();
    c.appMarks(NEW_CARD);
    assert.equal(c.self.selectedNode, NEW_CARD, 'still marked on screen');
    assert.equal(c.self.userSelectedNode, null);
});

test('a click of the person is the selection; a later mark of the app replaces it with none', () => {
    const c = canvas();
    c.personClicks(OLD_CARD);
    assert.equal(c.self.userSelectedNode, OLD_CARD);
    c.appMarks(NEW_CARD);
    assert.equal(c.self.selectedNode, NEW_CARD);
    assert.equal(c.self.userSelectedNode, null, 'the card on screen is not the one the person marked');
});

test('only the click handler of a card passes byUser; showCard and the result mark do not', () => {
    const canvasSrc = read('renderer', 'universe_canvas.js');
    assert.equal((canvasSrc.match(/byUser: true/g) || []).length, 1);
    assert.match(canvasSrc, /if \(!e\.target\.classList\.contains\('node-delete'\)\) \{\s*this\.selectNode\(data\.id, \{ byUser: true \}\);/);
    assert.match(canvasSrc, /clear\(\) \{[\s\S]*?this\.userSelectedNode = null;\s*\}/);
    assert.match(read('renderer', 'ideas-chat.js'), /canvas\.selectNode\(found\.data\.id\);/);
    assert.match(read('renderer', 'result-target.js'), /win\.spaceCanvas\.selectNode\(nodeId\);/);
});

test('the context of a sentence takes the card of the person, not the marked one', () => {
    const chat = read('renderer', 'ideas-chat.js');
    assert.match(chat, /const selection = canvas && canvas\.userSelectedNode != null \? \[canvas\.userSelectedNode\] : \[\];/);
    assert.doesNotMatch(chat, /\[canvas\.selectedNode\]/);
});

test('run 37 shape: a new card the app marked goes along as last_id only, selection stays empty', () => {
    const c = canvas();
    c.appMarks(NEW_CARD);
    const selection = c.self.userSelectedNode != null ? [c.self.userSelectedNode] : [];
    const context = buildContext({
        bubble: { id: BUBBLE, title: 'Bubble A' },
        nodes: [{ id: OLD_CARD, title: 'Karte 1' }, { id: NEW_CARD, title: 'Karte 2' }],
        nodesBubbleId: BUBBLE, selection, lastId: NEW_CARD,
    });
    assert.deepEqual(context.selection, []);
    assert.equal(context.last_id, NEW_CARD);
});
