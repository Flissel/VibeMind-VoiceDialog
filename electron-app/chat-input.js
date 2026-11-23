/**
 * The context a sentence from the chat of the app carries to the Brain.
 *
 * `eingabe: "getippt"` tells the Brain that a person typed the sentence into a chat field of the
 * app and sent it themselves. The Brain lets a Desktop task run only then. So the mark is set here,
 * in the main process, and nowhere else: whatever `eingabe` a context brings along is dropped, and
 * it is set only when the chat field reported a send by the person (`typed === true`, from a
 * trusted keyboard or click event). Voice, follow-ups, repeats by the app and anything automatic
 * never set it.
 */
'use strict';

const TYPED = 'getippt';

/**
 * @param {unknown} context   what the renderer sends (open bubble, cards), may be missing
 * @param {unknown} typed     true only for a send by the person in a chat field
 * @returns {object|undefined} the context to pass on, undefined when there is nothing to pass
 */
function chatContext(context, typed) {
    const base = context && typeof context === 'object' && !Array.isArray(context) ? { ...context } : {};
    delete base.eingabe;
    if (typed === true) base.eingabe = TYPED;
    return Object.keys(base).length ? base : undefined;
}

module.exports = { chatContext, TYPED };
