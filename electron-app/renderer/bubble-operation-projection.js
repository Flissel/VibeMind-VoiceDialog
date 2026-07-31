/*
 * Read-only renderer projection for canonical Bubbles task/evidence events.
 * It deliberately does not infer orchestration, provider, or execution success.
 */
(function(root, factory) {
    var api = factory(root.document);
    if (typeof module === 'object' && module.exports) {
        module.exports = api;
    }
    root.bubbleOperationProjection = api;
})(typeof window !== 'undefined' ? window : globalThis, function(documentRef) {
    'use strict';

    var EVENT_TYPE = 'bubbles.operation_projection';
    var LIFECYCLES = new Set([
        'planned',
        'awaiting_clarification',
        'awaiting_approval',
        'approval_required',
        'queued',
        'running',
        'cancelled',
        'failed',
        'completed',
        'succeeded',
        'blocked_dependency',
    ]);
    var COMPLETED_LIFECYCLES = new Set(['completed', 'succeeded']);
    var UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

    function isDatabaseUuid(value) {
        return typeof value === 'string' && UUID_PATTERN.test(value.trim());
    }

    function isSafeSnapshot(value) {
        if (!value || typeof value !== 'object' || Array.isArray(value)) return false;
        return Object.keys(value).length > 0 && Object.keys(value).every(function(key) {
            var item = value[key];
            return key.trim() && (
                item === null ||
                typeof item === 'string' ||
                typeof item === 'boolean' ||
                (typeof item === 'number' && Number.isFinite(item))
            );
        });
    }

    function isEvidenceList(value) {
        return Array.isArray(value) && value.every(function(reference) {
            return typeof reference === 'string' && reference.trim();
        });
    }

    function unverified(params, reason) {
        params = params && typeof params === 'object' ? params : {};
        return {
            canonical_space_id: 'bubbles',
            bubble_id: isDatabaseUuid(params.bubble_id) ? params.bubble_id.trim().toLowerCase() : null,
            operation_id: typeof params.operation_id === 'string' && params.operation_id.trim() ? params.operation_id.trim() : null,
            lifecycle: typeof params.lifecycle === 'string' && LIFECYCLES.has(params.lifecycle) ? params.lifecycle : null,
            score_snapshot: isSafeSnapshot(params.score_snapshot) ? { ...params.score_snapshot } : {},
            evidence_refs: isEvidenceList(params.evidence_refs) ? params.evidence_refs.slice() : [],
            verified: false,
            execution_verified: false,
            verification_reason: reason,
        };
    }

    function project(message) {
        if (!message || message.type !== EVENT_TYPE) return unverified(null, 'unsupported_event');
        var params = message.params;
        if (!params || typeof params !== 'object' || Array.isArray(params)) return unverified(null, 'missing_params');
        if (params.canonical_space_id !== 'bubbles') {
            return unverified(params, params.canonical_space_id ? 'foreign_canonical_space_id' : 'missing_canonical_space_id');
        }
        if (!isDatabaseUuid(params.bubble_id)) return unverified(params, params.bubble_id ? 'invalid_bubble_id' : 'missing_bubble_id');
        if (typeof params.operation_id !== 'string' || !params.operation_id.trim()) return unverified(params, 'missing_operation_id');
        if (typeof params.lifecycle !== 'string' || !LIFECYCLES.has(params.lifecycle)) return unverified(params, 'invalid_lifecycle');
        if (!isSafeSnapshot(params.score_snapshot)) {
            return unverified(params, params.score_snapshot ? 'invalid_score_snapshot' : 'missing_score_snapshot');
        }
        if (!isEvidenceList(params.evidence_refs)) {
            return unverified(params, params.evidence_refs === undefined ? 'missing_evidence_refs' : 'invalid_evidence_refs');
        }
        if (COMPLETED_LIFECYCLES.has(params.lifecycle) && !params.evidence_refs.length) {
            return unverified(params, 'completed_requires_evidence');
        }
        if (params.verified !== true) return unverified(params, 'upstream_unverified');

        return {
            canonical_space_id: 'bubbles',
            bubble_id: params.bubble_id.trim().toLowerCase(),
            operation_id: params.operation_id.trim(),
            lifecycle: params.lifecycle,
            score_snapshot: { ...params.score_snapshot },
            evidence_refs: params.evidence_refs.slice(),
            verified: true,
            execution_verified: false,
            verification_reason: typeof params.verification_reason === 'string' && params.verification_reason
                ? params.verification_reason
                : 'renderer_projection_envelope_valid',
        };
    }

    function render(projection) {
        if (!documentRef) return projection;
        var target = documentRef.getElementById('bubble-operation-projection');
        if (!target) return projection;
        var score = Object.keys(projection.score_snapshot).length ? JSON.stringify(projection.score_snapshot) : 'unavailable';
        var evidence = projection.evidence_refs.length ? projection.evidence_refs.join(', ') : 'none';
        target.textContent = [
            'Bubbles operation: ' + (projection.operation_id || 'unverified'),
            'Lifecycle: ' + (projection.lifecycle || 'unverified'),
            'Score: ' + score,
            'Evidence: ' + evidence,
            'Envelope: ' + (projection.verified ? 'verified' : 'unverified') + ' (' + projection.verification_reason + ')',
            'Execution: unverified',
        ].join(' | ');
        target.dataset.verified = String(projection.verified);
        return projection;
    }

    function createStore() {
        var byBubbleId = Object.create(null);
        function reduce(message) {
            var result = project(message);
            if (result.bubble_id && message && message.type === EVENT_TYPE) byBubbleId[result.bubble_id] = result;
            return result;
        }
        function rehydrate(bubbleId) {
            if (!isDatabaseUuid(bubbleId)) return null;
            var result = byBubbleId[bubbleId.trim().toLowerCase()] || null;
            return result ? render(result) : null;
        }
        return { reduce: reduce, rehydrate: rehydrate };
    }

    var store = createStore();
    return {
        EVENT_TYPE: EVENT_TYPE,
        isDatabaseUuid: isDatabaseUuid,
        createStore: createStore,
        reduce: function(message) { return render(store.reduce(message)); },
        rehydrate: store.rehydrate,
        request: function(bubbleId) {
            if (!isDatabaseUuid(bubbleId)) return false;
            if (!root.vibemind || typeof root.vibemind.sendToPython !== 'function') return false;
            root.vibemind.sendToPython({
                type: 'get_bubbles_operation_projection',
                canonical_space_id: 'bubbles',
                bubble_id: bubbleId.trim().toLowerCase(),
            });
            return true;
        },
    };
});
