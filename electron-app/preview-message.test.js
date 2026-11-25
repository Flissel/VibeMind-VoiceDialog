// The live preview of a project: the name and the field the senders use are the ones the window reads.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const { TYPES, DEFAULT_VNC_URL, previewOf } = require('./renderer/preview-message');

const read = (...parts) => fs.readFileSync(path.join(__dirname, ...parts), 'utf8');

test('a ready message shows its address; without a usable one the sandbox screen on 6090', () => {
    assert.deepEqual(previewOf({ type: TYPES.ready, project_id: 'p-1', vnc_url: 'http://localhost:6123/vnc.html', port: 6123, project_title: 'Testprojekt' }),
        { url: 'http://localhost:6123/vnc.html', title: 'Testprojekt', projectId: 'p-1' });
    assert.equal(DEFAULT_VNC_URL, 'http://localhost:6090/vnc.html?autoconnect=true&resize=scale&reconnect=true');
    for (const vnc_url of [undefined, '', 'javascript:alert(1)', 'file:///c:/x', 'kein url']) {
        assert.equal(previewOf({ type: TYPES.ready, vnc_url }).url, DEFAULT_VNC_URL, String(vnc_url));
    }
    assert.deepEqual(previewOf(null), { url: DEFAULT_VNC_URL, title: 'Live-Vorschau', projectId: null });
});

test('the window handles each preview message under the name the senders use', () => {
    const html = read('renderer', 'index.html');
    for (const type of Object.values(TYPES)) assert.match(html, new RegExp(`case '${type}'`), type);
    assert.doesNotMatch(html, /case 'project-preview/, 'the old names with a dash are gone');
    assert.match(html, /window\.VibePreviewMessage\.previewOf\(message\)/);
    assert.ok(html.indexOf('src="preview-message.js"') > -1 && html.indexOf('src="preview-message.js"') < html.indexOf('src="vnc-preview.js"'));

    const handlers = read('renderer', 'handlers', 'project-handlers.js');
    for (const type of Object.values(TYPES)) assert.match(handlers, new RegExp(`H\\['${type}'\\]`), type);
});

test('Python and the main process send project_id and vnc_url, no longer projectId and vncUrl', () => {
    const python = read('..', 'python', 'ipc', 'project_manager.py');
    const pyBody = python.slice(python.indexOf('async def handle_start_project_preview'), python.indexOf('# -- Callbacks'));
    assert.doesNotMatch(pyBody, /"projectId"|"vncUrl"/);
    assert.match(pyBody, /"type": "project_preview_ready",\s*"project_id": project_id,\s*"vnc_url": vnc_url,\s*"port": vnc_port,/);
    for (const type of ['project_preview_ready', 'project_preview_error', 'project_preview_stopped']) assert.match(pyBody, new RegExp(`"type": "${type}"`));

    const main = read('main.js');
    const sends = main.match(/type: 'project_preview_\w+',\s*\n\s*\w+:/g) || [];
    assert.equal(sends.length, 4);
    for (const send of sends) assert.match(send, /project_id:$/, send);
    assert.match(main, /type: 'project_preview_ready',\s*project_id: projectId,\s*vnc_url: vncUrl,/);
});
