const test = require('node:test');
const assert = require('node:assert/strict');

const { buildRealtimeMessage, SUBSCRIPTIONS } = require('./supabase-realtime');

function sub(table, event) {
    const found = SUBSCRIPTIONS.find((entry) => entry.table === table && entry.event === event);
    assert.ok(found, `${table}.${event} is subscribed`);
    return found;
}

test('requiring supabase-realtime does not load the Supabase SDK', () => {
    // The SDK is only needed once subscriptions start; tests and tools can read the mapping without it.
    assert.equal(Object.keys(require.cache).some((file) => /[\\/]@supabase[\\/]/.test(file)), false);
});

test('an ideas INSERT names its table so the renderer can tell a bubble from a canvas node', () => {
    const message = buildRealtimeMessage(sub('ideas', 'INSERT'), {
        id: 'a1', title: 'Neu', description: '', score: 0, status: 'draft', parent_id: null,
    });

    assert.equal(message.type, 'node_added');
    assert.equal(message.source, 'supabase');
    assert.equal(message.table, 'ideas');
    assert.equal(message.node.id, 'a1');
    assert.equal(message.node.parent_id, null);
});

test('an ideas DELETE and a canvas_nodes DELETE are both node_removed but carry different tables', () => {
    const idea = buildRealtimeMessage(sub('ideas', 'DELETE'), { id: 'a1' });
    const node = buildRealtimeMessage(sub('canvas_nodes', 'DELETE'), { id: 'n1' });

    assert.deepEqual(idea, { type: 'node_removed', source: 'supabase', table: 'ideas', node_id: 'a1' });
    assert.deepEqual(node, { type: 'node_removed', source: 'supabase', table: 'canvas_nodes', node_id: 'n1' });
});

test('rowForEvent reads a deleted row from `old`: Realtime sends an empty `new` on DELETE', () => {
    const { rowForEvent } = require('./supabase-realtime');

    assert.deepEqual(rowForEvent({ eventType: 'DELETE', new: {}, old: { id: 'a1' } }), { id: 'a1' });
    assert.deepEqual(rowForEvent({ eventType: 'INSERT', new: { id: 'a1', title: 'Neu' }, old: {} }), { id: 'a1', title: 'Neu' });
    assert.deepEqual(rowForEvent({ eventType: 'UPDATE', new: { id: 'a1', title: 'B' }, old: { id: 'a1' } }), { id: 'a1', title: 'B' });
    assert.deepEqual(rowForEvent({ eventType: 'DELETE', new: {}, old: null }), {});
    assert.deepEqual(rowForEvent({}), {});
});

test('a deleted idea reaches the renderer with its id', () => {
    const { rowForEvent } = require('./supabase-realtime');
    const message = buildRealtimeMessage(
        sub('ideas', 'DELETE'), rowForEvent({ eventType: 'DELETE', new: {}, old: { id: 'a1' } }));

    assert.equal(message.node_id, 'a1');
});

test('only a repeated INSERT is dropped; a later UPDATE or DELETE of the same row goes through', () => {
    const { isRepeatedInsert } = require('./supabase-realtime');
    const seen = new Set();

    assert.equal(isRepeatedInsert(seen, 'INSERT', 'a1'), false);
    assert.equal(isRepeatedInsert(seen, 'INSERT', 'a1'), true);
    assert.equal(isRepeatedInsert(seen, 'UPDATE', 'a1'), false);
    assert.equal(isRepeatedInsert(seen, 'UPDATE', 'a1'), false);
    assert.equal(isRepeatedInsert(seen, 'DELETE', 'a1'), false);
    // After a delete the id may come back (undo of a delete re-inserts the same row).
    assert.equal(isRepeatedInsert(seen, 'INSERT', 'a1'), false);
    assert.equal(isRepeatedInsert(seen, 'INSERT', ''), false);
});

test('a payload field can never overwrite type, source or table', () => {
    const message = buildRealtimeMessage(
        { table: 'ideas', messageType: 'node_added', transform: () => ({ type: 'x', source: 'y', table: 'z', node: {} }) },
        {},
    );

    assert.equal(message.type, 'node_added');
    assert.equal(message.source, 'supabase');
    assert.equal(message.table, 'ideas');
});
