/**
 * The context a sentence from the chat of the app carries to the Brain.
 *
 * `eingabe: "getippt"` tells the Brain that a person typed the sentence into a chat field of the
 * app and sent it themselves. The Brain lets a Desktop task run only then. So the mark is set here,
 * in the main process, and nowhere else: whatever `eingabe` a context brings along is dropped, and
 * it is set only when the chat field reported a send by the person (`typed === true`). Voice,
 * follow-ups, repeats by the app and anything automatic never set it.
 *
 * Python cannot tell where a message came from: the generic `to-python` channel lets any page
 * forward any message. So a typed sentence also carries `eingabe_beleg`, a random value that
 * only this main process knows and hands to the Python process in its environment at spawn
 * (VIBEMIND_EINGABE_BELEG). Python keeps the mark only with that value (python/ipc/clawport_handlers.py).
 */
'use strict';

const crypto = require('crypto');

const TYPED = 'getippt';
const PROOF_ENV = 'VIBEMIND_EINGABE_BELEG';
const PROOF = crypto.randomBytes(32).toString('hex'); // new with every start, never sent to a renderer

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

/** The message for Python for a sentence of a chat field of the app. */
function chatMessage(text, context, typed, proof = PROOF) {
    const message = { type: 'chat_text_input', text };
    const passed = chatContext(context, typed);
    if (passed) message.context = passed;
    if (passed && passed.eingabe === TYPED) message.eingabe_beleg = proof;
    return message;
}

/**
 * A message from the generic `to-python` channel never carries the mark nor the proof: only
 * chatMessage() of the main process may. Returns a cleaned copy (or the message as it is).
 */
function withoutTypedMark(message) {
    if (!message || typeof message !== 'object' || Array.isArray(message)) return message;
    const clean = { ...message };
    delete clean.eingabe_beleg;
    if (clean.context && typeof clean.context === 'object' && !Array.isArray(clean.context) && 'eingabe' in clean.context) {
        clean.context = { ...clean.context };
        delete clean.context.eingabe;
    }
    return clean;
}

/** The environment of the Python process with the proof of this start. */
function withProof(env, proof = PROOF) {
    return { ...env, [PROOF_ENV]: proof };
}

module.exports = { chatContext, chatMessage, withoutTypedMark, withProof, TYPED, PROOF_ENV };
