"""Ideas Space StreamListener — Bubbles, Ideas, Formatting, Exploration."""

import logging

from ..base_listener import BaseStreamListener

logger = logging.getLogger(__name__)


class IdeasStreamListener(BaseStreamListener):

    @property
    def name(self) -> str:
        return "ideas"

    @property
    def event_types_description(self) -> str:
        return """Du verwaltest Bubbles (Bereiche/Spaces) und Ideen (Notizen/Eintraege).

BUBBLE-Events:
- bubble.list: "Zeig mir meine Bubbles", "Welche Bubbles habe ich?", "Liste Bubbles"
- bubble.create: "Erstelle Bubble [NAME]", "Neuer Bereich fuer [NAME]" → payload: {title: "NAME"}
- bubble.enter: "Geh in [NAME]", "Oeffne [NAME]", "Wechsle zu [NAME]" → payload: {bubble_name: "NAME"}
- bubble.exit: "Zurueck", "Raus", "Verlasse Bubble", "Zur Uebersicht"
- bubble.delete: "Loesche Bubble [NAME]" → payload: {bubble_name: "NAME"}
- bubble.find: "Such nach Bubble [NAME]" → payload: {query: "NAME"}
- bubble.stats: "Wie viele Ideen?", "Bubble Info"
- bubble.current: "Welche Bubble bin ich gerade?"

IDEE-Events:
- idea.list: "Was habe ich notiert?", "Zeig Notizen", "Liste auf"
- idea.count: "Wie viele Ideen habe ich?"
- idea.create: "Notiere [INHALT]", "Merke dir [INHALT]", "Neue Idee: [NAME]" → payload: {title: "NAME", content: "..."}
- idea.find: "Suche nach [QUERY]" → payload: {query: "QUERY"}
- idea.update: "Aendere [NAME]" → payload: {idea_name: "NAME", new_content: "..."}
- idea.delete: "Loesche Idee [NAME]" → payload: {idea_name: "NAME"}
- idea.move: "Verschiebe [IDEE] nach [SPACE]" → payload: {idea_name: "...", target_bubble: "..."}

VERBINDUNGEN:
- idea.connect: "Verbinde [A] mit [B]" → payload: {idea1: "A", idea2: "B"}
- idea.auto_link: "Verlinke die Ideen sinnvoll", "Finde Verbindungen"
- idea.analyze_links: "Analysiere Verlinkungen", "Welche Ideen sollten verlinkt werden?"

FORMATIERUNG:
- idea.format_table: "Formatiere als Tabelle"
- idea.format_action_list: "Formatiere als Aktionsliste"
- idea.format_pros_cons: "Formatiere als Pro/Contra"
- idea.format_kanban: "Erstelle Kanban Board"
- idea.format_mindmap: "Erstelle Mindmap"
- idea.format_swot: "Erstelle SWOT Analyse"
- idea.summarize: "Fasse zusammen" → payload: {idea_name: "...", style: "concise"|"detailed"|"actionable"}

KI-TOOLS:
- idea.expand: "Erweitere die Ideen", "Brainstorme neue Ideen"
- idea.explain: "Erklaere die Idee [NAME]"
- idea.whitepaper: "Erstelle White Paper"

EXPLORATION (AI-Scientist):
- idea.explore.start: "Finde tiefere Verbindungen", "Erforsche Zusammenhaenge"
- idea.explore.stop: "Stopp Exploration"
- idea.explore.status: "Exploration Status"

WICHTIG: Alles was mit Notizen, Ideen, Bubbles, Spaces, Formatierung, Verlinkung zu tun hat ist dein Bereich."""
