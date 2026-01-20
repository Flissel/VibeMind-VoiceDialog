"""
Space Container for VibeMind Event Buffer System

A Space represents one area in the multiverse (Ideas, Coding, Desktop).
Each Space contains:
- A User Agent (for interaction/clarification)
- Worker Agents (for autonomous task execution)
- Input queue (for buffered user input)
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any, TYPE_CHECKING
from enum import Enum

from swarm.navigation import SpaceType

if TYPE_CHECKING:
    from autogen_agentchat.agents import AssistantAgent

logger = logging.getLogger(__name__)


@dataclass
class SpaceConfig:
    """Configuration for a Space."""
    space_type: SpaceType
    user_agent_name: str  # e.g., "rachel", "antoni", "adam"
    display_name: str  # e.g., "Ideas Space (Rachel)"
    worker_names: List[str] = field(default_factory=list)

    # Navigation triggers (keywords that switch to this space)
    trigger_keywords: List[str] = field(default_factory=list)


# Default configurations for each space
SPACE_CONFIGS: Dict[SpaceType, SpaceConfig] = {
    SpaceType.IDEAS: SpaceConfig(
        space_type=SpaceType.IDEAS,
        user_agent_name="rachel",
        display_name="Ideas Space (Rachel)",
        worker_names=["bubble_worker", "idea_worker", "score_worker"],
        trigger_keywords=["ideas", "rachel", "bubbles", "spaces", "multiverse"],
    ),
    SpaceType.CODING: SpaceConfig(
        space_type=SpaceType.CODING,
        user_agent_name="antoni",
        display_name="Coding Space (Antoni)",
        worker_names=["generate_worker", "preview_worker", "file_worker"],
        trigger_keywords=["coding", "antoni", "code", "programmieren", "projekte"],
    ),
    SpaceType.DESKTOP: SpaceConfig(
        space_type=SpaceType.DESKTOP,
        user_agent_name="adam",
        display_name="Desktop Space (Adam)",
        worker_names=["click_worker", "type_worker", "app_worker"],
        trigger_keywords=["desktop", "adam", "computer", "system", "automat"],
    ),
}


@dataclass
class Space:
    """
    Container for a single Space in the multiverse.

    Each Space has:
    - One User Agent (handles user interaction, clarification)
    - Multiple Worker Agents (handle autonomous execution)
    - Input queue (buffered user input)
    - Task tracking (active/pending tasks)
    """

    config: SpaceConfig
    user_agent: Optional["AssistantAgent"] = None
    workers: Dict[str, Any] = field(default_factory=dict)  # name -> worker instance
    input_queue: asyncio.Queue = field(default_factory=asyncio.Queue)
    active_task: Optional[Any] = None
    pending_tasks: List[Any] = field(default_factory=list)

    @property
    def name(self) -> str:
        """Get space name."""
        return self.config.space_type.value

    @property
    def display_name(self) -> str:
        """Get human-readable display name."""
        return self.config.display_name

    @property
    def user_agent_name(self) -> str:
        """Get user agent name (rachel, antoni, adam)."""
        return self.config.user_agent_name

    def is_busy(self) -> bool:
        """Check if space has active task."""
        return self.active_task is not None

    def has_pending_input(self) -> bool:
        """Check if there's pending input in queue."""
        return not self.input_queue.empty()

    async def queue_input(self, text: str, timestamp: float) -> None:
        """Add input to the space's queue."""
        from swarm.event_buffer import InputEvent
        event = InputEvent(
            text=text,
            timestamp=timestamp,
            target_space=self.config.space_type,
        )
        await self.input_queue.put(event)
        logger.debug(f"Queued input for {self.name}: {text[:50]}...")

    async def get_next_input(self, timeout: float = 0.5) -> Optional[Any]:
        """Get next input from queue (with timeout)."""
        try:
            return await asyncio.wait_for(
                self.input_queue.get(),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            return None


class SpaceRegistry:
    """
    Registry of all spaces in the multiverse.

    Manages space lifecycle and provides lookup functionality.
    """

    def __init__(self):
        self._spaces: Dict[SpaceType, Space] = {}
        self._initialized = False

    def initialize(self) -> None:
        """Initialize all spaces with default configs."""
        for space_type, config in SPACE_CONFIGS.items():
            self._spaces[space_type] = Space(config=config)
        self._initialized = True
        logger.info(f"SpaceRegistry initialized with {len(self._spaces)} spaces")

    def get_space(self, space_type: SpaceType) -> Optional[Space]:
        """Get a space by type."""
        return self._spaces.get(space_type)

    def get_space_by_name(self, name: str) -> Optional[Space]:
        """Get a space by name string (e.g., 'ideas', 'coding')."""
        try:
            space_type = SpaceType(name.lower())
            return self.get_space(space_type)
        except ValueError:
            return None

    def get_space_by_agent(self, agent_name: str) -> Optional[Space]:
        """Get space by user agent name (e.g., 'rachel' -> Ideas Space)."""
        agent_lower = agent_name.lower()
        for space in self._spaces.values():
            if space.user_agent_name == agent_lower:
                return space
        return None

    def all_spaces(self) -> List[Space]:
        """Get all spaces."""
        return list(self._spaces.values())

    def set_user_agent(self, space_type: SpaceType, agent: "AssistantAgent") -> None:
        """Set the user agent for a space."""
        space = self.get_space(space_type)
        if space:
            space.user_agent = agent
            logger.info(f"Set user agent for {space_type.value}: {agent.name}")

    def add_worker(self, space_type: SpaceType, worker_name: str, worker: Any) -> None:
        """Add a worker to a space."""
        space = self.get_space(space_type)
        if space:
            space.workers[worker_name] = worker
            logger.debug(f"Added worker {worker_name} to {space_type.value}")

    def get_busy_spaces(self) -> List[Space]:
        """Get all spaces that have active tasks."""
        return [s for s in self._spaces.values() if s.is_busy()]

    def get_spaces_with_pending_input(self) -> List[Space]:
        """Get all spaces that have pending input."""
        return [s for s in self._spaces.values() if s.has_pending_input()]


# Singleton instance
_space_registry: Optional[SpaceRegistry] = None


def get_space_registry() -> SpaceRegistry:
    """Get or create the global space registry."""
    global _space_registry
    if _space_registry is None:
        _space_registry = SpaceRegistry()
        _space_registry.initialize()
    return _space_registry


def reset_space_registry() -> None:
    """Reset the space registry (for testing)."""
    global _space_registry
    _space_registry = None


__all__ = [
    "Space",
    "SpaceConfig",
    "SpaceRegistry",
    "SpaceType",
    "SPACE_CONFIGS",
    "get_space_registry",
    "reset_space_registry",
]
