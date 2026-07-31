const assert = require('node:assert/strict');

const projection = require('./bubble-operation-projection.js');

const BUBBLE_ID = 'a4b83e77-9069-4bad-9bb1-c6d5d83a7992';

function operation(lifecycle, overrides) {
    return {
        type: 'bubbles.operation_projection',
        params: {
            canonical_space_id: 'bubbles',
            bubble_id: BUBBLE_ID,
            operation_id: 'operation-42',
            lifecycle: lifecycle,
            score_snapshot: { score: 87 },
            evidence_refs: lifecycle === 'completed' ? ['evidence:receipt-42'] : [],
            verified: true,
            verification_reason: 'renderer_projection_envelope_valid',
            ...(overrides || {}),
        },
    };
}

function run(name, test) {
    try {
        test();
        process.stdout.write(`ok - ${name}\n`);
    } catch (error) {
        process.stderr.write(`not ok - ${name}\n`);
        throw error;
    }
}

run('projects every supported Bubbles lifecycle without asserting execution', () => {
    [
        'planned',
        'awaiting_clarification',
        'awaiting_approval',
        'running',
        'cancelled',
        'failed',
        'completed',
    ].forEach((lifecycle) => {
        const result = projection.reduce(operation(lifecycle));
        assert.equal(result.verified, true);
        assert.equal(result.bubble_id, BUBBLE_ID);
        assert.equal(result.operation_id, 'operation-42');
        assert.equal(result.lifecycle, lifecycle);
        assert.deepEqual(result.score_snapshot, { score: 87 });
        assert.equal(result.execution_verified, false);
    });
});

run('fails closed for missing or foreign identities and completed without evidence', () => {
    [
        operation('planned', { bubble_id: undefined }),
        operation('planned', { bubble_id: '42' }),
        operation('planned', { canonical_space_id: 'shuttles' }),
        operation('planned', { operation_id: '' }),
        operation('completed', { evidence_refs: [] }),
    ].forEach((message) => {
        const result = projection.reduce(message);
        assert.equal(result.verified, false);
        assert.equal(result.execution_verified, false);
    });
});

run('keeps shuttle workflow aliases out of canonical Bubbles projection', () => {
    const result = projection.reduce({
        type: 'shuttle.completed',
        params: {
            bubble_id: BUBBLE_ID,
            operation_id: 'operation-42',
            lifecycle: 'completed',
            score_snapshot: { score: 87 },
            evidence_refs: ['evidence:receipt-42'],
            verified: true,
        },
    });

    assert.equal(result.verified, false);
    assert.equal(result.verification_reason, 'unsupported_event');
});

run('rehydrates only the projection stored under the canonical DB UUID', () => {
    const store = projection.createStore();
    const saved = store.reduce(operation('running'));

    assert.equal(store.rehydrate(BUBBLE_ID), saved);
    assert.equal(store.rehydrate(42), null);
    assert.equal(store.rehydrate('42'), null);
});
