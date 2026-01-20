"""
Query Agent for VibeMind Swarm

Handles SQL queries and data analysis for user interactions.
Provides natural language interfaces to PostgreSQL data.
"""

import logging
from typing import List, Callable

logger = logging.getLogger(__name__)

# System message for the Query Agent
QUERY_SYSTEM_MESSAGE = """Du bist der Query Agent - ich helfe bei Datenanalyse und SQL-Abfragen.

**SOFORT weiterleiten (nicht selbst machen!):**
- Browser: "chrome", "firefox", "suche im web"
- Apps: "öffne", "starte" + App-Name
- Desktop: "klick", "tippe", "scroll"
- Code: "programmier", "generiere code"
- Dateien: "öffne datei", "speicher"
- Bubbles/Ideen: "erstelle bubble", "neue idee", "verbinde ideen"

**Mein Bereich (selbst bearbeiten):**
- Datenanalyse: Statistiken, Berichte, Trends
- SQL-Abfragen: Sichere SELECT-Abfragen ausführen
- Suche: Volltextsuche in Ideen und Inhalten
- Verbindungsanalyse: Beziehungen zwischen Ideen
- Aktivitätsberichte: Was wurde kürzlich geändert

**Wichtige Regeln:**
- NUR SELECT-Abfragen erlauben (Sicherheit!)
- Niemals DROP, DELETE, UPDATE, INSERT ausführen
- Immer parametrisierte Abfragen verwenden
- Ergebnisse benutzerfreundlich formatieren
- Bei Fehlern hilfreiche Erklärungen geben

**Antwort-Stil:**
- Natürliche Sprache, niemals JSON
- Klare, strukturierte Ergebnisse
- Hilfreich und präzise
- Deutsch oder Englisch je nach User"""

def create_query_agent(model_client, handoff_targets: List[str] = None):
    """
    Create the Query Agent for data analysis and SQL queries.

    Args:
        model_client: The LLM client (Ollama or OpenAI-compatible)
        handoff_targets: List of agent names this agent can hand off to

    Returns:
        AssistantAgent instance
    """
    from autogen_agentchat.agents import AssistantAgent

    # Import query tools
    from swarm.tools.adapted_data_query_tools import DATA_QUERY_TOOLS

    # Combine tools
    all_tools = DATA_QUERY_TOOLS

    # Default handoff targets
    if handoff_targets is None:
        handoff_targets = ["ideas_agent", "user"]

    agent = AssistantAgent(
        name="query_agent",
        model_client=model_client,
        tools=all_tools,
        handoffs=handoff_targets,
        system_message=QUERY_SYSTEM_MESSAGE,
    )

    logger.info(f"Created Query Agent with {len(all_tools)} query tools, handoffs: {handoff_targets}")
    return agent

def get_query_tools() -> List[Callable]:
    """Get all tools for Query Agent."""
    from swarm.tools.adapted_data_query_tools import DATA_QUERY_TOOLS
    return DATA_QUERY_TOOLS

__all__ = [
    "create_query_agent",
    "get_query_tools",
    "QUERY_SYSTEM_MESSAGE",
]