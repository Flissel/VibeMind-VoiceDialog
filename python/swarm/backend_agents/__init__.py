"""
Backend Agents - Tool Executors for VibeMind Swarm

Backend agents listen to Redis streams and execute the actual tools.
Each agent is responsible for a specific domain:

- BubblesAgent: Space/Bubble management (13 tools)
- IdeasAgent: Ideas/Notes within bubbles (38 tools)
- DesktopAgent: Desktop automation (12 tools)
- CodingAgent: Code generation (8 tools)

Architecture:
1. Rachel (voice) sends intent to Orchestrator
2. Orchestrator classifies and seeds event to Redis
3. Backend Agent receives event, executes tool
4. Backend Agent publishes status back to Redis
5. StatusListener receives status, triggers Rachel TTS
"""

# Lazy imports to avoid circular dependencies after migration
# BaseBackendAgent is always needed, so import it eagerly
from swarm.backend_agents.base_agent import BaseBackendAgent


def get_bubbles_agent():
    """Get BubblesAgent singleton (lazy import)."""
    from swarm.backend_agents.bubbles_agent import get_bubbles_agent as _get
    return _get()


def get_ideas_agent():
    """Get IdeasAgent singleton (lazy import)."""
    from swarm.backend_agents.ideas_agent import get_ideas_agent as _get
    return _get()


def get_desktop_agent():
    """Get DesktopAgent singleton (lazy import)."""
    from swarm.backend_agents.desktop_agent import get_desktop_agent as _get
    return _get()


def get_coding_agent():
    """Get CodingAgent singleton (lazy import)."""
    from swarm.backend_agents.coding_agent import get_coding_agent as _get
    return _get()


# For backward compatibility, also provide the classes via __getattr__
def __getattr__(name):
    """Lazy load agent classes to avoid circular imports."""
    if name == "BubblesAgent":
        from swarm.backend_agents.bubbles_agent import BubblesAgent
        return BubblesAgent
    elif name == "IdeasAgent":
        from swarm.backend_agents.ideas_agent import IdeasAgent
        return IdeasAgent
    elif name == "DesktopAgent":
        from swarm.backend_agents.desktop_agent import DesktopAgent
        return DesktopAgent
    elif name == "CodingAgent":
        from swarm.backend_agents.coding_agent import CodingAgent
        return CodingAgent
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "BaseBackendAgent",
    "BubblesAgent",
    "get_bubbles_agent",
    "IdeasAgent",
    "get_ideas_agent",
    "DesktopAgent",
    "get_desktop_agent",
    "CodingAgent",
    "get_coding_agent",
]
