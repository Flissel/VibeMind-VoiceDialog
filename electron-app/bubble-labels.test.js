const test = require('node:test');
const assert = require('node:assert/strict');

const {
    truncateName,
    placeMarker,
    labelOpacity,
    isLiveTopLevelIdea,
    bubbleDataFromIdea,
    NEW_HIGHLIGHT_MS,
} = require('./renderer/bubble-labels');

test('the highlight for a new bubble lasts 30 seconds', () => {
    assert.equal(NEW_HIGHLIGHT_MS, 30000);
});

test('truncateName keeps short names and cuts long ones with an ellipsis', () => {
    assert.equal(truncateName('Marketing'), 'Marketing');
    assert.equal(truncateName('  Marketing  '), 'Marketing');
    const long = 'Eine sehr lange Ueberschrift fuer eine Bubble die nicht passt';
    const cut = truncateName(long, 24);
    assert.equal(cut.length, 24);
    assert.ok(cut.endsWith('…'));
    assert.ok(long.startsWith(cut.slice(0, -1).trimEnd()));
});

test('truncateName never returns an empty label', () => {
    for (const value of [undefined, null, '', '   ', 42]) {
        assert.equal(truncateName(value), 'Ohne Namen');
    }
});

test('placeMarker leaves a point inside the view where it is', () => {
    assert.deepEqual(
        placeMarker({ x: 400, y: 300, behind: false }, 800, 600, 40),
        { x: 400, y: 300, offscreen: false, angle: 0 },
    );
});

test('placeMarker pins a point outside the view to the nearest edge and points at it', () => {
    const right = placeMarker({ x: 1500, y: 300, behind: false }, 800, 600, 40);
    assert.equal(right.offscreen, true);
    assert.equal(right.x, 760);
    assert.equal(right.y, 300);
    assert.equal(right.angle, 0); // arrow points right

    const top = placeMarker({ x: 400, y: -900, behind: false }, 800, 600, 40);
    assert.equal(top.offscreen, true);
    assert.equal(top.y, 40);
    assert.equal(top.angle, -90); // arrow points up
});

test('placeMarker treats a bubble behind the camera as off screen on the mirrored side', () => {
    // A point behind the camera projects mirrored through the centre.
    const marker = placeMarker({ x: 700, y: 300, behind: true }, 800, 600, 40);
    assert.equal(marker.offscreen, true);
    assert.equal(marker.x, 40);
    assert.equal(marker.angle, 180); // arrow points left
});

test('placeMarker survives a degenerate view', () => {
    const marker = placeMarker({ x: NaN, y: NaN, behind: false }, 800, 600, 40);
    assert.equal(marker.offscreen, true);
    assert.ok(Number.isFinite(marker.x) && Number.isFinite(marker.y));
});

test('labelOpacity fades distant bubbles but keeps them readable', () => {
    assert.equal(labelOpacity(3), 1);
    assert.equal(labelOpacity(8), 1);
    assert.equal(labelOpacity(100), 0.45);
    const mid = labelOpacity(16.5);
    assert.ok(mid < 1 && mid > 0.45);
});

test('avoidOverlap moves a label below one that is already placed and leaves free ones alone', () => {
    const { avoidOverlap } = require('./renderer/bubble-labels');
    const placed = [];
    const first = avoidOverlap({ x: 100, y: 100, w: 80, h: 17 }, placed);
    const second = avoidOverlap({ x: 110, y: 104, w: 80, h: 17 }, placed);
    const far = avoidOverlap({ x: 400, y: 100, w: 80, h: 17 }, placed);

    assert.deepEqual(first, { x: 100, y: 100, w: 80, h: 17 });
    assert.equal(second.x, 110);
    assert.ok(second.y >= first.y + 17, `second at ${second.y}`);
    assert.deepEqual(far, { x: 400, y: 100, w: 80, h: 17 });
    assert.equal(placed.length, 3);
});

test('isLiveTopLevelIdea accepts only a new top-level row of the ideas table', () => {
    const idea = { id: 'a1', title: 'Neu', type: 'idea', parent_id: null };
    assert.equal(isLiveTopLevelIdea({ type: 'node_added', source: 'supabase', table: 'ideas', node: idea }), true);
    // A child idea is not a bubble of the overview.
    assert.equal(isLiveTopLevelIdea({ source: 'supabase', table: 'ideas', node: { ...idea, parent_id: 'b0' } }), false);
    // canvas_nodes also arrive as node_added; they are not bubbles.
    assert.equal(isLiveTopLevelIdea({ source: 'supabase', table: 'canvas_nodes', node: idea }), false);
    // The Python backend sends its own shape (node_type: 'bubble') and is handled elsewhere.
    assert.equal(isLiveTopLevelIdea({ node: { id: 'a1', node_type: 'bubble' } }), false);
    assert.equal(isLiveTopLevelIdea({ source: 'supabase', table: 'ideas', node: { title: 'ohne id' } }), false);
    assert.equal(isLiveTopLevelIdea(null), false);
});

test('bubbleDataFromIdea builds the shape addBubble expects, inside the ring around the centre', () => {
    const values = [0.25, 0.5, 0.1, 0.2, 0.3, 0.5, 0.5];
    const data = bubbleDataFromIdea({ id: 'a1', title: 'Neu' }, () => values.shift());

    assert.equal(data.id, 'a1');
    assert.equal(data.db_id, 'a1');
    assert.equal(data.title, 'Neu');
    const ring = Math.hypot(data.position.x, data.position.z);
    assert.ok(ring >= 2 && ring <= 4, `ring ${ring}`);
    assert.ok(data.position.y >= -0.5 && data.position.y <= 0.5);
    assert.ok(data.radius >= 0.6 && data.radius <= 0.9);
    for (const channel of ['r', 'g', 'b']) {
        assert.ok(data.color[channel] >= 0 && data.color[channel] <= 1);
    }
});
