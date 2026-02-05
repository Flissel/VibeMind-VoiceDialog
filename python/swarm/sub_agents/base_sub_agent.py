"""
Base Sub-Agent Factories - Create shared Memory and Context sub-agents.

These sub-agents are AutoGen AssistantAgents that participate in
the Swarm team alongside the main domain agents.

Memory Sub-Agent: User profiling from domain perspective
Context Sub-Agent: Running transcript summary for AI restart
"""

import logging

logger = logging.getLogger(__name__)


def create_memory_sub_agent(parent_name: str, domain: str, model_client):
    """
    Create a Memory Sub-Agent (AutoGen AssistantAgent) for user profiling.

    This agent evaluates intents from its parent's domain perspective
    and stores behavioral insights to Supermemory.

    Args:
        parent_name: Parent agent name (e.g., "ideas_agent")
        domain: Domain identifier (e.g., "ideas", "coding", "desktop")
        model_client: AutoGen model client

    Returns:
        AssistantAgent configured as memory sub-agent
    """
    from autogen_agentchat.agents import AssistantAgent
    from swarm.tools.memory_sub_agent_tools import MEMORY_SUB_AGENT_TOOLS

    agent_name = f"{domain}_memory"

    system_message = (
        f"Du bist der Memory Sub-Agent fuer die {domain.upper()}-Domain.\n\n"
        f"**Deine Aufgabe:** Analysiere jeden Intent aus der "
        f"{domain.upper()}-Perspektive und extrahiere User-Verhaltensmuster.\n\n"
        f"**Was du extrahierst:**\n"
        f"- Zeitliche Muster (wann nutzt User welche Features)\n"
        f"- Sequenz-Muster (welche Aktionen folgen aufeinander)\n"
        f"- Praeferenz-Signale (bevorzugte Formate, Sprache, Detailtiefe)\n"
        f"- Domain-Affinitaet (wie oft wechselt User in diese Domain)\n\n"
        f"**Tools:**\n"
        f"- get_domain_profile: Aktuelles {domain}-Profil abrufen\n"
        f"- get_all_profiles: Alle Domain-Profile abrufen\n"
        f"- search_user_insights: Spezifische Insights suchen\n\n"
        f"Gib nach Abschluss an {parent_name} zurueck."
    )

    agent = AssistantAgent(
        name=agent_name,
        model_client=model_client,
        tools=MEMORY_SUB_AGENT_TOOLS,
        handoffs=[parent_name],
        system_message=system_message,
    )

    logger.info(f"Created memory sub-agent: {agent_name} (parent: {parent_name})")
    return agent


def create_context_sub_agent(parent_name: str, domain: str, model_client):
    """
    Create a Context Sub-Agent (AutoGen AssistantAgent) for session context.

    This agent maintains a running summary of the conversation
    from its parent's domain perspective for AI restart capability.

    Args:
        parent_name: Parent agent name (e.g., "ideas_agent")
        domain: Domain identifier (e.g., "ideas", "coding", "desktop")
        model_client: AutoGen model client

    Returns:
        AssistantAgent configured as context sub-agent
    """
    from autogen_agentchat.agents import AssistantAgent
    from swarm.tools.context_sub_agent_tools import CONTEXT_SUB_AGENT_TOOLS

    agent_name = f"{domain}_context"

    system_message = (
        f"Du bist der Context Sub-Agent fuer die {domain.upper()}-Domain.\n\n"
        f"**Deine Aufgabe:** Halte einen laufenden Kontext/Zusammenfassung "
        f"der aktuellen Session fuer die {domain.upper()}-Domain.\n\n"
        f"**Restart-Context enthaelt:**\n"
        f"- Aktueller Zustand der Domain\n"
        f"- Letzte 5 Aktionen in dieser Domain\n"
        f"- Offene Tasks/wartende Aktionen\n"
        f"- User-Praeferenzen fuer diese Session\n\n"
        f"**Tools:**\n"
        f"- get_restart_context: Gespeicherten Kontext abrufen\n"
        f"- get_current_summary: Aktuelle Zusammenfassung anzeigen\n"
        f"- get_recent_actions: Letzte Aktionen auflisten\n\n"
        f"Gib nach Abschluss an {parent_name} zurueck."
    )

    agent = AssistantAgent(
        name=agent_name,
        model_client=model_client,
        tools=CONTEXT_SUB_AGENT_TOOLS,
        handoffs=[parent_name],
        system_message=system_message,
    )

    logger.info(f"Created context sub-agent: {agent_name} (parent: {parent_name})")
    return agent


__all__ = [
    "create_memory_sub_agent",
    "create_context_sub_agent",
]
