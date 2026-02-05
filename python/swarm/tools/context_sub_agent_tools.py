"""
Context Sub-Agent Tools - Voice-callable tools for context management.

These tools allow agents to query and manage session context,
including restart context retrieval and conversation summaries.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


async def get_restart_context() -> str:
    """
    Get the full restart context for the current session.

    Returns a summary of the conversation so far, enabling
    the AI to resume with full context after a restart.

    Returns:
        Session context summary string
    """
    try:
        from swarm.broadcast.sub_agents.context_sub_agent import get_context_sub_agent
        agent = get_context_sub_agent()
        context = await agent.get_restart_context()

        if not context:
            return "Kein gespeicherter Session-Kontext vorhanden."

        return f"[Restart-Kontext]\n{context}"

    except Exception as e:
        logger.debug(f"get_restart_context failed: {e}")
        return f"Kontext konnte nicht abgerufen werden: {e}"


def get_current_summary() -> str:
    """
    Get the current in-memory conversation summary (no API call).

    Returns:
        Current session summary
    """
    try:
        from swarm.broadcast.sub_agents.context_sub_agent import get_context_sub_agent
        agent = get_context_sub_agent()
        summary = agent.get_current_summary()

        if not summary:
            return "Noch keine Zusammenfassung vorhanden (Session gerade gestartet)."

        return f"[Aktuelle Zusammenfassung]\n{summary}"

    except Exception as e:
        logger.debug(f"get_current_summary failed: {e}")
        return f"Zusammenfassung nicht verfuegbar: {e}"


def get_recent_actions(limit: int = 10) -> str:
    """
    Get the most recent recorded actions.

    Args:
        limit: Maximum number of actions to return

    Returns:
        Formatted list of recent actions
    """
    try:
        from swarm.broadcast.sub_agents.context_sub_agent import get_context_sub_agent
        agent = get_context_sub_agent()
        actions = agent.get_recent_actions(limit=limit)

        if not actions:
            return "Noch keine Aktionen aufgezeichnet."

        lines = [f"Letzte {len(actions)} Aktionen:"]
        for a in actions:
            lines.append(
                f"  [{a['n']}] {a['intent']}: {a.get('user', '')[:80]}"
            )

        return "\n".join(lines)

    except Exception as e:
        logger.debug(f"get_recent_actions failed: {e}")
        return f"Aktionen nicht verfuegbar: {e}"


# Tools list for AutoGen agent registration
CONTEXT_SUB_AGENT_TOOLS = [
    get_restart_context,
    get_current_summary,
    get_recent_actions,
]

__all__ = [
    "get_restart_context",
    "get_current_summary",
    "get_recent_actions",
    "CONTEXT_SUB_AGENT_TOOLS",
]
