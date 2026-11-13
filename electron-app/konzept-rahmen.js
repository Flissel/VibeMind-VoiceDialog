/**
 * Konzept-Flaeche in der eingebetteten Rowboat-Ansicht: ein Rahmen, der ein Wissens-HTML zeigt
 * (app://workspace/knowledge/...html), darf nicht wegnavigieren und nichts aus dem Netz laden.
 *
 * Abschrift der reinen Entscheidungen aus dem Rowboat-Fork, apps/x/packages/shared/src/konzept.ts
 * (isKnowledgeHtmlDocumentUrl, frameNavigationDecision, shouldBlockFrameRequest; Zweig cc/konzept-flaeche,
 * 2026-11-13). Die voice-App kann @x/shared nicht laden: Aenderungen dort hier nachziehen.
 * Anders als Rowboat entscheidet die voice-App nur nach der Adresse (sie liefert die Dateien nicht selbst aus,
 * kennt also Symlink-Ziel und Content-Type nicht); dafuer sorgen dort die Antwortkoepfe (CSP mit sandbox).
 */
const WORKSPACE_PRAEFIX = 'app://workspace/';

function segmente(pfad) {
  return pfad.replace(/\\/g, '/').split('/').filter((s) => s !== '' && s !== '.');
}

/** Windows ignoriert Punkte und Leerzeichen am Segmentende. */
function segName(s) {
  return s.replace(/[. ]+$/, '').toLowerCase();
}

function istHtmlPfad(pfad) {
  return /\.(html?|xhtml)$/i.test(pfad);
}

/** Erstes Segment `knowledge`; bei `..` sicherheitshalber ja. */
function imWissensordner(pfad) {
  const segs = segmente(pfad);
  if (segs.includes('..')) return true;
  return segs.length >= 2 && segName(segs[0]) === 'knowledge';
}

/** Rohform und, falls anders, prozent-dekodierte Form des Pfadteils (ohne `?`/`#`). */
function pfadFormen(pfadOderUrl) {
  const roh = pfadOderUrl.split(/[?#]/)[0];
  try {
    const dekodiert = decodeURIComponent(roh);
    return dekodiert === roh ? [roh] : [roh, dekodiert];
  } catch {
    return [roh];
  }
}

/** Zeigt diese Adresse ein Wissens-HTML? Nach Namen, roh und dekodiert; im Zweifel ja. */
function istWissensHtmlAdresse(url) {
  if (typeof url !== 'string') return false;
  if (url.slice(0, WORKSPACE_PRAEFIX.length).toLowerCase() !== WORKSPACE_PRAEFIX) return false;
  const formen = pfadFormen(url.slice(WORKSPACE_PRAEFIX.length));
  return formen.some(imWissensordner) && formen.some((f) => istHtmlPfad(f.replace(/[. ]+$/, '')));
}

/** frameNavigationDecision: 'block' fuer einen Rahmen mit Wissens-HTML, sonst 'allow'. */
function rahmenNavigation(rahmenUrl) {
  return istWissensHtmlAdresse(rahmenUrl) ? 'block' : 'allow';
}

function ohneFragment(url) {
  const i = url.indexOf('#');
  return i === -1 ? url : url.slice(0, i);
}

/**
 * shouldBlockFrameRequest: Anfrage aus einem Rahmen mit Wissens-HTML abbrechen, ausser `data:`, `blob:`,
 * `about:` oder die eigene Adresse des Rahmens. Andere Rahmen bleiben unberuehrt; ohne Schema: abbrechen.
 */
function anfrageSperren(rahmenUrl, anfrageUrl) {
  if (!istWissensHtmlAdresse(rahmenUrl)) return false;
  const m = /^([a-z][a-z0-9+.-]*):/i.exec(String(anfrageUrl));
  const schema = m ? m[1].toLowerCase() : null;
  if (schema === 'data' || schema === 'blob' || schema === 'about') return false;
  return ohneFragment(String(anfrageUrl)) !== ohneFragment(rahmenUrl);
}

/**
 * Rueckhalt in der Einbettungssitzung: Anfragen aus Rahmen (oder deren Vorfahren) mit Wissens-HTML abbrechen.
 * Ohne `details.frame` (aeltere Electron-Fassung, Rahmen schon weg) entscheidet die CSP allein.
 */
function rueckhaltAnmelden(session) {
  session.webRequest.onBeforeRequest((details, callback) => {
    let sperren = false;
    try {
      for (let rahmen = details.frame || null; rahmen; rahmen = rahmen.parent) {
        if (anfrageSperren(rahmen.url, details.url)) {
          sperren = true;
          break;
        }
      }
    } catch {
      // Rahmen schon verworfen: im Zweifel nichts durchlassen, ausser dem Laden der Oberflaeche selbst.
      sperren = details.resourceType !== 'mainFrame';
    }
    callback(sperren ? { cancel: true } : {});
  });
}

module.exports = { anfrageSperren, istWissensHtmlAdresse, rahmenNavigation, rueckhaltAnmelden };
