const path = require('node:path');

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
  const token = env.LAURA_TOKEN;
  if (typeof token !== 'string' || token.trim() === '') return null;

  return {
    baseUrl: env.LAURA_URL || `http://127.0.0.1:${env.LAURA_PORT || '8765'}`,
    token,
  };
}

function canonical(value, platform) {
  const resolved = path.resolve(value);
  return platform === 'win32' ? resolved.toLowerCase() : resolved;
}

function isInsideWorkspace(root, candidate, platform = process.platform) {
  if (!root || !candidate || !path.isAbsolute(root) || !path.isAbsolute(candidate)) return false;

  const canonicalRoot = canonical(root, platform);
  const canonicalCandidate = canonical(candidate, platform);
  const prefix = canonicalRoot.endsWith(path.sep) ? canonicalRoot : canonicalRoot + path.sep;
  return canonicalCandidate === canonicalRoot || canonicalCandidate.startsWith(prefix);
}

module.exports = { isInsideWorkspace, readLauraServiceInfo, resolveLauraRendererPath };
