"""
VibeMind Desktop Space Module

Adam's domain - Desktop automation and system control.
Includes backend agent, adapted tools, and user agent.

Migrated from:
- swarm/backend_agents/desktop_agent.py
- swarm/user_agents/adam.py
- swarm/tools/adapted_desktop_tools.py
- tools/desktop_tools.py, quickaction_tools.py, task_tools.py, moire_tools.py
"""

from .agents import DesktopAgent, get_desktop_agent, AdamAgent, create_adam_agent

__all__ = [
    # Backend Agent
    "DesktopAgent",
    "get_desktop_agent",
    # User Agent
    "AdamAgent",
    "create_adam_agent",
]
