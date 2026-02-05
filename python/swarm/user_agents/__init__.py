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

# Eagerly import base classes (no circular dependency)
from swarm.user_agents.base import BaseUserAgent, UserAgentConfig


# Lazy import helper functions
def create_rachel_agent(*args, **kwargs):
    """Create RachelAgent (lazy import)."""
    from swarm.user_agents.rachel import create_rachel_agent as _create
    return _create(*args, **kwargs)


def create_antoni_agent(*args, **kwargs):
    """Create AntoniAgent (lazy import)."""
    from swarm.user_agents.antoni import create_antoni_agent as _create
    return _create(*args, **kwargs)


def create_adam_agent(*args, **kwargs):
    """Create AdamAgent (lazy import)."""
    from swarm.user_agents.adam import create_adam_agent as _create
    return _create(*args, **kwargs)


# For backward compatibility, also provide the classes via __getattr__
def __getattr__(name):
    """Lazy load agent classes to avoid circular imports."""
    if name == "RachelAgent":
        from swarm.user_agents.rachel import RachelAgent
        return RachelAgent
    elif name == "AntoniAgent":
        from swarm.user_agents.antoni import AntoniAgent
        return AntoniAgent
    elif name == "AdamAgent":
        from swarm.user_agents.adam import AdamAgent
        return AdamAgent
    elif name == "RACHEL_VOICE_PROMPT":
        from swarm.user_agents.rachel import RACHEL_VOICE_PROMPT
        return RACHEL_VOICE_PROMPT
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


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
