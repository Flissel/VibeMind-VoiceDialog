"""
Shuttle Agent for VibeMind Swarm

Handles transfers between spaces and idea promotions.
Acts as the routing/coordination agent.
"""

import logging
from typing import List, Callable

logger = logging.getLogger(__name__)

# System message for the Shuttle Agent
SHUTTLE_SYSTEM_MESSAGE = """Du bist der Shuttle Agent - Router zwischen spezialisierten Agents.

**Routing-Regeln (SOFORT ausführen):**

→ desktop_agent:
  - Browser: "chrome", "firefox", "edge", "browser"
  - Suchen: "suche", "search", "google", "web"
  - Apps: "öffne", "starte", "open", "launch"
  - Automation: "klick", "click", "tippe", "type", "scroll"
  - System: "desktop", "computer", "screenshot"

→ coding_agent:
  - Code: "code", "programmier", "program"
  - Generieren: "generiere", "generate", "erstelle code"
  - Projekt: "projekt erstellen", "new project"

→ ideas_agent:
  - Spaces: "space", "bubble", "raum"
  - Ideen: "idee", "idea", "notiz", "note"

→ user (Aufgabe fertig oder Input nötig)

**Antwort-Stil:**
- Kurz: "Ich verbinde dich mit Adam für Desktop..." → handoff
- Niemals JSON
- Nicht erklären, einfach machen

Beispiel: "suche in chrome" → "Ich leite das an Adam weiter..." → handoff zu desktop_agent"""


def transfer_to_ideas() -> str:
    """Transfer to ideas agent for bubble/note management."""
    return "ideas_agent"


def transfer_to_coding() -> str:
    """Transfer to coding agent for code generation."""
    return "coding_agent"


def transfer_to_desktop() -> str:
    """Transfer to desktop agent for automation."""
    return "desktop_agent"


def create_shuttle_agent(model_client, handoff_targets: List[str] = None):
    """
    Create the Shuttle Agent for routing and coordination.

    Args:
        model_client: The LLM client (Ollama or OpenAI-compatible)
        handoff_targets: List of agent names this agent can hand off to

    Returns:
        AssistantAgent instance
    """
    from autogen_agentchat.agents import AssistantAgent

    # Import promotion tool
    from swarm.tools.adapted_bubble_tools import promote_bubble

    # Shuttle agent tools (minimal - mainly routes)
    tools = [
        promote_bubble,
    ]

    # Default handoff targets - can route to all other agents
    if handoff_targets is None:
        handoff_targets = ["ideas_agent", "coding_agent", "desktop_agent", "user"]

    agent = AssistantAgent(
        name="shuttle_agent",
        model_client=model_client,
        tools=tools,
        handoffs=handoff_targets,
        system_message=SHUTTLE_SYSTEM_MESSAGE,
    )

    logger.info(f"Created Shuttle Agent with {len(tools)} tools, handoffs: {handoff_targets}")
    return agent


__all__ = [
    "create_shuttle_agent",
    "SHUTTLE_SYSTEM_MESSAGE",
]
