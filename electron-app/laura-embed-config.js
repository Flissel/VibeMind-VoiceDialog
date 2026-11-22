const fs = require('node:fs');
const path = require('node:path');

const LAURA_SESSION_PARTITION = 'persist:laura';

function isAllowedLauraIpcEvent(event, webContents, rendererUrl) {
  if (!event || !webContents || typeof rendererUrl !== 'string') return false;
  let expectedUrl;
  try {
    expectedUrl = new URL(rendererUrl);
  } catch {
    return false;
  }
  if (expectedUrl.protocol !== 'file:' || expectedUrl.search || expectedUrl.hash) return false;
  return event.sender === webContents
    && event.senderFrame === webContents.mainFrame
    && event.senderFrame?.url === expectedUrl.href;
}

function resolveLauraRendererPath({ dirname, resourcesPath, existsSync }) {
  const packaged = path.join(resourcesPath || '', 'laura-renderer', 'index.html');
  const development = path.resolve(
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
  );

  if (resourcesPath && existsSync(packaged)) return packaged;
  if (existsSync(development)) return development;
  throw new Error(`Laura renderer missing; run pnpm laura:build (checked ${development})`);
}

function readLauraServiceInfo(env) {
  const token = typeof env.LAURA_TOKEN === 'string' && env.LAURA_TOKEN.trim() !== '' ? env.LAURA_TOKEN : '';
  const explicitUrl = typeof env.LAURA_URL === 'string' ? env.LAURA_URL.trim() : '';
  // Fails closed without a token, as before. One deliberate exception: the operator names the
  // service (LAURA_URL) AND states that it runs without a token (LAURA_ALLOW_NO_TOKEN=1). The
  // API only checks X-Laura-Token when it was started with LAURA_TOKEN.
  const tokenless = explicitUrl !== '' && env.LAURA_ALLOW_NO_TOKEN === '1';
  if (!token && !tokenless) return null;

  return {
    baseUrl: explicitUrl || `http://127.0.0.1:${env.LAURA_PORT || '8765'}`,
    token,
  };
}

function canonicalRealPath(value, pathApi, platform, realpathSync) {
  const resolved = realpathSync(value);
  if (typeof resolved !== 'string') throw new TypeError('realpath resolver must return a string');
  return pathApi.normalize(resolved);
}

function resolveInsideWorkspace(
  root,
  candidate,
  platform = process.platform,
  realpathSync = fs.realpathSync.native,
) {
  if (typeof root !== 'string' || typeof candidate !== 'string' || !root || !candidate) {
    return null;
  }

  const pathApi = platform === 'win32' ? path.win32 : path.posix;
  if (!pathApi.isAbsolute(root) || !pathApi.isAbsolute(candidate)) return null;

  try {
    const canonicalRootPath = canonicalRealPath(root, pathApi, platform, realpathSync);
    const canonicalCandidate = canonicalRealPath(candidate, pathApi, platform, realpathSync);
    const canonicalRoot = platform === 'win32' ? canonicalRootPath.toLowerCase() : canonicalRootPath;
    const candidateForComparison = platform === 'win32'
      ? canonicalCandidate.toLowerCase()
      : canonicalCandidate;
    const prefix = canonicalRoot.endsWith(pathApi.sep)
      ? canonicalRoot
      : canonicalRoot + pathApi.sep;
    return candidateForComparison === canonicalRoot || candidateForComparison.startsWith(prefix)
      ? canonicalCandidate
      : null;
  } catch {
    return null;
  }
}

function isInsideWorkspace(root, candidate, platform, realpathSync) {
  return Boolean(resolveInsideWorkspace(root, candidate, platform, realpathSync));
}

module.exports = {
  LAURA_SESSION_PARTITION,
  isAllowedLauraIpcEvent,
  isInsideWorkspace,
  readLauraServiceInfo,
  resolveInsideWorkspace,
  resolveLauraRendererPath,
};
