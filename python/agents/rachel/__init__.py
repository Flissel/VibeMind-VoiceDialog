"""
Rachel Agent - Multiverse Navigator

Rachel ist der Haupt-Navigator durch die Bubble-Welt (Multiverse).
Sie kann in Bubbles eintreten, neue Spaces erstellen und Ideen verwalten.
Rachel = Multiverse Agent
"""

from .config import AGENT_CONFIG
from .tools import get_tools, get_tool_definitions
from .prompts import SYSTEM_PROMPT, FIRST_MESSAGE

__all__ = [
    "AGENT_CONFIG",
    "get_tools",
    "get_tool_definitions",
    "SYSTEM_PROMPT",
    "FIRST_MESSAGE",
]