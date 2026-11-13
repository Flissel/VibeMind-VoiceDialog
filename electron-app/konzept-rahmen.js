/**
 * Konzept-Flaeche in der eingebetteten Rowboat-Ansicht: ein Rahmen, der ein Dokument unter
 * app://workspace/knowledge/ zeigt, darf nicht wegnavigieren und nichts aus dem Netz laden.
 *
 * Abschrift der reinen Entscheidungen aus dem Rowboat-Fork, apps/x/packages/shared/src/konzept.ts
 * (isKnowledgeFrameUrl, frameNavigationDecision, shouldBlockFrameRequest, isConfinedCommit, confinedInView,
 * backstopDecision; Zweig cc/konzept-flaeche, 2026-11-13, Rulings R43-R45) und der Verdrahtung in
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

function ohneFragment(url) {
  const i = url.indexOf('#');
  return i === -1 ? url : url.slice(0, i);
}

function schema(url) {
  const m = /^([a-z][a-z0-9+.-]*):/i.exec(String(url));
  return m ? m[1].toLowerCase() : null;
}

/** Bleibt im Dokument, nie im Netz (chrome-extension: = Chromiums PDF-Betrachter). */
const DOKUMENT_SCHEMATA = new Set(['data', 'blob', 'about', 'chrome-extension']);

/** shouldBlockFrameRequest: Anfrage aus einem eingesperrten Rahmen abbrechen, ausser im Dokument oder an die eigene Adresse. */
function anfrageSperren(rahmenUrl, anfrageUrl) {
  if (!istEingesperrterRahmen(rahmenUrl)) return false;
  const s = schema(anfrageUrl);
  if (s !== null && DOKUMENT_SCHEMATA.has(s)) return false;
  return ohneFragment(String(anfrageUrl)) !== ohneFragment(rahmenUrl);
}

/** Nachfrist nach dem Verschwinden des letzten eingesperrten Rahmens (R45). */
const NACHFRIST_MS = 5000;

/** isConfinedCommit (R45): Rahmen uebernimmt ein Dokument unter knowledge/, oder sein Elternrahmen ist eingesperrt. */
function eingesperrtNachNavigation(url, elternEingesperrt) {
  return elternEingesperrt === true || istEingesperrterRahmen(url);
}

/** confinedInView (R45): Ansicht zeigt einen eingesperrten Rahmen, oder der letzte verschwand vor hoechstens 5 s. */
function konzeptInAnsicht(anzahl, zuletztEntferntUm, jetzt) {
  if (anzahl > 0) return true;
  return zuletztEntferntUm !== null && jetzt >= zuletztEntferntUm && jetzt - zuletztEntferntUm <= NACHFRIST_MS;
}

/**
 * backstopDecision (R44/R45), reine Werte. Der Verweiser zaehlt nie. rahmen: { bekannt: true, url, eingesperrt }
 * oder { bekannt: false }. Hauptrahmen nie; Rahmen bekannt -> nur wenn eingesperrt (ausser Dokument-Schemata und
 * eigene Adresse); unbekannt -> app:, devtools: und Dokument-Schemata frei, sonst abbrechen, solange/kurz nachdem
 * die Ansicht einen eingesperrten Rahmen zeigt.
 */
function anfrageEntscheidung({ url, resourceType, rahmen, konzeptOffen }) {
  if (resourceType === 'mainFrame') return false;
  if (rahmen && rahmen.bekannt) {
    if (!rahmen.eingesperrt) return false;
    const s = schema(url);
    if (s !== null && DOKUMENT_SCHEMATA.has(s)) return false;
    return ohneFragment(String(url)) !== ohneFragment(String(rahmen.url));
  }
  const s = schema(url);
  if (s !== null && (s === 'app' || s === 'devtools' || DOKUMENT_SCHEMATA.has(s))) return false;
  return konzeptOffen === true;
}

/**
 * Eingesperrte Rahmen je Ansicht (R45), beim Navigieren festgehalten. Schluessel: webContents.id; Inhalt: die
 * frameTreeNodeId der Rahmen (bleibt ueber Navigationen und Prozesswechsel des Rahmens gleich, wird von Chromium
 * nicht wiederverwendet; processId/routingId wechseln beim Prozesswechsel). Den Rahmen eines Ereignisses findet die
 * Ansicht ueber processId/routingId im Rahmenbaum (mainFrame.framesInSubtree), ohne webFrameMain.
 */
const eingesperrtJeAnsicht = new Map();

function rahmenListe(webContents) {
  return webContents.mainFrame.framesInSubtree;
}

function aufraeumen(webContents, stand) {
  if (stand.knoten.size === 0) return;
  let lebend;
  try {
    lebend = new Set(rahmenListe(webContents).map((f) => f.frameTreeNodeId));
  } catch {
    return; // Baum nicht lesbar: nichts entfernen
  }
  for (const id of stand.knoten) {
    if (!lebend.has(id)) {
      stand.knoten.delete(id);
      stand.zuletztEntferntUm = Date.now();
    }
  }
}

function rahmenVerfolgen(webContents) {
  const schluessel = typeof webContents.id === 'number' ? webContents.id : webContents;
  if (eingesperrtJeAnsicht.has(schluessel)) return eingesperrtJeAnsicht.get(schluessel);
  const stand = { knoten: new Set(), zuletztEntferntUm: null };
  eingesperrtJeAnsicht.set(schluessel, stand);
  const uebernommen = (url, istHauptrahmen, processId, routingId) => {
    aufraeumen(webContents, stand);
    if (istHauptrahmen) return;
    let id;
    let elternId;
    try {
      const rahmen = rahmenListe(webContents).find((f) => f.processId === processId && f.routingId === routingId);
      if (!rahmen) return;
      id = rahmen.frameTreeNodeId;
      elternId = rahmen.parent ? rahmen.parent.frameTreeNodeId : undefined;
    } catch {
      return;
    }
    const elternEingesperrt = elternId !== undefined && stand.knoten.has(elternId);
    if (eingesperrtNachNavigation(url, elternEingesperrt)) {
      stand.knoten.add(id);
    } else if (stand.knoten.delete(id)) {
      stand.zuletztEntferntUm = Date.now();
    }
  };
  webContents.on('did-frame-navigate', (_e, url, _code, _text, istHauptrahmen, processId, routingId) =>
    uebernommen(url, istHauptrahmen, processId, routingId));
  webContents.on('did-navigate-in-page', (_e, url, istHauptrahmen, processId, routingId) =>
    uebernommen(url, istHauptrahmen, processId, routingId));
  webContents.on('destroyed', () => eingesperrtJeAnsicht.delete(schluessel));
  return stand;
}

/**
 * Rueckhalt in der Einbettungssitzung (R40, R44, R45). Rahmen lesbar (details.frame): eingesperrt, wenn er in der
 * festgehaltenen Menge steht oder er/ein Vorfahr unter knowledge/ liegt. Sonst: abbrechen, solange die Ansicht einen
 * eingesperrten Rahmen zeigt oder bis 5 s danach. Der Verweiser zaehlt nie. Fehler im Rueckhalt: abbrechen.
 */
function rueckhaltAnmelden(session) {
  session.webRequest.onBeforeRequest((details, callback) => {
    let sperren = true;
    try {
      const wc = details.webContents;
      const stand = wc ? eingesperrtJeAnsicht.get(typeof wc.id === 'number' ? wc.id : wc) : undefined;
      let rahmen = { bekannt: false };
      try {
        if (details.frame) {
          const url = details.frame.url;
          let eingesperrt = stand ? stand.knoten.has(details.frame.frameTreeNodeId) : false;
          for (let r = details.frame; r && !eingesperrt; r = r.parent) eingesperrt = istEingesperrterRahmen(r.url);
          rahmen = { bekannt: true, url, eingesperrt };
        }
      } catch {
        rahmen = { bekannt: false }; // Rahmen schon verworfen
      }
      let konzeptOffen = false;
      if (!rahmen.bekannt && wc && stand) {
        aufraeumen(wc, stand);
        konzeptOffen = konzeptInAnsicht(stand.knoten.size, stand.zuletztEntferntUm, Date.now());
      }
      sperren = anfrageEntscheidung({ url: details.url, resourceType: details.resourceType, rahmen, konzeptOffen });
    } catch {
      sperren = details.resourceType !== 'mainFrame';
    }
    callback(sperren ? { cancel: true } : {});
  });
}

module.exports = {
  NACHFRIST_MS,
  anfrageEntscheidung,
  anfrageSperren,
  eingesperrtNachNavigation,
  istEingesperrterRahmen,
  konzeptInAnsicht,
  rahmenNavigation,
  rahmenVerfolgen,
  rueckhaltAnmelden,
};
