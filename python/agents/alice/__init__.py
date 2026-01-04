"""
Alice Agent - Coordinator Hub

Alice ist der zentrale Koordinator. Sie delegiert Aufgaben an:
- Adam (Desktop-Arbeit)
- Antoni (Coding/Schreiben)
- Rachel (zurück zum Multiverse)
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