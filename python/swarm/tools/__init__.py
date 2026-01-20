"""
Swarm Tools Package

Contains typed tool adapters for AutoGen Swarm agents.
These wrap the original Dict-based tools with typed function signatures.
"""

# Lazy imports to avoid circular dependencies
def get_bubble_tools():
    from .adapted_bubble_tools import BUBBLE_TOOLS
    return BUBBLE_TOOLS

def get_idea_tools():
    from .adapted_idea_tools import IDEA_TOOLS
    return IDEA_TOOLS

def get_desktop_tools():
    from .adapted_desktop_tools import DESKTOP_TOOLS
    return DESKTOP_TOOLS

def get_event_tools():
    from .event_query_tools import EVENT_TOOLS
    return EVENT_TOOLS

__all__ = [
    "get_bubble_tools",
    "get_idea_tools",
    "get_desktop_tools",
    "get_event_tools",
]
