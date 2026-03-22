"""
User Agents for VibeMind Event Buffer System

User Agents handle direct user interaction:
- Clarification when input is unclear
- Delegation to workers for execution
- TTS output coordination

Active agent:
- Rachel: Ideas Space (bubbles, ideas, navigation) — the voice agent
"""

# Eagerly import base classes (no circular dependency)
from swarm.user_agents.base import BaseUserAgent, UserAgentConfig


# Lazy import helper functions
def create_rachel_agent(*args, **kwargs):
    """Create RachelAgent (lazy import)."""
    from spaces.ideas.agents.rachel_agent import create_rachel_agent as _create
    return _create(*args, **kwargs)


# For backward compatibility, also provide the classes via __getattr__
def __getattr__(name):
    """Lazy load agent classes to avoid circular imports."""
    if name == "RachelAgent":
        from spaces.ideas.agents.rachel_agent import RachelAgent
        return RachelAgent
    elif name == "RACHEL_VOICE_PROMPT":
        from spaces.ideas.agents.rachel_agent import RACHEL_VOICE_PROMPT
        return RACHEL_VOICE_PROMPT
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "BaseUserAgent",
    "UserAgentConfig",
    "RachelAgent",
    "create_rachel_agent",
]
