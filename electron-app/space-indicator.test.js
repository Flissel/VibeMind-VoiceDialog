const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const { describeForRenderer } = require('./external-spaces');

/** Runs renderer/space-navigator.js against a tiny page with the indicator elements. */
function loadNavigator(spaces) {
    const elements = {};
    const element = (id) => (elements[id] = elements[id] || {
        id, textContent: '', className: '', classList: { add() {}, remove() {}, toggle() {} },
    });
    const document = {
        getElementById: element,
        querySelector: (sel) => (sel === '.agent-indicator' ? element('agent-indicator') : null),
        querySelectorAll: () => [],
    };
    const window = {
        multiverseApp: { getSpaceInfo: (id) => spaces[id] || null, currentSpace: 'ideas', isNavigating: false },
        vibemind: {},
    };
    const context = vm.createContext({ window, document, console: { log() {}, error() {} }, setTimeout, clearTimeout });
    vm.runInContext(fs.readFileSync(path.join(__dirname, 'renderer', 'space-navigator.js'), 'utf8'), context);
    return { nav: window.spaceNavigator, elements };
}

test('the indicator top right names the agent of Lernen and Auftraege in German, as the space does', () => {
    // the spaces as the scene keeps them (sceneEntry: name = label, agent from the main process)
    const spaces = Object.fromEntries(describeForRenderer({}).map((s) => [s.id, { name: s.label, icon: s.icon, agent: s.agent }]));
    const { nav, elements } = loadNavigator(spaces);
    const shown = {};
    for (const id of Object.keys(spaces)) {
        nav.syncSpace(id);
        shown[id] = [elements['current-space-name'].textContent, elements['current-agent-name'].textContent];
    }
    assert.deepEqual(shown.learning, ['Lernen', 'Lernen']);
    assert.deepEqual(shown.orders, ['Aufträge', 'Aufträge']);
    assert.deepEqual(shown.sales, ['Sales', 'Sales']);
    for (const [id, [, agent]] of Object.entries(shown)) {
        assert.doesNotMatch(agent, /^(Learning|Orders)$/, `${id}: no English key on screen`);
    }
    assert.equal(elements['agent-indicator'].className, 'agent-indicator orders', 'the colour class still follows the key');
});

test('without a name the key with a capital stays (Rachel and the other built-in agents)', () => {
    const { nav } = loadNavigator({});
    assert.equal(nav.displayName('rachel'), 'Rachel');
    assert.equal(nav.displayName('orders', '  '), 'Orders');
    assert.equal(nav.displayName('orders', 'Aufträge'), 'Aufträge');
});
