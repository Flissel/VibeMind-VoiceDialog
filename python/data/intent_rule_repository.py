"""
Intent Rule Repository with Supermemory Integration

Stores and retrieves intent classification rules using Supermemory's
semantic search capabilities. This replaces hardcoded keyword matching
with embedding-based similarity search.

Architecture:
    User Input -> Supermemory Search -> Top-K Rules -> LLM + Rules -> Intent
"""

import logging
import json
import os
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class IntentRule:
    """An intent classification rule with examples."""
    id: str
    intent_type: str  # e.g., "idea.auto_link"
    description: str  # e.g., "Alle Ideen automatisch verlinken"
    examples: List[str]  # Example phrases that trigger this intent
    priority: int = 0  # Higher = more important
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "intent_type": self.intent_type,
            "description": self.description,
            "examples": self.examples,
            "priority": self.priority,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "IntentRule":
        return cls(
            id=data.get("id", ""),
            intent_type=data.get("intent_type", ""),
            description=data.get("description", ""),
            examples=data.get("examples", []),
            priority=data.get("priority", 0),
            metadata=data.get("metadata", {}),
        )


# =============================================================================
# DEFAULT INTENT RULES
# =============================================================================

INITIAL_INTENT_RULES = [
    # === IDEA OPERATIONS ===
    {
        "intent_type": "idea.auto_link",
        "description": "Alle Ideen im Space automatisch verlinken (KI-basiert) / Auto-link all ideas in the space",
        "examples": [
            # German
            "Verlinke die Ideen sinnvoll",
            "Verbinde alle Ideen automatisch",
            "Gehe systematisch durch die Ideen und verlinke relevante",
            "Finde Verbindungen zwischen den Ideen",
            "Die Ideen sollen miteinander verknüpft werden",
            "Verknüpfe die Notizen intelligent",
            "Erstelle sinnvolle Verbindungen",
            "Link die Ideen zusammen",
            # English
            "Link the ideas together",
            "Auto-link all ideas",
            "Connect all ideas automatically",
            "Find connections between ideas",
            "Link related ideas",
            "Smart link all notes",
        ],
        "priority": 10,
    },
    {
        "intent_type": "idea.connect",
        "description": "Zwei spezifische Ideen verbinden (Namen werden genannt) / Connect two specific ideas by name",
        "examples": [
            # German
            "Verbinde Idee A mit Idee B",
            "Verlinke Marketing mit Social Media",
            "Mach eine Verbindung zwischen Projekt Alpha und Budget",
            "Verknüpfe die Idee X mit Y",
            "Link die Notiz A zu B",
            # English
            "Connect idea A with idea B",
            "Link Marketing to Social Media",
            "Connect Project Alpha with Budget",
            "Link idea X to Y",
            "Make a connection between A and B",
        ],
        "priority": 10,
    },
    {
        "intent_type": "idea.connect_multi",
        "description": "Eine Idee mit mehreren anderen verbinden (per Index oder Name) / Connect one idea to multiple others",
        "examples": [
            # German - numeric references
            "Verbinde 2 mit 3, 4 und 5",
            "Verknüpfe 1 mit 2, 3, 4",
            "Link 3 zu 4, 5, 6",
            # German - mixed
            "Verbinde Idee 1 mit 2, 3, 4, 5",
            "Verknüpfe die erste mit der zweiten, dritten und vierten",
            # English - numeric references
            "Connect 3 to 4 and 5 and 6",
            "Link 1 to 2, 3, 4",
            "Link 2 to 3, 4, 5, 6",
            # English - mixed
            "Connect idea 1 with 2, 3, 4",
        ],
        "priority": 11,  # Higher priority than idea.connect for multi-target
    },
    {
        "intent_type": "idea.analyze_links",
        "description": "Verlinkungsvorschläge anzeigen ohne auszuführen / Show link suggestions without executing",
        "examples": [
            # German
            "Zeige ein Beispiel zum Verlinken",
            "Welche Ideen sollten verbunden werden?",
            "Analysiere die Ideen und schlage Verlinkungen vor",
            "Was könnte zusammengehören?",
            "Vorschläge für Verbindungen",
            # English
            "Which ideas should be connected?",
            "Analyze ideas and suggest links",
            "What could belong together?",
            "Show link suggestions",
            "Suggest connections",
        ],
        "priority": 10,
    },
    {
        "intent_type": "idea.list",
        "description": "Alle Ideen im aktuellen Space auflisten / List all ideas in the current space",
        "examples": [
            # German
            "Zeig mir meine Ideen",
            "Was habe ich notiert?",
            "Liste die Notizen auf",
            "Welche Ideen gibt es hier?",
            "Was steht im Space?",
            # English
            "Show me my ideas",
            "What have I noted?",
            "List the notes",
            "What ideas are here?",
            "Show ideas in this space",
            "List all ideas",
        ],
        "priority": 5,
    },
    {
        "intent_type": "idea.count",
        "description": "Anzahl der Ideen im Space abfragen / Count ideas in space",
        "examples": [
            # German
            "Wie viele Ideen habe ich?",
            "Anzahl der Ideen",
            "Wie viele Notizen sind hier?",
            "Zähle die Ideen",
            "Wie viele Einträge gibt es?",
            "Wie viele Ideen sind in diesem Space?",
            # English
            "How many ideas do I have?",
            "Count the ideas",
            "How many notes are here?",
            "Number of ideas",
            "How many ideas in this space?",
        ],
        "priority": 5,
    },
    {
        "intent_type": "idea.create",
        "description": "Neue Idee erstellen / Create a new idea",
        "examples": [
            # German
            "Erstelle eine neue Idee",
            "Notiere mir das",
            "Merke dir das",
            "Schreib auf dass",
            "Neue Notiz anlegen",
            "Neue Idee: [irgendein Inhalt]",
            "Neue Idee erstellen mit dem Titel",
            "Leg eine neue Idee an",
            "Speichere diese Idee",
            "Neue Idee speichern",
            "Idee hinzufügen",
            "Füge eine Idee hinzu",
            # English
            "Create a new idea",
            "Note this down",
            "Remember this",
            "Write down that",
            "New note",
            "New idea: [some content]",
            "Create idea with title",
            "Add a new idea",
            "Save this idea",
            "Add idea",
        ],
        "priority": 10,  # Higher priority - explicit creation intent
    },
    {
        "intent_type": "idea.delete",
        "description": "Eine spezifische Idee oder alle Ideen löschen / Delete a specific idea or all ideas",
        "examples": [
            # German
            "Lösche die Idee über Marketing",
            "Entferne diese Notiz",
            "Lösche alle Ideen",
            "Lösche alle Notizen in diesem Space",
            "Alle Ideen entfernen",
            "Räume diesen Space auf",
            "Entferne die Idee X",
            "Lösche die Idee",
            "Diese Idee löschen",
            "Entferne alle Notizen",
            # English
            "Delete the marketing idea",
            "Remove this note",
            "Delete all ideas",
            "Delete all notes in this space",
            "Remove idea X",
            "Delete the idea",
            "Remove all notes",
        ],
        "priority": 9,  # High priority to prevent confusion with list
    },
    {
        "intent_type": "idea.find",
        "description": "Nach einer Idee suchen / Search for an idea",
        "examples": [
            # German
            "Suche nach der Idee über Marketing",
            "Finde die Notiz zum Thema Budget",
            "Wo ist die Idee zu Projekt X?",
            "Suche in meinen Ideen nach",
            # English
            "Search for the idea about marketing",
            "Find the note about budget",
            "Where is the idea about project X?",
            "Search my ideas for",
            "Find idea",
        ],
        "priority": 5,
    },
    {
        "intent_type": "idea.update",
        "description": "Eine bestehende Idee bearbeiten, umbenennen oder aktualisieren / Edit, rename or update an existing idea",
        "examples": [
            # German - Edit/Update
            "Ändere die Idee Marketing",
            "Bearbeite die Notiz",
            "Aktualisiere die Idee",
            "Update die Idee X",
            "Modifiziere den Inhalt",
            "Ergänze die Idee um",
            "Füge zur Idee hinzu",
            # German - Rename (NEW)
            "Benenne die Idee um",
            "Benenne den Root-Node um",
            "Benenne den Root-Node um in X",
            "Benenne die Notiz um",
            "Benenne den Node um in X",
            "Nenne die Idee jetzt X",
            "Die Idee soll jetzt X heißen",
            "Gib der Idee einen neuen Namen",
            # English
            "Edit the marketing idea",
            "Update the note",
            "Modify the idea",
            "Change idea X",
            "Update the content",
            "Add to the idea",
            # English - Rename (NEW)
            "Rename the idea to X",
            "Rename the node",
            "Rename the root node",
            "Give the idea a new name",
        ],
        "priority": 8,
    },
    {
        "intent_type": "idea.summarize",
        "description": "Zusammenfassung einer Idee oder des Spaces erstellen / Create a summary of an idea or the space",
        "examples": [
            # German
            "Erstelle eine Zusammenfassung",
            "Fasse die Ideen zusammen",
            "Summary des Spaces",
            "Was ist das Wichtigste hier?",
            # English
            "Create a summary",
            "Summarize the ideas",
            "Summary of the space",
            "What's most important here?",
            "Give me a summary",
        ],
        "priority": 8,
    },
    {
        "intent_type": "idea.whitepaper",
        "description": "Whitepaper aus Ideen generieren / Generate a whitepaper from ideas",
        "examples": [
            # German
            "Erstelle ein Whitepaper",
            "Generiere ein Dokument aus den Ideen",
            "Mach ein Paper daraus",
            "Whitepaper basierend auf",
            # English
            "Create a whitepaper",
            "Generate a document from the ideas",
            "Make a paper from this",
            "Whitepaper based on",
            "Write a whitepaper",
        ],
        "priority": 8,
    },
    {
        "intent_type": "idea.expand",
        "description": "Ideen erweitern oder unterteilen / Expand or subdivide ideas",
        "examples": [
            # German
            "Erweitere die Ideen",
            "Generiere verwandte Ideen",
            "Unterteile in kleinere Konzepte",
            "Entwickle Unterideen",
            "Brainstorme neue Ideen",
            # English
            "Expand the ideas",
            "Generate related ideas",
            "Subdivide into smaller concepts",
            "Develop sub-ideas",
            "Brainstorm new ideas",
            "Break down the idea",
        ],
        "priority": 7,
    },
    {
        "intent_type": "idea.classify",
        "description": "Idee klassifizieren oder ans Backend senden / Classify idea or send to backend for analysis",
        "examples": [
            # German
            "Klassifiziere die Idee",
            "Klassifiziere das",
            "Send das ans Backend",
            "Analysiere diese Idee",
            "Kategorisiere den Node",
            "Klassifiziere den Root-Node",
            "Was fuer eine Art Idee ist das?",
            "Ordne die Idee ein",
            "Backend-Klassifizierung",
            # English
            "Classify the idea",
            "Classify this",
            "Send to backend",
            "Analyze this idea",
            "Categorize the node",
            "What kind of idea is this?",
            "Backend classification",
        ],
        "priority": 8,
    },
    {
        "intent_type": "idea.link_to_root",
        "description": "Idee mit Root-Node verknüpfen / Link idea to root node",
        "examples": [
            # German
            "Verknüpfe das mit dem Root",
            "Link zur Hauptidee",
            "Mit Root verbinden",
            "An Root anhängen",
            "Verbinde das mit der Wurzel",
            "Zum Root-Node verlinken",
            "Mit dem Haupt-Node verbinden",
            # English
            "Connect to root",
            "Link to root",
            "Link to main node",
            "Connect to main idea",
            "Attach to root",
        ],
        "priority": 7,
    },
    {
        "intent_type": "idea.current_space",
        "description": "Aktuellen Space/Position anzeigen / Show current space/position",
        "examples": [
            # German
            "Wo bin ich gerade?",
            "In welchem Space bin ich?",
            "Welcher Space ist das?",
            "Zeig mir meinen aktuellen Space",
            "Wo befinde ich mich?",
            "Aktueller Space?",
            "Welcher Bereich ist aktiv?",
            # English
            "Where am I?",
            "What space am I in?",
            "Which space is this?",
            "Show my current space",
            "Current location?",
            "What's the current space?",
            "Which area is active?",
        ],
        "priority": 8,
    },
    {
        "intent_type": "idea.format_table",
        "description": "Idee als Tabelle formatieren (direktes Formatieren) / Format idea as table (direct formatting)",
        "examples": [
            # German
            "Formatiere die Idee als Tabelle",
            "Erstelle eine Tabelle aus der Idee",
            "Mach eine Tabelle mit Calls ID, Requirement und Content",
            "Strukturiere die Idee in Tabellenform",
            "Wandle die Notiz in eine Tabelle um",
            "Tabelle erstellen aus",
            "Als Tabelle formatieren",
            "Formatiere in eine Tabelle mit Spalten",
            # English
            "Format the idea as a table",
            "Create a table from the idea",
            "Make a table with columns",
            "Structure as table",
            "Format as table",
            "Table format please",
        ],
        "priority": 8,
    },
    {
        "intent_type": "idea.format_note",
        "description": "Idee als einfache Notiz formatieren / Format idea as simple note",
        "examples": [
            # German
            "Formatiere als Notiz",
            "Zurueck zur Textform",
            "Mach daraus eine einfache Notiz",
            "Als Text formatieren",
            "Wandle zurueck in Notiz",
            "Einfache Textform",
            # English
            "Format as note",
            "Back to text form",
            "Make it a simple note",
            "Format as text",
            "Convert back to note",
            "Plain text format",
        ],
        "priority": 8,
    },
    {
        "intent_type": "idea.format_action_list",
        "description": "Idee als Aufgabenliste formatieren / Format idea as action/task list",
        "examples": [
            # German
            "Formatiere als Aufgabenliste",
            "Mach eine Aufgabenliste daraus",
            "Erstelle Tasks daraus",
            "Als Todos formatieren",
            "Wandle in Aufgaben um",
            "Mach eine Todo-Liste",
            "Extrahiere die Aufgaben",
            # English
            "Format as action list",
            "Make a task list from this",
            "Create tasks from this",
            "Format as todos",
            "Convert to tasks",
            "Make a todo list",
            "Extract the tasks",
        ],
        "priority": 8,
    },
    {
        "intent_type": "idea.format_pros_cons",
        "description": "Idee als Pro-Contra-Liste formatieren / Format idea as pros and cons list",
        "examples": [
            # German
            "Erstelle Pro-Contra-Liste",
            "Formatiere als Vor- und Nachteile",
            "Mach eine Pro-Contra-Analyse",
            "Zeig Vorteile und Nachteile",
            "Was sind die Pros und Cons?",
            "Analysiere Vor- und Nachteile",
            # English
            "Create pros and cons list",
            "Format as advantages and disadvantages",
            "Make a pro-con analysis",
            "Show pros and cons",
            "What are the pros and cons?",
            "Analyze advantages and disadvantages",
        ],
        "priority": 8,
    },
    {
        "intent_type": "idea.format_hierarchy",
        "description": "Idee als Gliederung/Hierarchie formatieren / Format idea as hierarchy/outline",
        "examples": [
            # German
            "Formatiere als Gliederung",
            "Erstelle eine Hierarchie",
            "Strukturiere als Outline",
            "Mach eine Baumstruktur",
            "Gliedere hierarchisch",
            "Erstelle eine Struktur",
            # English
            "Format as outline",
            "Create a hierarchy",
            "Structure as outline",
            "Make a tree structure",
            "Organize hierarchically",
            "Create structure",
        ],
        "priority": 8,
    },
    {
        "intent_type": "idea.format_specs",
        "description": "Idee als technische Spezifikation formatieren / Format idea as technical specification",
        "examples": [
            # German
            "Formatiere als Spezifikation",
            "Erstelle technische Specs",
            "Mach eine Anforderungsliste",
            "Formatiere als Requirements",
            "Extrahiere technische Anforderungen",
            "Als technische Doku formatieren",
            # English
            "Format as specification",
            "Create technical specs",
            "Make a requirements list",
            "Format as requirements",
            "Extract technical requirements",
            "Format as technical documentation",
        ],
        "priority": 8,
    },
    {
        "intent_type": "idea.convert_format",
        "description": "Idee von einem Format in ein anderes konvertieren (Formatwechsel) / Convert idea from one format to another (format change)",
        "examples": [
            # German - KEY: emphasize CONVERSION from existing format
            "Konvertiere die Tabelle zu einer Notiz",
            "Wandle die Aufgabenliste in eine Tabelle um",
            "Aendere das Format von Notiz zu Tabelle",
            "Mach aus der Tabelle eine Notiz",
            "Konvertiere das aktuelle Format zu",
            "Wechsle das Format von X zu Y",
            "Die Tabelle soll jetzt eine Liste werden",
            "Aus der Gliederung eine Tabelle machen",
            # English - KEY: emphasize CONVERSION from existing format
            "Convert the table to a note",
            "Change the task list into a table",
            "Change the format from note to table",
            "Turn the table into a note",
            "Convert current format to",
            "Switch format from X to Y",
            "The table should become a list now",
            "Convert from outline to table",
        ],
        "priority": 9,  # Higher priority to distinguish from direct formatting
    },
    {
        "intent_type": "idea.list_formats",
        "description": "Verfuegbare Formate auflisten / List available formats",
        "examples": [
            # German
            "Welche Formate gibt es?",
            "Zeig mir die Formatoptionen",
            "Was fuer Formate kann ich nutzen?",
            "Liste die Formattypen auf",
            # English
            "What formats are available?",
            "Show me the format options",
            "What formats can I use?",
            "List the format types",
            "Available formats?",
        ],
        "priority": 5,
    },

    # === BUBBLE/SPACE OPERATIONS ===
    {
        "intent_type": "bubble.enter",
        "description": "In einen Space wechseln / Switch to a space",
        "examples": [
            # German
            "Gehe in den Space Marketing",
            "Wechsle zum Space Projekte",
            "Öffne den Bereich Design",
            "Bring mich zum Space",
            "Zeig mir den Space",
            "Navigiere zum Space",
            "Navigiere mich in den Marketing Space",
            "Navigiere mich in den Debug Information Space",
            "Gehe in den Debug Space",
            "Bring mich in den Ideas Space",
            # English
            "Go to the Marketing space",
            "Switch to the Projects space",
            "Open the Design area",
            "Take me to the space",
            "Navigate to space",
            "Enter the space",
            "Take me to the Debug Information space",
            "Navigate me to the Projects area",
        ],
        "priority": 5,
    },
    {
        "intent_type": "bubble.create",
        "description": "Neuen Space erstellen / Create a new space",
        "examples": [
            # German
            "Erstelle einen neuen Space",
            "Neuer Bereich für Marketing",
            "Lege eine neue Bubble an",
            "Mach einen Space für",
            "Neuen Space anlegen",
            # English
            "Create a new space",
            "New area for Marketing",
            "Create a new bubble",
            "Make a space for",
            "Add new space",
        ],
        "priority": 5,
    },
    {
        "intent_type": "bubble.list",
        "description": "Alle Spaces auflisten / List all spaces",
        "examples": [
            # German
            "Zeig mir meine Spaces",
            "Welche Bereiche gibt es?",
            "Liste alle Bubbles auf",
            "Was für Spaces habe ich?",
            "Alle Spaces anzeigen",
            # English
            "Show me my spaces",
            "What areas are there?",
            "List all bubbles",
            "What spaces do I have?",
            "Show all spaces",
            "List my spaces",
        ],
        "priority": 5,
    },
    {
        "intent_type": "bubble.update",
        "description": "Space umbenennen oder Beschreibung ändern / Rename space or change description",
        "examples": [
            # German
            "Benenne den Space um",
            "Ändere den Namen zu Marketing",
            "Nenne den Space jetzt Projekte",
            "Update den Bubble-Namen",
            "Gib dem Space einen neuen Namen",
            "Benenne die Bubble um in Test",
            "Der Name soll jetzt sein",
            # English
            "Rename the space",
            "Change the name to Marketing",
            "Call the space Projects now",
            "Update the bubble name",
            "Give the space a new name",
            "Rename the bubble to Test",
        ],
        "priority": 5,
    },
    {
        "intent_type": "bubble.delete",
        "description": "Einen oder mehrere Spaces/Bubbles loeschen / Delete one or more spaces/bubbles",
        "examples": [
            # German
            "Loesche alle Bubbles",
            "Loesche den Space Marketing",
            "Space loeschen",
            "Entferne die Bubble",
            "Bubble entfernen",
            "Loesche diesen Space",
            "Den Space loeschen",
            # English
            "Delete all bubbles",
            "Delete the Marketing space",
            "Delete space",
            "Remove the bubble",
            "Remove this bubble",
            "Delete this space",
        ],
        "priority": 10,
    },
    {
        "intent_type": "bubble.delete_all_except",
        "description": "Alle Spaces/Bubbles loeschen ausser bestimmten / Delete all spaces/bubbles except specified ones",
        "examples": [
            # German
            "Loesche alle Bubbles ausser Langzeitspeicher",
            "Loesche alle Spaces ausser VibeMind",
            "Loesche alle Bubbles bis auf Marketing",
            "Loesche alle ausser X und Y",
            "Entferne alle Bubbles ausgenommen VibeMind",
            "Alle Spaces loeschen ausser Projekte",
            "Loesche alles bis auf Langzeitspeicher und VibeMind",
            # English
            "Delete all spaces except VibeMind",
            "Delete all bubbles except Langzeitspeicher",
            "Remove all bubbles but keep Ideas",
            "Delete everything except X and Y",
            "Delete all spaces but not Marketing",
        ],
        "priority": 12,  # Higher priority than bubble.delete to match first
    },
    {
        "intent_type": "bubble.stats",
        "description": "Statistiken des aktuellen Spaces anzeigen / Show statistics of the current space",
        "examples": [
            # German
            "Zeig mir Statistiken vom Space",
            "Zeig mir Statistiken vom aktuellen Space",
            "Space Statistiken",
            "Wie viele Ideen sind im Space?",
            "Statistiken anzeigen",
            "Zeig mir die Zahlen vom Space",
            "Uebersicht vom Space",
            "Space Info",
            "Details zum Space",
            "Wie gross ist dieser Space?",
            # English
            "Show me space statistics",
            "Show statistics of the current space",
            "Space stats",
            "How many ideas are in the space?",
            "Show statistics",
            "Show me the space numbers",
            "Space overview",
            "Space info",
            "Details about the space",
            "How big is this space?",
        ],
        "priority": 8,
    },

    # === CONVERSATION ===
    {
        "intent_type": "conversation.greeting",
        "description": "Begrüßung oder Small Talk / Greeting or small talk",
        "examples": [
            # German
            "Hallo",
            "Hi Rachel",
            "Guten Morgen",
            "Hey wie geht's?",
            "Guten Tag",
            # English
            "Hello",
            "Hi Rachel",
            "Good morning",
            "Hey how are you?",
            "Good day",
        ],
        "priority": 1,
    },
    {
        "intent_type": "conversation.help",
        "description": "Hilfe oder Funktionsübersicht anfordern / Request help or feature overview",
        "examples": [
            # German
            "Was kannst du alles?",
            "Hilf mir",
            "Wie funktioniert das?",
            "Zeig mir die Funktionen",
            "Was sind meine Optionen?",
            # English
            "What can you do?",
            "Help me",
            "How does this work?",
            "Show me the features",
            "What are my options?",
            "Help",
        ],
        "priority": 3,
    },

    # === TASK MEMORY (Supermemory-based task history) ===
    {
        "intent_type": "task.list_today",
        "description": "Alle heute ausgefuehrten Tasks anzeigen / Show all tasks executed today",
        "examples": [
            # German
            "Was habe ich heute gemacht?",
            "Heutige Tasks",
            "Zeig mir meine Tasks von heute",
            "Was wurde heute alles ausgefuehrt?",
            "Meine heutigen Aktionen",
            "Was habe ich heute erledigt?",
            # English
            "What did I do today?",
            "Today's tasks",
            "Show me my tasks from today",
            "What was executed today?",
            "My actions today",
            "What did I accomplish today?",
        ],
        "priority": 6,
    },
    {
        "intent_type": "task.recent",
        "description": "Die letzten ausgefuehrten Tasks anzeigen / Show recently executed tasks",
        "examples": [
            # German
            "Was war der letzte Task?",
            "Letzte Tasks",
            "Was hab ich zuletzt gemacht?",
            "Zeig mir die letzten Aktionen",
            "Meine letzten Tasks",
            "Was war meine letzte Aktion?",
            # English
            "What was the last task?",
            "Recent tasks",
            "What did I do last?",
            "Show me the last actions",
            "My recent tasks",
            "What was my last action?",
        ],
        "priority": 6,
    },
    {
        "intent_type": "task.search",
        "description": "In der Task-Historie suchen / Search task history",
        "examples": [
            # German
            "Suche nach Tasks mit Marketing",
            "Finde Tasks mit Ideen",
            "Wann habe ich das zuletzt gemacht?",
            "Zeig mir alle Tasks zu X",
            "Suche in meiner Task-Historie",
            # English
            "Search for tasks with marketing",
            "Find tasks with ideas",
            "When did I last do that?",
            "Show me all tasks about X",
            "Search my task history",
        ],
        "priority": 6,
    },
    {
        "intent_type": "task.stats",
        "description": "Task-Statistiken und meistgenutzte Befehle anzeigen / Show task statistics and most used commands",
        "examples": [
            # German
            "Task Statistiken",
            "Meine Nutzung",
            "Zeig mir meine Statistiken",
            "Wie viele Tasks habe ich gemacht?",
            "Meine meistgenutzten Befehle",
            "Nutzungsstatistiken",
            # English
            "Task statistics",
            "My usage",
            "Show me my statistics",
            "How many tasks have I done?",
            "My most used commands",
            "Usage statistics",
        ],
        "priority": 6,
    },

    # === SYSTEM TASK STATUS (Real-time Redis monitoring) ===
    {
        "intent_type": "system.active_tasks",
        "description": "Alle aktuell laufenden Tasks anzeigen / Show all currently running tasks",
        "examples": [
            # German
            "Was laeuft gerade?",
            "Aktive Tasks",
            "Laufende Aufgaben",
            "Welche Tasks sind aktiv?",
            "Was wird gerade ausgefuehrt?",
            "Zeig mir die laufenden Tasks",
            "Gibt es aktive Aufgaben?",
            # English
            "What's running right now?",
            "Active tasks",
            "Running tasks",
            "Which tasks are active?",
            "What's being executed?",
            "Show me running tasks",
            "Are there active tasks?",
        ],
        "priority": 5,
    },
    {
        "intent_type": "system.queue_status",
        "description": "Status der Task-Queues anzeigen / Show task queue status",
        "examples": [
            # German
            "Queue Status",
            "Wie voll sind die Queues?",
            "Zeig mir die Warteschlangen",
            "Warteschlangen Status",
            "Wie viele Tasks warten?",
            "Status der Aufgaben-Queues",
            # English
            "Queue status",
            "How full are the queues?",
            "Show me the queues",
            "Queue statistics",
            "How many tasks are waiting?",
            "Task queue status",
        ],
        "priority": 5,
    },
    {
        "intent_type": "system.recent_completions",
        "description": "Kuerzlich abgeschlossene Tasks anzeigen / Show recently completed tasks",
        "examples": [
            # German
            "Was wurde erledigt?",
            "Letzte abgeschlossene Tasks",
            "Was ist fertig geworden?",
            "Zeig mir was fertig ist",
            "Welche Tasks sind fertig?",
            "Erledigte Aufgaben",
            # English
            "What was completed?",
            "Recently completed tasks",
            "What finished?",
            "Show me what's done",
            "Which tasks are finished?",
            "Completed tasks",
        ],
        "priority": 5,
    },
    {
        "intent_type": "system.status",
        "description": "System-Status und aktive Operationen anzeigen / Show system status and active operations",
        "examples": [
            # German
            "System Status",
            "Was macht das System?",
            "Zeig mir den Systemstatus",
            "Wie ist der Status?",
            "Status anzeigen",
            "Systeminfo",
            "Was passiert gerade im System?",
            "Gibt es hängende Operationen?",
            "Was hängt?",
            # English
            "System status",
            "What is the system doing?",
            "Show me the system status",
            "What's the status?",
            "Show status",
            "System info",
            "What's happening in the system?",
            "Are there stuck operations?",
        ],
        "priority": 7,
    },
]


class IntentRuleRepository:
    """
    Repository for intent rules using Supermemory for semantic search.

    Rules are stored as memories with type="intent_rule" and can be
    retrieved via semantic similarity search.

    Fast Startup Mode (FAST_STARTUP=true):
    - Rules are stored locally only (no Supermemory network calls)
    - Local word-overlap search is used for intent matching
    - Startup time: <1 second instead of 30+ seconds
    """

    MEMORY_TYPE = "intent_rule"
    SESSION_ID = "vibemind_intent_rules"  # Fixed session for all rules

    def __init__(self, use_supermemory: bool = True):
        """
        Initialize the repository.

        Args:
            use_supermemory: If True, use Supermemory API. If False, use local fallback.
        """
        # FAST_STARTUP=true disables Supermemory network calls entirely
        # This reduces startup from 30+ seconds to <1 second
        fast_startup = os.getenv("FAST_STARTUP", "true").lower() == "true"

        if fast_startup:
            self.use_supermemory = False
            self._client = None
            logger.info("[IntentRuleRepository] FAST_STARTUP mode - using local rules only (no Supermemory)")
        else:
            self.use_supermemory = use_supermemory
            self._client = None
            if use_supermemory:
                try:
                    from memory.supermemory_client import SupermemoryClient
                    self._client = SupermemoryClient()
                    logger.info("[IntentRuleRepository] Using Supermemory for intent rules")
                except Exception as e:
                    logger.warning(f"[IntentRuleRepository] Supermemory unavailable: {e}")
                    self.use_supermemory = False

        self._local_rules: Dict[str, IntentRule] = {}
        self._initialized = False

    def seed_default_rules(self) -> int:
        """
        Seed the default intent rules into Supermemory.

        Returns:
            Number of rules seeded
        """
        if self._initialized:
            logger.debug("[IntentRuleRepository] Already initialized, skipping seed")
            return 0

        count = 0
        for rule_data in INITIAL_INTENT_RULES:
            try:
                self.add_rule(
                    intent_type=rule_data["intent_type"],
                    description=rule_data["description"],
                    examples=rule_data["examples"],
                    priority=rule_data.get("priority", 0),
                )
                count += 1
            except Exception as e:
                logger.error(f"[IntentRuleRepository] Failed to seed rule {rule_data.get('intent_type')}: {e}")

        self._initialized = True
        logger.info(f"[IntentRuleRepository] Seeded {count} intent rules")
        return count

    def add_rule(
        self,
        intent_type: str,
        description: str,
        examples: List[str],
        priority: int = 0,
    ) -> str:
        """
        Add a new intent rule.

        Args:
            intent_type: The intent type (e.g., "idea.auto_link")
            description: Description of what this intent does
            examples: Example phrases that trigger this intent
            priority: Priority for conflicts (higher = more important)

        Returns:
            Rule ID
        """
        rule_id = f"rule_{intent_type.replace('.', '_')}"

        rule = IntentRule(
            id=rule_id,
            intent_type=intent_type,
            description=description,
            examples=examples,
            priority=priority,
        )

        # Store locally for fallback
        self._local_rules[rule_id] = rule

        if self.use_supermemory and self._client:
            try:
                # Store each example as a separate memory for better semantic search
                for i, example in enumerate(examples):
                    content = f"{example}"
                    metadata = {
                        "type": self.MEMORY_TYPE,
                        "intent_type": intent_type,
                        "description": description,
                        "rule_id": rule_id,
                        "example_index": i,
                        "priority": priority,
                    }
                    self._client.store_memory(content, metadata)

                logger.debug(f"[IntentRuleRepository] Stored rule {rule_id} with {len(examples)} examples")
            except Exception as e:
                logger.error(f"[IntentRuleRepository] Failed to store rule in Supermemory: {e}")

        return rule_id

    def search_similar(
        self,
        query: str,
        top_k: int = 5,
    ) -> List[IntentRule]:
        """
        Search for intent rules similar to the query using semantic search.

        Args:
            query: User input to match against rules
            top_k: Maximum number of rules to return

        Returns:
            List of matching IntentRule objects, sorted by relevance
        """
        if self.use_supermemory and self._client:
            try:
                results = self._client.retrieve_context(
                    session_id=self.SESSION_ID,
                    query=query,
                    limit=top_k * 2,  # Get more to deduplicate
                )

                # Group by intent_type and get unique rules
                seen_intents = set()
                rules = []

                for result in results:
                    metadata = result.get("metadata", {})
                    if metadata.get("type") != self.MEMORY_TYPE:
                        continue

                    intent_type = metadata.get("intent_type")
                    if intent_type in seen_intents:
                        continue

                    seen_intents.add(intent_type)
                    rule = IntentRule(
                        id=metadata.get("rule_id", ""),
                        intent_type=intent_type,
                        description=metadata.get("description", ""),
                        examples=[result.get("content", "")],  # Just the matched example
                        priority=metadata.get("priority", 0),
                    )
                    rules.append(rule)

                    if len(rules) >= top_k:
                        break

                if rules:
                    logger.debug(f"[IntentRuleRepository] Found {len(rules)} rules via Supermemory for query: {query[:50]}...")
                    return rules
                else:
                    logger.debug(f"[IntentRuleRepository] Supermemory returned no results, falling back to local search")

            except Exception as e:
                logger.warning(f"[IntentRuleRepository] Supermemory search failed: {e}")

        # Fallback: Simple word overlap matching
        logger.debug(f"[IntentRuleRepository] Using local word-overlap search for: {query[:50]}...")
        return self._local_search(query, top_k)

    def _local_search(self, query: str, top_k: int) -> List[IntentRule]:
        """
        Local fallback search using simple word overlap.

        Args:
            query: User input to match
            top_k: Maximum results

        Returns:
            List of matching rules
        """
        query_words = set(query.lower().split())
        scores = []

        for rule in self._local_rules.values():
            max_score = 0
            for example in rule.examples:
                example_words = set(example.lower().split())
                overlap = len(query_words.intersection(example_words))
                union = len(query_words.union(example_words))
                if union > 0:
                    score = overlap / union + (rule.priority * 0.01)
                    max_score = max(max_score, score)

            if max_score > 0:
                scores.append((rule, max_score))

        scores.sort(key=lambda x: x[1], reverse=True)
        return [rule for rule, _ in scores[:top_k]]

    def get_all_rules(self) -> List[IntentRule]:
        """Get all stored rules."""
        return list(self._local_rules.values())

    def get_rule(self, rule_id: str) -> Optional[IntentRule]:
        """Get a specific rule by ID."""
        return self._local_rules.get(rule_id)


# =============================================================================
# SINGLETON
# =============================================================================

_repository: Optional[IntentRuleRepository] = None


def get_intent_rule_repository() -> IntentRuleRepository:
    """Get or create the singleton IntentRuleRepository."""
    global _repository
    if _repository is None:
        _repository = IntentRuleRepository()
    return _repository


__all__ = [
    "IntentRule",
    "IntentRuleRepository",
    "get_intent_rule_repository",
    "INITIAL_INTENT_RULES",
]
