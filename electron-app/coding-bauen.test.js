// K8: "Ja, bauen" of the coding way is signed by the main process, after a real input of the person in the
// visible window, once per question. Invented ids and keys, no real data.
const test = require('node:test');
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const { EventEmitter } = require('node:events');
const { createCodingConfirm, createInputWitness, zeichen, isBuildYes, HEADER, TEXT } = require('./coding-bauen');

const read = (...parts) => fs.readFileSync(path.join(__dirname, ...parts), 'utf8');
const KEY = 'k'.repeat(48);
const FRAGE = '0123456789abcdef0123456789abcdef';

/** A fake http.request that records the request and answers with `reply`. */
function fakeRequest(reply) {
  const sent = [];
  const request = (options, onResponse) => {
    const req = new EventEmitter();
    let data = '';
    req.write = (chunk) => { data += chunk.toString('utf8'); };
    req.end = () => {
      sent.push({ options, body: JSON.parse(data) });
      const res = new EventEmitter();
      onResponse(res);
      res.statusCode = 200;
      res.emit('data', Buffer.from(JSON.stringify(reply)));
      res.emit('end');
    };
    req.destroy = () => {};
    return req;
  };
  return { request, sent };
}

function setup({ reply = { ok: true, final_text: 'Ich baue es.', plan_id: 'p1' }, visible = true, remote = false, env = { VIBEMIND_EINGABE_SCHLUESSEL: KEY, BRAIN_PORT: '5000' } } = {}) {
  let clock = 1795600000000;
  const fake = fakeRequest(reply);
  const confirm = createCodingConfirm({ env, nowMs: () => clock, request: fake.request, isVisible: () => visible, remoteOpen: () => remote });
  const contents = new EventEmitter();
  confirm.watch(contents);
  const press = () => contents.emit('input-event', {}, { type: 'keyDown', key: 'Enter' });
  return { confirm, fake, press, tick: (ms) => { clock += ms; }, now: () => clock };
}

test('the sign: "<sec>.<hmac>" over "<sec>\\ncoding-bauen <frage_id>" with the shared key', () => {
  const expected = crypto.createHmac('sha256', KEY).update(`1795600000\ncoding-bauen ${FRAGE}`).digest('hex');
  assert.equal(zeichen(KEY, FRAGE, 1795600000.9), `1795600000.${expected}`);
  // the same sign as the Brain makes it (core/desktop_tagesrest.eingabe_zeichen over core/coding_auftrag.beleg_satz),
  // computed once in Python for this invented key and frage_id
  assert.equal(zeichen(KEY, FRAGE, 1795600000),
    '1795600000.ce50e27d5aea82d1de32cd6657d2e9ad2ee70d2c61f3c48fc0c6a8e694b9228e');
});

test('"Ja, bauen" in every form the Brain counts (core/coding_auftrag.py _JA); nothing else', () => {
  for (const text of ['Ja, bauen', 'ja bauen', 'Ja, bauen!', 'Ja bau', 'Ja, baue es', 'Ja bitte bauen', 'Ja, starte den Bau',
    'Ja, start den Bau.', '„Ja, bauen“', '"Ja, bauen."', '  JA, BAUEN … ']) {
    assert.equal(isBuildYes(text), true, text);
  }
  for (const text of ['Ja', 'Bauen', 'Ja, bau mir eine App', 'Nein, nicht bauen', 'Ja, erledigen', 'Ja bauen wir später', null]) {
    assert.equal(isBuildYes(text), false, String(text));
  }
});

test('the key is read trimmed, as the Brain reads it; a short key signs nothing', async () => {
  const s = setup({ env: { VIBEMIND_EINGABE_SCHLUESSEL: `  ${KEY}\n`, BRAIN_PORT: '5000' } });
  s.confirm.remember({ coding_frage: FRAGE });
  s.press();
  await s.confirm.confirm('Ja, bauen');
  assert.equal(s.fake.sent[0].options.headers[HEADER], zeichen(KEY, FRAGE, s.now() / 1000));
  const short = setup({ env: { VIBEMIND_EINGABE_SCHLUESSEL: 'k'.repeat(31) } });
  short.confirm.remember({ coding_frage: FRAGE });
  short.press();
  assert.equal((await short.confirm.confirm('Ja, bauen')).message, TEXT.keinSchluessel);
  assert.equal(short.fake.sent.length, 0);
});

test('the question of the Brain is kept; the page gets the answer without its id', () => {
  const s = setup();
  const shown = s.confirm.remember({ type: 'chat_response', success: false, question: true, message: 'Soll ich bauen?', coding_frage: FRAGE });
  assert.deepEqual(shown, { type: 'chat_response', success: false, question: true, message: 'Soll ich bauen?' });
  assert.equal(s.confirm.handles('Ja, bauen', true), true);
  assert.equal(s.confirm.handles('Ja, bauen', false), false, 'not a sentence of the person');
  assert.equal(s.confirm.handles('Ja', true), false);
  const other = setup();
  other.confirm.remember({ coding_frage: 'nicht-hex' });
  assert.equal(other.confirm.handles('Ja, bauen', true), false);
});

test('after a real input: the main process sends "Ja, bauen" with frage_id, space projects and the sign', async () => {
  const s = setup();
  s.confirm.remember({ coding_frage: FRAGE });
  s.press();
  const result = await s.confirm.confirm('Ja, bauen');
  assert.deepEqual(result, { type: 'chat_response', success: true, message: 'Ich baue es.', plan_id: 'p1' });
  const [call] = s.fake.sent;
  assert.equal(call.options.host, '127.0.0.1');
  assert.equal(call.options.port, 5000);
  assert.equal(call.options.path, '/api/multihop/execute');
  assert.deepEqual(call.body, { intent: 'Ja, bauen', context: { space: 'projects', frage_id: FRAGE } });
  assert.equal(call.options.headers[HEADER], zeichen(KEY, FRAGE, s.now() / 1000));
  assert.equal('Origin' in call.options.headers, false);
  assert.equal('Sec-Fetch-Site' in call.options.headers, false);
  assert.equal(s.confirm.handles('Ja, bauen', true), false, 'the question is used once');
});

test('no real input, an old input, a hidden window or test mode: nothing goes out, a clear sentence', async () => {
  const none = setup();
  none.confirm.remember({ coding_frage: FRAGE });
  assert.equal((await none.confirm.confirm('Ja, bauen')).message, TEXT.keineEingabe);
  const late = setup();
  late.confirm.remember({ coding_frage: FRAGE });
  late.press(); late.tick(2000);
  assert.equal((await late.confirm.confirm('Ja, bauen')).message, TEXT.keineEingabe);
  const hidden = setup({ visible: false });
  hidden.confirm.remember({ coding_frage: FRAGE });
  hidden.press();
  assert.equal((await hidden.confirm.confirm('Ja, bauen')).message, TEXT.keineEingabe);
  const remote = setup({ remote: true });
  remote.confirm.remember({ coding_frage: FRAGE });
  remote.press();
  assert.equal((await remote.confirm.confirm('Ja, bauen')).message, TEXT.pruefmodus);
  const nokey = setup({ env: {} });
  nokey.confirm.remember({ coding_frage: FRAGE });
  nokey.press();
  assert.equal((await nokey.confirm.confirm('Ja, bauen')).message, TEXT.keinSchluessel);
  for (const s of [none, late, hidden, remote, nokey]) assert.equal(s.fake.sent.length, 0);
});

test('the question expires after 300 s', () => {
  const s = setup();
  s.confirm.remember({ coding_frage: FRAGE });
  s.tick(300001);
  assert.equal(s.confirm.handles('Ja, bauen', true), false);
});

test('the Brain says nicht_belegt: the chat gets a clear sentence', async () => {
  const s = setup({ reply: { ok: false, grund: 'nicht_belegt' } });
  s.confirm.remember({ coding_frage: FRAGE });
  s.press();
  assert.deepEqual(await s.confirm.confirm('Ja, bauen'), { type: 'chat_response', success: false, message: TEXT.nichtBelegt });
});

test('the witness takes Enter or a left press, each once', () => {
  let clock = 0;
  const w = createInputWitness(() => clock);
  w.record({ type: 'keyDown', key: 'a' });
  assert.equal(w.take(), false);
  w.record({ type: 'mouseDown', button: 'right' });
  assert.equal(w.take(), false);
  w.record({ type: 'mouseDown', button: 'left' });
  assert.equal(w.take(), true);
  assert.equal(w.take(), false);
});

test('main.js: the confirmation is handled before Python, every Python answer passes remember()', () => {
  const main = read('main.js');
  assert.match(main, /if \(codingConfirm\.handles\(text, typed\)\) return await codingConfirm\.confirm\(text\);/);
  assert.match(main, /const answer = codingConfirm\.remember\(await sendToPythonAndWait\(message,/);
  assert.match(main, /codingConfirm\.watch\(mainWindow\.webContents\);/);
  assert.match(main, /remoteOpen: \(\) => REMOTE_CONTROL_OPEN,/);
});
