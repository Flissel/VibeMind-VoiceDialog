const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

// main.js cannot be loaded outside Electron, so these read its source.
const main = fs.readFileSync(path.join(__dirname, 'main.js'), 'utf8');

function handler(name) {
    const start = main.indexOf(`ipcMain.handle('${name}'`);
    assert.ok(start > 0, `${name} is registered`);
    const next = main.indexOf('ipcMain.handle(', start + 1);
    return main.slice(start, next > 0 ? next : undefined);
}

test('main.js hands no written-in value over as a password or sign-in name', () => {
    // a key followed directly by a non-empty quoted string: a value in the code instead of from the
    // environment (an empty '' as "nothing set" is fine)
    const literal = /\b(password|passwort|passwd|pwd|emailOrLdapLoginId|N8N_UI_PASSWORD)\s*[:=]\s*(['"`])(?!\2)/gi;
    const found = [...main.matchAll(literal)].map((m) => main.slice(0, m.index).split('\n').length);
    assert.deepEqual(found, [], `literal sign-in data in main.js on line(s) ${found.join(', ')}`);
});

test('the n8n editor signs in only with N8N_UI_EMAIL and N8N_UI_PASSWORD from the environment', () => {
    const body = handler('clawport:open-n8n-editor');
    assert.match(body, /process\.env\.N8N_UI_EMAIL/);
    assert.match(body, /process\.env\.N8N_UI_PASSWORD/);
    assert.match(body, /JSON\.stringify\(\{ emailOrLdapLoginId: email, password \}\)/, 'the account goes into the page as JSON');
    assert.doesNotMatch(body, /emailOrLdapLoginId:\s*['"`]/);
});

test('without the two values the editor opens at its sign-in page and says so calmly, no sign-in attempt', () => {
    const body = handler('clawport:open-n8n-editor');
    const missing = body.indexOf('if (!email || !password)');
    const attempt = body.indexOf("webContents.on('did-navigate'");
    assert.ok(missing > 0 && attempt > missing, 'the check comes before the sign-in is set up');
    const branch = body.slice(missing, body.indexOf('}', body.indexOf('return {', missing)) + 1);
    assert.match(branch, /return \{ success: true, autoLogin: false, message: '[^']*anmelden[^']*' \}/);
    assert.ok(body.indexOf('n8nWindow.loadURL(`${n8nUrl}/signin`)') < missing, 'the sign-in page is loaded either way');
    assert.doesNotMatch(branch, /throw|error:/i, 'no error, just a note');
});
