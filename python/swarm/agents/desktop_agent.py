"""
Desktop Agent for VibeMind Swarm

Handles desktop automation and system tasks.
This is the primary agent for the Desktop/Automation Space.
"""

import logging
from typing import List, Callable

logger = logging.getLogger(__name__)

# System message for the Desktop Agent
DESKTOP_SYSTEM_MESSAGE = """You are the Desktop Agent - I automate your computer.

**What I can do:**
- Open and control apps
- Click, type, scroll
- Take screenshots
- Track tasks

**Response Style:**
- Always respond in natural language, never raw JSON
- Be conversational: "I'll open Chrome for you..."
- Describe actions briefly, confirm when done

**Handoffs:**
- When done → handoff to user
- Need ideas/spaces → handoff to shuttle_agent

Ask what the user wants automated if the request is unclear."""


def create_desktop_agent(model_client, handoff_targets: List[str] = None):
    """
    Create the Desktop Agent for automation tasks.

    Args:
        model_client: The LLM client (Ollama or OpenAI-compatible)
        handoff_targets: List of agent names this agent can hand off to

    Returns:
        AssistantAgent instance
    """
    from autogen_agentchat.agents import AssistantAgent
    from swarm.tools.adapted_desktop_tools import DESKTOP_TOOLS

    # Default handoff targets
    if handoff_targets is None:
        handoff_targets = ["shuttle_agent", "user"]

    agent = AssistantAgent(
        name="desktop_agent",
        model_client=model_client,
        tools=DESKTOP_TOOLS,
        handoffs=handoff_targets,
        system_message=DESKTOP_SYSTEM_MESSAGE,
    )

    logger.info(f"Created Desktop Agent with {len(DESKTOP_TOOLS)} tools, handoffs: {handoff_targets}")
    return agent


def get_desktop_tools() -> List[Callable]:
    """Get all tools for Desktop Agent."""
    from swarm.tools.adapted_desktop_tools import DESKTOP_TOOLS
    return DESKTOP_TOOLS


__all__ = [
    "create_desktop_agent",
    "get_desktop_tools",
    "DESKTOP_SYSTEM_MESSAGE",
]
