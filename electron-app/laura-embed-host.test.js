const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const os = require('node:os');
const path = require('node:path');

const { createLauraEmbedHost } = require('./laura-embed-host');

const IPC_CHANNELS = [
  'laura:service-info',
  'laura:pick-file',
  'laura:save-file',
  'laura:pick-files',
  'laura:pick-folder',
  'laura:list-media-in-folder',
  'laura:open-path',
  'laura:reveal-path',
];

function createFakes(env = {}, overrides = {}) {
  const trustedSender = { id: 'trusted-laura-renderer' };
  const event = { sender: trustedSender };
  const handlers = new Map();
  const removed = [];
  const protocols = new Map();
  const unhandled = [];
  const opened = [];
  const revealed = [];

  return {
    deps: {
      app: { getPath: () => 'C:\\fake-user-data', ...overrides.app },
      dialog: {
        showOpenDialog: async () => ({ canceled: true, filePaths: [] }),
        showSaveDialog: async () => ({ canceled: true }),
        ...overrides.dialog,
      },
      env,
      isAllowedSender: overrides.isAllowedSender || ((sender) => sender === trustedSender),
      ipcMain: {
        handle(channel, handler) {
          handlers.set(channel, handler);
        },
        removeHandler(channel) {
          removed.push(channel);
          handlers.delete(channel);
        },
      },
      logger: { warn() {}, ...overrides.logger },
      net: { fetch: async () => new Response('', { status: 404 }), ...overrides.net },
      now: overrides.now || (() => Date.now()),
      openFile: overrides.openFile,
      readdir: overrides.readdir,
      protocol: {
        handle(scheme, handler) {
          protocols.set(scheme, handler);
        },
        unhandle(scheme) {
          unhandled.push(scheme);
          protocols.delete(scheme);
        },
      },
      shell: {
        async openPath(candidate) {
          opened.push(candidate);
          return '';
        },
        showItemInFolder(candidate) {
          revealed.push(candidate);
        },
        ...overrides.shell,
      },
    },
    handlers,
    event,
    opened,
    protocols,
    removed,
    revealed,
    unhandled,
    trustedSender,
  };
}

function installFakes(env, overrides) {
  const fakes = createFakes(env, overrides);
  createLauraEmbedHost(fakes.deps).install();
  return fakes;
}

async function createWorkspace(t) {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), 'laura-host-'));
  const workspace = path.join(root, 'workspace');
  await fs.mkdir(workspace);
  t.after(() => fs.rm(root, { force: true, recursive: true }));
  return { root, workspace };
}

test('install registers the exact Laura surface and dispose removes it', async () => {
  const fakes = createFakes();
  const host = createLauraEmbedHost(fakes.deps);

  host.install();

  assert.deepEqual([...fakes.handlers.keys()], IPC_CHANNELS);
  assert.deepEqual([...fakes.protocols.keys()], ['laura-media']);
  assert.equal(await fakes.handlers.get('laura:service-info')(fakes.event), null);

  host.dispose();

  assert.deepEqual(fakes.removed, IPC_CHANNELS);
  assert.deepEqual(fakes.unhandled, ['laura-media']);
  assert.equal(fakes.handlers.size, 0);
  assert.equal(fakes.protocols.size, 0);
});

test('IPC rejects untrusted senders before service data or privileged handlers are reached', async () => {
  let dialogs = 0;
  const fakes = installFakes(
    { LAURA_TOKEN: 'top-secret' },
    { dialog: { showOpenDialog: async () => { dialogs += 1; return { canceled: true, filePaths: [] }; } } },
  );
  const untrusted = { sender: { id: 'other-renderer' } };

  for (const channel of IPC_CHANNELS) {
    await assert.rejects(async () => fakes.handlers.get(channel)(untrusted), /unauthorized/i, channel);
  }
  assert.equal(dialogs, 0);
  assert.deepEqual(
    await fakes.handlers.get('laura:service-info')(fakes.event),
    { baseUrl: 'http://127.0.0.1:8765', token: 'top-secret' },
  );
});

test('dialog handlers preserve Laura cancel and success semantics', async (t) => {
  const { workspace } = await createWorkspace(t);
  const savedPath = path.join(workspace, 'notes.txt');
  const openResults = [
    { canceled: true, filePaths: [] },
    { canceled: false, filePaths: [path.join(workspace, 'one.mp4')] },
    { canceled: false, filePaths: [path.join(workspace, 'one.mp4'), path.join(workspace, 'two.wav')] },
    { canceled: false, filePaths: [workspace] },
  ];
  const saveResults = [
    { canceled: true },
    { canceled: false, filePath: savedPath },
  ];
  const fakes = installFakes(
    { LAURA_WORKSPACE: workspace },
    {
      dialog: {
        showOpenDialog: async () => openResults.shift(),
        showSaveDialog: async () => saveResults.shift(),
      },
    },
  );

  assert.equal(await fakes.handlers.get('laura:pick-file')(fakes.event), null);
  assert.equal(await fakes.handlers.get('laura:pick-file')(fakes.event), path.join(workspace, 'one.mp4'));
  assert.equal(await fakes.handlers.get('laura:save-file')(fakes.event, 'notes.txt', 'first'), null);
  assert.equal(await fakes.handlers.get('laura:save-file')(fakes.event, 'notes.txt', 'saved'), savedPath);
  assert.equal(await fs.readFile(savedPath, 'utf8'), 'saved');
  assert.deepEqual(await fakes.handlers.get('laura:pick-files')(fakes.event), [
    path.join(workspace, 'one.mp4'),
    path.join(workspace, 'two.wav'),
  ]);
  assert.equal(await fakes.handlers.get('laura:pick-folder')(fakes.event), workspace);
});

test('list-media-in-folder returns only supported files', async (t) => {
  const { workspace } = await createWorkspace(t);
  await Promise.all([
    fs.writeFile(path.join(workspace, 'clip.MP4'), ''),
    fs.writeFile(path.join(workspace, 'sound.flac'), ''),
    fs.writeFile(path.join(workspace, 'notes.txt'), ''),
    fs.mkdir(path.join(workspace, 'nested.mov')),
  ]);
  const fakes = installFakes({ LAURA_WORKSPACE: workspace });

  const result = await fakes.handlers.get('laura:list-media-in-folder')(fakes.event, workspace);

  assert.deepEqual(result.sort(), [
    path.join(workspace, 'clip.MP4'),
    path.join(workspace, 'sound.flac'),
  ].sort());
});

test('folder listing rejects arbitrary outside paths but grants a canonically picked folder', async (t) => {
  const { root, workspace } = await createWorkspace(t);
  const outside = path.join(root, 'outside');
  await fs.mkdir(outside);
  await fs.writeFile(path.join(outside, 'clip.mp4'), 'media');
  let reads = 0;
  const fakes = installFakes(
    { LAURA_WORKSPACE: workspace },
    {
      dialog: { showOpenDialog: async () => ({ canceled: false, filePaths: [outside] }) },
      readdir: async (...args) => { reads += 1; return fs.readdir(...args); },
    },
  );

  await assert.rejects(
    fakes.handlers.get('laura:list-media-in-folder')(fakes.event, outside),
    /not authorized/i,
  );
  assert.equal(reads, 0);
  assert.equal(await fakes.handlers.get('laura:pick-folder')(fakes.event), await fs.realpath(outside));
  assert.deepEqual(
    await fakes.handlers.get('laura:list-media-in-folder')(fakes.event, outside),
    [path.join(await fs.realpath(outside), 'clip.mp4')],
  );
  assert.equal(reads, 1);
});

test('open and reveal reject outside paths and allow real paths inside the workspace', async (t) => {
  const { root, workspace } = await createWorkspace(t);
  const inside = path.join(workspace, 'clip.mp4');
  const outside = path.join(root, 'outside.mp4');
  await Promise.all([fs.writeFile(inside, ''), fs.writeFile(outside, '')]);
  const fakes = installFakes({ LAURA_WORKSPACE: workspace });

  assert.match(await fakes.handlers.get('laura:open-path')(fakes.event, outside), /^rejected:/);
  assert.match(await fakes.handlers.get('laura:reveal-path')(fakes.event, outside), /^rejected:/);
  assert.equal(await fakes.handlers.get('laura:open-path')(fakes.event, inside), '');
  assert.equal(await fakes.handlers.get('laura:reveal-path')(fakes.event, inside), '');
  assert.deepEqual(fakes.opened, [inside]);
  assert.deepEqual(fakes.revealed, [inside]);
});

test('media protocol fails closed for bad URLs, missing auth, and unknown media', async (t) => {
  const { workspace } = await createWorkspace(t);
  let fetches = 0;
  const unauthenticated = installFakes({ LAURA_WORKSPACE: workspace }, {
    net: { fetch: async () => { fetches += 1; return new Response('{}'); } },
  });
  const unauthenticatedHandler = unauthenticated.protocols.get('laura-media');

  assert.equal((await unauthenticatedHandler(new Request('laura-media://media/only-one-part'))).status, 400);
  assert.equal((await unauthenticatedHandler(new Request('laura-media://media/asset/source'))).status, 404);
  assert.equal(fetches, 0);

  const authenticated = installFakes(
    { LAURA_TOKEN: 'top-secret', LAURA_URL: 'http://laura.test', LAURA_WORKSPACE: workspace },
    { net: { fetch: async () => new Response('{}', { status: 404 }) } },
  );
  assert.equal(
    (await authenticated.protocols.get('laura-media')(
      new Request('laura-media://media/unknown/source'),
    )).status,
    404,
  );
});

test('media protocol sends auth, rejects unsafe API paths, and streams full and ranged files', async (t) => {
  const { root, workspace } = await createWorkspace(t);
  const mediaPath = path.join(workspace, 'audio.mp3');
  const outsidePath = path.join(root, 'outside.mp3');
  await Promise.all([fs.writeFile(mediaPath, '0123456789'), fs.writeFile(outsidePath, 'outside')]);
  const requests = [];
  let assetPath = outsidePath;
  const fakes = installFakes(
    { LAURA_TOKEN: 'top-secret', LAURA_URL: 'http://laura.test', LAURA_WORKSPACE: workspace },
    {
      net: {
        fetch: async (url, options) => {
          requests.push({ url, options });
          return Response.json({ files: [{ kind: 'proxy', path: assetPath }] });
        },
      },
    },
  );
  const handler = fakes.protocols.get('laura-media');

  assert.equal((await handler(new Request('laura-media://media/asset-1/proxy'))).status, 404);
  assetPath = mediaPath;
  const full = await handler(new Request('laura-media://media/asset-1/proxy'));
  assert.equal(full.status, 200);
  assert.equal(full.headers.get('content-type'), 'audio/mpeg');
  assert.equal(full.headers.get('content-length'), '10');
  assert.equal(await full.text(), '0123456789');
  assert.equal(requests.length, 2);
  assert.equal(requests[0].url, 'http://laura.test/assets/asset-1');
  assert.equal(requests[0].options.headers['X-Laura-Token'], 'top-secret');

  const partial = await handler(new Request('laura-media://media/asset-1/proxy', {
    headers: { Range: 'bytes=2-5' },
  }));
  assert.equal(partial.status, 206);
  assert.equal(partial.headers.get('content-range'), 'bytes 2-5/10');
  assert.equal(partial.headers.get('content-length'), '4');
  assert.equal(await partial.text(), '2345');

  const suffix = await handler(new Request('laura-media://media/asset-1/proxy', {
    headers: { Range: 'bytes=-4' },
  }));
  assert.equal(suffix.status, 206);
  assert.equal(suffix.headers.get('content-range'), 'bytes 6-9/10');
  assert.equal(await suffix.text(), '6789');

  const oversizedSuffix = await handler(new Request('laura-media://media/asset-1/proxy', {
    headers: { Range: 'bytes=-20' },
  }));
  assert.equal(oversizedSuffix.status, 206);
  assert.equal(oversizedSuffix.headers.get('content-range'), 'bytes 0-9/10');
  assert.equal(await oversizedSuffix.text(), '0123456789');

  const invalid = await handler(new Request('laura-media://media/asset-1/proxy', {
    headers: { Range: 'bytes=20-' },
  }));
  assert.equal(invalid.status, 416);
  assert.equal(invalid.headers.get('content-range'), 'bytes */10');
  assert.equal((await handler(new Request('laura-media://media/asset-1/proxy', {
    headers: { Range: 'bytes=0-1,4-5' },
  }))).status, 416);
  assert.equal(requests.length, 2, 'only a successful safe path is cached');
});

test('media protocol preserves content types for supported media containers', async (t) => {
  const { workspace } = await createWorkspace(t);
  const cases = [
    ['wav', 'audio/wav'],
    ['mp3', 'audio/mpeg'],
    ['m4a', 'audio/mp4'],
    ['aac', 'audio/aac'],
    ['flac', 'audio/flac'],
    ['aif', 'audio/aiff'],
    ['aiff', 'audio/aiff'],
    ['webm', 'video/webm'],
    ['mov', 'video/quicktime'],
    ['mkv', 'video/x-matroska'],
    ['avi', 'video/x-msvideo'],
    ['mpg', 'video/mpeg'],
    ['mpeg', 'video/mpeg'],
    ['mp4', 'video/mp4'],
    ['m4v', 'video/mp4'],
    ['mxf', 'application/mxf'],
    ['unknown', 'application/octet-stream'],
  ];
  const mediaPaths = new Map();
  await Promise.all(cases.map(async ([extension]) => {
    const mediaPath = path.join(workspace, `sample.${extension}`);
    mediaPaths.set(extension, mediaPath);
    await fs.writeFile(mediaPath, extension);
  }));
  const fakes = installFakes(
    { LAURA_TOKEN: 'top-secret', LAURA_URL: 'http://laura.test', LAURA_WORKSPACE: workspace },
    {
      net: {
        fetch: async (url) => {
          const assetId = new URL(url).pathname.split('/').pop();
          return Response.json({ files: [{ kind: 'source', path: mediaPaths.get(assetId) }] });
        },
      },
    },
  );
  const handler = fakes.protocols.get('laura-media');

  for (const [extension, expectedContentType] of cases) {
    const response = await handler(new Request(`laura-media://media/${extension}/source`));
    assert.equal(response.status, 200);
    assert.equal(response.headers.get('content-type'), expectedContentType, extension);
    await response.arrayBuffer();
  }
});

test('media cache expires and refetches after five seconds', async (t) => {
  const { workspace } = await createWorkspace(t);
  const mediaPath = path.join(workspace, 'clip.mp4');
  await fs.writeFile(mediaPath, 'clip');
  let clock = 1000;
  let fetches = 0;
  const fakes = installFakes(
    { LAURA_TOKEN: 'token', LAURA_URL: 'http://laura.test', LAURA_WORKSPACE: workspace },
    {
      now: () => clock,
      net: { fetch: async () => { fetches += 1; return Response.json({ files: [{ kind: 'source', path: mediaPath }] }); } },
    },
  );
  const handler = fakes.protocols.get('laura-media');

  await (await handler(new Request('laura-media://media/asset/source'))).arrayBuffer();
  clock = 5999;
  await (await handler(new Request('laura-media://media/asset/source'))).arrayBuffer();
  assert.equal(fetches, 1);
  clock = 6000;
  await (await handler(new Request('laura-media://media/asset/source'))).arrayBuffer();
  assert.equal(fetches, 2);
});

test('a missing cached file is evicted so a later backend path can recover', async (t) => {
  const { workspace } = await createWorkspace(t);
  const firstPath = path.join(workspace, 'first.mp4');
  const recoveredPath = path.join(workspace, 'recovered.mp4');
  await Promise.all([fs.writeFile(firstPath, 'first'), fs.writeFile(recoveredPath, 'recovered')]);
  let backendPath = firstPath;
  let fetches = 0;
  const fakes = installFakes(
    { LAURA_TOKEN: 'token', LAURA_URL: 'http://laura.test', LAURA_WORKSPACE: workspace },
    { net: { fetch: async () => { fetches += 1; return Response.json({ files: [{ kind: 'source', path: backendPath }] }); } } },
  );
  const handler = fakes.protocols.get('laura-media');

  assert.equal(await (await handler(new Request('laura-media://media/asset/source'))).text(), 'first');
  await fs.rm(firstPath);
  assert.equal((await handler(new Request('laura-media://media/asset/source'))).status, 404);
  backendPath = recoveredPath;
  assert.equal(await (await handler(new Request('laura-media://media/asset/source'))).text(), 'recovered');
  assert.equal(fetches, 3);
});

test('media streaming uses the opened file handle and closes it for invalid ranges', async (t) => {
  const { workspace } = await createWorkspace(t);
  const mediaPath = path.join(workspace, 'clip.mp4');
  await fs.writeFile(mediaPath, '0123');
  const openedPaths = [];
  let closes = 0;
  const realHandle = await fs.open(mediaPath, 'r');
  const fakes = installFakes(
    { LAURA_TOKEN: 'token', LAURA_URL: 'http://laura.test', LAURA_WORKSPACE: workspace },
    {
      net: { fetch: async () => Response.json({ files: [{ kind: 'source', path: mediaPath }] }) },
      openFile: async (candidate) => {
        openedPaths.push(candidate);
        return {
          stat: () => realHandle.stat(),
          createReadStream: (options) => realHandle.createReadStream(options),
          close: async () => { closes += 1; await realHandle.close(); },
        };
      },
    },
  );

  const response = await fakes.protocols.get('laura-media')(new Request(
    'laura-media://media/asset/source',
    { headers: { Range: 'bytes=20-' } },
  ));
  assert.equal(response.status, 416);
  assert.deepEqual(openedPaths, [await fs.realpath(mediaPath)]);
  assert.equal(closes, 1);
});

test('export lane rechecks pending exports and streams only ready workspace files', async (t) => {
  const { workspace } = await createWorkspace(t);
  const exportPath = path.join(workspace, 'render.mp4');
  await fs.writeFile(exportPath, 'rendered');
  let status = 'rendering';
  const requests = [];
  const fakes = installFakes(
    { LAURA_TOKEN: 'export-token', LAURA_URL: 'http://laura.test', LAURA_WORKSPACE: workspace },
    {
      net: {
        fetch: async (url, options) => {
          requests.push({ url, options });
          return Response.json({ status, path: exportPath });
        },
      },
    },
  );
  const handler = fakes.protocols.get('laura-media');

  assert.equal((await handler(new Request('laura-media://media/export/export-7'))).status, 404);
  status = 'ready';
  const ready = await handler(new Request('laura-media://media/export/export-7'));
  assert.equal(ready.status, 200);
  assert.equal(await ready.text(), 'rendered');
  assert.equal(requests.length, 2);
  assert.equal(requests[0].url, 'http://laura.test/exports/export-7');
  assert.equal(requests[0].options.headers['X-Laura-Token'], 'export-token');
});
