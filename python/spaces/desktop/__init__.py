"""
VibeMind Desktop Space Module

Adam's domain - Desktop automation and system control.
Includes backend agent, tools, and user agent.
"""

# Re-export from legacy modules for backward compatibility
from swarm.backend_agents.desktop_agent import DesktopAgent, get_desktop_agent
from swarm.user_agents.adam import AdamAgent, create_adam_agent

__all__ = [
    # Backend Agent
    "DesktopAgent",
    "get_desktop_agent",
    # User Agent
    "AdamAgent",
    "create_adam_agent",
]
