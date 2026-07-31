const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

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
            evidence_refs: lifecycle === 'completed' || lifecycle === 'succeeded'
                ? ['evidence:receipt-42']
                : [],
            verified: true,
            verification_reason: 'renderer_projection_envelope_valid',
            ...(overrides || {}),
        },
    };
}

function freshProjection(documentStub) {
    const modulePath = require.resolve('./bubble-operation-projection.js');
    const hadDocument = Object.prototype.hasOwnProperty.call(global, 'document');
    const previousDocument = global.document;
    delete require.cache[modulePath];
    if (documentStub) global.document = documentStub;
    else delete global.document;
    const fresh = require('./bubble-operation-projection.js');
    if (hadDocument) global.document = previousDocument;
    else delete global.document;
    return fresh;
}

function withVibemind(vibemind, test) {
    const hadVibemind = Object.prototype.hasOwnProperty.call(global, 'vibemind');
    const previousVibemind = global.vibemind;
    global.vibemind = vibemind;
    try {
        test();
    } finally {
        if (hadVibemind) global.vibemind = previousVibemind;
        else delete global.vibemind;
    }
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
        const result = projection.createStore().reduce(operation(lifecycle));
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

run('renders a valid projection immediately without rehydrate or user action', () => {
    const target = { textContent: '', dataset: {} };
    const documentStub = {
        getElementById(id) {
            return id === 'bubble-operation-projection' ? target : null;
        },
    };

    freshProjection(documentStub).reduce(operation('completed'));

    assert.match(target.textContent, /Bubbles operation: operation-42/);
    assert.match(target.textContent, /Lifecycle: completed/);
    assert.match(target.textContent, /Score: {"score":87}/);
    assert.match(target.textContent, /Evidence: evidence:receipt-42/);
    assert.match(target.textContent, /Envelope: verified \(renderer_projection_envelope_valid\)/);
    assert.match(target.textContent, /Execution: unverified/);
});

run('requests stored projection only for a canonical database UUID', () => {
    const sent = [];
    const api = freshProjection();

    withVibemind({ sendToPython(message) { sent.push(message); } }, () => {
        assert.equal(api.request(BUBBLE_ID), true);
        assert.deepEqual(sent, [{
            type: 'get_bubbles_operation_projection',
            canonical_space_id: 'bubbles',
            bubble_id: BUBBLE_ID,
        }]);
        assert.equal(api.request(42), false);
        assert.equal(api.request('42'), false);
        assert.equal(sent.length, 1);
    });
});

run('navigation gates projection rehydrate and request behind user intent and db_id', () => {
    const source = fs.readFileSync(path.join(__dirname, 'bubble-navigation.js'), 'utf8');

    assert.match(source, /enterSpace\(bubbleId, true\)/);
    assert.match(source, /if \(userInitiated && window\.bubbleOperationProjection &&[\s\S]*isDatabaseUuid\(dbId\)\)/);
    assert.match(source, /bubbleOperationProjection\.rehydrate\(dbId\);[\s\S]*bubbleOperationProjection\.request\(dbId\);/);
});

run('keeps a newer lifecycle projection when the same operation regresses', () => {
    const store = projection.createStore();
    const completed = store.reduce(operation('completed'));
    const stale = store.reduce(operation('running'));

    assert.equal(completed.verified, true);
    assert.equal(stale.verified, false);
    assert.equal(stale.verification_reason, 'stale_lifecycle_regression');
    assert.equal(store.rehydrate(BUBBLE_ID), completed);

    const newOperation = store.reduce(operation('running', { operation_id: 'operation-43' }));
    assert.equal(newOperation.verified, true);
    assert.equal(store.rehydrate(BUBBLE_ID), newOperation);
});

run('never regresses a terminal operation or running operation with the same operation_id', () => {
    ['cancelled', 'failed', 'completed', 'succeeded'].forEach((terminal) => {
        const store = projection.createStore();
        const current = store.reduce(operation(terminal));
        const stale = store.reduce(operation('running'));

        assert.equal(current.verified, true);
        assert.equal(stale.verified, false);
        assert.equal(store.rehydrate(BUBBLE_ID), current);
    });

    const store = projection.createStore();
    const running = store.reduce(operation('running'));
    const stale = store.reduce(operation('planned'));
    assert.equal(stale.verified, false);
    assert.equal(store.rehydrate(BUBBLE_ID), running);
});
