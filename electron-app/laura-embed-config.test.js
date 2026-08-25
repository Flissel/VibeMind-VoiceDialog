const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const {
  LAURA_SESSION_PARTITION,
  isAllowedLauraIpcEvent,
  isInsideWorkspace,
  readLauraServiceInfo,
  resolveInsideWorkspace,
  resolveLauraRendererPath,
} = require('./laura-embed-config');

test('Laura uses a dedicated persistent Electron session partition', () => {
  assert.equal(LAURA_SESSION_PARTITION, 'persist:laura');
});

test('main installs Laura host on its isolated session protocol with a sender boundary', () => {
  const mainSource = fs.readFileSync(path.join(__dirname, 'main.js'), 'utf8');

  assert.match(mainSource, /\bsession\b/);
  assert.match(mainSource, /session\.fromPartition\(LAURA_SESSION_PARTITION\)\.protocol/);
  assert.match(
    mainSource,
    /isAllowedSender:\s*\(event\)\s*=>\s*isAllowedLauraIpcEvent\(/,
  );
  assert.match(mainSource, /pathToFileURL\(resolveLauraRendererPath\(/);
});

test('Laura IPC accepts only its exact local main frame', () => {
  const rendererUrl = 'file:///C:/Laura/index.html';
  const mainFrame = { url: rendererUrl };
  const webContents = { mainFrame };

  assert.equal(isAllowedLauraIpcEvent({ sender: webContents, senderFrame: mainFrame }, webContents, rendererUrl), true);
  assert.equal(
    isAllowedLauraIpcEvent(
      { sender: webContents, senderFrame: { url: rendererUrl } },
      webContents,
      rendererUrl,
    ),
    false,
    'subframes are rejected even when they belong to the same webContents',
  );
  mainFrame.url = 'https://remote.example/laura';
  assert.equal(isAllowedLauraIpcEvent({ sender: webContents, senderFrame: mainFrame }, webContents, rendererUrl), false);
  mainFrame.url = `${rendererUrl}?unexpected=1`;
  assert.equal(isAllowedLauraIpcEvent({ sender: webContents, senderFrame: mainFrame }, webContents, rendererUrl), false);
});

function rendererPaths() {
  const dirname = path.resolve('fixtures', 'voice', 'electron-app');
  const resourcesPath = path.resolve('fixtures', 'resources');
  return {
    development: path.resolve(
      dirname,
      '..',
      '..',
      'spaces',
      'video',
      'laura',
      'apps',
      'desktop',
      'dist',
      'index.html',
    ),
    dirname,
    packaged: path.join(resourcesPath, 'laura-renderer', 'index.html'),
    resourcesPath,
  };
}

test('renderer resolution prefers the packaged Laura resource', () => {
  const { development, dirname, packaged, resourcesPath } = rendererPaths();
  const existing = new Set([packaged, development]);

  const result = resolveLauraRendererPath({
    dirname,
    resourcesPath,
    existsSync: (candidate) => existing.has(candidate),
  });

  assert.equal(result, packaged);
});

test('renderer resolution falls back to the Laura development build', () => {
  const { development, dirname, resourcesPath } = rendererPaths();

  const result = resolveLauraRendererPath({
    dirname,
    resourcesPath,
    existsSync: (candidate) => candidate === development,
  });

  assert.equal(result, development);
});

test('renderer resolution gives a clear build instruction when both builds are absent', () => {
  const { development, dirname, resourcesPath } = rendererPaths();

  assert.throws(
    () => resolveLauraRendererPath({ dirname, resourcesPath, existsSync: () => false }),
    {
      message: `Laura renderer missing; run pnpm laura:build (checked ${development})`,
    },
  );
});

test('service info fails closed without a non-empty Laura token', () => {
  assert.equal(readLauraServiceInfo({}), null);
  assert.equal(readLauraServiceInfo({ LAURA_TOKEN: '' }), null);
  assert.equal(readLauraServiceInfo({ LAURA_TOKEN: '   ' }), null);
});

test('service info uses the explicit Laura URL when authenticated', () => {
  assert.deepEqual(
    readLauraServiceInfo({ LAURA_URL: 'http://localhost:9000', LAURA_TOKEN: 'secret' }),
    { baseUrl: 'http://localhost:9000', token: 'secret' },
  );
});

test('service info defaults to localhost and the configured or default port', () => {
  assert.deepEqual(
    readLauraServiceInfo({ LAURA_TOKEN: 'secret' }),
    { baseUrl: 'http://127.0.0.1:8765', token: 'secret' },
  );
  assert.deepEqual(
    readLauraServiceInfo({ LAURA_PORT: '9876', LAURA_TOKEN: 'secret' }),
    { baseUrl: 'http://127.0.0.1:9876', token: 'secret' },
  );
});

test('workspace guard accepts Windows drive roots and descendants case-insensitively', () => {
  const realpathSync = (value) => value;

  assert.equal(
    isInsideWorkspace(
      'C:\\Laura\\Workspace',
      'c:\\laura\\workspace\\Exports\\clip.mp4',
      'win32',
      realpathSync,
    ),
    true,
  );
  assert.equal(
    isInsideWorkspace('C:\\Laura\\Workspace', 'c:\\LAURA\\WORKSPACE', 'win32', realpathSync),
    true,
  );
});

test('workspace guard uses POSIX path semantics independently of the host', () => {
  const realpathSync = (value) => value;

  assert.equal(
    isInsideWorkspace('/srv/laura/workspace', '/srv/laura/workspace/clip.mp4', 'linux', realpathSync),
    true,
  );
});

test('workspace guard rejects relative Windows paths and prefix siblings', () => {
  const root = 'C:\\Laura\\Workspace';
  const realpathSync = (value) => value;

  assert.equal(isInsideWorkspace(root, '', 'win32', realpathSync), false);
  assert.equal(isInsideWorkspace(root, 'exports\\clip.mp4', 'win32', realpathSync), false);
  assert.equal(
    isInsideWorkspace('Laura\\Workspace', 'C:\\Laura\\Workspace\\clip.mp4', 'win32', realpathSync),
    false,
  );
  assert.equal(
    isInsideWorkspace(root, 'C:\\Laura\\Workspace-evil\\clip.mp4', 'win32', realpathSync),
    false,
  );
});

test('workspace guard rejects a junction or symlink escape after resolving real paths', () => {
  const root = 'C:\\Laura\\Workspace';
  const candidate = 'C:\\Laura\\Workspace\\linked\\clip.mp4';
  const realpathSync = (value) => {
    if (value === root) return 'C:\\Real\\Workspace';
    if (value === candidate) return 'D:\\Outside\\clip.mp4';
    throw new Error('unexpected path');
  };

  assert.equal(isInsideWorkspace(root, candidate, 'win32', realpathSync), false);
  assert.equal(resolveInsideWorkspace(root, candidate, 'win32', realpathSync), null);
});

test('workspace resolution returns the canonical real target inside the workspace', () => {
  const root = '/srv/laura/workspace-link';
  const candidate = '/srv/laura/workspace-link/clip.mp4';
  const realpathSync = (value) => {
    if (value === root) return '/real/laura/workspace';
    if (value === candidate) return '/real/laura/workspace/clip.mp4';
    throw new Error('unexpected path');
  };

  assert.equal(
    resolveInsideWorkspace(root, candidate, 'linux', realpathSync),
    '/real/laura/workspace/clip.mp4',
  );
  assert.equal(isInsideWorkspace(root, candidate, 'linux', realpathSync), true);
});

test('workspace guard fails closed when default realpath resolution fails', () => {
  const root = path.resolve('fixtures', 'missing-workspace-for-realpath-test');
  const candidate = path.join(root, 'clip.mp4');

  assert.equal(isInsideWorkspace(root, candidate), false);
});
