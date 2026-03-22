"""Conversational StreamListener — Greetings, help, feedback, unclear intent."""

import logging

from ..base_listener import BaseStreamListener

logger = logging.getLogger(__name__)


class ConversationalStreamListener(BaseStreamListener):

    @property
    def name(self) -> str:
        return "conversational"

    @property
    def event_types_description(self) -> str:
        return """Du erkennst Gespraeche die KEINE Aktion ausloesen — Begruessung, Hilfe, Feedback.

Events:
- conversation.greeting: "Hallo", "Hi", "Guten Tag", "Hey Rachel"
- conversation.help: "Was kannst du?", "Hilfe", "Zeig mir deine Funktionen"
- conversation.goodbye: "Tschuess", "Bis spaeter", "Gute Nacht"
- conversation.unknown: Unklare Anfragen die in keinen anderen Bereich passen

EVALUATION FEEDBACK:
- evaluation.correct: "Ja genau", "Richtig", "Perfekt", "Super"
- evaluation.incorrect: "Das war falsch", "Nein", "Falsch verstanden"
- evaluation.clarify: "Ich meinte [X]", "Eigentlich wollte ich [X]"
- evaluation.stats: "Zeig Accuracy", "Wie gut verstehst du mich?"

WANN BIST DU ZUSTAENDIG:
- Begruessung und Verabschiedung
- Hilfe-Anfragen
- Feedback zur letzten Aktion
- Smalltalk ohne konkrete Aufgabe

WANN BIST DU NICHT ZUSTAENDIG:
- Sobald eine konkrete Aufgabe erkennbar ist (Bubble erstellen, App oeffnen, etc.)
- Fragen die sich auf ein spezifisches Space beziehen

WICHTIG: Setze confidence nur dann hoch (>0.5) wenn wirklich KEINE andere Aktion gemeint ist. Bei Zweifel: niedrige confidence, damit ein anderer Listener gewinnt."""
