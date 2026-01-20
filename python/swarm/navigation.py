"""
Navigation Layer for VibeMind Event Buffer System

Handles space navigation like the Electron app multiverse.
Recognizes navigation keywords and manages current space state.
"""

import asyncio
import logging
import re
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Callable, Any
from enum import Enum

logger = logging.getLogger(__name__)


class SpaceType(Enum):
    """Available space types in the multiverse."""
    IDEAS = "ideas"
    CODING = "coding"
    DESKTOP = "desktop"


@dataclass
class NavigationEvent:
    """Event emitted when navigation occurs."""
    from_space: Optional[SpaceType]
    to_space: SpaceType
    trigger_text: str
    timestamp: float


# Navigation keywords per space (German + English)
NAVIGATION_PATTERNS: Dict[SpaceType, List[str]] = {
    SpaceType.IDEAS: [
        r"(?:geh|wechsel|zurück)\s*(?:zu|nach|in)?\s*ideas?",
        r"(?:go|switch|back)\s*(?:to)?\s*ideas?",
        r"ideen?\s*(?:space|bereich|raum)",
        r"rachel",  # User agent name
        r"multiverse",
        r"bubbles?",
        r"spaces?",
    ],
    SpaceType.CODING: [
        r"(?:geh|wechsel|zurück)\s*(?:zu|nach|in)?\s*coding",
        r"(?:go|switch|back)\s*(?:to)?\s*coding",
        r"code?\s*(?:space|bereich|raum)",
        r"programmier",
        r"antoni",  # User agent name
        r"projekte?",
    ],
    SpaceType.DESKTOP: [
        r"(?:geh|wechsel|zurück)\s*(?:zu|nach|in)?\s*desktop",
        r"(?:go|switch|back)\s*(?:to)?\s*desktop",
        r"desktop\s*(?:space|bereich|raum)",
        r"automat",
        r"adam",  # User agent name
        r"computer",
        r"system",
    ],
}


class NavigationLayer:
    """
    Manages navigation between spaces in the multiverse.

    Like the Electron app, but for voice:
    - Recognizes navigation keywords
    - Maintains current space state
    - Emits navigation events
    """

    def __init__(self, default_space: SpaceType = SpaceType.IDEAS):
        """
        Initialize navigation layer.

        Args:
            default_space: Starting space (default: Ideas)
        """
        self.current_space: SpaceType = default_space
        self._previous_space: Optional[SpaceType] = None
        self._navigation_history: List[NavigationEvent] = []
        self._listeners: List[Callable[[NavigationEvent], Any]] = []

        # Compile regex patterns for performance
        self._compiled_patterns: Dict[SpaceType, List[re.Pattern]] = {}
        for space, patterns in NAVIGATION_PATTERNS.items():
            self._compiled_patterns[space] = [
                re.compile(p, re.IGNORECASE) for p in patterns
            ]

        logger.info(f"NavigationLayer initialized, starting in {default_space.value}")

    def detect_navigation(self, text: str) -> Optional[SpaceType]:
        """
        Check if text contains navigation intent.

        Args:
            text: User input text

        Returns:
            Target space if navigation detected, None otherwise
        """
        text_lower = text.lower().strip()

        # Check each space's patterns
        for space, patterns in self._compiled_patterns.items():
            for pattern in patterns:
                if pattern.search(text_lower):
                    # Don't navigate if already in target space
                    if space != self.current_space:
                        return space
                    else:
                        logger.debug(f"Already in {space.value}, no navigation needed")
                        return None

        return None

    async def navigate_to(self, target: SpaceType, trigger_text: str = "") -> NavigationEvent:
        """
        Navigate to a different space.

        Args:
            target: Target space
            trigger_text: The text that triggered navigation

        Returns:
            NavigationEvent describing the transition
        """
        import time

        event = NavigationEvent(
            from_space=self.current_space,
            to_space=target,
            trigger_text=trigger_text,
            timestamp=time.time(),
        )

        self._previous_space = self.current_space
        self.current_space = target
        self._navigation_history.append(event)

        logger.info(f"Navigated: {event.from_space.value if event.from_space else 'None'} -> {event.to_space.value}")

        # Notify listeners
        for listener in self._listeners:
            try:
                result = listener(event)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.error(f"Navigation listener error: {e}")

        return event

    def go_back(self) -> Optional[SpaceType]:
        """
        Return to previous space.

        Returns:
            Previous space if available, None otherwise
        """
        if self._previous_space:
            return self._previous_space
        return None

    async def process_input(self, text: str) -> tuple[bool, Optional[NavigationEvent]]:
        """
        Process user input and handle navigation if detected.

        Args:
            text: User input text

        Returns:
            Tuple of (was_navigation, navigation_event)
        """
        target = self.detect_navigation(text)

        if target:
            event = await self.navigate_to(target, text)
            return True, event

        return False, None

    def add_listener(self, callback: Callable[[NavigationEvent], Any]) -> None:
        """Add a navigation event listener."""
        self._listeners.append(callback)

    def remove_listener(self, callback: Callable[[NavigationEvent], Any]) -> None:
        """Remove a navigation event listener."""
        if callback in self._listeners:
            self._listeners.remove(callback)

    def get_space_name(self, space: Optional[SpaceType] = None) -> str:
        """Get human-readable space name."""
        s = space or self.current_space
        names = {
            SpaceType.IDEAS: "Ideas Space (Rachel)",
            SpaceType.CODING: "Coding Space (Antoni)",
            SpaceType.DESKTOP: "Desktop Space (Adam)",
        }
        return names.get(s, "Unknown Space")

    def get_user_agent_name(self, space: Optional[SpaceType] = None) -> str:
        """Get the user agent name for a space."""
        s = space or self.current_space
        agents = {
            SpaceType.IDEAS: "rachel",
            SpaceType.CODING: "antoni",
            SpaceType.DESKTOP: "adam",
        }
        return agents.get(s, "unknown")


# Singleton instance
_navigation_layer: Optional[NavigationLayer] = None


def get_navigation_layer() -> NavigationLayer:
    """Get or create the global navigation layer."""
    global _navigation_layer
    if _navigation_layer is None:
        _navigation_layer = NavigationLayer()
    return _navigation_layer


def reset_navigation_layer() -> None:
    """Reset the navigation layer (for testing)."""
    global _navigation_layer
    _navigation_layer = None


__all__ = [
    "NavigationLayer",
    "NavigationEvent",
    "SpaceType",
    "NAVIGATION_PATTERNS",
    "get_navigation_layer",
    "reset_navigation_layer",
]
