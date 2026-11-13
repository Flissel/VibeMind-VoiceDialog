/**
 * Konzept-Flaeche in der eingebetteten Rowboat-Ansicht: ein Rahmen, der ein Dokument unter
 * app://workspace/knowledge/ zeigt, darf nicht wegnavigieren und nichts aus dem Netz laden.
 *
 * Abschrift der reinen Entscheidungen aus dem Rowboat-Fork, apps/x/packages/shared/src/konzept.ts
 * (isKnowledgeFrameUrl, frameNavigationDecision, isConfinedCommit, noteFrameCommit, noteFramesAttached,
 * backstopDecision; Zweig cc/konzept-flaeche, 2026-11-13, Rulings R43-R46) und der Verdrahtung in
 * apps/x/apps/main/src/main.ts. Die voice-App kann @x/shared nicht laden: Aenderungen
 * dort hier nachziehen. Anders als Rowboat kennt die voice-App keine "als Wissens-HTML ausgelieferten"
 * Adressen (sie liefert die Dateien nicht selbst aus); dafuer sorgen Rowboats Antwortkoepfe (CSP mit sandbox).
 */

function segmente(pfad) {
  return pfad.replace(/\\/g, '/').split('/').filter((s) => s !== '' && s !== '.');
}

/** Windows ignoriert Punkte und Leerzeichen am Segmentende. */
function segName(s) {
  return s.replace(/[. ]+$/, '').toLowerCase();
}

/**
 * isKnowledgeFrameUrl (R43): Dokument unter app://workspace/knowledge/, gleich welcher Endung. Schema und Host
 * ohne Gross/Klein; Pfad roh und prozent-dekodiert; ungueltige Kodierung oder `..`: eingesperrt. Adressen
 * ausserhalb von app://workspace (auch leer/about:blank beim ersten Laden): nicht eingesperrt.
 */
function istEingesperrterRahmen(url) {
  if (typeof url !== 'string') return false;
  const m = /^app:\/\/workspace(?=[/?#]|$)/i.exec(url);
  if (m === null) return false;
  const roh = url.slice(m[0].length).split(/[?#]/)[0];
  let dekodiert;
  try {
    dekodiert = decodeURIComponent(roh);
  } catch {
    return true;
  }
  return [roh, dekodiert].some((pfad) => {
    const segs = segmente(pfad);
    return segs.includes('..') || (segs.length >= 1 && segName(segs[0]) === 'knowledge');
  });
}

/** frameNavigationDecision: 'block' fuer einen eingesperrten Rahmen, sonst 'allow'. */
function rahmenNavigation(rahmenUrl) {
  return istEingesperrterRahmen(rahmenUrl) ? 'block' : 'allow';
}

function schema(url) {
  const m = /^([a-z][a-z0-9+.-]*):/i.exec(String(url));
  return m ? m[1].toLowerCase() : null;
}

/** Bleibt im Dokument bzw. in der App, nie im Netz (chrome-extension: = Chromiums PDF-Betrachter). */
const FREIE_SCHEMATA = new Set(['data', 'blob', 'about', 'app', 'devtools', 'chrome-extension']);

/** Nachfrist nach dem Entlassen eines eingesperrten Rahmens (R46). */
const NACHFRIST_MS = 5000;

/** Zustand je Ansicht (R46): confined = eingesperrte Rahmen, kuerzlich = entlassene mit Zeitpunkt (frameTreeNodeId). */
function neuerStand() {
  return { confined: new Set(), kuerzlich: new Map() };
}

function nochKuerzlich(kuerzlich, id, jetzt) {
  const t = kuerzlich.get(id);
  return t !== undefined && jetzt - t <= NACHFRIST_MS; // Uhr zurueckgesprungen: weiter eingesperrt
}

function entlassen(stand, id, jetzt) {
  if (stand.confined.delete(id)) stand.kuerzlich.set(id, jetzt);
}

function abgelaufeneVergessen(stand, jetzt) {
  for (const id of [...stand.kuerzlich.keys()]) if (!nochKuerzlich(stand.kuerzlich, id, jetzt)) stand.kuerzlich.delete(id);
}

/** isConfinedCommit: Dokument unter knowledge/, oder der Elternrahmen ist eingesperrt. */
function eingesperrtNachNavigation(url, elternEingesperrt) {
  return elternEingesperrt === true || istEingesperrterRahmen(url);
}

/** noteFrameCommit (R46): eingesperrt -> aufnehmen; sonst nur bei echtem Dokumentwechsel entlassen, nie bei In-Page. */
function rahmenUebernommen(stand, { rahmenId, elternId, url, inPage, jetzt }) {
  abgelaufeneVergessen(stand, jetzt);
  const elternEingesperrt = elternId !== null && elternId !== undefined && stand.confined.has(elternId);
  if (eingesperrtNachNavigation(url, elternEingesperrt)) {
    stand.confined.add(rahmenId);
    stand.kuerzlich.delete(rahmenId);
  } else if (!inPage) {
    entlassen(stand, rahmenId, jetzt);
  }
}

/** noteFramesAttached (R46): Rahmen, die nicht mehr im Baum haengen, entlassen. */
function rahmenImBaum(stand, ids, jetzt) {
  for (const id of [...stand.confined]) if (!ids.has(id)) entlassen(stand, id, jetzt);
  abgelaufeneVergessen(stand, jetzt);
}

/**
 * backstopDecision (R44-R46), reine Werte; der Verweiser zaehlt nie. Hauptrahmen, freie Schemata: durchlassen.
 * Rahmen oder Vorfahr mit Adresse unter knowledge/: abbrechen. Rahmen identifiziert und im Baum: abbrechen, wenn er
 * oder ein Vorfahr in confined oder nicht abgelaufen in kuerzlich steht. Sonst: abbrechen, solange confined nicht leer
 * ist oder kuerzlich einen nicht abgelaufenen Eintrag hat.
 */
function anfrageEntscheidung({ url, resourceType, rahmenId, vorfahrenIds, imBaum, ketteUnterWissen, confined, kuerzlich, jetzt }) {
  if (resourceType === 'mainFrame') return false;
  const s = schema(url);
  if (s !== null && FREIE_SCHEMATA.has(s)) return false;
  if (ketteUnterWissen) return true;
  const eingesperrt = (id) => confined.has(id) || nochKuerzlich(kuerzlich, id, jetzt);
  if (rahmenId !== null && imBaum) return [rahmenId, ...vorfahrenIds].some(eingesperrt);
  return confined.size > 0 || [...kuerzlich.keys()].some((id) => nochKuerzlich(kuerzlich, id, jetzt));
}

/**
 * Zustand je Ansicht, Schluessel webContents.id. Den Rahmen eines Navigations-Ereignisses findet die Ansicht ueber
 * processId/routingId im Rahmenbaum (mainFrame.framesInSubtree), ohne webFrameMain. Identitaet: frameTreeNodeId
 * (bleibt ueber Navigationen und Prozesswechsel des Rahmens gleich, wird von Chromium nicht wiederverwendet).
 */
const standJeAnsicht = new Map();

function ansichtSchluessel(webContents) {
  return typeof webContents.id === 'number' ? webContents.id : webContents;
}

function rahmenIds(webContents) {
  try {
    return new Set(webContents.mainFrame.framesInSubtree.map((f) => f.frameTreeNodeId));
  } catch {
    return null; // Baum nicht lesbar: nichts entlassen
  }
}

function rahmenVerfolgen(webContents) {
  const schluessel = ansichtSchluessel(webContents);
  if (standJeAnsicht.has(schluessel)) return standJeAnsicht.get(schluessel);
  const stand = neuerStand();
  standJeAnsicht.set(schluessel, stand);
  const uebernommen = (url, istHauptrahmen, processId, routingId, inPage) => {
    const jetzt = Date.now();
    const ids = rahmenIds(webContents);
    if (ids) rahmenImBaum(stand, ids, jetzt);
    if (istHauptrahmen) return;
    try {
      const rahmen = webContents.mainFrame.framesInSubtree.find((f) => f.processId === processId && f.routingId === routingId);
      if (!rahmen) return;
      rahmenUebernommen(stand, {
        rahmenId: rahmen.frameTreeNodeId,
        elternId: rahmen.parent ? rahmen.parent.frameTreeNodeId : null,
        url,
        inPage,
        jetzt,
      });
    } catch {
      // Rahmen schon verworfen: der Rueckhalt entscheidet dann nach der Ansicht
    }
  };
  webContents.on('did-frame-navigate', (_e, url, _code, _text, istHauptrahmen, processId, routingId) =>
    uebernommen(url, istHauptrahmen, processId, routingId, false));
  webContents.on('did-navigate-in-page', (_e, url, istHauptrahmen, processId, routingId) =>
    uebernommen(url, istHauptrahmen, processId, routingId, true));
  webContents.on('destroyed', () => standJeAnsicht.delete(schluessel));
  return stand;
}

const LEER_IDS = new Set();
const LEER_KUERZLICH = new Map();

/** Rueckhalt in der Einbettungssitzung (R40, R44-R46). Fehler im Rueckhalt: abbrechen (ausser Hauptrahmen). */
function rueckhaltAnmelden(session) {
  session.webRequest.onBeforeRequest((details, callback) => {
    let sperren = true;
    try {
      const jetzt = Date.now();
      const wc = details.webContents;
      const stand = wc ? standJeAnsicht.get(ansichtSchluessel(wc)) : undefined;
      const ids = wc ? rahmenIds(wc) : null;
      if (stand && ids) rahmenImBaum(stand, ids, jetzt);
      let rahmenId = null;
      const vorfahrenIds = [];
      let ketteUnterWissen = false;
      try {
        if (details.frame) {
          rahmenId = details.frame.frameTreeNodeId;
          for (let r = details.frame; r; r = r.parent) {
            if (r !== details.frame) vorfahrenIds.push(r.frameTreeNodeId);
            if (istEingesperrterRahmen(r.url)) ketteUnterWissen = true;
          }
        }
      } catch {
        rahmenId = null; // Rahmen schon verworfen
      }
      sperren = anfrageEntscheidung({
        url: details.url,
        resourceType: details.resourceType,
        rahmenId: typeof rahmenId === 'number' ? rahmenId : null,
        vorfahrenIds,
        imBaum: typeof rahmenId === 'number' && ids !== null && ids.has(rahmenId),
        ketteUnterWissen,
        confined: stand ? stand.confined : LEER_IDS,
        kuerzlich: stand ? stand.kuerzlich : LEER_KUERZLICH,
        jetzt,
      });
    } catch {
      sperren = details.resourceType !== 'mainFrame';
    }
    callback(sperren ? { cancel: true } : {});
  });
}

module.exports = {
  NACHFRIST_MS,
  anfrageEntscheidung,
  eingesperrtNachNavigation,
  istEingesperrterRahmen,
  neuerStand,
  rahmenImBaum,
  rahmenNavigation,
  rahmenUebernommen,
  rahmenVerfolgen,
  rueckhaltAnmelden,
};
