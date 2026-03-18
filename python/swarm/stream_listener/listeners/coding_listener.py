"""Coding Space StreamListener — Code generation, preview, projects."""

import logging

from ..base_listener import BaseStreamListener

logger = logging.getLogger(__name__)


class CodingStreamListener(BaseStreamListener):

    @property
    def name(self) -> str:
        return "coding"

    @property
    def event_types_description(self) -> str:
        return """Du bist zustaendig fuer Code-Generierung, Projekte und Vorschau.

Events:
- code.generate: "Erstelle eine App fuer [X]", "Baue mir [PROJEKT] mit [TECH]", "Programmiere [X]" → payload: {title: "Beschreibung"}
- code.modify: "Aendere den Code zu [INSTRUCTION]", "Modifiziere [CHANGE]" → payload: {instruction: "..."}
- code.status: "Wie ist der Code-Status?", "Projekt-Fortschritt?"
- code.preview.start: "Zeig Preview", "Starte Vorschau"
- code.preview.stop: "Stoppe Preview", "Schliesse Vorschau"
- code.list: "Zeig meine Projekte"
- code.cancel: "Stoppe die Generierung", "Cancel"
- idea.to_project: "Mach ein Projekt aus dieser Idee" → payload: {idea_name: "..."}

WICHTIG: Alles was mit Programmierung, Code, Apps bauen, Software-Entwicklung, Technologie-Projekte zu tun hat ist dein Bereich."""
