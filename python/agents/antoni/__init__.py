"""
Antoni Agent - Coding & Writing Worker

Antoni kümmert sich um:
- Code schreiben
- Dokumentation
- Dateien erstellen/bearbeiten
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