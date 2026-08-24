const { createReadStream } = require('node:fs');
const { readdir, stat, writeFile } = require('node:fs/promises');
const path = require('node:path');
const { Readable } = require('node:stream');

const { isInsideWorkspace, readLauraServiceInfo } = require('./laura-embed-config');

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
  if (extension === '.m4a' || extension === '.aac') return 'audio/aac';
  if (extension === '.flac') return 'audio/flac';
  return 'video/mp4';
}

function createLauraEmbedHost({ app, dialog, env, ipcMain, net, protocol, shell }) {
  const serviceInfo = readLauraServiceInfo(env);
  const workspaceRoot = env.LAURA_WORKSPACE || path.join(app.getPath('userData'), 'laura-workspace');
  const mediaPathCache = new Map();
  const exportPathCache = new Map();
  let installed = false;

  function safeWorkspacePath(candidate) {
    return isInsideWorkspace(workspaceRoot, candidate) ? path.resolve(candidate) : null;
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
    const cached = mediaPathCache.get(key);
    if (cached) return safeWorkspacePath(cached);

    const asset = await fetchJson(
      `${serviceInfo?.baseUrl || ''}/assets/${encodeURIComponent(assetId)}`,
    );
    if (!asset || !Array.isArray(asset.files)) return null;
    const file = asset.files.find((candidate) => candidate && candidate.kind === kind);
    const safePath = file && typeof file.path === 'string' ? safeWorkspacePath(file.path) : null;
    if (!safePath) return null;
    mediaPathCache.set(key, safePath);
    return safePath;
  }

  async function resolveExportPath(exportId) {
    const cached = exportPathCache.get(exportId);
    if (cached) return safeWorkspacePath(cached);

    const exported = await fetchJson(
      `${serviceInfo?.baseUrl || ''}/exports/${encodeURIComponent(exportId)}`,
    );
    if (!exported || exported.status !== 'ready' || typeof exported.path !== 'string') return null;
    const safePath = safeWorkspacePath(exported.path);
    if (!safePath) return null;
    exportPathCache.set(exportId, safePath);
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

    let total;
    try {
      total = (await stat(filePath)).size;
    } catch {
      return new Response('media missing on disk', { status: 404 });
    }

    const baseHeaders = {
      'Accept-Ranges': 'bytes',
      'Content-Type': contentTypeFor(filePath),
    };
    const rangeHeader = request.headers.get('Range');
    if (rangeHeader !== null) {
      const match = /^bytes=(\d+)-(\d*)$/.exec(rangeHeader);
      if (!match) return rangeNotSatisfiable(total, baseHeaders);
      const start = Number(match[1]);
      const requestedEnd = match[2] === '' ? total - 1 : Number(match[2]);
      const end = Math.min(requestedEnd, total - 1);
      if (!Number.isSafeInteger(start) || !Number.isSafeInteger(requestedEnd)
          || start >= total || start > end) {
        return rangeNotSatisfiable(total, baseHeaders);
      }
      return new Response(Readable.toWeb(createReadStream(filePath, { start, end })), {
        status: 206,
        headers: {
          ...baseHeaders,
          'Content-Length': String(end - start + 1),
          'Content-Range': `bytes ${start}-${end}/${total}`,
        },
      });
    }

    return new Response(Readable.toWeb(createReadStream(filePath)), {
      status: 200,
      headers: { ...baseHeaders, 'Content-Length': String(total) },
    });
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
      return result.canceled || result.filePaths.length === 0 ? null : result.filePaths[0];
    }],
    ['laura:list-media-in-folder', async (_event, folder) => {
      const entries = await readdir(folder, { withFileTypes: true });
      return entries
        .filter((entry) => entry.isFile() && MEDIA_EXTENSIONS.has(path.extname(entry.name).toLowerCase()))
        .map((entry) => path.join(folder, entry.name));
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
      for (const [channel, handler] of handlers) ipcMain.handle(channel, handler);
      protocol.handle('laura-media', handleMedia);
      installed = true;
    },
    dispose() {
      if (!installed) return;
      for (const channel of IPC_CHANNELS) ipcMain.removeHandler(channel);
      protocol.unhandle('laura-media');
      mediaPathCache.clear();
      exportPathCache.clear();
      installed = false;
    },
  };
}

module.exports = { createLauraEmbedHost };
