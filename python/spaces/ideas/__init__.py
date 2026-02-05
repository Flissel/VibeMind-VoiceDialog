"""
VibeMind Ideas Space Module

Rachel's domain - Bubble and idea management.
Includes backend agents, tools, and user agent.
"""

# Re-export from legacy modules for backward compatibility
from swarm.backend_agents.ideas_agent import IdeasAgent, get_ideas_agent
from swarm.backend_agents.bubbles_agent import BubblesAgent, get_bubbles_agent
from swarm.user_agents.rachel import RachelAgent, create_rachel_agent

__all__ = [
    # Backend Agents
    "IdeasAgent",
    "get_ideas_agent",
    "BubblesAgent",
    "get_bubbles_agent",
    # User Agent
    "RachelAgent",
    "create_rachel_agent",
]
