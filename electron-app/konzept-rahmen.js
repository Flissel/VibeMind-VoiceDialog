/**
 * Konzept-Flaeche in der eingebetteten Rowboat-Ansicht: ein Rahmen, der ein Dokument unter
 * app://workspace/knowledge/ zeigt, darf nicht wegnavigieren und nichts aus dem Netz laden.
 *
 * Abschrift der reinen Entscheidungen aus dem Rowboat-Fork, apps/x/packages/shared/src/konzept.ts
 * (isKnowledgeFrameUrl, frameNavigationDecision, shouldBlockFrameRequest, shouldBlockRequest; Zweig
 * cc/konzept-flaeche, 2026-11-13, Rulings R43/R44). Die voice-App kann @x/shared nicht laden: Aenderungen
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

/**
 * shouldBlockRequest (R44), reine Werte: Hauptrahmen nie; Rahmenkette bekannt -> nach ihr; unbekannt -> Verweiser
 * eingesperrt -> abbrechen; sonst app:, devtools: und Dokument-Schemata frei, alles andere nur abbrechen, solange
 * in derselben Ansicht ein eingesperrter Rahmen offen ist.
 */
function anfrageEntscheidung({ url, resourceType, rahmen, referrer, konzeptOffen }) {
  if (resourceType === 'mainFrame') return false;
  if (rahmen !== null) return rahmen.some((r) => anfrageSperren(r, url));
  if (referrer && anfrageSperren(referrer, url)) return true;
  const s = schema(url);
  if (s !== null && (s === 'app' || s === 'devtools' || DOKUMENT_SCHEMATA.has(s))) return false;
  return konzeptOffen === true;
}

/**
 * Rueckhalt in der Einbettungssitzung. Rahmen ueber details.frame (samt Vorfahren); fehlt er, zaehlen der Verweiser
 * und ob die Ansicht (details.webContents) gerade einen eingesperrten Rahmen zeigt.
 */
function rueckhaltAnmelden(session) {
  session.webRequest.onBeforeRequest((details, callback) => {
    let rahmen = null;
    try {
      if (details.frame) {
        rahmen = [];
        for (let r = details.frame; r; r = r.parent) rahmen.push(r.url);
      }
    } catch {
      rahmen = null; // Rahmen schon verworfen: wie unbekannt
    }
    let konzeptOffen = false;
    if (rahmen === null && details.webContents) {
      try {
        konzeptOffen = details.webContents.mainFrame.framesInSubtree.some((f) => istEingesperrterRahmen(f.url));
      } catch {
        konzeptOffen = true;
      }
    }
    const sperren = anfrageEntscheidung({
      url: details.url, resourceType: details.resourceType, rahmen, referrer: details.referrer, konzeptOffen,
    });
    callback(sperren ? { cancel: true } : {});
  });
}

module.exports = { anfrageEntscheidung, anfrageSperren, istEingesperrterRahmen, rahmenNavigation, rueckhaltAnmelden };
