"""
VibeMind Debug Tools

Debug utilities for Electron and Voice Dialog debugging.
"""

from .electron_debug_agent import (
    ElectronDebugAgent,
    CDPClient,
    DebugLogger,
    DebugConfig,
)

__all__ = [
    "ElectronDebugAgent",
    "CDPClient", 
    "DebugLogger",
    "DebugConfig",
]