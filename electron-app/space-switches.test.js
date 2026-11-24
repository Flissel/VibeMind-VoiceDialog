const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const THREE = require('./renderer/lib/three.min.js');
const { hiddenSpaces } = require('./space-switches');
const { apply } = require('./renderer/space-switches');
const { pickSpace } = require('./renderer/space-pick');

const read = (...parts) => fs.readFileSync(path.join(__dirname, ...parts), 'utf8');

test('the Dashboard is off by default; the switch brings it back', () => {
    assert.deepEqual(hiddenSpaces({}), ['clawport']);
    for (const value of ['an', 'ein', 'on', 'true', '1', 'JA', ' an ']) {
        assert.deepEqual(hiddenSpaces({ VIBEMIND_DASHBOARD_SPACE: value }), [], value);
    }
    assert.deepEqual(hiddenSpaces({ VIBEMIND_DASHBOARD_SPACE: 'aus' }), ['clawport']);
    assert.deepEqual(hiddenSpaces({ VIBEMIND_DASHBOARD_SPACE: 'vielleicht' }), ['clawport'], 'unknown value: the default');
});

function fakeStyle() {
    const props = {};
    return { props, setProperty(name, value, priority = '') { props[name] = { value, important: priority === 'important' }; } };
}

function fakeDoc(ids) {
    const tabs = Object.fromEntries(ids.map((id) => [id, {
        id: 'tab-' + id, hidden: false, attrs: {}, style: fakeStyle(), setAttribute(k, v) { this.attrs[k] = v; },
    }]));
    return { tabs, getElementById: (name) => Object.values(tabs).find((t) => t.id === name) || null };
}

/** Every rule of the page's stylesheets, @imports followed, in cascade order. */
function pageRules() {
    const rules = [];
    const load = (file) => {
        const css = read('renderer', file).replace(/\/\*[\s\S]*?\*\//g, '');
        for (const m of css.matchAll(/@import url\('([^']+)'\);/g)) load(m[1]);
        // flatten @media and friends: their rules count as possibly applying
        for (const m of css.replace(/@import[^;]*;/g, '').matchAll(/([^{}@]+)\{([^{}]*)\}/g)) {
            rules.push({ selectors: m[1].split(',').map((s) => s.trim()).filter(Boolean), body: m[2], order: rules.length });
        }
    };
    const page = read('renderer', 'index.html');
    for (const m of page.matchAll(/<link rel="stylesheet" href="([^"]+)">/g)) load(m[1]);
    return rules;
}

function specificity(selector) {
    const s = selector.replace(/::[\w-]+/g, '');
    return [(s.match(/#[\w-]+/g) || []).length,
        (s.match(/\.[\w-]+|\[[^\]]*\]|:(?!not\()[\w-]+/g) || []).length,
        (s.replace(/\[[^\]]*\]/g, '').match(/(^|[\s>+~])[a-z][\w-]*/gi) || []).length];
}

/**
 * The display a tab button ends up with, as the browser would cascade it: the subject of each
 * selector must fit the button (class space-tab, its id, data-space, hidden); ancestors and states
 * like :hover are assumed to fit when the rule would SHOW the tab, and not to fit when it would
 * hide it, so the answer errs towards "visible".
 */
function computedDisplay(tab, rules) {
    const attrs = { class: 'space-tab', id: tab.id, 'data-space': tab.id.replace(/^tab-/, ''), ...(tab.hidden ? { hidden: '' } : {}) };
    const fits = (compound, lenient) => {
        if (/::/.test(compound)) return false;
        const parts = compound.match(/[.#]?[\w-]+|\[[^\]]*\]|:not\([^)]*\)|:[\w-]+(\([^)]*\))?/g) || [];
        return parts.every((p) => {
            if (p.startsWith('.')) return attrs.class.split(' ').includes(p.slice(1));
            if (p.startsWith('#')) return attrs.id === p.slice(1);
            if (p.startsWith('[')) {
                const m = p.match(/^\[([\w-]+)(?:="([^"]*)")?\]$/);
                return Boolean(m) && m[1] in attrs && (m[2] === undefined || attrs[m[1]] === m[2]);
            }
            if (p.startsWith(':')) return lenient;
            return p.toLowerCase() === 'button';
        });
    };
    let best = { value: 'inline-block', important: false, spec: [-1, -1, -1], order: -1 };
    const bySpec = (a, b) => { for (let i = 0; i < 3; i++) if (a[i] !== b[i]) return a[i] - b[i]; return 0; };
    const beats = (a, b) => (a.important !== b.important ? a.important
        : bySpec(a.spec, b.spec) !== 0 ? bySpec(a.spec, b.spec) > 0 : a.order > b.order);
    for (const rule of rules) {
        const decl = rule.body.match(/(?:^|;)\s*display\s*:\s*([^;!]+?)\s*(!important)?\s*(?:;|$)/);
        if (!decl) continue;
        const shows = decl[1] !== 'none';
        for (const selector of rule.selectors) {
            const chain = selector.split(/\s*[>+~]\s*|\s+/);
            const subject = chain[chain.length - 1];
            if (!shows && chain.length > 1) continue;              // a hiding rule must fit the button alone
            if (!fits(subject, shows)) continue;
            const candidate = { value: decl[1], important: Boolean(decl[2]), spec: specificity(selector), order: rule.order };
            if (beats(candidate, best)) best = candidate;
        }
    }
    const inline = tab.style.props.display;
    if (inline && (inline.important || !best.important)) return inline.value;
    return best.value;
}

test('the switched-off tab is really not shown: its computed display is none, the others still show', () => {
    const rules = pageRules();
    assert.ok(rules.some((r) => r.selectors.includes('.space-tab')), 'the tab rules are read');
    const doc = fakeDoc(['ideas', 'clawport']);
    // the case that was seen: hidden is set, but .space-tab { display: flex } wins
    assert.equal(computedDisplay({ ...doc.tabs.clawport, hidden: true, style: fakeStyle() }, rules.filter((r) => !r.selectors.includes('.space-tab[hidden]'))), 'flex');
    apply({ spaces: { clawport: { objects: [] } } }, doc, ['clawport']);
    assert.equal(computedDisplay(doc.tabs.clawport, rules), 'none');
    assert.equal(computedDisplay({ ...doc.tabs.clawport, style: fakeStyle() }, rules), 'none', 'the stylesheet alone hides it too');
    assert.equal(computedDisplay(doc.tabs.ideas, rules), 'flex', 'the other tabs are shown');
});

test('switched off: no tab, out of the scene, objects kept, not clickable', () => {
    const scene = new THREE.Scene();
    const board = new THREE.Group();
    const face = new THREE.Mesh(new THREE.BoxGeometry(2, 2, 0.2), new THREE.MeshBasicMaterial());
    const inner = new THREE.Group();
    inner.add(face);
    board.add(inner);
    board.position.set(-8, 0, 12);
    scene.add(board);
    const app = { scene, spaces: { ideas: { objects: [] }, clawport: { group: board, objects: [board] } } };
    const doc = fakeDoc(['ideas', 'clawport']);

    // before: the board is the click target of the Dashboard
    board.updateMatrixWorld(true);
    const ray = new THREE.Raycaster(new THREE.Vector3(-8, 0, 30), new THREE.Vector3(0, 0, -1));
    assert.equal(pickSpace(ray, app.spaces, 'ideas'), 'clawport');

    assert.deepEqual(apply(app, doc, ['clawport', 'gibt-es-nicht']), ['clawport']);
    assert.equal(app.spaces.clawport.hidden, true);
    assert.equal(board.parent, null, 'out of the scene');
    assert.equal(app.spaces.clawport.group, board, 'kept, nothing deleted');
    assert.equal(doc.tabs.clawport.hidden, true);
    assert.equal(doc.tabs.clawport.attrs['aria-hidden'], 'true');
    assert.equal(doc.tabs.ideas.hidden, false);
    assert.equal(pickSpace(ray, app.spaces, 'ideas'), null, 'no click opens it');
});

test('the scene does not enter a space switched off, by any way; key cycling skips it', () => {
    const scene = read('renderer', 'multiverse.js');
    assert.match(scene, /navigateToSpace\(targetSpace, options = \{\}\) \{\s*if \(this\.isNavigating \|\| targetSpace === this\.currentSpace\) \{\s*return false;\s*\}\s*\/\/[^\n]*\n\s*if \(this\.spaces\[targetSpace\] && this\.spaces\[targetSpace\]\.hidden\) \{\s*return false;/);
    const cycling = scene.match(/const spaceKeys = Object\.keys\(this\.spaces\)\.filter\(\(key\) => !this\.spaces\[key\]\.hidden \|\| key === this\.currentSpace\);/g);
    assert.equal(cycling && cycling.length, 2, 'previous and next');
});

test('main, preload and page are wired; the Dashboard code stays', () => {
    assert.match(read('main.js'), /ipcMain\.handle\('get-space-switches', \(\) => require\('\.\/space-switches'\)\.hiddenSpaces\(process\.env\)\)/);
    assert.match(read('preload.js'), /getSpaceSwitches: \(\) => ipcRenderer\.invoke\('get-space-switches'\)/);
    const page = read('renderer', 'index.html');
    assert.match(page, /<script defer src="space-switches\.js"><\/script>/);
    assert.match(page, /id="tab-clawport"/, 'the tab is hidden, not removed');
    assert.ok(fs.existsSync(path.join(__dirname, 'clawport-manager.js')));
    assert.match(read('main.js'), /ipcMain\.handle\('clawport:chat-text-input'/);
});
