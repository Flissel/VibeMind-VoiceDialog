"""Minibook Space StreamListener — Cross-space collaboration, discussions."""

import logging

from ..base_listener import BaseStreamListener

logger = logging.getLogger(__name__)


class MinibookStreamListener(BaseStreamListener):

    @property
    def name(self) -> str:
        return "minibook"

    @property
    def event_types_description(self) -> str:
        return """Du koordinierst Zusammenarbeit zwischen verschiedenen Spaces (Multi-Space-Aufgaben).

Events:
- minibook.collaborate: "Recherchiere X und erstelle daraus eine Idee", "Finde Infos und schreib Code dafuer" → payload: {task: "...", goal: "..."}
- minibook.discuss: "Bespreche X in Minibook", "Starte eine Diskussion zu X" → payload: {message: "...", topic: "..."}
- minibook.status: "Minibook Status", "Ist Minibook verbunden?"
- minibook.results: "Was kam bei der Diskussion raus?", "Ergebnisse der Zusammenarbeit"
- minibook.list_projects: "Welche Projekte gibt es in Minibook?"
- minibook.poll: "Neue Antworten von Minibook?"

WANN BIST DU ZUSTAENDIG:
- Aufgaben die MEHRERE Spaces betreffen (z.B. "Recherchiere UND erstelle Idee" = Research + Ideas)
- Explizite Minibook/Collaboration-Anfragen
- Wenn der User nach Space-uebergreifender Zusammenarbeit fragt

WANN BIST DU NICHT ZUSTAENDIG:
- Reine Einzelspace-Aufgaben (nur Ideas, nur Coding, nur Desktop)
- Einfache Anfragen die nur ein Space betreffen"""
