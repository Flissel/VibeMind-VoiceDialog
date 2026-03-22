"""Shuttles Space StreamListener — Requirements pipeline, shuttle management."""

import logging

from ..base_listener import BaseStreamListener

logger = logging.getLogger(__name__)


class ShuttlesStreamListener(BaseStreamListener):

    @property
    def name(self) -> str:
        return "shuttles"

    @property
    def event_types_description(self) -> str:
        return """Du verwaltest die Shuttle-Pipeline fuer Anforderungen und Spezifikationen.

Events:
- shuttle.create: "Erstelle ein Shuttle fuer [ANFORDERUNG]", "Neue Anforderung: [X]" → payload: {title: "...", description: "..."}
- shuttle.status: "Shuttle Status", "Wie weit ist das Shuttle?"
- shuttle.advance: "Bringe das Shuttle voran", "Naechste Stufe"
- shuttle.list: "Zeig meine Shuttles", "Welche Anforderungen gibt es?"

WANN BIST DU ZUSTAENDIG:
- Alles was mit Anforderungen (Requirements), Spezifikationen und der Shuttle-Pipeline zu tun hat
- Wenn der User explizit "Shuttle" erwaehnt"""
