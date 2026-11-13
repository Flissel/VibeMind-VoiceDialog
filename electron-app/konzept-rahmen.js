/**
 * Konzept-Flaeche in der eingebetteten Rowboat-Ansicht: ein Rahmen, der ein Dokument unter
 * app://workspace/knowledge/ zeigt, darf nicht wegnavigieren und nichts aus dem Netz laden.
 *
 * Abschrift der reinen Entscheidungen aus dem Rowboat-Fork, apps/x/packages/shared/src/konzept.ts
 * (isKnowledgeFrameUrl, frameNavigationDecision, isConfinedCommit, noteFrameCommit, noteFramesAttached,
 * isFrameChainConfined, backstopDecision; Zweig cc/konzept-flaeche, 2026-11-13, Rulings R43-R47) und der Verdrahtung in
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
  const formen = [segmente(roh), segmente(dekodiert)];
  if (formen.some((segs) => segs.includes('..'))) return true;
  if (!formen.some((segs) => segs.length >= 1 && segName(segs[0]) === 'knowledge')) return false;
  // R49: PDFs zeigt Chromiums eingebauter Betrachter (chrome-extension:) im Rahmen; sie bleiben wie vorher.
  // Der dekodierte letzte Name entscheidet. Rowboat liefert x.pdf nach Namen als application/pdf aus; kaeme sie
  // je als text/html, bekaeme sie Rowboats Regel (CSP mit sandbox).
  const letzte = formen[1][formen[1].length - 1];
  return !(formen[1].length >= 2 && segName(letzte).endsWith('.pdf'));
}

/**
 * frameNavigationDecision: 'block' fuer einen Rahmen unter knowledge/ oder einen, den der Rueckhalt-Zustand (auch
 * ueber einen Vorfahren) sperrt (R47, eingesperrtNachStand); sonst 'allow'.
 */
function rahmenNavigation(rahmenUrl, eingesperrtNachStand = false) {
  return eingesperrtNachStand === true || istEingesperrterRahmen(rahmenUrl) ? 'block' : 'allow';
}

function schema(url) {
  const m = /^([a-z][a-z0-9+.-]*):/i.exec(String(url));
  return m ? m[1].toLowerCase() : null;
}

/** Bleibt im Dokument, nie im Netz: fuer jede Anfrage frei (R47). */
const DOKUMENT_SCHEMATA = new Set(['data', 'blob', 'about']);

/** Verkehr der App, frei bei unbekanntem Rahmen trotz offenem Konzept (R47); aus einer eingesperrten Kette nie. */
const UNBEKANNT_FREI = new Set(['app', 'devtools']);

function ohneQueryUndFragment(url) {
  return String(url).split(/[?#]/)[0];
}

/** Nachfrist nach dem Abbau eines eingesperrten Rahmens (R46). */
const NACHFRIST_MS = 5000;

/** Zustand je Ansicht (R46/R47): confined = eingesperrt auf Lebenszeit, kuerzlich = abgebaut mit Zeitpunkt. */
function neuerStand() {
  return { confined: new Set(), kuerzlich: new Map() };
}

function nochKuerzlich(kuerzlich, id, jetzt) {
  const t = kuerzlich.get(id);
  return t !== undefined && jetzt - t <= NACHFRIST_MS; // Uhr zurueckgesprungen: weiter eingesperrt
}

function abgelaufeneVergessen(stand, jetzt) {
  for (const id of [...stand.kuerzlich.keys()]) if (!nochKuerzlich(stand.kuerzlich, id, jetzt)) stand.kuerzlich.delete(id);
}

/** isFrameChainConfined: Rahmen oder Vorfahr (Knoten-Ids) eingesperrt oder vor hoechstens 5 s abgebaut. */
function ketteEingesperrt(ids, confined, kuerzlich, jetzt) {
  return ids.some((id) => confined.has(id) || nochKuerzlich(kuerzlich, id, jetzt));
}

function konzeptInAnsicht(confined, kuerzlich, jetzt) {
  return confined.size > 0 || [...kuerzlich.keys()].some((id) => nochKuerzlich(kuerzlich, id, jetzt));
}

/** isConfinedCommit: Dokument unter knowledge/, oder der Elternrahmen ist eingesperrt. */
function eingesperrtNachNavigation(url, elternEingesperrt) {
  return elternEingesperrt === true || istEingesperrterRahmen(url);
}

/** noteFrameCommit (R47): eingesperrt -> aufnehmen, auf Lebenszeit; keine Navigation entlaesst. */
function rahmenUebernommen(stand, { rahmenId, elternId, url, jetzt }) {
  abgelaufeneVergessen(stand, jetzt);
  const elternEingesperrt = elternId !== null && elternId !== undefined && stand.confined.has(elternId);
  if (eingesperrtNachNavigation(url, elternEingesperrt)) {
    stand.confined.add(rahmenId);
    stand.kuerzlich.delete(rahmenId);
  }
}

/** noteFramesAttached (R47): nur der Abbau entlaesst, fuer 5 s nach kuerzlich. */
function rahmenImBaum(stand, ids, jetzt) {
  for (const id of [...stand.confined]) {
    if (!ids.has(id)) {
      stand.confined.delete(id);
      stand.kuerzlich.set(id, jetzt);
    }
  }
  abgelaufeneVergessen(stand, jetzt);
}

/**
 * backstopDecision (R44-R47), reine Werte; der Verweiser zaehlt nie. Hauptrahmen, data:/blob:/about:: frei.
 * Eingesperrte Kette (Adresse unter knowledge/ oder Id in confined/kuerzlich, Rahmen oder Vorfahr): nur das eigene
 * Dokument (ohne Query/Fragment), sonst nichts. Bekannter, angehaengter, nicht eingesperrter Rahmen: frei. Sonst
 * app:/devtools: frei, alles andere abbrechen, solange die Ansicht einen Rahmen sperrt oder bis 5 s nach dem Abbau.
 */
function anfrageEntscheidung({ url, resourceType, rahmenId, rahmenUrl, vorfahrenIds, imBaum, ketteUnterWissen, confined, kuerzlich, jetzt }) {
  if (resourceType === 'mainFrame') return false;
  const s = schema(url);
  if (s !== null && DOKUMENT_SCHEMATA.has(s)) return false;
  const kette = rahmenId === null ? [] : [rahmenId, ...vorfahrenIds];
  if (ketteUnterWissen || ketteEingesperrt(kette, confined, kuerzlich, jetzt)) {
    // R48: "eigenes Dokument" nur fuer eine Rahmen-Adresse unter app://workspace/knowledge/, nie fuer eine Netz-Adresse
    if (istEingesperrterRahmen(rahmenUrl) && ohneQueryUndFragment(url) === ohneQueryUndFragment(rahmenUrl)) return false;
    return true;
  }
  if (rahmenId !== null && imBaum) return false;
  if (s !== null && UNBEKANNT_FREI.has(s)) return false;
  return konzeptInAnsicht(confined, kuerzlich, jetzt);
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

/** Ids und Adressen des Rahmens und seiner Vorfahren (Rahmen zuerst); null, wenn nicht lesbar. */
function rahmenKette(rahmen) {
  if (!rahmen) return null;
  try {
    const ids = [];
    const urls = [];
    for (let r = rahmen; r; r = r.parent) {
      ids.push(r.frameTreeNodeId);
      urls.push(r.url);
    }
    return typeof ids[0] === 'number' ? { ids, urls } : null;
  } catch {
    return null; // Rahmen schon verworfen
  }
}

/** Sperrt der Zustand der Ansicht diesen Rahmen oder einen Vorfahren? Fuer die Navigationssperre (R47). */
function rahmenGesperrt(webContents, rahmen) {
  const stand = webContents ? standJeAnsicht.get(ansichtSchluessel(webContents)) : undefined;
  const kette = rahmenKette(rahmen);
  if (!stand || !kette) return false;
  return ketteEingesperrt(kette.ids, stand.confined, stand.kuerzlich, Date.now());
}

function rahmenVerfolgen(webContents) {
  const schluessel = ansichtSchluessel(webContents);
  if (standJeAnsicht.has(schluessel)) return standJeAnsicht.get(schluessel);
  const stand = neuerStand();
  standJeAnsicht.set(schluessel, stand);
  const uebernommen = (url, istHauptrahmen, processId, routingId) => {
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
        jetzt,
      });
    } catch {
      // Rahmen schon verworfen: der Rueckhalt entscheidet dann nach der Ansicht
    }
  };
  webContents.on('did-frame-navigate', (_e, url, _code, _text, istHauptrahmen, processId, routingId) =>
    uebernommen(url, istHauptrahmen, processId, routingId));
  webContents.on('did-navigate-in-page', (_e, url, istHauptrahmen, processId, routingId) =>
    uebernommen(url, istHauptrahmen, processId, routingId));
  webContents.on('destroyed', () => standJeAnsicht.delete(schluessel));
  return stand;
}

const LEER_IDS = new Set();
const LEER_KUERZLICH = new Map();

/** Rueckhalt in der Einbettungssitzung (R40, R44-R47). Fehler im Rueckhalt: abbrechen (ausser Hauptrahmen). */
function rueckhaltAnmelden(session) {
  session.webRequest.onBeforeRequest((details, callback) => {
    let sperren = true;
    try {
      const jetzt = Date.now();
      const wc = details.webContents;
      const stand = wc ? standJeAnsicht.get(ansichtSchluessel(wc)) : undefined;
      const ids = wc ? rahmenIds(wc) : null;
      if (stand && ids) rahmenImBaum(stand, ids, jetzt);
      const kette = rahmenKette(details.frame);
      const rahmenId = kette ? kette.ids[0] : null;
      sperren = anfrageEntscheidung({
        url: details.url,
        resourceType: details.resourceType,
        rahmenId,
        rahmenUrl: kette ? kette.urls[0] : null,
        vorfahrenIds: kette ? kette.ids.slice(1) : [],
        imBaum: rahmenId !== null && ids !== null && ids.has(rahmenId),
        ketteUnterWissen: kette ? kette.urls.some(istEingesperrterRahmen) : false,
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
  ketteEingesperrt,
  neuerStand,
  rahmenGesperrt,
  rahmenImBaum,
  rahmenNavigation,
  rahmenUebernommen,
  rahmenVerfolgen,
  rueckhaltAnmelden,
};
