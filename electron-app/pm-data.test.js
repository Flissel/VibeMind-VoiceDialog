// The project manager in the entry "Auftraege". Fakes only: no real call, invented projects and keys.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const { pmConfig, rpcPayload, callTool, createPmOverview, createPmChat, NOT_REACHABLE, NOT_SET_UP, CHAT_NOT_SET_UP } = require('./pm-data');

const READ_KEY = 'erfundener-lese-schluessel';
const GATE_KEY = 'erfundener-gateway-schluessel';
const ENV = {
    PM_MCP_URL: 'http://127.0.0.1:18766/mcp', PM_TOKEN_ANZEIGE: READ_KEY,
    PM_CLAW_GATEWAY_URL: 'http://127.0.0.1:18896', PM_CLAW_GATEWAY_TOKEN: GATE_KEY, PM_CLAW_SITZUNG: 'agent:main:test:direct:0',
};

const stream = (value) => `event: message\ndata: ${JSON.stringify({ jsonrpc: '2.0', id: 1, result: { content: [{ type: 'text', text: JSON.stringify(value) }] } })}\n\n`;

const DIGEST = { projekte: [
    { slug: 'gartenhaus', phase: 'aufnahme', p1_offen: 2, entwuerfe_offen: 1, warnungen_offen: 0, phase_vorschlag: null },
    { slug: 'webshop', phase: 'angebot', p1_offen: 0, entwuerfe_offen: 0, warnungen_offen: 1, phase_vorschlag: 'umsetzung' },
] };
const VORGAENGE = {
    stand: '2026-11-25T10:00:00Z',
    entwuerfe_wartend: [{ id_kurz: 'ab12cd34', slug: 'gartenhaus', kanal: 'mail', art: 'runde', seit: '2026-11-25T08:00:00Z', betreff_laenge: 20, text_laenge: 400 }],
    mails: [{ zeit: '2026-11-25T09:30:00Z', richtung: 'ein', slug: 'webshop', art: 'eingang', betreff_laenge: 12 }],
    warnungen: [{ id_kurz: 'ef56ab78', slug: 'webshop', typ: 'widerspruch', feld_id: 'budget', seit: '2026-11-24T12:00:00Z' }],
    mails_unzugeordnet: 3,
};

function fakePost(answers) {
    const asked = [];
    const post = async (url, options) => {
        asked.push({ url, ...options, body: JSON.parse(options.body) });
        const answer = typeof answers === 'function' ? answers(url, JSON.parse(options.body)) : answers;
        if (answer instanceof Error) throw answer;
        return { headers: {}, ...answer };
    };
    return { post, asked };
}

const byTool = (map) => (_url, body) => map[body.params.name];

test('set up only with address and key; the chat only with all three', () => {
    assert.equal(pmConfig({}).overviewReady, false);
    assert.equal(pmConfig({ PM_MCP_URL: ENV.PM_MCP_URL }).overviewReady, false);
    assert.equal(pmConfig({ PM_MCP_URL: 'ftp://x', PM_TOKEN_ANZEIGE: READ_KEY }).overviewReady, false);
    assert.equal(pmConfig(ENV).overviewReady, true);
    assert.equal(pmConfig({ ...ENV, PM_CLAW_SITZUNG: ' ' }).chatReady, false);
    assert.equal(pmConfig(ENV).chatReady, true);
    assert.equal(pmConfig(ENV).chat.url, 'http://127.0.0.1:18896/v1/chat/completions');
});

test('the answer of pm-mcp: one data line of an event stream, its text parsed again', async () => {
    assert.deepEqual(rpcPayload(stream({ a: 1 })).result.content[0].text, '{"a":1}');
    const { post, asked } = fakePost({ status: 200, text: stream(DIGEST) });
    const result = await callTool(pmConfig(ENV).overview, 'digest', {}, post);
    assert.deepEqual(result, { ok: true, value: DIGEST });
    assert.equal(asked[0].url, ENV.PM_MCP_URL);
    assert.equal(asked[0].headers.Authorization, `Bearer ${READ_KEY}`);
    assert.equal(asked[0].headers.Accept, 'application/json, text/event-stream');
    assert.deepEqual(asked[0].body, { jsonrpc: '2.0', id: 1, method: 'tools/call', params: { name: 'digest', arguments: {} } });
    assert.equal(asked[0].timeoutMs, 10000);
});

test('the overview: phase, open fields, waiting drafts, warnings and the last mails per project', async () => {
    const { post, asked } = fakePost(byTool({ digest: { status: 200, text: stream(DIGEST) }, vorgaenge_lesen: { status: 200, text: stream(VORGAENGE) } }));
    const section = await createPmOverview({ env: ENV, post, now: () => new Date('2026-11-25T10:00:05Z') })();
    assert.deepEqual(asked.map((a) => a.body.params.name).sort(), ['digest', 'vorgaenge_lesen']);
    assert.equal(section.id, 'pm');
    assert.equal(section.state, 'ok');
    assert.equal(section.text, '2 aktive Projekte.');
    assert.equal(section.stand, '2026-11-25T10:00:05.000Z');
    const [projekte, entwuerfe, warnungen, vorgaenge] = section.groups;
    assert.deepEqual(projekte.items, [
        { title: 'gartenhaus', detail: 'Phase aufnahme · 2 Pflichtfelder offen · 1 Entwurf wartet' },
        { title: 'webshop', detail: 'Phase angebot · 1 Warnung · Vorschlag: umsetzung' },
    ]);
    assert.equal(entwuerfe.title, 'Wartende Entwürfe');
    assert.deepEqual(entwuerfe.items[0], { title: 'ab12cd34 · gartenhaus', detail: 'runde, mail · zum Freigeben im Chat: schick ab12cd34', zeit: '2026-11-25T08:00:00Z' });
    assert.deepEqual(warnungen.items[0], { title: 'widerspruch · webshop', detail: 'Feld budget', zeit: '2026-11-24T12:00:00Z' });
    assert.deepEqual(vorgaenge.items[0], { title: 'Eingang · webshop', detail: 'eingang', zeit: '2026-11-25T09:30:00Z' });
    assert.equal(vorgaenge.text, '3 Mails ohne Projekt.');
});

test('not set up, not reachable, wrong key, an error of the tool: a calm sentence, never the raw answer', async () => {
    const none = fakePost({ status: 200, text: '' });
    assert.equal((await createPmOverview({ env: {}, post: none.post })()).text, NOT_SET_UP);
    assert.equal(none.asked.length, 0, 'without key nothing is asked');

    const gone = fakePost(new Error('ECONNREFUSED'));
    const off = await createPmOverview({ env: ENV, post: gone.post })();
    assert.deepEqual([off.state, off.text], ['aus', NOT_REACHABLE]);

    const wrong = await createPmOverview({ env: ENV, post: fakePost({ status: 401, text: '' }).post })();
    assert.deepEqual([wrong.state, wrong.text], ['fehler', 'Schlüssel passt nicht.']);

    const raw = await createPmOverview({ env: ENV, post: fakePost({ status: 200, text: '<html>geheim</html>' }).post })();
    assert.equal(raw.text, NOT_REACHABLE);
    assert.doesNotMatch(JSON.stringify(raw), /geheim/);

    const db = await createPmOverview({ env: ENV, post: fakePost({ status: 200, text: stream({ fehler: 'Datenbank nicht erreichbar.' }) }).post })();
    assert.equal(db.text, NOT_REACHABLE);
    const other = await createPmOverview({ env: ENV, post: fakePost({ status: 200, text: stream({ fehler: 'Dieses Werkzeug darf die Anzeige nicht aufrufen.' }) }).post })();
    assert.equal(other.text, 'Dieses Werkzeug darf die Anzeige nicht aufrufen.');
});

test('when the service goes away the last data stays, with its time and the calm sentence', async () => {
    let up = true;
    const { post } = fakePost((_url, body) => (up
        ? { status: 200, text: stream(body.params.name === 'digest' ? DIGEST : VORGAENGE) }
        : new Error('timeout')));
    const read = createPmOverview({ env: ENV, post, now: () => new Date('2026-11-25T10:00:00Z') });
    await read();
    up = false;
    const later = await read();
    assert.equal(later.state, 'aus');
    assert.match(later.text, /^Projektmanager nicht erreichbar\./);
    assert.equal(later.stand, '2026-11-25T10:00:00.000Z');
    assert.equal(later.groups[0].items.length, 2);
});

test('the chat sends exactly one user message with the session key; the answer comes back as text', async () => {
    const { post, asked } = fakePost({ status: 200, text: JSON.stringify({ choices: [{ message: { role: 'assistant', content: '<b>Projekt gartenhaus</b> ist aktiv.' } }] }) });
    const chat = createPmChat({ env: ENV, post });
    assert.deepEqual(chat.state(), { aktiv: true, text: '' });
    assert.deepEqual(await chat.send('  Was ist offen?  '), { ok: true, antwort: '<b>Projekt gartenhaus</b> ist aktiv.' });
    const [call] = asked;
    assert.equal(call.url, 'http://127.0.0.1:18896/v1/chat/completions');
    assert.equal(call.headers.Authorization, `Bearer ${GATE_KEY}`);
    assert.equal(call.headers['x-openclaw-session-key'], ENV.PM_CLAW_SITZUNG);
    assert.equal(call.headers['x-openclaw-model'], undefined);
    assert.deepEqual(call.body, { model: 'openclaw/default', messages: [{ role: 'user', content: 'Was ist offen?' }] }, 'no history, no system message, no tools');
    assert.equal(call.timeoutMs, 5 * 60 * 1000);
});

test('the chat: not set up, empty text, one run at a time, and the refusals of the gateway', async () => {
    const none = createPmChat({ env: { ...ENV, PM_CLAW_GATEWAY_TOKEN: '' }, post: fakePost({}).post });
    assert.deepEqual(none.state(), { aktiv: false, text: CHAT_NOT_SET_UP });
    assert.equal((await none.send('hallo')).text, CHAT_NOT_SET_UP);

    let release;
    const slow = createPmChat({ env: ENV, post: () => new Promise((resolve) => { release = resolve; }) });
    assert.equal((await slow.send('   ')).text, 'Bitte zuerst etwas schreiben.');
    const first = slow.send('eins');
    assert.equal((await slow.send('zwei')).text, 'Die letzte Nachricht läuft noch.');
    release({ status: 200, headers: {}, text: JSON.stringify({ choices: [{ message: { content: 'ok' } }] }) });
    assert.equal((await first).antwort, 'ok');

    const said = (status, text = '', headers = {}) => createPmChat({ env: ENV, post: fakePost({ status, text, headers }).post, log: () => {} }).send('x');
    assert.equal((await said(401)).text, 'Schlüssel passt nicht.');
    assert.equal((await said(404)).text, 'Chat ist auf dem Server ausgeschaltet.');
    assert.equal((await said(405)).text, 'Chat ist auf dem Server ausgeschaltet.');
    assert.equal((await said(200, 'kein json')).text, NOT_REACHABLE);
    assert.equal((await createPmChat({ env: ENV, post: fakePost(new Error('weg')).post }).send('x')).text, NOT_REACHABLE);

    const lines = [];
    const bad = await createPmChat({ env: ENV, post: fakePost({ status: 400, text: JSON.stringify({ error: { message: 'session key not allowed' } }) }).post, log: (l) => lines.push(l) }).send('x');
    assert.equal(bad.text, 'Die Anfrage wurde abgelehnt.');
    assert.match(lines[0], /session key not allowed/);
    assert.doesNotMatch(lines.join('\n'), new RegExp(GATE_KEY), 'the key never goes into the log');

    let clock = 0;
    const busy = fakePost({ status: 429, text: '', headers: { 'retry-after': '30' } });
    const limited = createPmChat({ env: ENV, post: busy.post, nowMs: () => clock });
    assert.match((await limited.send('x')).text, /in 30 s/);
    clock = 10000;
    assert.match((await limited.send('x')).text, /in 20 s/);
    assert.equal(busy.asked.length, 1, 'waits as the gateway asks');
});

test('the page shows the card on top, the agent as text only, and builds no release button', () => {
    const page = fs.readFileSync(path.join(__dirname, 'auftraege', 'index.html'), 'utf8');
    const script = page.slice(page.indexOf('<script>'));
    assert.doesNotMatch(script, /innerHTML|outerHTML|insertAdjacentHTML|document\.write/, 'nothing goes in as HTML');
    assert.match(script, /nachricht\('pm', String\(antwort\.antwort\)\)/);
    assert.doesNotMatch(script, /'Freigeben'|"Freigeben"/);
    assert.match(script, /setInterval\(pmLaden, 60000\)/);
    assert.match(script, /window\.auftraege\.lesen\('pm'\)/);
    assert.doesNotMatch(page, /PM_TOKEN|PM_CLAW|18766|18896/, 'no key name, no address in the page');
});
