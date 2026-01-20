"""
Planning Agent for VibeMind Swarm

Intelligent task planning and decomposition using conversation context.
Creates execution plans for complex user requests.
"""

import logging
from typing import List, Callable

logger = logging.getLogger(__name__)

# System message for the Planning Agent
PLANNING_SYSTEM_MESSAGE = """Du bist der Planning Agent - ich analysiere komplexe Anfragen und erstelle Ausführungspläne.

**SOFORT weiterleiten (nicht selbst machen!):**
- Einfache Aufgaben: "erstelle eine Idee" → ideas_agent
- Datenbankabfragen: "zeige Statistiken" → query_agent
- Code-Generierung: "schreibe Code" → coding_agent
- Desktop-Aktionen: "öffne Programm" → desktop_agent

**Mein Bereich (selbst bearbeiten):**
- Komplexe Planung: Mehrstufige Aufgaben analysieren und zerlegen
- Context-Analyse: Gesprächsverlauf verstehen und nutzen
- Task-Koordination: Abhängigkeiten und parallele Ausführung planen
- Ressourcen-Zuweisung: Richtige Agenten für Teilaufgaben auswählen

**Planung-Strategien:**
1. **Transcript-Analyse**: Verstehe den Gesprächskontext
2. **Anforderungsanalyse**: Identifiziere benötigte Fähigkeiten
3. **Task-Decomposition**: Zerlege in manageable Schritte
4. **Dependency-Mapping**: Definiere Ausführungsreihenfolge
5. **Agent-Zuweisung**: Weise Tasks den richtigen Agenten zu

**Ausgabe-Format:**
- Strukturierte JSON-Pläne mit klaren Tasks
- Abhängigkeiten und Koordinationshinweise
- Ressourcen-Anforderungen und Zeitabschätzungen

**Beispiele für komplexe Aufgaben:**
- "Entwickle ein Self-Aware System für Code mit Conversion-Alliance"
- "Analysiere alle Ideen und erstelle Aktionslisten"
- "Erweitere das System um KI-gestützte Funktionen"

Bei komplexen Anfragen: Analysiere Transcript → Erstelle Plan → Koordiniere Ausführung."""

def create_planning_agent(model_client, handoff_targets: List[str] = None):
    """
    Create the Planning Agent for intelligent task planning.

    Args:
        model_client: The LLM client (Ollama or OpenAI-compatible)
        handoff_targets: List of agent names this agent can hand off to

    Returns:
        AssistantAgent instance
    """
    from autogen_agentchat.agents import AssistantAgent

    # Import planning tools
    from swarm.tools.planning_tools import PLANNING_TOOLS

    # Combine tools
    all_tools = PLANNING_TOOLS

    # Default handoff targets - all other agents
    if handoff_targets is None:
        handoff_targets = ["ideas_agent", "query_agent", "coding_agent", "desktop_agent", "data_agent"]

    agent = AssistantAgent(
        name="planning_agent",
        model_client=model_client,
        tools=all_tools,
        handoffs=handoff_targets,
        system_message=PLANNING_SYSTEM_MESSAGE,
    )

    logger.info(f"Created Planning Agent with {len(all_tools)} planning tools, handoffs: {handoff_targets}")
    return agent

def get_planning_tools() -> List[Callable]:
    """Get all tools for Planning Agent."""
    from swarm.tools.planning_tools import PLANNING_TOOLS
    return PLANNING_TOOLS

__all__ = [
    "create_planning_agent",
    "get_planning_tools",
    "PLANNING_SYSTEM_MESSAGE",
]