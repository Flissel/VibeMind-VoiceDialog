"""
Adam Agent - Desktop Worker

Adam führt Desktop-Aufgaben aus:
- Apps öffnen/steuern
- Klicks und Eingaben
- System-Operationen
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