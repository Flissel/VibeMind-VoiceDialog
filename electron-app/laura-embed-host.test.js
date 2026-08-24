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
    opened,
    protocols,
    removed,
    revealed,
    unhandled,
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
  assert.equal(await fakes.handlers.get('laura:service-info')(), null);

  host.dispose();

  assert.deepEqual(fakes.removed, IPC_CHANNELS);
  assert.deepEqual(fakes.unhandled, ['laura-media']);
  assert.equal(fakes.handlers.size, 0);
  assert.equal(fakes.protocols.size, 0);
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

  assert.equal(await fakes.handlers.get('laura:pick-file')(), null);
  assert.equal(await fakes.handlers.get('laura:pick-file')(), path.join(workspace, 'one.mp4'));
  assert.equal(await fakes.handlers.get('laura:save-file')(null, 'notes.txt', 'first'), null);
  assert.equal(await fakes.handlers.get('laura:save-file')(null, 'notes.txt', 'saved'), savedPath);
  assert.equal(await fs.readFile(savedPath, 'utf8'), 'saved');
  assert.deepEqual(await fakes.handlers.get('laura:pick-files')(), [
    path.join(workspace, 'one.mp4'),
    path.join(workspace, 'two.wav'),
  ]);
  assert.equal(await fakes.handlers.get('laura:pick-folder')(), workspace);
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

  const result = await fakes.handlers.get('laura:list-media-in-folder')(null, workspace);

  assert.deepEqual(result.sort(), [
    path.join(workspace, 'clip.MP4'),
    path.join(workspace, 'sound.flac'),
  ].sort());
});

test('open and reveal reject outside paths and allow real paths inside the workspace', async (t) => {
  const { root, workspace } = await createWorkspace(t);
  const inside = path.join(workspace, 'clip.mp4');
  const outside = path.join(root, 'outside.mp4');
  await Promise.all([fs.writeFile(inside, ''), fs.writeFile(outside, '')]);
  const fakes = installFakes({ LAURA_WORKSPACE: workspace });

  assert.match(await fakes.handlers.get('laura:open-path')(null, outside), /^rejected:/);
  assert.match(await fakes.handlers.get('laura:reveal-path')(null, outside), /^rejected:/);
  assert.equal(await fakes.handlers.get('laura:open-path')(null, inside), '');
  assert.equal(await fakes.handlers.get('laura:reveal-path')(null, inside), '');
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

  const invalid = await handler(new Request('laura-media://media/asset-1/proxy', {
    headers: { Range: 'bytes=20-' },
  }));
  assert.equal(invalid.status, 416);
  assert.equal(invalid.headers.get('content-range'), 'bytes */10');
  assert.equal(requests.length, 2, 'only a successful safe path is cached');
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
