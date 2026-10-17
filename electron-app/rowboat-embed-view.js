/**
 * Schliesst die Rowboat-Ansicht an den Einbettungszugang an
 * (Spec vibemind-os 2026-10-17-rowboat-einbettung, Abschnitte 3 und 4).
 *
 * - Rowboats eigener Preload ruft ipcRenderer.invoke(channel); die Handler sitzen nur auf dieser
 *   Ansicht (webContents.ipc), kollidieren also nie mit den Kanaelen der voice-App.
 * - app:// (Oberflaeche, Workspace-Dateien, Vorschauen) laeuft in der eigenen Sitzung
 *   APP_PARTITION und wird hier im Hauptprozess mit dem Token weitergeleitet.
 */
const APP_PARTITION = 'persist:rowboat-embed';
const APP_SCHEME_PRIVILEGES = {
  scheme: 'app',
  privileges: { standard: true, secure: true, supportFetchAPI: true, corsEnabled: true, stream: true },
};
const BROWSER_PANE_NOTE = 'Der Browser-Bereich laeuft nur im Rowboat-Fenster.';

function attachEmbedIpc(webContents, client, channels, { onBrowserPane } = {}) {
  for (const channel of channels) {
    webContents.ipc.handle(channel, (_event, args) => {
      if (channel === 'browser:setVisible' && args && args.visible === true && onBrowserPane) onBrowserPane();
      return client.invoke(channel, args);
    });
  }
  const onPush = (channel, payload) => {
    if (!webContents.isDestroyed()) webContents.send(channel, payload);
  };
  client.on('push', onPush);
  return function detach() {
    for (const channel of channels) webContents.ipc.removeHandler(channel);
    client.removeListener('push', onPush);
  };
}

async function proxyAppRequest(request, client, fetchImpl = globalThis.fetch) {
  const info = client.connected ? client.info : null;
  if (!info) return new Response('Rowboat nicht verbunden', { status: 503 });
  const url = new URL(request.url);
  const headers = { authorization: `Bearer ${info.token}` };
  const range = request.headers.get('range');
  if (range) headers.range = range;
  return fetchImpl(`http://127.0.0.1:${info.port}/app/${url.host}${url.pathname}${url.search}`, {
    method: request.method === 'HEAD' ? 'HEAD' : 'GET',
    headers,
  });
}

function registerAppProtocol(session, client, fetchImpl) {
  session.protocol.handle('app', (request) => proxyAppRequest(request, client, fetchImpl));
}

module.exports = { APP_PARTITION, APP_SCHEME_PRIVILEGES, BROWSER_PANE_NOTE, attachEmbedIpc, proxyAppRequest, registerAppProtocol };
