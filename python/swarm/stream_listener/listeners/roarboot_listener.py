"""Roarboot Space StreamListener — Knowledge graph, emails, meetings, docker."""

import logging

from ..base_listener import BaseStreamListener

logger = logging.getLogger(__name__)


class RoarbootStreamListener(BaseStreamListener):

    @property
    def name(self) -> str:
        return "roarboot"

    @property
    def event_types_description(self) -> str:
        return """Du verwaltest den Knowledge Graph (Rowboat/Roarboot) — Wissen, Emails, Meetings, Praesentationen.

KNOWLEDGE GRAPH:
- roarboot.search: "Durchsuche mein Wissen nach X", "Was weiss ich ueber X?" → payload: {query: "X"}
- roarboot.query: "Infos zu Projekt X", "Erzaehl mir ueber X" → payload: {subject: "X"}

CONTENT GENERATION:
- roarboot.email_draft: "Schreibe Email an X wegen Y" → payload: {recipient: "X", topic: "Y"}
- roarboot.meeting_brief: "Bereite mein Meeting mit X vor" → payload: {meeting: "X"}
- roarboot.deck: "Erstelle eine Praesentation ueber X" → payload: {topic: "X"}
- roarboot.voice_note: "Merke dir fuer den Knowledge Graph: X" → payload: {text: "X"}

SYSTEM:
- roarboot.status: "Roarboot Status", "Ist Rowboat verbunden?"
- roarboot.open: "Oeffne Roarboot", "Zeig Rowboat"
- roarboot.reset: "Neues Gespraech mit Roarboot"

DOCKER:
- roarboot.docker.start: "Starte Roarboot", "Rowboat hochfahren"
- roarboot.docker.stop: "Stoppe Roarboot"
- roarboot.docker.restart: "Starte Roarboot neu"
- roarboot.docker.status: "Roarboot Docker Status", "Laufen die Container?"

WICHTIG: Alles was mit Wissen, Knowledge Graph, Email-Entwuerfe, Meeting-Vorbereitung, Praesentationen und Rowboat/Roarboot zu tun hat ist dein Bereich."""
