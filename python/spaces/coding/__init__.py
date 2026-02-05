"""
VibeMind Coding Space Module

Antoni's domain - Code generation and project management.
Includes backend agent, tools, and user agent.
"""

# Re-export from legacy modules for backward compatibility
from swarm.backend_agents.coding_agent import CodingAgent, get_coding_agent
from swarm.user_agents.antoni import AntoniAgent, create_antoni_agent

__all__ = [
    # Backend Agent
    "CodingAgent",
    "get_coding_agent",
    # User Agent
    "AntoniAgent",
    "create_antoni_agent",
]
