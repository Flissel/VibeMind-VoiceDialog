/**
 * Which space did a click hit?
 *
 * The click handler used to test the spaces one after the other in a fixed order and
 * took the first one whose objects lay anywhere on the sight line. A space standing
 * behind the clicked one could win (clicking the studio opened the dashboard behind
 * it). Here the nearest hit wins, as the eye expects.
 *
 * The objects tested per space are exactly the ones the old handler tested.
 */
(function (root) {
    'use strict';

    const meshesOneLevelDeep = (group) => group.children.flatMap(
        (c) => (c.isGroup ? c.children.filter((m) => m.isMesh) : (c.isMesh ? [c] : [])));
    const directMeshes = (group) => group.children.filter((c) => c.isMesh);

    /** Per space: which objects count as its click target, and whether to test their children too. */
    const TARGETS = [
        { key: 'swedesign', objects: (s) => s.group && directMeshes(s.group) },
        { key: 'clawport', objects: (s) => s.group && meshesOneLevelDeep(s.group) },
        { key: 'roarboot', objects: (s) => s.group && directMeshes(s.group) },
        { key: 'agentfarm', objects: (s) => s.group && meshesOneLevelDeep(s.group) },
        { key: 'video', objects: (s) => s.group && meshesOneLevelDeep(s.group) },
        { key: 'flowzen', objects: (s) => s.group && s.group.children, recursive: true },
        { key: 'mirofish', objects: (s) => s.objects && s.objects[0] && meshesOneLevelDeep(s.objects[0]) },
        { key: 'thebrain', objects: (s) => s.group && meshesOneLevelDeep(s.group) },
    ];

    /**
     * @param raycaster  set from the camera through the click
     * @param spaces     MultiverseApp.spaces
     * @param currentSpace the space the user is in; it is never picked again
     * @param inFront    objects that keep their own click when they are nearer (the idea bubbles)
     * @returns {string|null} key of the space to open
     */
    function pickSpace(raycaster, spaces, currentSpace, inFront = []) {
        let best = null;
        let bestDistance = Infinity;
        for (const target of TARGETS) {
            const space = spaces[target.key];
            if (!space || target.key === currentSpace) continue;
            const objects = target.objects(space);
            if (!objects || !objects.length) continue;
            const hits = raycaster.intersectObjects(objects, Boolean(target.recursive));
            if (hits.length && hits[0].distance < bestDistance) {
                best = target.key;
                bestDistance = hits[0].distance;
            }
        }
        if (best && inFront.length) {
            const nearer = raycaster.intersectObjects(inFront, false);
            if (nearer.length && nearer[0].distance < bestDistance) return null;
        }
        return best;
    }

    const api = { pickSpace, TARGETS };
    if (typeof module !== 'undefined' && module.exports) module.exports = api;
    else root.VibeSpacePick = api;
})(typeof window !== 'undefined' ? window : globalThis);
