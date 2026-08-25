const fs = require('node:fs');
const { open, readdir, writeFile } = require('node:fs/promises');
const path = require('node:path');
const { Readable } = require('node:stream');

const { readLauraServiceInfo, resolveInsideWorkspace } = require('./laura-embed-config');

const CACHE_TTL_MS = 5000;

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

const MEDIA_EXTENSIONS = new Set([
  '.mp4', '.mov', '.mkv', '.m4v', '.avi', '.webm', '.mxf', '.mpg', '.mpeg',
  '.wav', '.aif', '.aiff', '.flac', '.mp3', '.m4a', '.aac',
]);

const MEDIA_FILTERS = [
  {
    name: 'Media',
    extensions: ['mp4', 'mov', 'mkv', 'm4v', 'avi', 'webm', 'mxf', 'wav', 'mp3', 'aac', 'flac'],
  },
  { name: 'All Files', extensions: ['*'] },
];

function contentTypeFor(filePath) {
  const extension = path.extname(filePath).toLowerCase();
  if (extension === '.wav') return 'audio/wav';
  if (extension === '.mp3') return 'audio/mpeg';
  if (extension === '.m4a') return 'audio/mp4';
  if (extension === '.aac') return 'audio/aac';
  if (extension === '.flac') return 'audio/flac';
  if (extension === '.aif' || extension === '.aiff') return 'audio/aiff';
  if (extension === '.webm') return 'video/webm';
  if (extension === '.mov') return 'video/quicktime';
  if (extension === '.mkv') return 'video/x-matroska';
  if (extension === '.avi') return 'video/x-msvideo';
  if (extension === '.mpg' || extension === '.mpeg') return 'video/mpeg';
  if (extension === '.mxf') return 'application/mxf';
  if (extension === '.mp4' || extension === '.m4v') return 'video/mp4';
  return 'application/octet-stream';
}

function createLauraEmbedHost({
  app,
  dialog,
  env,
  ipcMain,
  isAllowedSender,
  net,
  now = Date.now,
  openFile = open,
  protocol,
  readdir: readDirectory = readdir,
  realpathSync = fs.realpathSync.native,
  shell,
}) {
  const serviceInfo = readLauraServiceInfo(env);
  const workspaceRoot = env.LAURA_WORKSPACE || path.join(app.getPath('userData'), 'laura-workspace');
  const mediaPathCache = new Map();
  const exportPathCache = new Map();
  const authorizedDirectories = new Set();
  let installed = false;

  function safeWorkspacePath(candidate) {
    return resolveInsideWorkspace(workspaceRoot, candidate, process.platform, realpathSync);
  }

  function canonicalExistingPath(candidate) {
    if (typeof candidate !== 'string' || !path.isAbsolute(candidate)) return null;
    try {
      return path.normalize(realpathSync(candidate));
    } catch {
      return null;
    }
  }

  function canonicalDirectoryKey(candidate) {
    return process.platform === 'win32' ? candidate.toLowerCase() : candidate;
  }

  function readCachedPath(cache, key) {
    const cached = cache.get(key);
    if (!cached) return null;
    if (now() >= cached.expiresAt) {
      cache.delete(key);
      return null;
    }
    const safePath = safeWorkspacePath(cached.path);
    if (!safePath) cache.delete(key);
    return safePath;
  }

  function cachePath(cache, key, filePath) {
    cache.set(key, { path: filePath, expiresAt: now() + CACHE_TTL_MS });
  }

  function evictCachedPath(filePath) {
    for (const cache of [mediaPathCache, exportPathCache]) {
      for (const [key, entry] of cache) {
        if (entry.path === filePath) cache.delete(key);
      }
    }
  }

  async function fetchJson(url) {
    if (!serviceInfo) return null;
    try {
      const response = await net.fetch(url, {
        headers: { 'X-Laura-Token': serviceInfo.token },
      });
      if (!response.ok) return null;
      return await response.json();
    } catch {
      return null;
    }
  }

  async function resolveMediaPath(assetId, kind) {
    const key = `${assetId}/${kind}`;
    const cached = readCachedPath(mediaPathCache, key);
    if (cached) return cached;

    const asset = await fetchJson(
      `${serviceInfo?.baseUrl || ''}/assets/${encodeURIComponent(assetId)}`,
    );
    if (!asset || !Array.isArray(asset.files)) return null;
    const file = asset.files.find((candidate) => candidate && candidate.kind === kind);
    const safePath = file && typeof file.path === 'string' ? safeWorkspacePath(file.path) : null;
    if (!safePath) return null;
    cachePath(mediaPathCache, key, safePath);
    return safePath;
  }

  async function resolveExportPath(exportId) {
    const cached = readCachedPath(exportPathCache, exportId);
    if (cached) return cached;

    const exported = await fetchJson(
      `${serviceInfo?.baseUrl || ''}/exports/${encodeURIComponent(exportId)}`,
    );
    if (!exported || exported.status !== 'ready' || typeof exported.path !== 'string') return null;
    const safePath = safeWorkspacePath(exported.path);
    if (!safePath) return null;
    cachePath(exportPathCache, exportId, safePath);
    return safePath;
  }

  function rangeNotSatisfiable(total, headers) {
    return new Response('range not satisfiable', {
      status: 416,
      headers: { ...headers, 'Content-Range': `bytes */${total}` },
    });
  }

  async function handleMedia(request) {
    let url;
    try {
      url = new URL(request.url);
    } catch {
      return new Response('bad media url', { status: 400 });
    }
    if (url.host !== 'media') return new Response('bad media url', { status: 400 });

    let parts;
    try {
      parts = url.pathname.split('/').filter(Boolean).map(decodeURIComponent);
    } catch {
      return new Response('bad media url', { status: 400 });
    }
    if (parts.length !== 2 || !parts[0] || !parts[1]) {
      return new Response('bad media url', { status: 400 });
    }

    const filePath = parts[0] === 'export'
      ? await resolveExportPath(parts[1])
      : await resolveMediaPath(parts[0], parts[1]);
    if (!filePath) return new Response('media not found', { status: 404 });

    let fileHandle;
    try {
      fileHandle = await openFile(filePath, 'r');
    } catch {
      evictCachedPath(filePath);
      return new Response('media missing on disk', { status: 404 });
    }

    let total;
    try {
      total = (await fileHandle.stat()).size;
    } catch {
      await fileHandle.close().catch(() => {});
      evictCachedPath(filePath);
      return new Response('media missing on disk', { status: 404 });
    }

    const baseHeaders = {
      'Accept-Ranges': 'bytes',
      'Content-Type': contentTypeFor(filePath),
    };
    const rangeHeader = request.headers.get('Range');
    let start = 0;
    let end = total - 1;
    let status = 200;
    if (rangeHeader !== null) {
      const match = /^bytes=(?:(\d+)-(\d*)|-(\d+))$/.exec(rangeHeader);
      if (!match) {
        await fileHandle.close().catch(() => {});
        return rangeNotSatisfiable(total, baseHeaders);
      }
      if (match[3] !== undefined) {
        const suffixLength = Number(match[3]);
        if (!Number.isSafeInteger(suffixLength) || suffixLength <= 0 || total === 0) {
          await fileHandle.close().catch(() => {});
          return rangeNotSatisfiable(total, baseHeaders);
        }
        start = Math.max(total - suffixLength, 0);
      } else {
        start = Number(match[1]);
        const requestedEnd = match[2] === '' ? total - 1 : Number(match[2]);
        end = Math.min(requestedEnd, total - 1);
        if (!Number.isSafeInteger(start) || !Number.isSafeInteger(requestedEnd)
            || start >= total || start > end) {
          await fileHandle.close().catch(() => {});
          return rangeNotSatisfiable(total, baseHeaders);
        }
      }
      status = 206;
    }

    try {
      const stream = fileHandle.createReadStream({ start, end, autoClose: true });
      return new Response(Readable.toWeb(stream), {
        status,
        headers: status === 206
          ? {
            ...baseHeaders,
            'Content-Length': String(end - start + 1),
            'Content-Range': `bytes ${start}-${end}/${total}`,
          }
          : { ...baseHeaders, 'Content-Length': String(total) },
      });
    } catch {
      await fileHandle.close().catch(() => {});
      evictCachedPath(filePath);
      return new Response('media missing on disk', { status: 404 });
    }
  }

  const handlers = new Map([
    ['laura:service-info', () => serviceInfo],
    ['laura:pick-file', async () => {
      const result = await dialog.showOpenDialog({
        properties: ['openFile'],
        filters: MEDIA_FILTERS,
      });
      return result.canceled || result.filePaths.length === 0 ? null : result.filePaths[0];
    }],
    ['laura:save-file', async (_event, defaultName, content) => {
      const result = await dialog.showSaveDialog({ defaultPath: defaultName });
      if (result.canceled || !result.filePath) return null;
      await writeFile(result.filePath, content, 'utf8');
      return result.filePath;
    }],
    ['laura:pick-files', async () => {
      const result = await dialog.showOpenDialog({ properties: ['openFile', 'multiSelections'] });
      return result.canceled ? [] : result.filePaths;
    }],
    ['laura:pick-folder', async () => {
      const result = await dialog.showOpenDialog({ properties: ['openDirectory'] });
      if (result.canceled || result.filePaths.length === 0) return null;
      const selected = canonicalExistingPath(result.filePaths[0]);
      if (!selected) return null;
      authorizedDirectories.add(canonicalDirectoryKey(selected));
      return selected;
    }],
    ['laura:list-media-in-folder', async (_event, folder) => {
      const canonicalFolder = canonicalExistingPath(folder);
      const allowedByWorkspace = canonicalFolder && safeWorkspacePath(canonicalFolder);
      const allowedByGrant = canonicalFolder
        && authorizedDirectories.has(canonicalDirectoryKey(canonicalFolder));
      if (!canonicalFolder || (!allowedByWorkspace && !allowedByGrant)) {
        throw new Error('folder is not authorized');
      }
      const entries = await readDirectory(canonicalFolder, { withFileTypes: true });
      return entries
        .filter((entry) => entry.isFile() && MEDIA_EXTENSIONS.has(path.extname(entry.name).toLowerCase()))
        .map((entry) => path.join(canonicalFolder, entry.name));
    }],
    ['laura:open-path', async (_event, candidate) => {
      const safePath = safeWorkspacePath(candidate);
      if (!safePath) return 'rejected: path is outside the workspace';
      await shell.openPath(safePath);
      return '';
    }],
    ['laura:reveal-path', (_event, candidate) => {
      const safePath = safeWorkspacePath(candidate);
      if (!safePath) return 'rejected: path is outside the workspace';
      shell.showItemInFolder(safePath);
      return '';
    }],
  ]);

  return {
    install() {
      if (installed) return;
      for (const [channel, handler] of handlers) {
        ipcMain.handle(channel, async (event, ...args) => {
          if (typeof isAllowedSender !== 'function' || !isAllowedSender(event?.sender)) {
            throw new Error('unauthorized Laura IPC sender');
          }
          return handler(event, ...args);
        });
      }
      protocol.handle('laura-media', handleMedia);
      installed = true;
    },
    dispose() {
      if (!installed) return;
      for (const channel of IPC_CHANNELS) ipcMain.removeHandler(channel);
      protocol.unhandle('laura-media');
      mediaPathCache.clear();
      exportPathCache.clear();
      authorizedDirectories.clear();
      installed = false;
    },
  };
}

module.exports = { createLauraEmbedHost };
