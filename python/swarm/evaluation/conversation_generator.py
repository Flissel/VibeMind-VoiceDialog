"""
Synthetic Conversation Generator

Generates test utterances for each intent type with varying:
- Difficulty levels (easy, medium, hard)
- Formality (du/Sie)
- Length (short/long)
- Directness (command/question/request)
"""

import json
import logging
import os
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any, Optional

from .intent_taxonomy import IntentCategory, INTENT_TAXONOMY

logger = logging.getLogger(__name__)


@dataclass
class SyntheticUtterance:
    """A synthetic user input with expected classification result."""
    text: str                           # "Erstelle einen Space namens Marketing"
    expected_intent: str                # "bubble.create"
    expected_payload: Dict[str, Any]    # {"title": "Marketing"}
    category: IntentCategory            # IntentCategory.CREATE
    difficulty: str = "medium"          # "easy" | "medium" | "hard"
    tags: List[str] = field(default_factory=list)  # ["german", "formal"]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "text": self.text,
            "expected_intent": self.expected_intent,
            "expected_payload": self.expected_payload,
            "category": self.category.value,
            "difficulty": self.difficulty,
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SyntheticUtterance":
        """Create from dictionary."""
        return cls(
            text=data["text"],
            expected_intent=data["expected_intent"],
            expected_payload=data.get("expected_payload", {}),
            category=IntentCategory(data["category"]),
            difficulty=data.get("difficulty", "medium"),
            tags=data.get("tags", []),
        )


# ==============================================================================
# UTTERANCE TEMPLATES - Predefined test cases for each intent
# ==============================================================================

UTTERANCE_TEMPLATES: Dict[str, List[SyntheticUtterance]] = {

    # ==========================================================================
    # BUBBLE / SPACE INTENTS
    # ==========================================================================

    "bubble.list": [
        # EASY
        SyntheticUtterance("Zeig mir alle Spaces", "bubble.list", {},
                          IntentCategory.QUERY, "easy", ["direct"]),
        SyntheticUtterance("Liste alle Bubbles auf", "bubble.list", {},
                          IntentCategory.QUERY, "easy", ["direct"]),
        SyntheticUtterance("Welche Spaces gibt es?", "bubble.list", {},
                          IntentCategory.QUERY, "easy", ["question"]),
        # MEDIUM
        SyntheticUtterance("Was fuer Bereiche habe ich angelegt?", "bubble.list", {},
                          IntentCategory.QUERY, "medium", ["implicit"]),
        SyntheticUtterance("Gib mir eine Uebersicht meiner Spaces", "bubble.list", {},
                          IntentCategory.QUERY, "medium", ["formal"]),
        # HARD
        SyntheticUtterance("Ich moechte sehen was ich alles an Bubbles erstellt habe", "bubble.list", {},
                          IntentCategory.QUERY, "hard", ["long", "implicit"]),
    ],

    "bubble.create": [
        # EASY
        SyntheticUtterance("Erstelle einen Space namens Marketing", "bubble.create",
                          {"title": "Marketing"}, IntentCategory.CREATE, "easy", ["direct", "with_name"]),
        SyntheticUtterance("Neuer Space: Projektplanung", "bubble.create",
                          {"title": "Projektplanung"}, IntentCategory.CREATE, "easy", ["short"]),
        SyntheticUtterance("Erstelle Bubble Finanzen", "bubble.create",
                          {"title": "Finanzen"}, IntentCategory.CREATE, "easy", ["direct"]),
        # MEDIUM
        SyntheticUtterance("Ich brauche einen Bereich fuer meine Finanzen", "bubble.create",
                          {"title": "Finanzen"}, IntentCategory.CREATE, "medium", ["implicit"]),
        SyntheticUtterance("Mach mir mal nen Space fuer die Urlaubsplanung", "bubble.create",
                          {"title": "Urlaubsplanung"}, IntentCategory.CREATE, "medium", ["colloquial"]),
        SyntheticUtterance("Leg einen neuen Bereich an fuer Rezepte", "bubble.create",
                          {"title": "Rezepte"}, IntentCategory.CREATE, "medium", ["informal"]),
        # HARD
        SyntheticUtterance("Koenntest du vielleicht einen neuen Bereich anlegen wo ich meine Rezepte sammeln kann?",
                          "bubble.create", {"title": "Rezepte"}, IntentCategory.CREATE, "hard", ["polite", "long"]),
        SyntheticUtterance("Ich haette gerne einen Space in dem ich alles zum Thema Musik organisieren kann",
                          "bubble.create", {"title": "Musik"}, IntentCategory.CREATE, "hard", ["formal", "long"]),
    ],

    "bubble.enter": [
        # EASY
        SyntheticUtterance("Gehe in den Space Marketing", "bubble.enter",
                          {"bubble_name": "Marketing"}, IntentCategory.NAVIGATE, "easy", ["direct"]),
        SyntheticUtterance("Oeffne Bubble Finanzen", "bubble.enter",
                          {"bubble_name": "Finanzen"}, IntentCategory.NAVIGATE, "easy", ["direct"]),
        SyntheticUtterance("Wechsle zu Projektplanung", "bubble.enter",
                          {"bubble_name": "Projektplanung"}, IntentCategory.NAVIGATE, "easy", ["short"]),
        # MEDIUM
        SyntheticUtterance("Bring mich in den Marketing Space", "bubble.enter",
                          {"bubble_name": "Marketing"}, IntentCategory.NAVIGATE, "medium", ["informal"]),
        SyntheticUtterance("Ich will in den Bereich Finanzen", "bubble.enter",
                          {"bubble_name": "Finanzen"}, IntentCategory.NAVIGATE, "medium", ["implicit"]),
        # HARD
        SyntheticUtterance("Koenntest du mich bitte in den Space bringen wo ich meine Marketing Sachen habe?",
                          "bubble.enter", {"bubble_name": "Marketing"}, IntentCategory.NAVIGATE, "hard", ["polite", "long"]),
    ],

    "bubble.exit": [
        # EASY
        SyntheticUtterance("Verlasse den Space", "bubble.exit", {},
                          IntentCategory.NAVIGATE, "easy", ["direct"]),
        SyntheticUtterance("Raus aus dem Bubble", "bubble.exit", {},
                          IntentCategory.NAVIGATE, "easy", ["colloquial"]),
        SyntheticUtterance("Zurueck", "bubble.exit", {},
                          IntentCategory.NAVIGATE, "easy", ["short"]),
        # MEDIUM
        SyntheticUtterance("Geh zurueck zur Uebersicht", "bubble.exit", {},
                          IntentCategory.NAVIGATE, "medium", ["implicit"]),
        SyntheticUtterance("Ich will hier raus", "bubble.exit", {},
                          IntentCategory.NAVIGATE, "medium", ["informal"]),
    ],

    "bubble.delete": [
        # EASY
        SyntheticUtterance("Loesche den Space Marketing", "bubble.delete",
                          {"bubble_name": "Marketing"}, IntentCategory.DELETE, "easy", ["direct"]),
        SyntheticUtterance("Entferne Bubble Finanzen", "bubble.delete",
                          {"bubble_name": "Finanzen"}, IntentCategory.DELETE, "easy", ["direct"]),
        # MEDIUM
        SyntheticUtterance("Den Marketing Space brauche ich nicht mehr", "bubble.delete",
                          {"bubble_name": "Marketing"}, IntentCategory.DELETE, "medium", ["implicit"]),
        SyntheticUtterance("Schmeiß den alten Bubble Projekte weg", "bubble.delete",
                          {"bubble_name": "Projekte"}, IntentCategory.DELETE, "medium", ["colloquial"]),
        # HARD
        SyntheticUtterance("Koenntest du bitte den Space mit dem Namen Marketing komplett entfernen?",
                          "bubble.delete", {"bubble_name": "Marketing"}, IntentCategory.DELETE, "hard", ["polite", "long"]),
    ],

    "bubble.stats": [
        # EASY
        SyntheticUtterance("Zeig mir die Statistiken", "bubble.stats", {},
                          IntentCategory.QUERY, "easy", ["direct"]),
        SyntheticUtterance("Space Statistiken", "bubble.stats", {},
                          IntentCategory.QUERY, "easy", ["short"]),
        # MEDIUM
        SyntheticUtterance("Wie viele Ideen habe ich in diesem Space?", "bubble.stats", {},
                          IntentCategory.QUERY, "medium", ["question"]),
        SyntheticUtterance("Gib mir eine Zusammenfassung dieses Bereichs", "bubble.stats", {},
                          IntentCategory.QUERY, "medium", ["formal"]),
    ],

    # ==========================================================================
    # IDEA INTENTS
    # ==========================================================================

    "idea.list": [
        # EASY
        SyntheticUtterance("Zeig mir alle Ideen", "idea.list", {},
                          IntentCategory.QUERY, "easy", ["direct"]),
        SyntheticUtterance("Liste die Notizen auf", "idea.list", {},
                          IntentCategory.QUERY, "easy", ["direct"]),
        SyntheticUtterance("Welche Ideen gibt es hier?", "idea.list", {},
                          IntentCategory.QUERY, "easy", ["question"]),
        # MEDIUM
        SyntheticUtterance("Was habe ich mir hier alles notiert?", "idea.list", {},
                          IntentCategory.QUERY, "medium", ["implicit"]),
        SyntheticUtterance("Gib mir eine Uebersicht der Ideen", "idea.list", {},
                          IntentCategory.QUERY, "medium", ["formal"]),
    ],

    "idea.create": [
        # EASY
        SyntheticUtterance("Neue Idee: Social Media Kampagne", "idea.create",
                          {"title": "Social Media Kampagne", "content": "Social Media Kampagne"},
                          IntentCategory.CREATE, "easy", ["direct"]),
        SyntheticUtterance("Erstelle eine Notiz ueber Budgetplanung", "idea.create",
                          {"title": "Budgetplanung", "content": "Idee ueber Budgetplanung"},
                          IntentCategory.CREATE, "easy", ["direct"]),
        SyntheticUtterance("Merke dir: Team Meeting am Montag", "idea.create",
                          {"title": "Team Meeting am Montag", "content": "Team Meeting am Montag"},
                          IntentCategory.CREATE, "easy", ["short"]),
        # MEDIUM
        SyntheticUtterance("Ich habe eine Idee fuer eine neue App die ich notieren moechte", "idea.create",
                          {"title": "neue App", "content": "Idee fuer eine neue App"},
                          IntentCategory.CREATE, "medium", ["implicit"]),
        SyntheticUtterance("Schreib mal auf dass wir noch den Newsletter planen muessen", "idea.create",
                          {"title": "Newsletter planen", "content": "Newsletter planen muessen"},
                          IntentCategory.CREATE, "medium", ["colloquial"]),
        # HARD
        SyntheticUtterance("Koenntest du dir bitte merken dass ich naechste Woche mit dem Marketing Team ueber die Q4 Strategie sprechen muss?",
                          "idea.create", {"title": "Q4 Strategie Besprechung", "content": "Naechste Woche mit Marketing Team ueber Q4 Strategie sprechen"},
                          IntentCategory.CREATE, "hard", ["polite", "long"]),
    ],

    "idea.find": [
        # EASY
        SyntheticUtterance("Suche nach Marketing", "idea.find",
                          {"query": "Marketing"}, IntentCategory.QUERY, "easy", ["direct"]),
        SyntheticUtterance("Finde Ideen zu Budget", "idea.find",
                          {"query": "Budget"}, IntentCategory.QUERY, "easy", ["direct"]),
        # MEDIUM
        SyntheticUtterance("Habe ich irgendwo was zu Social Media notiert?", "idea.find",
                          {"query": "Social Media"}, IntentCategory.QUERY, "medium", ["question"]),
        SyntheticUtterance("Zeig mir alles was mit Kampagne zu tun hat", "idea.find",
                          {"query": "Kampagne"}, IntentCategory.QUERY, "medium", ["implicit"]),
    ],

    "idea.update": [
        # EASY
        SyntheticUtterance("Aktualisiere die Idee Marketing Kampagne", "idea.update",
                          {"idea_name": "Marketing Kampagne"}, IntentCategory.MODIFY, "easy", ["direct"]),
        SyntheticUtterance("Aendere Budget zu Jahresbudget", "idea.update",
                          {"idea_name": "Budget", "new_title": "Jahresbudget"},
                          IntentCategory.MODIFY, "easy", ["short"]),
        # MEDIUM
        SyntheticUtterance("Die Idee Social Media braucht ein Update", "idea.update",
                          {"idea_name": "Social Media"}, IntentCategory.MODIFY, "medium", ["implicit"]),
        SyntheticUtterance("Fuege zur Newsletter Idee noch hinzu dass wir Bilder brauchen", "idea.update",
                          {"idea_name": "Newsletter", "new_content": "Bilder brauchen"},
                          IntentCategory.MODIFY, "medium", ["addition"]),
    ],

    "idea.delete": [
        # EASY
        SyntheticUtterance("Loesche die Idee Marketing", "idea.delete",
                          {"idea_name": "Marketing"}, IntentCategory.DELETE, "easy", ["direct"]),
        SyntheticUtterance("Entferne die Notiz Budget", "idea.delete",
                          {"idea_name": "Budget"}, IntentCategory.DELETE, "easy", ["direct"]),
        # MEDIUM
        SyntheticUtterance("Die Idee zu Social Media ist nicht mehr relevant", "idea.delete",
                          {"idea_name": "Social Media"}, IntentCategory.DELETE, "medium", ["implicit"]),
        SyntheticUtterance("Schmeiß die alte Notiz weg", "idea.delete",
                          {"idea_name": "alte Notiz"}, IntentCategory.DELETE, "medium", ["colloquial"]),
    ],

    "idea.connect": [
        # EASY
        SyntheticUtterance("Verbinde Marketing mit Social Media", "idea.connect",
                          {"idea1": "Marketing", "idea2": "Social Media"},
                          IntentCategory.MODIFY, "easy", ["direct"]),
        SyntheticUtterance("Verlinke Budget und Planung", "idea.connect",
                          {"idea1": "Budget", "idea2": "Planung"},
                          IntentCategory.MODIFY, "easy", ["direct"]),
        # MEDIUM
        SyntheticUtterance("Die Ideen Newsletter und Kampagne gehoeren zusammen", "idea.connect",
                          {"idea1": "Newsletter", "idea2": "Kampagne"},
                          IntentCategory.MODIFY, "medium", ["implicit"]),
        SyntheticUtterance("Mach eine Verbindung zwischen Social Media und Content", "idea.connect",
                          {"idea1": "Social Media", "idea2": "Content"},
                          IntentCategory.MODIFY, "medium", ["informal"]),
    ],

    "idea.expand": [
        # EASY
        SyntheticUtterance("Erweitere die Ideen", "idea.expand", {},
                          IntentCategory.GENERATE, "easy", ["direct"]),
        SyntheticUtterance("Generiere verwandte Ideen", "idea.expand", {},
                          IntentCategory.GENERATE, "easy", ["direct"]),
        SyntheticUtterance("Mach mehr Ideen aus den bestehenden", "idea.expand", {},
                          IntentCategory.GENERATE, "easy", ["informal"]),
        # MEDIUM - Phase 16 German trigger words
        SyntheticUtterance("Unterteile die Ideen in kleinere Konzepte", "idea.expand", {},
                          IntentCategory.GENERATE, "medium", ["subdivision"]),
        SyntheticUtterance("Arbeite die Ideen weiter aus", "idea.expand", {},
                          IntentCategory.GENERATE, "medium", ["elaboration"]),
        SyntheticUtterance("Entwickle Unterideen zu den bestehenden Notizen", "idea.expand", {},
                          IntentCategory.GENERATE, "medium", ["subdivision"]),
        SyntheticUtterance("Zerlege die Ideen in kleinere Teile", "idea.expand", {},
                          IntentCategory.GENERATE, "medium", ["subdivision"]),
        SyntheticUtterance("Formuliere die Ideen weiter aus", "idea.expand", {},
                          IntentCategory.GENERATE, "medium", ["elaboration"]),
        SyntheticUtterance("Brainstorme ergaenzende Ideen", "idea.expand", {},
                          IntentCategory.GENERATE, "medium", ["brainstorm"]),
        SyntheticUtterance("Reichere die Ideen an", "idea.expand", {},
                          IntentCategory.GENERATE, "medium", ["enrichment"]),
        # HARD
        SyntheticUtterance("Kannst du aus den vorhandenen Notizen mehrere detailliertere Ideen ableiten und diese miteinander verlinken?",
                          "idea.expand", {}, IntentCategory.GENERATE, "hard", ["complex", "linking"]),
        SyntheticUtterance("Unterteile sie basierend auf ihren Inhalten in kleinere Ideen", "idea.expand", {},
                          IntentCategory.GENERATE, "hard", ["context_aware"]),
        SyntheticUtterance("Ideen weiter ausarbeiten, in Unterideen unterteilen", "idea.expand", {},
                          IntentCategory.GENERATE, "hard", ["multi_action"]),
    ],

    "idea.move": [
        # EASY
        SyntheticUtterance("Verschiebe Marketing nach Projekte", "idea.move",
                          {"idea_name": "Marketing", "target_space": "Projekte"},
                          IntentCategory.MODIFY, "easy", ["direct"]),
        SyntheticUtterance("Move Budget to Finanzen", "idea.move",
                          {"idea_name": "Budget", "target_space": "Finanzen"},
                          IntentCategory.MODIFY, "easy", ["english"]),
        # MEDIUM
        SyntheticUtterance("Bringe die Idee Social Media in den Space Marketing", "idea.move",
                          {"idea_name": "Social Media", "target_space": "Marketing"},
                          IntentCategory.MODIFY, "medium", ["formal"]),
        SyntheticUtterance("Die Notiz Newsletter soll in den Kampagnen Bereich", "idea.move",
                          {"idea_name": "Newsletter", "target_space": "Kampagnen"},
                          IntentCategory.MODIFY, "medium", ["implicit"]),
        # HARD
        SyntheticUtterance("Koenntest du die Idee mit dem Langzeitspeicher in den Space Mind a bubble verschieben?",
                          "idea.move", {"idea_name": "Langzeitspeicher", "target_space": "Mind a bubble"},
                          IntentCategory.MODIFY, "hard", ["polite", "long"]),
    ],

    # ==========================================================================
    # DESKTOP AUTOMATION INTENTS
    # ==========================================================================

    "desktop.open_app": [
        # EASY
        SyntheticUtterance("Oeffne Chrome", "desktop.open_app",
                          {"app_name": "Chrome"}, IntentCategory.AUTOMATE, "easy", ["direct"]),
        SyntheticUtterance("Starte VS Code", "desktop.open_app",
                          {"app_name": "VS Code"}, IntentCategory.AUTOMATE, "easy", ["direct"]),
        SyntheticUtterance("Mach Spotify auf", "desktop.open_app",
                          {"app_name": "Spotify"}, IntentCategory.AUTOMATE, "easy", ["colloquial"]),
        # MEDIUM
        SyntheticUtterance("Ich brauche den Browser", "desktop.open_app",
                          {"app_name": "Browser"}, IntentCategory.AUTOMATE, "medium", ["implicit"]),
        SyntheticUtterance("Koenntest du bitte Excel starten?", "desktop.open_app",
                          {"app_name": "Excel"}, IntentCategory.AUTOMATE, "medium", ["polite"]),
    ],

    "desktop.click": [
        # EASY
        SyntheticUtterance("Klicke auf den Button", "desktop.click",
                          {"description": "Button"}, IntentCategory.AUTOMATE, "easy", ["direct"]),
        SyntheticUtterance("Druecke auf OK", "desktop.click",
                          {"description": "OK"}, IntentCategory.AUTOMATE, "easy", ["short"]),
        # MEDIUM
        SyntheticUtterance("Klick mal auf das Senden Symbol", "desktop.click",
                          {"description": "Senden Symbol"}, IntentCategory.AUTOMATE, "medium", ["informal"]),
    ],

    "desktop.type": [
        # EASY
        SyntheticUtterance("Schreibe Hallo Welt", "desktop.type",
                          {"text": "Hallo Welt"}, IntentCategory.AUTOMATE, "easy", ["direct"]),
        SyntheticUtterance("Tippe meine Email Adresse ein", "desktop.type",
                          {"text": "meine Email Adresse"}, IntentCategory.AUTOMATE, "easy", ["direct"]),
        # MEDIUM
        SyntheticUtterance("Gib in das Suchfeld Machine Learning ein", "desktop.type",
                          {"text": "Machine Learning"}, IntentCategory.AUTOMATE, "medium", ["context"]),
    ],

    "desktop.press_key": [
        # EASY
        SyntheticUtterance("Druecke Enter", "desktop.press_key",
                          {"key": "Enter"}, IntentCategory.AUTOMATE, "easy", ["direct"]),
        SyntheticUtterance("Escape Taste", "desktop.press_key",
                          {"key": "Escape"}, IntentCategory.AUTOMATE, "easy", ["short"]),
        SyntheticUtterance("Druecke Strg C", "desktop.press_key",
                          {"key": "Ctrl+C"}, IntentCategory.AUTOMATE, "easy", ["shortcut"]),
        # MEDIUM
        SyntheticUtterance("Mach das rueckgaengig mit Strg Z", "desktop.press_key",
                          {"key": "Ctrl+Z"}, IntentCategory.AUTOMATE, "medium", ["implicit"]),
    ],

    "desktop.screenshot": [
        # EASY
        SyntheticUtterance("Mach einen Screenshot", "desktop.screenshot", {},
                          IntentCategory.AUTOMATE, "easy", ["direct"]),
        SyntheticUtterance("Screenshot", "desktop.screenshot", {},
                          IntentCategory.AUTOMATE, "easy", ["short"]),
        # MEDIUM
        SyntheticUtterance("Fotografiere den Bildschirm", "desktop.screenshot", {},
                          IntentCategory.AUTOMATE, "medium", ["metaphor"]),
    ],

    "desktop.scroll": [
        # EASY
        SyntheticUtterance("Scroll nach unten", "desktop.scroll",
                          {"direction": "down"}, IntentCategory.AUTOMATE, "easy", ["direct"]),
        SyntheticUtterance("Scroll hoch", "desktop.scroll",
                          {"direction": "up"}, IntentCategory.AUTOMATE, "easy", ["short"]),
        # MEDIUM
        SyntheticUtterance("Geh weiter runter auf der Seite", "desktop.scroll",
                          {"direction": "down"}, IntentCategory.AUTOMATE, "medium", ["implicit"]),
    ],

    "desktop.task": [
        # EASY
        SyntheticUtterance("Oeffne Google und suche nach Python Tutorials", "desktop.task",
                          {"description": "Oeffne Google und suche nach Python Tutorials"},
                          IntentCategory.AUTOMATE, "easy", ["multi_step"]),
        # MEDIUM
        SyntheticUtterance("Geh auf YouTube und spiele das neueste Video von TechLinked ab", "desktop.task",
                          {"description": "YouTube oeffnen und neuestes TechLinked Video abspielen"},
                          IntentCategory.AUTOMATE, "medium", ["complex"]),
        # HARD
        SyntheticUtterance("Koenntest du bitte Chrome oeffnen, zu meinem Gmail gehen und die neueste Email von Max oeffnen?",
                          "desktop.task", {"description": "Chrome oeffnen, Gmail aufrufen, neueste Email von Max oeffnen"},
                          IntentCategory.AUTOMATE, "hard", ["polite", "multi_step"]),
    ],

    # ==========================================================================
    # CODE GENERATION INTENTS
    # ==========================================================================

    "code.generate": [
        # EASY
        SyntheticUtterance("Generiere eine Todo App", "code.generate",
                          {"description": "Todo App"}, IntentCategory.CREATE, "easy", ["direct"]),
        SyntheticUtterance("Erstelle Code fuer einen Taschenrechner", "code.generate",
                          {"description": "Taschenrechner"}, IntentCategory.CREATE, "easy", ["direct"]),
        # MEDIUM
        SyntheticUtterance("Ich brauche eine einfache Website mit Login", "code.generate",
                          {"description": "Website mit Login"}, IntentCategory.CREATE, "medium", ["implicit"]),
        SyntheticUtterance("Bau mir eine React App fuer Notizen", "code.generate",
                          {"description": "React Notizen App", "tech_stack": "React"},
                          IntentCategory.CREATE, "medium", ["tech_specific"]),
        # HARD
        SyntheticUtterance("Koenntest du mir eine vollstaendige REST API mit Node.js und Express generieren die Benutzer verwalten kann?",
                          "code.generate", {"description": "REST API fuer Benutzerverwaltung", "tech_stack": "Node.js, Express"},
                          IntentCategory.CREATE, "hard", ["polite", "detailed"]),
    ],

    "code.status": [
        # EASY
        SyntheticUtterance("Wie ist der Status?", "code.status", {},
                          IntentCategory.QUERY, "easy", ["short"]),
        SyntheticUtterance("Zeig mir den Fortschritt", "code.status", {},
                          IntentCategory.QUERY, "easy", ["direct"]),
        # MEDIUM
        SyntheticUtterance("Ist die Code Generierung schon fertig?", "code.status", {},
                          IntentCategory.QUERY, "medium", ["question"]),
    ],

    "code.preview.start": [
        # EASY
        SyntheticUtterance("Starte die Vorschau", "code.preview.start", {},
                          IntentCategory.PREVIEW, "easy", ["direct"]),
        SyntheticUtterance("Zeig mir die App", "code.preview.start", {},
                          IntentCategory.PREVIEW, "easy", ["implicit"]),
        # MEDIUM
        SyntheticUtterance("Kann ich das Projekt mal in Aktion sehen?", "code.preview.start", {},
                          IntentCategory.PREVIEW, "medium", ["question"]),
    ],

    "code.preview.stop": [
        # EASY
        SyntheticUtterance("Stoppe die Vorschau", "code.preview.stop", {},
                          IntentCategory.PREVIEW, "easy", ["direct"]),
        SyntheticUtterance("Beende das Preview", "code.preview.stop", {},
                          IntentCategory.PREVIEW, "easy", ["short"]),
    ],

    "code.list": [
        # EASY
        SyntheticUtterance("Zeig mir alle Projekte", "code.list", {},
                          IntentCategory.QUERY, "easy", ["direct"]),
        SyntheticUtterance("Welche Code Projekte habe ich?", "code.list", {},
                          IntentCategory.QUERY, "easy", ["question"]),
    ],

    "code.cancel": [
        # EASY
        SyntheticUtterance("Abbrechen", "code.cancel", {},
                          IntentCategory.DELETE, "easy", ["short"]),
        SyntheticUtterance("Stoppe die Generierung", "code.cancel", {},
                          IntentCategory.DELETE, "easy", ["direct"]),
        # MEDIUM
        SyntheticUtterance("Ich will das Projekt doch nicht mehr", "code.cancel", {},
                          IntentCategory.DELETE, "medium", ["implicit"]),
    ],

    # ==========================================================================
    # CONVERSATION INTENTS
    # ==========================================================================

    "conversation.greeting": [
        # EASY
        SyntheticUtterance("Hallo", "conversation.greeting", {},
                          IntentCategory.CONVERSATION, "easy", ["short"]),
        SyntheticUtterance("Hi Rachel", "conversation.greeting", {},
                          IntentCategory.CONVERSATION, "easy", ["informal"]),
        SyntheticUtterance("Guten Morgen", "conversation.greeting", {},
                          IntentCategory.CONVERSATION, "easy", ["formal"]),
        SyntheticUtterance("Hey wie gehts?", "conversation.greeting", {},
                          IntentCategory.CONVERSATION, "easy", ["colloquial"]),
    ],

    "conversation.help": [
        # EASY
        SyntheticUtterance("Hilfe", "conversation.help", {},
                          IntentCategory.CONVERSATION, "easy", ["short"]),
        SyntheticUtterance("Was kannst du?", "conversation.help", {},
                          IntentCategory.CONVERSATION, "easy", ["question"]),
        SyntheticUtterance("Zeig mir was du machen kannst", "conversation.help", {},
                          IntentCategory.CONVERSATION, "easy", ["direct"]),
        # MEDIUM
        SyntheticUtterance("Ich weiss nicht wie das funktioniert, kannst du mir helfen?", "conversation.help", {},
                          IntentCategory.CONVERSATION, "medium", ["implicit"]),
    ],

    # ==========================================================================
    # EVALUATION FEEDBACK INTENTS
    # ==========================================================================

    "evaluation.correct": [
        # EASY
        SyntheticUtterance("Das war richtig", "evaluation.correct", {},
                          IntentCategory.EVALUATION, "easy", ["direct"]),
        SyntheticUtterance("Ja genau", "evaluation.correct", {},
                          IntentCategory.EVALUATION, "easy", ["short"]),
        SyntheticUtterance("Perfekt", "evaluation.correct", {},
                          IntentCategory.EVALUATION, "easy", ["short"]),
        SyntheticUtterance("Genau das wollte ich", "evaluation.correct", {},
                          IntentCategory.EVALUATION, "easy", ["confirmation"]),
        SyntheticUtterance("Richtig verstanden", "evaluation.correct", {},
                          IntentCategory.EVALUATION, "easy", ["direct"]),
    ],

    "evaluation.incorrect": [
        # EASY
        SyntheticUtterance("Das war falsch", "evaluation.incorrect", {},
                          IntentCategory.EVALUATION, "easy", ["direct"]),
        SyntheticUtterance("Nein das meinte ich nicht", "evaluation.incorrect", {},
                          IntentCategory.EVALUATION, "easy", ["negation"]),
        SyntheticUtterance("Falsch verstanden", "evaluation.incorrect", {},
                          IntentCategory.EVALUATION, "easy", ["short"]),
        SyntheticUtterance("Das ist nicht was ich wollte", "evaluation.incorrect", {},
                          IntentCategory.EVALUATION, "easy", ["negation"]),
        SyntheticUtterance("Nee nicht richtig", "evaluation.incorrect", {},
                          IntentCategory.EVALUATION, "easy", ["colloquial"]),
    ],

    "evaluation.clarify": [
        # EASY
        SyntheticUtterance("Ich meinte eine Idee erstellen", "evaluation.clarify",
                          {"correction": "eine Idee erstellen"}, IntentCategory.EVALUATION, "easy", ["correction"]),
        SyntheticUtterance("Eigentlich wollte ich einen Space oeffnen", "evaluation.clarify",
                          {"intended_action": "Space oeffnen"}, IntentCategory.EVALUATION, "easy", ["clarification"]),
        # MEDIUM
        SyntheticUtterance("Nein ich wollte dass du die Ideen erweiterst nicht auflistest", "evaluation.clarify",
                          {"correction": "Ideen erweitern", "intended_action": "idea.expand"},
                          IntentCategory.EVALUATION, "medium", ["detailed_correction"]),
    ],
}


def get_all_utterances() -> List[SyntheticUtterance]:
    """Get all predefined utterances."""
    result = []
    for intent, utterances in UTTERANCE_TEMPLATES.items():
        result.extend(utterances)
    return result


def get_utterances_by_intent(intent: str) -> List[SyntheticUtterance]:
    """Get utterances for a specific intent."""
    return UTTERANCE_TEMPLATES.get(intent, [])


def get_utterances_by_category(category: IntentCategory) -> List[SyntheticUtterance]:
    """Get all utterances for a specific category."""
    result = []
    for intent, utterances in UTTERANCE_TEMPLATES.items():
        for utt in utterances:
            if utt.category == category:
                result.append(utt)
    return result


def get_utterances_by_difficulty(difficulty: str) -> List[SyntheticUtterance]:
    """Get all utterances of a specific difficulty level."""
    result = []
    for intent, utterances in UTTERANCE_TEMPLATES.items():
        for utt in utterances:
            if utt.difficulty == difficulty:
                result.append(utt)
    return result


def get_stats() -> Dict[str, Any]:
    """Get statistics about the utterance templates."""
    all_utts = get_all_utterances()

    by_intent = {}
    by_category = {}
    by_difficulty = {"easy": 0, "medium": 0, "hard": 0}

    for utt in all_utts:
        # By intent
        if utt.expected_intent not in by_intent:
            by_intent[utt.expected_intent] = 0
        by_intent[utt.expected_intent] += 1

        # By category
        cat_name = utt.category.value
        if cat_name not in by_category:
            by_category[cat_name] = 0
        by_category[cat_name] += 1

        # By difficulty
        by_difficulty[utt.difficulty] += 1

    return {
        "total": len(all_utts),
        "intents_covered": len(by_intent),
        "by_intent": by_intent,
        "by_category": by_category,
        "by_difficulty": by_difficulty,
    }


def export_to_json(filepath: str) -> None:
    """Export all utterances to a JSON file."""
    all_utts = get_all_utterances()
    data = [utt.to_dict() for utt in all_utts]

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    logger.info(f"Exported {len(all_utts)} utterances to {filepath}")


def import_from_json(filepath: str) -> List[SyntheticUtterance]:
    """Import utterances from a JSON file."""
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    utterances = [SyntheticUtterance.from_dict(d) for d in data]
    logger.info(f"Imported {len(utterances)} utterances from {filepath}")
    return utterances


__all__ = [
    "SyntheticUtterance",
    "UTTERANCE_TEMPLATES",
    "get_all_utterances",
    "get_utterances_by_intent",
    "get_utterances_by_category",
    "get_utterances_by_difficulty",
    "get_stats",
    "export_to_json",
    "import_from_json",
]
