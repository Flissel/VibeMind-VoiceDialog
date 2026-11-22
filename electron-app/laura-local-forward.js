/**
 * Makes a Laura service on another machine reachable as a local one.
 *
 * The Laura page only lets itself talk to this machine (its Content-Security-Policy
 * allows http://127.0.0.1:* and localhost). When the service runs elsewhere (LAURA_URL
 * names another host), the page could never reach it. Instead of weakening the page,
 * the app forwards a local port to the service: the page keeps talking to 127.0.0.1,
 * the bytes go to the real host. The forward listens on 127.0.0.1 only, and the
 * service still checks X-Laura-Token.
 */
const net = require('node:net');

function isLoopback(hostname) {
  return hostname === '127.0.0.1' || hostname === 'localhost' || hostname === '[::1]' || hostname === '::1';
}

/** The remote target of LAURA_URL, or null when it is unset, invalid or already local. */
function remoteTarget(env = process.env) {
  const raw = typeof env.LAURA_URL === 'string' ? env.LAURA_URL.trim() : '';
  if (!raw) return null;
  let url;
  try {
    url = new URL(raw);
  } catch (_) {
    return null;
  }
  if (url.protocol !== 'http:' || isLoopback(url.hostname)) return null; // TLS would need its own handling
  return { host: url.hostname, port: Number(url.port || 80) };
}

/**
 * Starts the forward. Resolves with { url, port, close }.
 * `preferredPort` is tried first (the Laura default 8765), then any free port.
 */
function startForward(target, { preferredPort = 8765, logger = console } = {}) {
  const sockets = new Set();
  const server = net.createServer((client) => {
    const upstream = net.connect(target.port, target.host);
    sockets.add(client).add(upstream);
    const done = () => { client.destroy(); upstream.destroy(); sockets.delete(client); sockets.delete(upstream); };
    client.on('error', done); upstream.on('error', done);
    client.on('close', done); upstream.on('close', done);
    client.pipe(upstream);
    upstream.pipe(client);
  });
  const listen = (port) => new Promise((resolve, reject) => {
    server.once('error', reject);
    server.listen(port, '127.0.0.1', () => { server.removeListener('error', reject); resolve(server.address().port); });
  });
  return listen(preferredPort)
    .catch((err) => (err && err.code === 'EADDRINUSE' ? listen(0) : Promise.reject(err)))
    .then((port) => {
      logger.log(`[Laura-Forward] 127.0.0.1:${port} -> ${target.host}:${target.port}`);
      return {
        port,
        url: `http://127.0.0.1:${port}`,
        close: () => new Promise((resolve) => { for (const s of sockets) s.destroy(); server.close(() => resolve()); }),
      };
    });
}

/**
 * If LAURA_URL names another machine, forwards it and rewrites LAURA_URL in `env` to the
 * local address, so every reader of LAURA_URL sees a local service. Returns the forward or null.
 */
async function forwardRemoteLaura(env = process.env, options = {}) {
  const target = remoteTarget(env);
  if (!target) return null;
  const forward = await startForward(target, options);
  env.LAURA_URL = forward.url;
  return forward;
}

module.exports = { remoteTarget, startForward, forwardRemoteLaura };
