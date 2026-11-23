/**
 * What a sentence carries to the Brain and how its answer is shown, for every chat field of the app.
 *
 * Context: every sentence names the space on screen (`context.space`, the key of the scene in
 * multiverse.js, e.g. ideas, projects, desktop, orders, sales). The Brain weighs its routing by it:
 * an unsure sentence stays in that space, and "nicht verstanden" names examples from it. In the
 * Ideas space the context of the Ideas chat (open bubble, cards on screen) goes along as before.
 *
 * Answer: three kinds.
 *   rueckfrage  the Brain did not understand or asks back (`question`, `rueckfrage: true` or
 *               `verstanden: false`): a calm question, never a red error.
 *   fehler      nothing usable came back (`success: false` or `ok: false`).
 *   antwort     everything else.
 * The text is the Brain's German sentence (`message`, or `final_text`). The raw original of an
 * error (`fehler`) is never shown.
 */
(function (root) {
    'use strict';

    const NO_ANSWER = 'Keine Antwort.';

    /** The context of a sentence sent from the space `space`; undefined without a space. */
    function contextFor(space, ideasContext) {
        const key = typeof space === 'string' ? space.trim() : '';
        if (!key) return undefined;
        if (key === 'ideas' && ideasContext && typeof ideasContext === 'object' && !Array.isArray(ideasContext)) {
            return { ...ideasContext, space: 'ideas' };
        }
        return { space: key };
    }

    function isQuestion(response) {
        return !!response && typeof response === 'object'
            && (response.question === true || response.rueckfrage === true || response.verstanden === false);
    }

    /** { kind: 'antwort' | 'rueckfrage' | 'fehler', text } for an answer of the Brain. */
    function view(response) {
        const said = (value) => (typeof value === 'string' && value.trim() ? value.trim() : '');
        const text = response && typeof response === 'object' ? said(response.message) || said(response.final_text) : '';
        if (isQuestion(response)) return { kind: 'rueckfrage', text: text || 'Wie meinst du das?' };
        const failed = !response || typeof response !== 'object' || response.success === false || response.ok === false;
        if (failed) return { kind: 'fehler', text: text || NO_ANSWER };
        return { kind: 'antwort', text: text || 'OK' };
    }

    const api = { contextFor, isQuestion, view, NO_ANSWER };
    if (typeof module !== 'undefined' && module.exports) module.exports = api;
    else root.VibeSentenceAnswer = api;
})(typeof window !== 'undefined' ? window : globalThis);
