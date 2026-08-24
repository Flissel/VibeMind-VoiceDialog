const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const {
  isInsideWorkspace,
  readLauraServiceInfo,
  resolveLauraRendererPath,
} = require('./laura-embed-config');

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
  const { dirname, resourcesPath } = rendererPaths();

  assert.throws(
    () => resolveLauraRendererPath({ dirname, resourcesPath, existsSync: () => false }),
    /Laura renderer missing; run (?:npm run|pnpm) laura:build/,
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

test('workspace guard accepts the root and descendants', () => {
  const root = path.resolve('fixtures', 'workspace');

  assert.equal(isInsideWorkspace(root, root), true);
  assert.equal(isInsideWorkspace(root, path.join(root, 'exports', 'clip.mp4')), true);
});

test('workspace guard rejects empty, relative, and prefix-sibling candidates', () => {
  const root = path.resolve('fixtures', 'workspace');

  assert.equal(isInsideWorkspace(root, ''), false);
  assert.equal(isInsideWorkspace(root, path.join('exports', 'clip.mp4')), false);
  assert.equal(isInsideWorkspace(root, `${root}-evil${path.sep}clip.mp4`), false);
});

test('workspace guard compares Windows paths case-insensitively', () => {
  const root = path.resolve('fixtures', 'Workspace');
  const candidate = path.join(root.toUpperCase(), 'Exports', 'clip.mp4');

  assert.equal(isInsideWorkspace(root.toLowerCase(), candidate, 'win32'), true);
});
