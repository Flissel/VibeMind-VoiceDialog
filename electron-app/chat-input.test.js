// eingabe: "getippt" goes to the Brain only for a sentence a person typed into a chat field of the app.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const { chatContext, chatMessage, withoutTypedMark, withProof, TYPED, PROOF_ENV } = require('./chat-input');

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
    const given = { space: 'ideas', eingabe: 'getippt' };
    chatContext(given, false);
    assert.equal(given.eingabe, 'getippt', 'the context of the renderer is not changed in place');
});

test('only a typed sentence of the main process carries the proof of this start', () => {
    assert.deepEqual(chatMessage('Öffne den Rechner', { space: 'desktop' }, true, 'p'),
        { type: 'chat_text_input', text: 'Öffne den Rechner', context: { space: 'desktop', eingabe: 'getippt' }, eingabe_beleg: 'p' });
    assert.deepEqual(chatMessage('Öffne den Rechner', { space: 'desktop', eingabe: 'getippt' }, false, 'p'),
        { type: 'chat_text_input', text: 'Öffne den Rechner', context: { space: 'desktop' } });
    assert.deepEqual(chatMessage('x', undefined, false, 'p'), { type: 'chat_text_input', text: 'x' });
    // the proof is random per start and goes to Python through its environment
    const env = withProof({ A: '1' }, 'p');
    assert.deepEqual(env, { A: '1', [PROOF_ENV]: 'p' });
    assert.equal(PROOF_ENV, 'VIBEMIND_EINGABE_BELEG');
    const real = chatMessage('x', undefined, true).eingabe_beleg;
    assert.match(real, /^[0-9a-f]{64}$/);
});

test('the generic to-python channel cannot claim a typed sentence', () => {
    const forged = { type: 'chat_text_input', text: 'Öffne den Rechner', context: { space: 'desktop', eingabe: 'getippt' }, eingabe_beleg: 'geraten' };
    assert.deepEqual(withoutTypedMark(forged), { type: 'chat_text_input', text: 'Öffne den Rechner', context: { space: 'desktop' } });
    assert.equal(forged.eingabe_beleg, 'geraten', 'the message of the sender is not changed in place');
    assert.deepEqual(withoutTypedMark({ type: 'get_bubbles' }), { type: 'get_bubbles' });
    assert.equal(withoutTypedMark(null), null);

    const main = fs.readFileSync(path.join(__dirname, 'main.js'), 'utf8');
    const flowzen = fs.readFileSync(path.join(__dirname, 'flowzen-manager.js'), 'utf8');
    assert.match(main, /sendToPython\(withoutTypedMark\(message\)\)/);
    assert.match(flowzen, /this\.sendToPython\(withoutTypedMark\(message\)\)/);
    assert.match(main, /env: withProof\(pythonEnv\)/);
    assert.match(main, /eingabe_beleg: '\*\*\*'/, 'the proof is never shown in the IPC log of the renderer');
    // the ClawPort channel never carries a context, so never the mark
    const clawport = main.slice(main.indexOf("ipcMain.handle('clawport:chat-text-input'"), main.indexOf("ipcMain.handle('clawport:chat-text-input'") + 300);
    assert.doesNotMatch(clawport, /eingabe|typed|chatMessage/);
});

test('only the trusted send of the two chat fields says "typed"; code calls do not', () => {
    const chat = fs.readFileSync(path.join(__dirname, 'renderer', 'ideas-chat.js'), 'utf8');
    const scene = fs.readFileSync(path.join(__dirname, 'renderer', 'multiverse.js'), 'utf8');
    assert.match(chat, /submit\(text, \{ typed: event\.isTrusted === true \}\)/);
    assert.match(chat, /async function submit\(text, \{ typed = false \} = \{\}\)/, 'a call from code is not typed');
    assert.match(scene, /this\.sendGameConsoleMessage\(\{ typed: e\.isTrusted === true \}\);/);
    assert.match(scene, /sendBtn\.addEventListener\('click', \(e\) => this\.sendGameConsoleMessage\(\{ typed: e\.isTrusted === true \}\)\)/);
    assert.match(scene, /async sendGameConsoleMessage\(\{ typed = false \} = \{\}\)/);
    assert.equal((scene.match(/sendGameConsoleMessage\(/g) || []).length, 3);
});

// The preload in a stand-in for its isolated world: which sends count as typed.
function preload() {
    let now = 1000;
    const listeners = {};
    const fields = {
        'gc-input': { id: 'gc-input', value: '' },
        'ideas-chat-input': { id: 'ideas-chat-input', value: '' },
    };
    const invoked = [];
    let exposed = null;
    const navigator = { userActivation: { isActive: true } };
    const window = { addEventListener(type, fn) { (listeners[type] = listeners[type] || []).push(fn); } };
    const context = {
        window, navigator, process: { env: {} },
        document: { getElementById: (id) => fields[id] || null },
        Date: { now: () => now },
        require(name) {
            if (name !== 'electron') throw new Error('not here: ' + name);
            return {
                contextBridge: { exposeInMainWorld(key, api) { if (key === 'vibemind') exposed = api; } },
                ipcRenderer: {
                    sendSync: () => ({}), send() {}, on() {}, removeListener() {}, removeAllListeners() {},
                    invoke(channel, payload) { invoked.push({ channel, payload }); return Promise.resolve({}); },
                },
            };
        },
        console,
    };
    context.globalThis = context;
    vm.runInNewContext(fs.readFileSync(path.join(__dirname, 'preload.js'), 'utf8'), context);
    const fire = (type, event) => { for (const fn of listeners[type] || []) fn(event); };
    return {
        fields, navigator,
        advance(ms) { now += ms; },
        enter(id, trusted = true) { fire('keydown', { isTrusted: trusted, key: 'Enter', shiftKey: false, target: fields[id] }); },
        clickSend(trusted = true) {
            const button = { id: 'gc-send-btn', type: 'button', closest: (sel) => (sel === 'button' ? button : null) };
            fire('click', { isTrusted: trusted, target: button });
        },
        send(text, typed) { exposed.sendChatMessage(text, undefined, typed); return invoked[invoked.length - 1].payload.typed; },
    };
}

test('the preload counts a sentence as typed only after a trusted Enter or click on the chat field with that very text', () => {
    const p = preload();
    p.fields['gc-input'].value = ' Öffne den Rechner ';
    p.enter('gc-input');
    assert.equal(p.send('Öffne den Rechner', true), true);
    assert.equal(p.send('Öffne den Rechner', true), false, 'one key press, one sentence');

    p.fields['ideas-chat-input'].value = 'Öffne den Rechner';
    p.enter('ideas-chat-input');
    assert.equal(p.send('Lösche alles', true), false, 'another text than the one in the field');

    p.fields['gc-input'].value = 'Öffne den Rechner';
    p.clickSend();
    assert.equal(p.send('Öffne den Rechner', true), true, 'the send button');
});

test('a script of the page gets no typed sentence', () => {
    const p = preload();
    // no event at all, only the claim
    assert.equal(p.send('Öffne den Rechner', true), false);
    // an event raised by a script is not trusted
    p.fields['gc-input'].value = 'Öffne den Rechner';
    p.enter('gc-input', false);
    assert.equal(p.send('Öffne den Rechner', true), false);
    p.clickSend(false);
    assert.equal(p.send('Öffne den Rechner', true), false);
    // too late after the key press
    p.enter('gc-input');
    p.advance(2001);
    assert.equal(p.send('Öffne den Rechner', true), false);
    // without a gesture the browser knows of
    p.enter('gc-input');
    p.navigator.userActivation.isActive = false;
    assert.equal(p.send('Öffne den Rechner', true), false);
    // the chat field itself did not claim it
    p.navigator.userActivation.isActive = true;
    p.enter('gc-input');
    assert.equal(p.send('Öffne den Rechner', false), false);
});
