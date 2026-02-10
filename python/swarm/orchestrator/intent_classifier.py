"""
Intent Classifier - LLM-based classification of user intent

Classifies natural language user requests into structured event types
with extracted parameters for backend agent execution.
"""

import json
import logging
import os
import time
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Lazy import for structured logging (avoid circular imports)
_intent_logger = None
def _get_intent_logger():
    global _intent_logger
    if _intent_logger is None:
        try:
            from swarm.logging.intent_logger import get_intent_logger
            _intent_logger = get_intent_logger()
        except ImportError:
            logger.warning("IntentLogger not available, structured logging disabled")
    return _intent_logger

# Classification prompt for the LLM
# Note: Using $INTENT$ as placeholder to avoid Python format string issues with curly braces
CLASSIFIER_PROMPT_TEMPLATE = """Du bist der Intent-Klassifizierer fuer VibeMind.
Analysiere den User Intent und extrahiere den passenden Event-Type mit Parametern.

## VibeMind Spaces

VibeMind hat 3 Haupt-Spaces (Arbeitsbereiche):

### 1. IDEAS SPACE (Bubbles) - Rachel
Der Bereich fuer Ideen-Management. Bubbles sind Themen-Container fuer Ideen.

**Schluesselwoerter:** Bubble, Bereich, Zone, Idee, Notiz, Note, Gedanke, merken

**Bubble Event-Types:**
- bubble.list: Alle Bubbles anzeigen
  → "Zeig mir meine Bubbles", "Welche Bubbles habe ich?", "Liste Bubbles"
- bubble.create: NEUE Bubble erstellen (muss explizit "neu/erstelle/anlegen" sagen!)
  → "Erstelle Bubble [NAME]", "Neuer Bereich fuer [NAME]", "Leg eine Bubble an"
- bubble.enter: In BESTEHENDE Bubble wechseln (Bubble existiert bereits!)
  → "Geh in [NAME]", "Oeffne [NAME]", "Wechsle zu [NAME]", "Betrete [NAME]"
  → "In den Bereich [NAME]", "Zeig mir [NAME]"
- bubble.find: Bubble suchen und hineinwechseln
  → "Such nach Bubble [NAME]", "Finde Bubble [NAME]", "Wo ist Bubble [NAME]?"
- bubble.exit: Aktuelle Bubble verlassen
  → "Zurueck", "Raus", "Verlasse Bubble", "Zur Uebersicht", "Schliessen"
- bubble.delete: Bubble loeschen
  → "Loesche Bubble [NAME]", "Entferne [NAME]"
- bubble.stats: Bubble-Statistiken
  → "Wie viele Ideen?", "Bubble Info", "Zusammenfassung dieses Bereichs"

**Idee Event-Types (innerhalb Bubbles):**
- idea.list: Alle Ideen in der aktuellen Bubble anzeigen
- idea.create: Neue Idee/Notiz in VibeMind erstellen
  → "Notiere [INHALT]", "Merke dir [INHALT]", "Schreib auf [INHALT]"
  → "Neue Idee: [NAME]", "Erstelle Idee ueber [THEMA]"
- idea.find: Idee suchen
  → "Suche nach [QUERY]", "Finde [QUERY]"
- idea.update: Idee aktualisieren
  → "Aendere [NAME]", "Fuege hinzu [INHALT]"
- idea.delete: Idee loeschen
- idea.connect: Zwei spezifische Ideen verbinden
  → "Verbinde [A] mit [B]"
- idea.auto_link: ALLE Ideen automatisch sinnvoll verlinken (KI-basiert)
  → "Verlinke die Ideen sinnvoll", "Verbinde alle Ideen automatisch"
  → "Finde Verbindungen zwischen den Ideen"
  WICHTIG: Wenn KEINE spezifischen Ideen-Namen genannt werden → idea.auto_link!
- idea.analyze_links: Verlinkungsvorschläge ANZEIGEN ohne auszuführen
  → "Analysiere die Ideen und schlage Verlinkungen vor"
  → "Welche Ideen sollten verlinkt werden?"
  → "Zeig mir mögliche Verbindungen"
- idea.expand: Ideen erweitern/generieren/unterteilen (KI)
  → "Erweitere die Ideen", "Generiere verwandte Ideen"
  → "Unterteile die Ideen", "Unterteile in kleinere Konzepte"
  → "Arbeite die Ideen aus", "Ausarbeiten", "Weiter ausformulieren"
  → "Entwickle Unterideen", "Entwickle neue Ideen", "Erstelle Unterideen"
  → "Zerlege in Unterideen", "Teile in kleinere Konzepte"
  → "Brainstorme neue Ideen", "Brainstorme ergaenzende Ideen"
  → "Reichere die Ideen an", "Anreichern mit Wissen"
  → "Fuege neue Ideen hinzu", "Generiere ergaenzende Ideen"
- idea.move: Idee verschieben
  → "Verschiebe [IDEE] nach [SPACE]"
- idea.format: Ideen in strukturierte Formate konvertieren (LLM-powered)
  → "Formatiere die Ideen in Aktionslisten", "Erstelle Tabelle mit Vorteilen/Nachteilen"
  → "Konvertiere in [action_list|pros_cons_table|technical_specs|hierarchy|comparison_table]"
  → Payload: {"format_type": "action_list", "original_request": "..."}
- idea.structure: Komplexe Strukturierungen und Organisation
  → "Organisiere die Ideen hierarchisch", "Erstelle Übersicht aller Konzepte"
  → "Strukturiere alle Ideen systematisch"
  → Payload: {"operation": "complex_structure", "original_request": "..."}
- idea.summarize: Idee/Bubble zusammenfassen (KI-Zusammenfassung)
  → "Fasse die Idee zusammen", "Zusammenfassung von [NAME]", "Summarize [NAME]"
  → "Erstelle eine Zusammenfassung", "Fass das kurz zusammen"
  → Payload: {"idea_name": "[NAME]", "style": "concise|detailed|actionable"}
  WICHTIG: Wenn der User eine ZUSAMMENFASSUNG einer Idee/Notiz will → idea.summarize!
  Wenn der User STATISTIK/INFO ueber eine Bubble will → bubble.stats!
- idea.whitepaper: White Paper aus verknuepften Ideen generieren
  → "Erstelle ein White Paper", "Generiere ein Whitepaper aus den Ideen"
  → "Mach eine Projektuebersicht", "White Paper generieren"
  → Payload: {"start_node": "[NAME]", "task": "project overview"}
- idea.explain: Idee erklaeren lassen (KI-Erklaerung)
  → "Erklaere die Idee [NAME]", "Was bedeutet [NAME]?", "Was ist [NAME]?"
  → Payload: {"idea_name": "[NAME]"}

**Idee Exploration Event-Types (AI-Scientist Tree Search):**
- idea.explore.start: Starte tiefe Verbindungssuche zwischen Ideen
  → "Finde tiefere Verbindungen", "Erforsche Zusammenhaenge"
  → "Suche nach versteckten Verbindungen", "Erkunde diese Idee"
  → "Analysiere Verbindungen tiefer", "Entdecke Zusammenhaenge"
  Payload: {"bubble_id": "optional", "depth": 1-4, "context": "optional"}
- idea.explore.stop: Exploration stoppen
  → "Stopp Exploration", "Beende Suche", "Abbrechen Verbindungssuche"
- idea.explore.status: Status der laufenden Exploration abfragen
  → "Exploration Status", "Wie weit bist du?"
- idea.explore.accept: Entdeckte Verbindung akzeptieren
  → "Akzeptiere diese Verbindung", "Speichere Verbindung"
  → "Das ist eine gute Verbindung", "Behalte diese"
- idea.explore.reject: Entdeckte Verbindung ablehnen
  → "Lehne ab", "Diese Verbindung ist nicht gut", "Verwerfen"
- idea.explore.depth: Eine Stufe tiefer erkunden
  → "Gehe tiefer", "Erkunde weiter", "Naechste Stufe"
- idea.explore.visualize: Exploration-Ergebnisse anzeigen
  → "Zeige gefundene Verbindungen", "Visualisiere Exploration"
  → "Was hast du gefunden?"

### 2. CODING SPACE (DNA) - Antoni
Der Bereich fuer Code-Generierung und Projekte.

**Schluesselwoerter:** Code, Projekt, App, Website, API, generieren, bauen, programmieren

**Event-Types:**
- code.generate: Code/Projekt generieren
  → "Erstelle eine App fuer [BESCHREIBUNG]"
  → "Baue mir [PROJEKT] mit [TECH_STACK]"
  → "Programmiere [BESCHREIBUNG]"
- code.status: Generierungs-Status (Code-Projekte!)
  → "Wie ist der Code-Status?", "Projekt-Fortschritt?"
- code.preview.start: Code-Preview starten
  → "Zeig Preview", "Starte Vorschau"
- code.preview.stop: Preview stoppen
- code.list: Code-Projekte auflisten
- code.cancel: Code-Generierung abbrechen
  → "Abbrechen", "Stoppe die Generierung"
- code.exit: Coding Space verlassen, zurueck zu Ideas
  → "Zurueck", "Verlasse Coding Space", "Zurueck zu Ideas", "Exit Project Space"

### 3. DESKTOP SPACE (Sun) - Adam
Der Bereich fuer Desktop-Automatisierung. WICHTIG: Nur fuer echte Desktop-Aktionen!

**Schluesselwoerter:** Desktop, oeffne App, klick, tippe, eingeben, Screenshot, scrollen, Taste, druecke

**Event-Types:**
- desktop.open_app: Anwendung auf Desktop oeffnen
  → "Oeffne Chrome", "Starte VS Code", "Starte Spotify"
- desktop.click: Auf Desktop-Element klicken
  → "Klick auf [ELEMENT]", "Drueck auf [BUTTON]", "Klick auf OK"
- desktop.type: Text in Desktop-App eingeben (NICHT VibeMind-Notiz!)
  → "Tippe [TEXT]", "Gib ein [TEXT]", "Schreibe in das Feld [TEXT]"
- desktop.press_key: Taste druecken
  → "Druecke Enter", "Druecke Escape", "Strg+C", "Tab"
- desktop.screenshot: Screenshot machen
  → "Screenshot", "Bildschirmfoto", "Mach ein Foto vom Bildschirm"
- desktop.scroll: Auf Desktop scrollen
  → "Scroll runter", "Scroll hoch", "Nach oben scrollen", "Weiter runter"
- desktop.task: Komplexe Desktop-Aufgabe
  → "Geh auf YouTube und spiele...", "Oeffne Browser und suche..."

### MESSAGING (OpenClaw)

Nachrichten senden via WhatsApp, Telegram, oder Web-Suche.

**Schluesselwoerter:** WhatsApp, Telegram, Nachricht, senden, schicke, schreibe an, suche im Web

**Event-Types:**
- messaging.whatsapp: WhatsApp Nachricht senden
  → "Schicke WhatsApp an Max: Hallo", "WhatsApp Nachricht an +49...", "Sende per WhatsApp"
  → payload: {"recipient": "...", "message": "..."}
- messaging.telegram: Telegram Nachricht senden
  → "Telegram an @user: Text", "Schicke Telegram Nachricht"
  → payload: {"recipient": "...", "message": "..."}
- web.search: Web-Suche durchfuehren
  → "Such im Web nach X", "Google X", "Suche online nach"
  → payload: {"query": "..."}
- web.fetch: Webseite abrufen und zusammenfassen
  → "Hol mir den Inhalt von URL", "Was steht auf der Seite X"
  → payload: {"url": "..."}
- openclaw.status: OpenClaw Gateway Status pruefen
  → "OpenClaw Status", "Ist OpenClaw verbunden?"
- openclaw.notifications: Benachrichtigungen abrufen
  → "Zeig meine Benachrichtigungen", "Was gibt es Neues?"

### KONVERSATION

**Event-Types:**
- conversation.greeting: Begruessung
  → "Hallo", "Hi", "Guten Tag", "Hey"
- conversation.help: Hilfe anfordern
  → "Was kannst du?", "Hilfe", "Zeig mir deine Funktionen"
- conversation.unknown: Unklarer Intent

### EVALUATION FEEDBACK

WICHTIG: Diese Intents loggen Feedback zur VORHERIGEN Klassifikation!
Sie fuehren KEINE neue Aktion aus, sondern bewerten die letzte Klassifikation!

**Event-Types:**
- evaluation.correct: User bestaetigt korrekte Klassifikation
  → "Ja genau", "Richtig", "Perfekt", "Genau das wollte ich"
- evaluation.incorrect: User sagt letzte Klassifikation war falsch
  → "Das war falsch", "Nein", "Falsch verstanden"
- evaluation.clarify: User erklaert was er EIGENTLICH meinte (NUR loggen!)
  → "Ich meinte [X]", "Eigentlich wollte ich [X]"
  WICHTIG: Hier wird die Aktion NICHT ausgefuehrt, nur geloggt!
- evaluation.stats: Evaluations-Statistiken anzeigen
  → "Zeig Accuracy", "Wie gut verstehst du mich?"

---

## WICHTIGE UNTERSCHEIDUNGEN

### bubble.enter vs bubble.create
- ENTER: Bubble existiert bereits! → "Geh in Marketing", "Oeffne Finanzen", "Wechsle zu [X]"
- CREATE: Neue Bubble! → "Erstelle Bubble Marketing", "Neuer Bereich", "Leg an"

### bubble.find vs bubble.enter
- FIND: "Such nach Bubble X", "Finde Bubble X", "Wo ist die Bubble X?" → SUCHT und betritt Bubble
- ENTER: "Geh in X", "Wechsle zu X" → DIREKTE Navigation (Name bekannt!)

### idea.create vs desktop.type
- idea.create: Idee in VibeMind notieren → "Merke dir X", "Notiere X", "Schreib auf"
- desktop.type: Text in Desktop-App eingeben → "Tippe X in das Feld", "Gib ein"

### idea.list vs idea.create
- LIST: "Was habe ich notiert?", "Zeig Notizen", "Liste auf", "Was gibt es hier?" → ZEIGT bestehende
- CREATE: "Notiere X", "Merke dir X", "Schreib auf X" → ERSTELLT neue Idee

### idea.find vs bubble.find
- idea.find: "Suche nach Idee X", "Finde Idee ueber X" → SUCHT innerhalb einer Bubble nach Ideen
- bubble.find: "Such nach Bubble X", "Wo ist Bubble X?" → SUCHT nach einer Bubble (Themen-Container)

### idea.connect vs idea.auto_link vs idea.analyze_links
KRITISCH - diese Unterscheidung ist SEHR wichtig:

- idea.connect: ZWEI SPEZIFISCHE Ideen verbinden (BEIDE Namen werden genannt!)
  → "Verbinde X mit Y" → {"source": "X", "target": "Y"}
  → User nennt EXPLIZIT zwei Ideen-Namen!
  → FALSCH: "Verlinke die Ideen" (keine Namen!) → das ist idea.auto_link!

- idea.auto_link: ALLE Ideen automatisch analysieren und sinnvoll verlinken
  → "Verlinke die Ideen sinnvoll" (KEINE spezifischen Namen!)
  → "Verbinde alle Ideen"
  → "Finde Verbindungen"
  → Erkennungsmerkmal: "die Ideen" (Plural, unspezifisch) statt "Idee X mit Y"

- idea.analyze_links: NUR Vorschläge ANZEIGEN ohne zu verlinken
  → "Analysiere die Ideen und schlage Verlinkungen vor"
  → "Welche Ideen sollten verbunden werden?"
  → "Zeige ein Beispiel zum Verlinken"
  → Erkennungsmerkmal: "schlage vor", "analysiere", "welche sollten", "beispiel"

WICHTIG - Weitere Erkennungsmerkmale:
- "systematisch" + "verlinke" → idea.auto_link (NICHT idea.connect!)
- "relevante" + "verlinke" → idea.auto_link
- "die Ideen" (Plural!) + "verlinke" → idea.auto_link
- "Beispiel" + "verlinke" → idea.analyze_links
- KEINE spezifischen Ideen-Namen genannt → idea.auto_link!
- NUR wenn ZWEI konkrete Namen genannt werden → idea.connect

### idea.move - Idee in andere Bubble verschieben
- "Verschiebe X nach Y" → {"idea_title": "X", "target_bubble": "Y"}
- "Bringe die Idee X in die Bubble Y" → {"idea_title": "X", "target_bubble": "Y"}
- Keywords: verschiebe, bringe, bewege

### COMPLEX WORKFLOW COMMANDS (Multi-Step)
Diese Befehle sind zusammengesetzt und sollten als Multi-Step erkannt werden:

**Space Formatierung/Analyse:**
- "Formatiere den Space" → idea.list + idea.auto_link + idea.expand
- "Bereite den Space für Whitepaper vor" → idea.list + idea.auto_link
- "Analysiere und verlinke alle Ideen" → idea.list + idea.auto_link
- "Organisiere die Ideen sinnvoll" → idea.list + idea.auto_link + idea.expand
- "Erstelle eine Übersicht aller Ideen" → idea.list + idea.auto_link

**Space Management:**
- "Erstelle Space X und füge Idee Y hinzu" → bubble.create + idea.create
- "Geh in Space X und liste Ideen" → bubble.enter + idea.list
- "Erstelle Space X, betrete ihn und verlinke Ideen" → bubble.create + bubble.enter + idea.auto_link

**Keywords für Multi-Step:**
- formatiere, bereite vor, analysiere, organisiere, übersicht
- und dann, danach, anschließend, sowie
- sinnvoll, automatisch, alle, zusammen

### evaluation.clarify vs echte Aktion
- evaluation.clarify: "Ich meinte eine Idee erstellen" → NUR loggen, NICHT ausfuehren!
- echte Aktion: "Erstelle eine Idee" → Aktion ausfuehren

### evaluation.correct - Kurze Bestaetigung
- "Perfekt", "Genau", "Ja genau", "Stimmt", "Super" → evaluation.correct (NICHT conversation.greeting!)

---

## MULTI-STEP ERKENNUNG

WICHTIG: Erkenne wenn der User MEHRERE Aktionen in einem Satz beschreibt!
Schluesselsignale: "und", "dann", "danach", "sowie", Kommas zwischen Aktionen

Beispiele fuer Multi-Step:
- "Erstelle Space Marketing und fuege eine Idee Social Media hinzu"
  → 2 Aktionen: bubble.create + idea.create
- "Geh in Projekt, liste die Ideen und verlinke sie sinnvoll"
  → 3 Aktionen: bubble.enter + idea.list + idea.auto_link
- "Erstelle eine Bubble Test, dann eine Idee Alpha und verbinde sie mit Beta"
  → 3 Aktionen: bubble.create + idea.create + idea.connect
- "Formatiere den aktuellen Space so dass die Ideen sinnvoll verlinkt werden"
  → 3 Aktionen: idea.list + idea.auto_link + idea.expand
- "Bereite den Space für Whitepaper vor"
  → 2 Aktionen: idea.list + idea.auto_link
- "Analysiere und verlinke alle Ideen"
  → 2 Aktionen: idea.list + idea.auto_link

Bei Multi-Step returniere DIESES Format:
{
    "is_multi_step": true,
    "steps": [
        {"event_type": "bubble.create", "payload": {"title": "Marketing"}},
        {"event_type": "idea.create", "payload": {"title": "Social Media"}}
    ],
    "response_hint": "Ich erstelle den Space und die Idee..."
}

REIHENFOLGE beachten (Dependencies):
- bubble.create VOR idea.create (Idee braucht Space)
- bubble.enter VOR idea.list (Liste braucht aktiven Space)
- idea.create VOR idea.connect (Verbindung braucht Ideen)

NICHT Multi-Step (nur EINE Aktion):
- "Erstelle eine Bubble" → Single: bubble.create
- "Verlinke die Ideen sinnvoll" → Single: idea.auto_link
- "Geh in Marketing" → Single: bubble.enter

---

## User Intent
$INTENT$

## Antwort
KRITISCH: Extrahiere die EXAKTEN Woerter/Namen aus dem User Intent!
Kopiere NIEMALS Beispielwerte!

Fuer SINGLE-STEP (eine Aktion):
{"event_type": "der.event.type", "payload": {"param": "WERT"}, "response_hint": "Deutsche Phrase"}

Fuer MULTI-STEP (mehrere Aktionen):
{"is_multi_step": true, "steps": [{"event_type": "...", "payload": {...}}, ...], "response_hint": "..."}

Das response_hint ist eine kurze deutsche Phrase die Rachel sprechen kann.
"""


class IntentClassifier:
    """
    LLM-based intent classifier.

    Uses Claude (via OpenRouter) to classify natural language
    into structured event types with parameters.
    """

    def __init__(self, model_client=None, model: Optional[str] = None):
        """
        Initialize the classifier.

        Args:
            model_client: Pre-configured model client
            model: Model override (default: Claude Haiku for speed)
        """
        self._client = model_client
        self._model = model or os.getenv("CLASSIFIER_MODEL", "anthropic/claude-3.5-haiku")
        self._own_client = None

    def _post_process_classification(self, result: Dict[str, Any], user_input: str) -> Dict[str, Any]:
        """
        Post-process classification to fix common misclassifications.

        Applies rule-based corrections for known error patterns identified
        in evaluation (76.1% -> 88%+ target).
        """
        # Track which rules are applied (for structured logging)
        self._applied_rules = []

        intent = result.get("event_type", "")
        text_lower = user_input.lower()
        payload = result.get("payload", {})

        # =====================================================================
        # Rule 15: Evaluation-Feedback Priority (EARLY RETURN for short feedback)
        # Must be FIRST to catch feedback before other rules process it
        # =====================================================================
        feedback_correct = ["perfekt", "genau das", "ja genau", "richtig so", "stimmt", "genau", "super"]
        feedback_incorrect = ["nein", "falsch", "nicht das", "das war falsch", "falsch verstanden"]

        # Short confirmations (< 30 chars) are almost always feedback
        if len(user_input) < 30:
            if any(kw in text_lower for kw in feedback_correct):
                result["event_type"] = "evaluation.correct"
                result["payload"] = {}
                self._applied_rules.append("rule_15_feedback_correct")
                logger.debug(f"Post-process: -> evaluation.correct (short feedback)")
                return result  # Early return - no further processing

        if any(kw in text_lower for kw in feedback_incorrect):
            result["event_type"] = "evaluation.incorrect"
            result["payload"] = {}
            self._applied_rules.append("rule_15_feedback_incorrect")
            logger.debug(f"Post-process: -> evaluation.incorrect (feedback)")
            return result  # Early return

        # Rule 1: "wechsle zu X" / "geh in X" / "oeffne X" -> bubble.enter (nicht create!)
        if intent == "bubble.create":
            enter_keywords = [
                "wechsle zu", "wechsel zu", "geh in", "gehe in",
                "oeffne", "öffne", "betrete", "in den bereich",
                "zeig mir den", "bring mich zu"
            ]
            # Check if it's navigation, not creation
            create_keywords = ["erstelle", "neu", "anlegen", "leg an", "mach einen", "neuen"]
            has_enter_keyword = any(kw in text_lower for kw in enter_keywords)
            has_create_keyword = any(kw in text_lower for kw in create_keywords)

            if has_enter_keyword and not has_create_keyword:
                result["event_type"] = "bubble.enter"
                # Convert title to bubble_name
                if "title" in payload:
                    result["payload"]["bubble_name"] = payload.pop("title")
                self._applied_rules.append("rule_1_enter_not_create")
                logger.debug(f"Post-process: bubble.create -> bubble.enter for '{user_input[:30]}...'")

        # Rule 2: "zurueck" / "uebersicht" / "raus" -> bubble.exit
        if intent == "conversation.unknown":
            exit_keywords = ["zurück", "zurueck", "übersicht", "uebersicht", "raus", "verlasse", "schliessen"]
            if any(kw in text_lower for kw in exit_keywords):
                result["event_type"] = "bubble.exit"
                result["payload"] = {}
                logger.debug(f"Post-process: conversation.unknown -> bubble.exit for '{user_input[:30]}...'")

        # Rule 3: Desktop-specific keywords -> desktop.type (nicht idea.create!)
        if intent == "idea.create":
            desktop_type_keywords = ["tippe", "eingeben", "feld", "formular", "gib ein", "schreibe in"]
            if any(kw in text_lower for kw in desktop_type_keywords):
                result["event_type"] = "desktop.type"
                # Convert to text payload
                content = payload.get("content", payload.get("title", user_input))
                result["payload"] = {"text": content}
                logger.debug(f"Post-process: idea.create -> desktop.type for '{user_input[:30]}...'")

        # Rule 4: "druecke enter/escape/tab" -> desktop.press_key
        if intent == "conversation.unknown" and "drück" in text_lower or "drueck" in text_lower:
            key_names = ["enter", "escape", "tab", "strg", "ctrl", "alt", "shift", "space", "leertaste"]
            for key in key_names:
                if key in text_lower:
                    result["event_type"] = "desktop.press_key"
                    result["payload"] = {"key": key}
                    logger.debug(f"Post-process: -> desktop.press_key ({key})")
                    break

        # Rule 5: "scroll runter/hoch" -> desktop.scroll
        if intent == "conversation.unknown":
            if "scroll" in text_lower:
                direction = "down" if any(kw in text_lower for kw in ["runter", "unten", "down"]) else "up"
                result["event_type"] = "desktop.scroll"
                result["payload"] = {"direction": direction}
                logger.debug(f"Post-process: -> desktop.scroll ({direction})")

        # Rule 6: "screenshot" -> desktop.screenshot
        if intent == "conversation.unknown":
            if "screenshot" in text_lower or "bildschirmfoto" in text_lower:
                result["event_type"] = "desktop.screenshot"
                result["payload"] = {}
                logger.debug(f"Post-process: -> desktop.screenshot")

        # Rule 6b: OpenClaw/Gateway status -> openclaw.status
        if intent == "conversation.unknown":
            openclaw_kw = ["openclaw", "gateway", "clawed"]
            status_kw = ["status", "verbunden", "connected", "zustand"]
            if any(kw in text_lower for kw in openclaw_kw) and any(kw in text_lower for kw in status_kw):
                result["event_type"] = "openclaw.status"
                result["payload"] = {}
                logger.debug(f"Post-process: -> openclaw.status")

        # Rule 7: evaluation.clarify - "ich meinte" / "eigentlich wollte" - MUST NOT execute action
        clarify_keywords = ["meinte", "eigentlich wollte", "ich wollte eigentlich", "nicht das"]
        if any(kw in text_lower for kw in clarify_keywords):
            # Force evaluation.clarify regardless of what LLM said
            if intent not in ["evaluation.correct", "evaluation.incorrect", "evaluation.stats"]:
                result["event_type"] = "evaluation.clarify"
                result["payload"] = {"correction": user_input}
                logger.debug(f"Post-process: -> evaluation.clarify (feedback)")

        # Rule 8: "abbrechen" / "stopp" without code context -> code.cancel or bubble.exit
        if intent == "conversation.unknown":
            if "abbrechen" in text_lower or "stopp" in text_lower:
                # Check for code-related context
                if any(kw in text_lower for kw in ["generierung", "code", "projekt"]):
                    result["event_type"] = "code.cancel"
                else:
                    result["event_type"] = "bubble.exit"
                result["payload"] = {}
                logger.debug(f"Post-process: -> code.cancel/bubble.exit")

        # Rule 9: idea.expand German trigger words
        if intent == "conversation.unknown":
            expand_keywords = [
                "unterteile", "erweitere", "ausarbeite", "entwickle",
                "zerlege", "brainstorme", "reichere", "anreichern",
                "formuliere", "ausformulieren", "unterideen"
            ]
            if any(kw in text_lower for kw in expand_keywords):
                # Check if context is about ideas/notes
                if any(ctx in text_lower for ctx in ["ideen", "idee", "notizen", "notiz", "sie", "es"]):
                    result["event_type"] = "idea.expand"
                    result["payload"] = {}
                    logger.debug(f"Post-process: -> idea.expand")

        # =====================================================================
        # Rule 10: Query-Keywords -> bubble.list or idea.list
        # Fixes: "Welche Spaces gibt es?" being classified as conversation.help
        # =====================================================================
        if intent in ["conversation.unknown", "conversation.help"]:
            list_keywords = ["welche", "zeig mir", "liste", "auflisten", "aufzählen", "aufzaehlen", "was gibt es"]
            if any(kw in text_lower for kw in list_keywords):
                # Determine if asking about spaces or ideas
                space_indicators = ["space", "spaces", "bereiche", "bereich", "bubbles", "bubble"]
                idea_indicators = ["notiz", "notizen", "ideen", "idee", "hier", "alles"]

                if any(s in text_lower for s in space_indicators):
                    result["event_type"] = "bubble.list"
                    result["payload"] = {}
                    logger.debug(f"Post-process: -> bubble.list (query)")
                elif any(i in text_lower for i in idea_indicators):
                    result["event_type"] = "idea.list"
                    result["payload"] = {}
                    logger.debug(f"Post-process: -> idea.list (query)")

        # =====================================================================
        # Rule 11: Stats Keywords -> bubble.stats (but NOT summary of ideas)
        # Fixes: "Gib mir eine Zusammenfassung dieses Bereichs" -> bubble.stats
        # Note: "zusammenfassung" with idea context -> idea.summarize (handled by LLM)
        # =====================================================================
        if intent in ["bubble.list", "conversation.unknown", "idea.list"]:
            # Pure stats keywords (no overlap with idea.summarize)
            stats_keywords = ["statistik", "wie viele", "info", "übersicht über", "uebersicht"]
            # "zusammenfassung" only for bubble.stats when it's about the bubble/bereich itself
            summary_bubble_keywords = ["zusammenfassung dieses bereichs", "zusammenfassung der bubble",
                                       "zusammenfassung des space"]
            if any(kw in text_lower for kw in stats_keywords):
                result["event_type"] = "bubble.stats"
                result["payload"] = {}
                logger.debug(f"Post-process: -> bubble.stats (stats)")
            elif any(kw in text_lower for kw in summary_bubble_keywords):
                result["event_type"] = "bubble.stats"
                result["payload"] = {}
                logger.debug(f"Post-process: -> bubble.stats (summary of bubble)")
            elif "zusammenfass" in text_lower:
                # Generic "zusammenfassung" -> idea.summarize (let LLM extract idea_name)
                result["event_type"] = "idea.summarize"
                result["payload"] = {}
                logger.debug(f"Post-process: -> idea.summarize (summary keyword)")

        # =====================================================================
        # Rule 12: Search Keywords -> idea.find (not bubble.enter)
        # Fixes: "Suche nach Marketing" being classified as bubble.enter
        # =====================================================================
        if intent == "bubble.enter":
            search_keywords = ["such", "finde", "alles was mit", "zeig mir alles", "zu tun hat"]
            if any(kw in text_lower for kw in search_keywords):
                result["event_type"] = "idea.find"
                # Try to extract the search query
                query = ""
                if "suche nach " in text_lower:
                    query = text_lower.split("suche nach ")[1].split()[0] if "suche nach " in text_lower else ""
                elif "finde " in text_lower:
                    query = text_lower.split("finde ")[1].split()[0] if "finde " in text_lower else ""
                elif "alles was mit " in text_lower:
                    parts = text_lower.split("alles was mit ")
                    if len(parts) > 1:
                        query = parts[1].split()[0]
                result["payload"] = {"query": query} if query else {}
                logger.debug(f"Post-process: bubble.enter -> idea.find (search)")

        # =====================================================================
        # Rule 13: Connect/Link Keywords -> idea.connect
        # Fixes: "Verbinde Marketing mit Social Media" -> conversation.unknown
        # EXTENDED: Also check idea.list (LLM classifies "vorhandene Ideen" as list)
        # IMPROVED: Extract full multi-word titles (not just last word)
        # =====================================================================
        if intent in ["conversation.unknown", "idea.create", "idea.list"]:
            connect_keywords = ["verbinde", "verbindung", "verknüpfe", "verknuepfe", "verlinke", "link"]
            if any(kw in text_lower for kw in connect_keywords):
                result["event_type"] = "idea.connect"
                # Extract source and target with multi-word support
                source, target = "", ""
                if " mit " in text_lower:
                    parts = text_lower.split(" mit ", 1)  # Split only on first "mit"
                    before_mit = parts[0]
                    after_mit = parts[1] if len(parts) > 1 else ""

                    # Remove leading keywords to get source (full multi-word title)
                    for kw in ["verbinde", "verlinke", "verknüpfe", "verknuepfe", "mach eine verbindung zwischen"]:
                        if before_mit.startswith(kw):
                            before_mit = before_mit[len(kw):].strip()
                            break

                    # Clean up common filler words at start
                    for filler in ["die idee ", "idee ", "die ", "den "]:
                        if before_mit.startswith(filler):
                            before_mit = before_mit[len(filler):].strip()
                            break

                    source = before_mit.strip()  # Full multi-word title

                    # Target: everything after "mit" until end or filler words
                    after_mit = after_mit.strip()
                    for filler in ["der idee ", "idee ", "der ", "die "]:
                        if after_mit.startswith(filler):
                            after_mit = after_mit[len(filler):].strip()
                            break
                    target = after_mit.strip()

                elif " zwischen " in text_lower and " und " in text_lower:
                    between_part = text_lower.split(" zwischen ")[1] if " zwischen " in text_lower else ""
                    if " und " in between_part:
                        entities = between_part.split(" und ", 1)
                        source = entities[0].strip()
                        target = entities[1].strip() if len(entities) > 1 else ""

                result["payload"] = {"source": source, "target": target}
                logger.debug(f"Post-process: -> idea.connect ('{source}' -> '{target}')")

        # =====================================================================
        # Rule 13b: Auto-Link Keywords -> idea.auto_link or idea.analyze_links
        # HINWEIS: Diese Regel ist ein Fallback. Das LLM sollte idea.auto_link/
        # idea.analyze_links korrekt klassifizieren. Wenn diese Regel greift,
        # sollte das LLM-Prompt verbessert werden!
        # Fixes: "Verlinke die Ideen sinnvoll" -> idea.connect (should be auto_link)
        # Fixes: "Analysiere die Ideen und schlage Verlinkungen vor"
        # =====================================================================
        if intent in ["idea.connect", "conversation.unknown", "idea.list",
                      "bubble.enter", "bubble.find", "conversation.clarify", "batch",
                      "bubble.current"]:  # Added bubble.current for "zeige beispiel" cases
            auto_link_keywords = ["sinnvoll", "automatisch", "alle ideen", "analysiere", "finde verbindungen",
                                  "miteinander", "untereinander", "zueinander", "zusammen",
                                  "systematisch", "relevante", "durchgehen", "die ideen"]  # Extended
            link_keywords = ["verlink", "verbind", "verknüpf", "verknuepf", "link"]
            analyze_keywords = ["analysiere", "schlage vor", "vorschlag", "suggest", "welche.*zusammen",
                                "beispiel"]  # Added "beispiel" for example requests

            has_link_keyword = any(kw in text_lower for kw in link_keywords)
            has_auto_keyword = any(kw in text_lower for kw in auto_link_keywords)
            has_analyze_keyword = any(kw in text_lower for kw in analyze_keywords)

            # "Analysiere und schlage Verlinkungen vor" -> idea.analyze_links
            if has_analyze_keyword and has_link_keyword:
                result["event_type"] = "idea.analyze_links"
                result["payload"] = {}
                self._applied_rules.append("rule_13b_analyze_links")
                # WARN-Level: LLM sollte dies selbst erkennen!
                logger.warning(f"[FALLBACK RULE 13b] LLM returned '{intent}' but should be 'idea.analyze_links' for: '{user_input[:60]}...'")
            # If it has both link and auto keywords, it's auto_link
            # Also if link keyword present but NO specific idea names (no "X mit Y")
            elif has_link_keyword and has_auto_keyword:
                result["event_type"] = "idea.auto_link"
                result["payload"] = {}
                self._applied_rules.append("rule_13b_auto_link")
                # WARN-Level: LLM sollte dies selbst erkennen!
                logger.warning(f"[FALLBACK RULE 13b] LLM returned '{intent}' but should be 'idea.auto_link' for: '{user_input[:60]}...'")
            elif has_link_keyword and intent == "idea.connect":
                # Check if two specific ideas were mentioned (source/target filled)
                source = payload.get("source", "")
                target = payload.get("target", "")
                if not source or not target:
                    # No specific ideas - probably want auto_link
                    result["event_type"] = "idea.auto_link"
                    result["payload"] = {}
                    self._applied_rules.append("rule_13b_auto_link_fallback")
                    logger.warning(f"[FALLBACK RULE 13b] LLM returned 'idea.connect' without names, converting to 'idea.auto_link' for: '{user_input[:60]}...'")

        # =====================================================================
        # Rule 14: Move/Bring Keywords -> idea.move
        # Fixes: "Bringe die Idee Social Media in den Space Marketing" -> idea.create
        # =====================================================================
        if intent in ["conversation.unknown", "idea.create"]:
            move_keywords = ["verschiebe", "bringe", "bewege", "schieb", "move"]
            if any(kw in text_lower for kw in move_keywords):
                # Don't override idea.connect
                if result.get("event_type") != "idea.connect":
                    result["event_type"] = "idea.move"
                    # Extract idea title and target space
                    idea_title, target_bubble = "", ""
                    if " nach " in text_lower:
                        parts = text_lower.split(" nach ")
                        idea_part = parts[0] if parts else ""
                        target_part = parts[1] if len(parts) > 1 else ""
                        # Try to extract the idea name (usually after "idee" or last word)
                        if "idee " in idea_part:
                            idea_title = idea_part.split("idee ")[1].strip().split()[0] if "idee " in idea_part else ""
                        else:
                            idea_title = idea_part.split()[-1] if idea_part.split() else ""
                        # Target is usually the first word after "nach"
                        target_bubble = target_part.split()[0] if target_part.split() else ""
                    elif " in den space " in text_lower or " in die bubble " in text_lower:
                        separator = " in den space " if " in den space " in text_lower else " in die bubble "
                        parts = text_lower.split(separator)
                        idea_part = parts[0] if parts else ""
                        target_part = parts[1] if len(parts) > 1 else ""
                        if "idee " in idea_part:
                            idea_title = idea_part.split("idee ")[1].strip().split()[0] if "idee " in idea_part else ""
                        target_bubble = target_part.split()[0] if target_part.split() else ""
                    elif " in " in text_lower:
                        parts = text_lower.split(" in ")
                        idea_part = parts[0] if parts else ""
                        target_part = parts[1] if len(parts) > 1 else ""
                        idea_title = idea_part.split()[-1] if idea_part.split() else ""
                        target_bubble = target_part.split()[-1] if target_part.split() else ""
                    result["payload"] = {"idea_title": idea_title, "target_bubble": target_bubble}
                    logger.debug(f"Post-process: -> idea.move ({idea_title} -> {target_bubble})")

        # =====================================================================
        # Rule 16: Search/Find Bubble Keywords -> bubble.find (NOT bubble.list!)
        # Fixes: "Such nach Bubble Swarm Team" -> bubble.list (should be bubble.find)
        # IMPORTANT: Don't include "gibt es" - that's a list pattern, not search!
        # =====================================================================
        if intent == "bubble.list":
            bubble_search_keywords = ["such", "finde", "wo ist", "namens"]
            # Only convert to find if search pattern found AND NOT a list pattern
            list_override_patterns = ["welche", "habe ich", "zeig mir alle", "liste"]
            if any(kw in text_lower for kw in bubble_search_keywords) and not any(p in text_lower for p in list_override_patterns):
                result["event_type"] = "bubble.find"
                # Try to extract bubble name/query
                query = ""
                for pattern in ["bubble namens ", "bubble ", "nach "]:
                    if pattern in text_lower:
                        parts = text_lower.split(pattern)
                        if len(parts) > 1 and parts[1].strip():
                            # Get remaining words as query
                            query = parts[1].strip()
                            # Remove trailing question marks or punctuation
                            query = query.rstrip("?!.")
                            break
                result["payload"] = {"query": query} if query else {}
                logger.debug(f"Post-process: bubble.list -> bubble.find (search: '{query}')")

        # =====================================================================
        # Rule 17: Generic "zurueck" without target -> context-aware exit
        # Fixes: "Zurueck" from Project Space not working
        # =====================================================================
        if intent in ["conversation.unknown", "bubble.exit"]:
            back_keywords = ["zurück", "zurueck", "back", "raus", "verlasse", "exit"]
            if any(kw in text_lower for kw in back_keywords):
                # Check if we're in a specific space context
                coding_context = ["projekt", "project", "code", "coding", "generation", "preview"]
                if any(ctx in text_lower for ctx in coding_context):
                    result["event_type"] = "code.exit"
                    result["payload"] = {}
                    logger.debug(f"Post-process: -> code.exit (coding context)")
                else:
                    # Default to bubble.exit for Ideas Space
                    result["event_type"] = "bubble.exit"
                    result["payload"] = {}
                    logger.debug(f"Post-process: -> bubble.exit (generic back)")

        # =====================================================================
        # Rule 20: Conversation intents have priority over "batch"
        # Fixes: "Hallo Rachel" and "Was kannst du?" being classified as batch
        # Phase 7: Simulation showed batch was returned for greetings/help
        # =====================================================================
        if intent == "batch":
            greeting_words = ["hallo", "hi", "hey", "guten", "moin", "servus", "grüß"]
            help_words = ["was kannst", "hilfe", "help", "wie funktioniert", "was machst du"]

            if any(w in text_lower for w in greeting_words):
                result["event_type"] = "conversation.greeting"
                result["payload"] = {}
                logger.debug(f"Post-process: batch -> conversation.greeting")
            elif any(w in text_lower for w in help_words):
                result["event_type"] = "conversation.help"
                result["payload"] = {}
                logger.debug(f"Post-process: batch -> conversation.help")

        # =====================================================================
        # Rule 21: Short context-sensitive commands -> use recent context
        # Fixes: "Geh rein" without bubble name should use last created bubble
        # Phase 7: Simulation showed "Geh rein" becoming conversation.clarify
        # =====================================================================
        if intent == "conversation.clarify" or (intent == "conversation.unknown" and len(user_input) < 20):
            short_enter_commands = ["geh rein", "rein", "enter", "betrete", "öffne", "oeffne"]
            if any(cmd in text_lower for cmd in short_enter_commands):
                # Try to get recent bubble context from SystemContextStore
                try:
                    from swarm.orchestrator.system_context_store import get_system_context_store
                    context_store = get_system_context_store()
                    recent_events = context_store.get_recent_events("bubble.create", limit=1)

                    if recent_events and recent_events[0].payload:
                        bubble_name = recent_events[0].payload.get("title", "")
                        if bubble_name:
                            result["event_type"] = "bubble.enter"
                            result["payload"] = {"bubble_name": bubble_name}
                            logger.debug(f"Post-process: -> bubble.enter (context: {bubble_name})")
                except Exception as e:
                    logger.debug(f"Context lookup failed for Rule 21: {e}")
                    # Fallback: just set bubble.enter without name, tool will ask
                    result["event_type"] = "bubble.enter"
                    result["payload"] = {}

        # =====================================================================
        # Rule 22: "Welche X gibt es?" -> X.list (nicht X.find)
        # Fixes: "Welche Bubbles gibt es?" -> bubble.list (nicht bubble.find)
        # Phase 8: Simulation showed bubble.find being used for list queries
        # =====================================================================
        if intent == "bubble.find":
            list_patterns = ["welche", "gibt es", "habe ich", "zeig mir alle", "liste", "auflisten"]
            # Only convert to list if it's a list pattern AND not a search
            if any(p in text_lower for p in list_patterns) and "such" not in text_lower and "finde" not in text_lower:
                result["event_type"] = "bubble.list"
                result["payload"] = {}
                logger.debug(f"Post-process: bubble.find -> bubble.list (list pattern detected)")

        # =====================================================================
        # Rule 23: Erweitern/Unterteilen -> idea.expand
        # Fixes: "Erweitere die Ideen" -> idea.expand (nicht conversation.clarify)
        # Phase 8: Simulation showed expand commands becoming conversation.clarify
        # =====================================================================
        if intent in ["conversation.clarify", "conversation.unknown"]:
            expand_words = ["erweitere", "unterteile", "entwickle", "ausarbeiten", "detailliere", "expandiere", "generiere"]
            if any(w in text_lower for w in expand_words):
                # Check if it's about ideas
                idea_context = ["idee", "ideen", "notiz", "notizen", "konzept", "gedanke"]
                if any(ctx in text_lower for ctx in idea_context) or len(text_lower.split()) <= 4:
                    result["event_type"] = "idea.expand"
                    result["payload"] = {}
                    logger.debug(f"Post-process: {intent} -> idea.expand (expand word detected)")

        # =====================================================================
        # Rule 25: Strukturierte Formatierung -> idea.format
        # Fixes: "Formatiere die Ideen in Aktionslisten" -> idea.format
        # Enables LLM-driven structured content conversion
        # =====================================================================
        if intent in ["conversation.unknown", "idea.list", "idea.expand"]:
            format_keywords = ["formatiere", "formatiert", "konvertiere", "wandele", "ueberfuehre", "ueberführen"]
            structure_keywords = ["aktionsliste", "action list", "tabelle", "table", "hierarchie", "hierarchy",
                                  "vor/nachteile", "pros/cons", "technische specs", "technical specs"]

            has_format_keyword = any(kw in text_lower for kw in format_keywords)
            has_structure_keyword = any(kw in text_lower for kw in structure_keywords)

            if has_format_keyword or has_structure_keyword:
                result["event_type"] = "idea.format"
                # Extract target format from text
                format_type = "action_list"  # default
                if "aktionsliste" in text_lower or "action list" in text_lower:
                    format_type = "action_list"
                elif "tabelle" in text_lower or "table" in text_lower:
                    if "vor" in text_lower and "nachteil" in text_lower:
                        format_type = "pros_cons_table"
                    else:
                        format_type = "comparison_table"
                elif "hierarchie" in text_lower or "hierarchy" in text_lower:
                    format_type = "hierarchy"
                elif "technische" in text_lower and "specs" in text_lower:
                    format_type = "technical_specs"

                result["payload"] = {"format_type": format_type, "original_request": user_input}
                self._applied_rules.append("rule_25_structured_formatting")
                logger.debug(f"Post-process: -> idea.format ({format_type})")

        # =====================================================================
        # Rule 26: Komplexe Strukturierungen -> idea.structure
        # Fixes: "Organisiere die Ideen hierarchisch" -> idea.structure
        # For complex multi-step structuring operations
        # =====================================================================
        if intent in ["conversation.unknown", "idea.list", "idea.auto_link"]:
            structure_keywords = ["organisiere", "organisier", "strukturiere", "übersicht", "uebersicht",
                                  "zusammenfass", "hierarchisch", "systematisch"]
            complex_indicators = ["alle", "gesamte", "komplett", "vollständig", "vollstaendig"]

            has_structure_keyword = any(kw in text_lower for kw in structure_keywords)
            has_complex_indicator = any(ci in text_lower for ci in complex_indicators)

            if has_structure_keyword and has_complex_indicator:
                result["event_type"] = "idea.structure"
                result["payload"] = {"operation": "complex_structure", "original_request": user_input}
                self._applied_rules.append("rule_26_complex_structure")
                logger.debug(f"Post-process: -> idea.structure (complex organization)")

        # =====================================================================
        # Rule 28: Exploration Keywords -> idea.explore.*
        # Fixes: "Finde tiefere Verbindungen" -> idea.explore.start
        # AI-Scientist-style deep connection discovery with interactive modes
        # =====================================================================
        if intent in ["conversation.unknown", "idea.auto_link", "idea.analyze_links", "idea.find"]:
            # Start keywords with mode detection
            explore_start_auto = ["verbindungen automatisch", "finde verbindungen auto"]
            explore_start_interactive = ["verbindungen interaktiv", "finde verbindungen interaktiv",
                                         "interaktive exploration", "erkunde interaktiv"]
            explore_start_guided = ["verbindungen guided", "erkunde richtung", "fokussiere auf",
                                    "geh in richtung"]
            explore_start_keywords = ["tiefere verbindungen", "erforsche zusammenhänge", "erforsche zusammenhaenge",
                                      "versteckte verbindungen", "erkunde diese idee", "entdecke zusammenhänge",
                                      "entdecke zusammenhaenge", "analysiere verbindungen tiefer",
                                      "finde tiefere", "suche versteckte", "finde verbindungen"]
            explore_stop_keywords = ["stopp exploration", "beende suche", "abbrechen verbindungssuche"]
            explore_accept_keywords = ["akzeptiere diese verbindung", "speichere verbindung", "gute verbindung",
                                       "behalte diese", "ja behalten", "ja gut", "nehme ich"]
            explore_reject_keywords = ["lehne ab", "verbindung ist nicht gut", "verwerfen",
                                       "nein danke", "nicht gut", "überspringe", "ueberspringe"]
            explore_depth_keywords = ["gehe tiefer", "erkunde weiter", "nächste stufe", "naechste stufe",
                                      "tiefer erkunden", "mehr davon"]
            explore_status_keywords = ["exploration status", "wie weit bist du"]
            explore_visualize_keywords = ["zeige gefundene verbindungen", "visualisiere exploration", "was hast du gefunden"]
            explore_continue_keywords = ["weitermachen", "mach weiter", "weiter suchen"]
            explore_direction_keywords = ["erkunde richtung", "fokus auf", "geh richtung"]

            # Check interactive mode first (more specific)
            if any(kw in text_lower for kw in explore_start_interactive):
                result["event_type"] = "idea.explore.start"
                result["payload"] = {"mode": "interactive"}
                self._applied_rules.append("rule_28_explore_start_interactive")
                logger.debug(f"Post-process: -> idea.explore.start (interactive)")
            elif any(kw in text_lower for kw in explore_start_guided):
                result["event_type"] = "idea.explore.start"
                result["payload"] = {"mode": "guided"}
                self._applied_rules.append("rule_28_explore_start_guided")
                logger.debug(f"Post-process: -> idea.explore.start (guided)")
            elif any(kw in text_lower for kw in explore_start_auto):
                result["event_type"] = "idea.explore.start"
                result["payload"] = {"mode": "auto"}
                self._applied_rules.append("rule_28_explore_start_auto")
                logger.debug(f"Post-process: -> idea.explore.start (auto)")
            elif any(kw in text_lower for kw in explore_start_keywords):
                result["event_type"] = "idea.explore.start"
                result["payload"] = {}  # Default mode
                self._applied_rules.append("rule_28_explore_start")
                logger.debug(f"Post-process: -> idea.explore.start")
            elif any(kw in text_lower for kw in explore_stop_keywords):
                result["event_type"] = "idea.explore.stop"
                result["payload"] = {}
                self._applied_rules.append("rule_28_explore_stop")
            elif any(kw in text_lower for kw in explore_accept_keywords):
                result["event_type"] = "idea.explore.accept"
                result["payload"] = {}
                self._applied_rules.append("rule_28_explore_accept")
            elif any(kw in text_lower for kw in explore_reject_keywords):
                result["event_type"] = "idea.explore.reject"
                result["payload"] = {}
                self._applied_rules.append("rule_28_explore_reject")
            elif any(kw in text_lower for kw in explore_depth_keywords):
                result["event_type"] = "idea.explore.depth"
                result["payload"] = {}
                self._applied_rules.append("rule_28_explore_depth")
            elif any(kw in text_lower for kw in explore_status_keywords):
                result["event_type"] = "idea.explore.status"
                result["payload"] = {}
                self._applied_rules.append("rule_28_explore_status")
            elif any(kw in text_lower for kw in explore_visualize_keywords):
                result["event_type"] = "idea.explore.visualize"
                result["payload"] = {}
                self._applied_rules.append("rule_28_explore_visualize")
            elif any(kw in text_lower for kw in explore_continue_keywords):
                result["event_type"] = "idea.explore.continue"
                result["payload"] = {}
                self._applied_rules.append("rule_28_explore_continue")
            elif any(kw in text_lower for kw in explore_direction_keywords):
                result["event_type"] = "idea.explore.direction"
                result["payload"] = {"direction": text}
                self._applied_rules.append("rule_28_explore_direction")

        # =====================================================================
        # Rule 24: Detect potential multi-step patterns LLM missed
        # If single-step but text contains multi-action indicators, flag it
        # =====================================================================
        # Note: text_lower already defined above from user_input
        multi_step_connectors = [" und ", " dann ", " danach ", ", dann ", " sowie ", ", und "]
        action_verbs = ["erstelle", "create", "fuege", "add", "geh", "go", "liste", "list",
                        "verbinde", "link", "loesche", "delete", "verlinke", "zeig", "show"]

        # Count action verbs in input
        verb_count = sum(1 for v in action_verbs if v in text_lower)
        has_connector = any(c in text_lower for c in multi_step_connectors)

        if verb_count >= 2 and has_connector:
            # LLM returned single-step but text looks like multi-step
            logger.info(f"Post-process Rule 24: Detected potential multi-step ({verb_count} verbs, has connector)")
            # Don't auto-convert, just log for monitoring
            # Future: Could trigger re-classification with explicit multi-step hint

        # =====================================================================
        # Rule 27: Multi-step structured formatting -> idea.structure
        # Fixes: "Organisiere alle Ideen hierarchisch" -> idea.structure (not multi-step)
        # =====================================================================
        if intent == "batch" or (isinstance(result, dict) and result.get("is_multi_step")):
            text_lower = user_input.lower()
            structure_keywords = ["organisiere", "organisier", "strukturiere", "übersicht", "uebersicht",
                                  "hierarchisch", "systematisch", "gesamte", "vollständig", "vollstaendig"]

            if any(kw in text_lower for kw in structure_keywords):
                # Convert multi-step to single idea.structure event
                result = {
                    "event_type": "idea.structure",
                    "payload": {"operation": "complex_structure", "original_request": user_input},
                    "response_hint": "Ich strukturiere alle Ideen systematisch..."
                }
                self._applied_rules.append("rule_27_multi_step_structure")
                logger.debug(f"Post-process: multi-step -> idea.structure")
                return result

        return result

    def _post_process_multi_step(self, result: Dict[str, Any], intent_text: str) -> Dict[str, Any]:
        """
        Post-process multi-step classification results.

        Validates and potentially corrects multi-step classifications.

        Args:
            result: Classification result with is_multi_step=True
            intent_text: Original user input

        Returns:
            Processed result dict
        """
        steps = result.get("steps", [])
        text_lower = intent_text.lower()

        # =====================================================================
        # Convert complex multi-step to single idea.structure
        # =====================================================================
        structure_keywords = ["organisiere", "organisier", "strukturiere", "übersicht", "uebersicht",
                              "hierarchisch", "systematisch", "gesamte", "vollständig", "vollstaendig"]

        if any(kw in text_lower for kw in structure_keywords):
            # Convert to single idea.structure event
            logger.debug(f"Multi-step post-process: Converting to idea.structure")
            return {
                "is_multi_step": False,
                "event_type": "idea.structure",
                "payload": {"operation": "complex_structure", "original_request": intent_text},
                "response_hint": "Ich strukturiere alle Ideen systematisch..."
            }

        # Filter out invalid steps
        valid_steps = []
        for step in steps:
            event_type = step.get("event_type", "")

            # Skip conversational events in multi-step
            if event_type.startswith("conversation."):
                logger.debug(f"Multi-step post-process: Skipping conversational step {event_type}")
                continue

            # Skip evaluation events in multi-step
            if event_type.startswith("evaluation."):
                logger.debug(f"Multi-step post-process: Skipping evaluation step {event_type}")
                continue

            valid_steps.append(step)

        result["steps"] = valid_steps

        # If no valid steps remain, convert to conversation.unknown
        if not valid_steps:
            logger.warning("Multi-step post-process: No valid steps, converting to conversation.unknown")
            return {
                "is_multi_step": False,
                "event_type": "conversation.unknown",
                "payload": {"original_text": intent_text},
                "response_hint": "Ich habe nicht verstanden welche Aktionen du ausfuehren moechtest."
            }

        return result

    @property
    def client(self):
        """Get or create model client.

        Note: Always creates own OpenAI client. The passed model_client
        from autogen uses a different interface (OpenAIChatCompletionClient)
        and is NOT compatible with direct chat.completions.create() calls.
        """
        if self._own_client is None:
            try:
                from openai import OpenAI
                api_key = os.getenv("OPENROUTER_API_KEY")
                if not api_key:
                    raise ValueError("OPENROUTER_API_KEY not set")

                self._own_client = OpenAI(
                    api_key=api_key,
                    base_url="https://openrouter.ai/api/v1"
                )
                logger.info(f"IntentClassifier using {self._model}")
            except Exception as e:
                logger.error(f"Failed to create classifier client: {e}")
                raise

        return self._own_client

    async def classify(self, intent_text: str) -> Dict[str, Any]:
        """
        Classify user intent into event type and payload.

        Args:
            intent_text: Natural language user request

        Returns:
            Dict with event_type, payload, and response_hint
        """
        start_time = time.perf_counter()
        original_intent = None

        try:
            prompt = CLASSIFIER_PROMPT_TEMPLATE.replace("$INTENT$", intent_text)

            response = self.client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,  # Low temperature for consistent classification
                max_tokens=500,
            )

            content = response.choices[0].message.content.strip()

            # Phase 12: Debug logging - show raw LLM response
            import sys
            print(f"[Python DEBUG] [LLM RESPONSE] {content[:300]}", file=sys.stderr)

            # Extract JSON from response (handle markdown code blocks and explanatory text)
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            elif not content.startswith("{") and "{" in content:
                # LLM returned explanation text before JSON - extract JSON
                first_brace = content.find("{")
                content = content[first_brace:]
                logger.debug("Extracted JSON from explanatory text")

            # Handle multiple JSON objects (LLM sometimes returns multiple for batch requests)
            # Only take the first valid JSON object
            if content.startswith("{"):
                # Find the end of the first JSON object by counting braces
                brace_count = 0
                end_pos = 0
                for i, char in enumerate(content):
                    if char == "{":
                        brace_count += 1
                    elif char == "}":
                        brace_count -= 1
                        if brace_count == 0:
                            end_pos = i + 1
                            break
                if end_pos > 0:
                    content = content[:end_pos]

            result = json.loads(content)

            # =====================================================================
            # Multi-Step Validation (Phase 12)
            # Handle both multi-step and single-step responses
            # =====================================================================
            if result.get("is_multi_step"):
                # Multi-step: Validate steps array
                if "steps" not in result or not isinstance(result["steps"], list):
                    result["steps"] = []
                    logger.warning("Multi-step response missing 'steps' array")

                # Ensure each step has event_type and payload
                valid_steps = []
                for i, step in enumerate(result["steps"]):
                    if not isinstance(step, dict):
                        logger.warning(f"Multi-step: Step {i} is not a dict, skipping")
                        continue
                    if "event_type" not in step:
                        logger.warning(f"Multi-step: Step {i} missing event_type, skipping")
                        continue
                    if "payload" not in step:
                        step["payload"] = {}
                    valid_steps.append(step)

                result["steps"] = valid_steps

                # Multi-step needs response_hint
                if "response_hint" not in result:
                    step_count = len(valid_steps)
                    result["response_hint"] = f"Ich fuehre {step_count} Aktionen aus..."

                logger.info(f"Multi-step detected: {len(valid_steps)} steps")

            else:
                # Single-step (legacy): Ensure standard fields
                if "event_type" not in result:
                    result["event_type"] = "conversation.unknown"
                if "payload" not in result:
                    result["payload"] = {"original_text": intent_text}
                if "response_hint" not in result:
                    result["response_hint"] = "Ich bearbeite deine Anfrage..."

            # Apply post-processing rules for common misclassifications
            # Skip for multi-step (no top-level event_type)
            if not result.get("is_multi_step"):
                original_intent = result["event_type"]
                result = self._post_process_classification(result, intent_text)

                if result["event_type"] != original_intent:
                    logger.info(f"Post-processed: '{intent_text[:40]}...' {original_intent} -> {result['event_type']}")
                else:
                    logger.info(f"Classified: '{intent_text[:40]}...' -> {result['event_type']}")
            else:
                # For multi-step, check if LLM missed any patterns
                result = self._post_process_multi_step(result, intent_text)
                step_types = [s.get("event_type") for s in result.get("steps", [])]
                logger.info(f"Multi-step classified: '{intent_text[:40]}...' -> {step_types}")

            # Structured logging
            latency_ms = (time.perf_counter() - start_time) * 1000
            intent_logger = _get_intent_logger()
            if intent_logger:
                intent_logger.log_classification(
                    session_id="unknown",  # TODO: Pass session_id from caller
                    user_input=intent_text,
                    classification=result,
                    latency_ms=latency_ms,
                    original_intent=original_intent,
                    rules_applied=getattr(self, "_applied_rules", []),
                    llm_model=self._model
                )

            return result

        except json.JSONDecodeError as e:
            latency_ms = (time.perf_counter() - start_time) * 1000
            logger.error(f"Failed to parse classifier response: {e}")
            intent_logger = _get_intent_logger()
            if intent_logger:
                intent_logger.log_error(
                    session_id="unknown",
                    user_input=intent_text,
                    error=f"JSON decode error: {e}",
                    latency_ms=latency_ms
                )
            # Still try post-processing rules for known patterns
            result = {
                "event_type": "conversation.unknown",
                "payload": {"original_text": intent_text, "error": str(e)},
                "response_hint": "Ich habe dich nicht ganz verstanden."
            }
            result = self._post_process_classification(result, intent_text)
            return result
        except Exception as e:
            latency_ms = (time.perf_counter() - start_time) * 1000
            logger.error(f"Classification error: {e}")
            intent_logger = _get_intent_logger()
            if intent_logger:
                intent_logger.log_error(
                    session_id="unknown",
                    user_input=intent_text,
                    error=str(e),
                    latency_ms=latency_ms
                )
            return {
                "event_type": "conversation.unknown",
                "payload": {"original_text": intent_text, "error": str(e)},
                "response_hint": "Es gab ein Problem bei der Verarbeitung."
            }

    def classify_sync(self, intent_text: str) -> Dict[str, Any]:
        """
        Synchronous classification (for non-async contexts).

        Args:
            intent_text: Natural language user request

        Returns:
            Dict with event_type, payload, and response_hint
        """
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Already in async context - run in thread
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(asyncio.run, self.classify(intent_text))
                    return future.result()
            return loop.run_until_complete(self.classify(intent_text))
        except RuntimeError:
            return asyncio.run(self.classify(intent_text))


# Singleton instance
_classifier: Optional[IntentClassifier] = None


def get_intent_classifier(model_client=None) -> IntentClassifier:
    """Get or create IntentClassifier singleton."""
    global _classifier
    if _classifier is None:
        _classifier = IntentClassifier(model_client)
    return _classifier


__all__ = [
    "IntentClassifier",
    "get_intent_classifier",
    "CLASSIFIER_PROMPT_TEMPLATE",
]
