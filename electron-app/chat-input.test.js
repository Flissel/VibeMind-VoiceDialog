// eingabe: "getippt" goes to the Brain only for a sentence a person typed into a chat field of the app.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const { chatContext, TYPED } = require('./chat-input');

test('a sentence the person sent from a chat field carries eingabe "getippt"', () => {
    assert.equal(TYPED, 'getippt');
    assert.deepEqual(chatContext({ space: 'ideas', bubble: null }, true), { space: 'ideas', bubble: null, eingabe: 'getippt' });
    // outside the Ideas space the console sends no context of its own: the mark alone goes
    assert.deepEqual(chatContext(undefined, true), { eingabe: 'getippt' });
});

test('anything not sent by the person carries no eingabe, even when the context brings one along', () => {
    for (const typed of [false, undefined, 'true', 1, null]) {
        assert.equal(chatContext(undefined, typed), undefined, String(typed));
        assert.deepEqual(chatContext({ space: 'ideas', eingabe: 'getippt' }, typed), { space: 'ideas' }, String(typed));
        assert.equal(chatContext({ eingabe: 'getippt' }, typed), undefined, String(typed));
    }
    // the context of the renderer is not changed in place
    const given = { space: 'ideas', eingabe: 'getippt' };
    chatContext(given, false);
    assert.equal(given.eingabe, 'getippt');
});

test('only the trusted send of the two chat fields says "typed"; code calls and the dashboard do not', () => {
    const dir = __dirname;
    const chat = fs.readFileSync(path.join(dir, 'renderer', 'ideas-chat.js'), 'utf8');
    const scene = fs.readFileSync(path.join(dir, 'renderer', 'multiverse.js'), 'utf8');
    const main = fs.readFileSync(path.join(dir, 'main.js'), 'utf8');

    // Ideas chat: the form submit, raised by the browser
    assert.match(chat, /submit\(text, \{ typed: event\.isTrusted === true \}\)/);
    assert.match(chat, /async function submit\(text, \{ typed = false \} = \{\}\)/, 'a call from code is not typed');
    // console below the scene: Enter and the send button
    assert.match(scene, /this\.sendGameConsoleMessage\(\{ typed: e\.isTrusted === true \}\);/);
    assert.match(scene, /sendBtn\.addEventListener\('click', \(e\) => this\.sendGameConsoleMessage\(\{ typed: e\.isTrusted === true \}\)\)/);
    assert.match(scene, /async sendGameConsoleMessage\(\{ typed = false \} = \{\}\)/);
    // no other caller in the renderer passes typed
    assert.equal((scene.match(/sendGameConsoleMessage\(/g) || []).length, 3);
    // the ClawPort channel never carries a context, so never the mark
    const clawport = main.slice(main.indexOf("ipcMain.handle('clawport:chat-text-input'"), main.indexOf("ipcMain.handle('clawport:chat-text-input'") + 300);
    assert.match(clawport, /\{ type: 'chat_text_input', text \}/);
    assert.doesNotMatch(clawport, /eingabe|typed/);
});
