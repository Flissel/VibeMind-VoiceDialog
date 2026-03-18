"""Research Space StreamListener — Web research, scraping, summarization."""

import logging

from ..base_listener import BaseStreamListener

logger = logging.getLogger(__name__)


class ResearchStreamListener(BaseStreamListener):

    @property
    def name(self) -> str:
        return "research"

    @property
    def event_types_description(self) -> str:
        return """Du fuehrst Online-Recherchen durch, scrapest Webseiten und fasst sie zusammen.

Events:
- research.web: "Recherchiere ueber X", "Finde heraus was X ist", "Was sagt das Internet ueber X?" → payload: {query: "X"}
- research.scrape: "Scrape die Seite [URL]", "Extrahiere den Inhalt von [URL]" → payload: {url: "..."}
- research.summarize: "Fasse die Seite [URL] zusammen" → payload: {url: "..."}
- research.to_idea: "Recherchiere X und speichere als Idee" → payload: {query: "X", title: "..."}
- research.to_rowboat: "Recherchiere X und speichere in Rowboat" → payload: {query: "X"}

ABGRENZUNG:
- "Recherchiere ueber X" = research.web (deep research, externe Quellen)
- "Such im Web nach X" = web.search (einfache Desktop-Suche)
- "Was weiss ich ueber X?" = roarboot.search (interner Knowledge Graph)

WICHTIG: Alles was mit tiefgehender Online-Recherche, Webseiten-Analyse und Zusammenfassungen externer Inhalte zu tun hat ist dein Bereich."""
