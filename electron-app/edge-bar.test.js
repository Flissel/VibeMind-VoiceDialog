// With a bubble open the area belongs to the cards and the chat (measured in the app 2026-11-23:
// the voice panel lay in the middle of the cards, Summaries / White Paper bottom left over cards,
// the EVAL tab reached into the right column).
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const edgeBar = require('./renderer/edge-bar');

function fakeDom() {
    const byId = new Map();
    const node = (id) => {
        const n = {
            id, children: [], parentNode: null, attrs: {}, classes: new Set(),
            get nextSibling() { const p = this.parentNode; return p ? p.children[p.children.indexOf(this) + 1] || null : null; },
            appendChild(child) { return this.insertBefore(child, null); },
            insertBefore(child, next) {
                if (child.parentNode) child.parentNode.children.splice(child.parentNode.children.indexOf(child), 1);
                const at = next ? this.children.indexOf(next) : -1;
                if (at >= 0) this.children.splice(at, 0, child); else this.children.push(child);
                child.parentNode = this;
                if (child.id) byId.set(child.id, child);
                return child;
            },
            setAttribute(k, v) { this.attrs[k] = v; },
            classList: null,
        };
        n.classList = { add: (c) => n.classes.add(c), remove: (c) => n.classes.delete(c), contains: (c) => n.classes.has(c) };
        if (id) byId.set(id, n);
        return n;
    };
    const body = node('body');
    const view = node('space-view');
    view.classes.add('hidden');
    const header = node('space-header');
    const canvas = node('space-canvas');
    body.appendChild(view);
    view.appendChild(header);
    view.appendChild(canvas);
    view.appendChild(node('summaries-toggle'));
    view.appendChild(node('summaries-panel'));
    view.appendChild(node('whitepaper-toggle'));
    body.appendChild(node('voice-panel'));
    body.appendChild(node('eval-toggle'));
    const doc = {
        body,
        getElementById: (id) => byId.get(id) || null,
        createElement: () => node(null),
    };
    return { doc, view, header, body };
}

test('bubble open: voice, Summaries, White Paper and EVAL sit in the bar of the header', () => {
    const { doc, view, header, body } = fakeDom();
    const bar = edgeBar.create();
    view.classes.delete('hidden');
    bar.sync(doc);
    const edge = doc.getElementById('space-edge-bar');
    assert.equal(edge.parentNode, header);
    assert.deepEqual(edge.children.map((c) => c.id), ['summaries-toggle', 'whitepaper-toggle', 'eval-toggle', 'voice-panel']);
    assert.ok(body.classes.has('bubble-open'));
    bar.sync(doc);   // a second entry moves nothing twice
    assert.equal(edge.children.length, 4);
});

test('bubble left: every element back where it was', () => {
    const { doc, view, body } = fakeDom();
    const before = (id) => { const el = doc.getElementById(id); return [el.parentNode.id, el.parentNode.children.indexOf(el)]; };
    const places = edgeBar.IDS.map(before);
    const bar = edgeBar.create();
    view.classes.delete('hidden');
    bar.sync(doc);
    view.classes.add('hidden');
    bar.sync(doc);
    assert.deepEqual(edgeBar.IDS.map(before), places);
    assert.ok(!body.classes.has('bubble-open'));
});

test('every way into a bubble counts: the bar follows #space-view', () => {
    const { doc, view } = fakeDom();
    let notify = null;
    class Observer { constructor(fn) { notify = fn; } observe(target, opts) { assert.equal(target, view); assert.deepEqual(opts.attributeFilter, ['class']); } }
    edgeBar.create().watch(doc, Observer);
    view.classes.delete('hidden');
    notify();
    assert.equal(doc.getElementById('voice-panel').parentNode.id, 'space-edge-bar');
    view.classes.add('hidden');
    notify();
    assert.equal(doc.getElementById('voice-panel').parentNode.id, 'body');
});

test('the bar is loaded and styled; nothing floats over the cards', () => {
    const html = fs.readFileSync(path.join(__dirname, 'renderer', 'index.html'), 'utf8');
    assert.match(html, /<script defer src="edge-bar\.js"><\/script>/);
    const css = fs.readFileSync(path.join(__dirname, 'renderer', 'styles', 'edge-bar.css'), 'utf8');
    for (const id of edgeBar.IDS) assert.match(css, new RegExp(`#space-edge-bar #${id}`));
    assert.match(css, /position: static/);
    assert.match(fs.readFileSync(path.join(__dirname, 'renderer', 'styles.css'), 'utf8'), /styles\/edge-bar\.css/);
});
