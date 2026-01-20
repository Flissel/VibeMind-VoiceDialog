"""
User Agents for VibeMind Event Buffer System

User Agents handle direct user interaction:
- Clarification when input is unclear
- Delegation to workers for execution
- TTS output coordination

Available agents:
- Rachel: Ideas Space (bubbles, ideas, navigation)
- Antoni: Coding Space (code generation, projects)
- Adam: Desktop Space (automation, apps, browser)
"""

from swarm.user_agents.base import BaseUserAgent, UserAgentConfig
from swarm.user_agents.rachel import RachelAgent, create_rachel_agent
from swarm.user_agents.antoni import AntoniAgent, create_antoni_agent
from swarm.user_agents.adam import AdamAgent, create_adam_agent

__all__ = [
    "BaseUserAgent",
    "UserAgentConfig",
    "RachelAgent",
    "AntoniAgent",
    "AdamAgent",
    "create_rachel_agent",
    "create_antoni_agent",
    "create_adam_agent",
]
