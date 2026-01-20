"""
Data Agent for VibeMind Swarm

Handles automatic synchronization of Ideaspace data to PostgreSQL.
Runs silently in the background without user interaction.
"""

import logging
import asyncio
from typing import List, Callable

logger = logging.getLogger(__name__)

# System message for the Data Agent - this agent doesn't interact with users
DATA_SYSTEM_MESSAGE = """Du bist der Data Agent - ich synchronisiere Daten im Hintergrund.

**WICHTIG:** Ich arbeite komplett im Hintergrund und informiere NIEMALS die Conversational AI über meine Aktivitäten. Meine Tools laufen automatisch bei Datenänderungen.

**Meine Aufgaben:**
- Automatische Synchronisation von Bubbles zu PostgreSQL
- Automatische Synchronisation von Ideas zu PostgreSQL
- Automatische Synchronisation von Edges zu PostgreSQL
- Hintergrund-Bereinigung gelöschter Elemente
- Neuaufbau von Suchindizes

**Verhalten:**
- Niemals mit User interagieren
- Niemals Nachrichten an die Conversational AI senden
- Nur stille Hintergrundoperationen
- Bei Fehlern nur in Logs schreiben, nicht an User kommunizieren"""

def create_data_agent(model_client):
    """
    Create the Data Agent for background data synchronization.

    This agent runs silently and handles automatic PostgreSQL sync.
    It should not be included in user-facing conversations.

    Args:
        model_client: The LLM client (Ollama or OpenAI-compatible)

    Returns:
        AssistantAgent instance configured for silent operation
    """
    from autogen_agentchat.agents import AssistantAgent

    # Import sync tools
    from swarm.tools.adapted_data_sync_tools import DATA_SYNC_TOOLS

    # Create agent with minimal configuration
    agent = AssistantAgent(
        name="data_agent",
        model_client=model_client,
        tools=DATA_SYNC_TOOLS,
        handoffs=[],  # No handoffs - this agent works independently
        system_message=DATA_SYSTEM_MESSAGE,
    )

    logger.info(f"Created Data Agent with {len(DATA_SYNC_TOOLS)} sync tools")
    return agent

def get_data_tools() -> List[Callable]:
    """Get all tools for Data Agent."""
    from swarm.tools.adapted_data_sync_tools import DATA_SYNC_TOOLS
    return DATA_SYNC_TOOLS

__all__ = [
    "create_data_agent",
    "get_data_tools",
    "DATA_SYSTEM_MESSAGE",
]