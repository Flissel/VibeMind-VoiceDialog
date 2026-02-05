"""
Event Buffer System for VibeMind

Handles input buffering, task orchestration, and correction detection.
Enables continuous speaking while agents work in parallel.

Key features:
- Input Queue per Space
- Correction detection (keyword + time window)
- Task status tracking
- Non-blocking input processing
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any, Callable
from enum import Enum

from swarm.navigation import SpaceType

logger = logging.getLogger(__name__)


# Correction detection settings
CORRECTION_KEYWORDS = [
    # German
    "nein", "eigentlich", "stopp", "warte", "nicht so", "halt",
    "abbrechen", "anders", "falsch", "doch nicht",
    # English
    "no", "actually", "stop", "wait", "not like that", "cancel",
    "wrong", "nevermind", "scratch that",
]
CORRECTION_WINDOW_MS = 3000  # 3 seconds


class TaskStatus(Enum):
    """Status of a task in the buffer."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


@dataclass
class InputEvent:
    """A single user input event."""
    text: str
    timestamp: float
    target_space: SpaceType
    is_correction: bool = False
    corrects_input_id: Optional[str] = None
    processed: bool = False
    input_id: str = field(default_factory=lambda: f"input_{time.time_ns()}")
    domain_hint: Optional[str] = None  # ideas, bubbles, desktop, coding, shuttles


@dataclass
class TaskInfo:
    """Information about an active task."""
    task_id: str
    input_event: InputEvent
    space: SpaceType
    status: TaskStatus = TaskStatus.PENDING
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    result: Optional[str] = None
    error: Optional[str] = None


class EventBuffer:
    """
    Central event buffer with task orchestration.

    Responsibilities:
    - Buffer incoming user input
    - Detect corrections/updates to previous input
    - Track task status per space
    - Coordinate TTS output priority
    """

    def __init__(self):
        # Input history (for correction detection)
        self.input_history: List[InputEvent] = []

        # Active tasks per space
        self.active_tasks: Dict[SpaceType, TaskInfo] = {}

        # Pending inputs per space (not yet dispatched)
        self.pending_inputs: Dict[SpaceType, List[InputEvent]] = {
            SpaceType.IDEAS: [],
            SpaceType.CODING: [],
            SpaceType.DESKTOP: [],
        }

        # Callbacks
        self._on_correction: Optional[Callable[[InputEvent, InputEvent], Any]] = None
        self._on_task_complete: Optional[Callable[[TaskInfo], Any]] = None

        logger.info("EventBuffer initialized")

    def detect_correction(self, new_input: str, last_input_ts: float) -> bool:
        """
        Detect if new input is a correction of previous input.

        Uses combination of:
        - Keyword detection (explicit correction words)
        - Time window (quick follow-up within 3 seconds)

        Args:
            new_input: The new user input text
            last_input_ts: Timestamp of the last input

        Returns:
            True if this appears to be a correction
        """
        text_lower = new_input.lower()

        # Check for explicit correction keywords
        is_keyword = any(kw in text_lower for kw in CORRECTION_KEYWORDS)
        if is_keyword:
            logger.debug(f"Correction detected via keyword: {new_input[:50]}")
            return True

        # Check time window (quick follow-up)
        time_since_last = (time.time() - last_input_ts) * 1000  # to ms
        is_recent = time_since_last < CORRECTION_WINDOW_MS

        if is_recent and self._looks_like_modification(new_input):
            logger.debug(f"Correction detected via time window: {new_input[:50]}")
            return True

        return False

    def _looks_like_modification(self, text: str) -> bool:
        """
        Heuristic to detect if input looks like a modification.

        Examples of modifications:
        - "mit blau statt rot" (with blue instead of red)
        - "aber größer" (but bigger)
        - "und auch..." (and also...)
        """
        modification_patterns = [
            "statt", "anstatt", "instead", "rather",
            "aber", "but",
            "und auch", "and also",
            "eher", "mehr", "weniger",
        ]
        text_lower = text.lower()
        return any(p in text_lower for p in modification_patterns)

    async def buffer_input(self, event: InputEvent) -> None:
        """
        Buffer an input event for later processing.

        Args:
            event: The input event to buffer
        """
        space = event.target_space
        self.pending_inputs[space].append(event)
        self.input_history.append(event)

        # Keep history bounded
        if len(self.input_history) > 100:
            self.input_history = self.input_history[-50:]

        logger.debug(f"Buffered input for {space.value}: {event.text[:50]}")

    async def process_input(
        self,
        text: str,
        target_space: SpaceType,
        timestamp: Optional[float] = None,
    ) -> InputEvent:
        """
        Process new user input.

        - Detects if it's a correction
        - Creates InputEvent
        - Buffers for target space

        Args:
            text: User input text
            target_space: Target space for this input
            timestamp: Optional timestamp (defaults to now)

        Returns:
            The created InputEvent
        """
        ts = timestamp or time.time()

        # Check if this is a correction
        is_correction = False
        corrects_id = None

        if self.input_history:
            last_input = self.input_history[-1]
            is_correction = self.detect_correction(text, last_input.timestamp)
            if is_correction:
                corrects_id = last_input.input_id

                # Notify callback if set
                if self._on_correction:
                    new_event = InputEvent(
                        text=text,
                        timestamp=ts,
                        target_space=target_space,
                        is_correction=True,
                        corrects_input_id=corrects_id,
                    )
                    try:
                        result = self._on_correction(last_input, new_event)
                        if asyncio.iscoroutine(result):
                            await result
                    except Exception as e:
                        logger.error(f"Correction callback error: {e}")

        # Create input event
        event = InputEvent(
            text=text,
            timestamp=ts,
            target_space=target_space,
            is_correction=is_correction,
            corrects_input_id=corrects_id,
        )

        # Buffer it
        await self.buffer_input(event)

        return event

    def get_pending_count(self, space: SpaceType) -> int:
        """Get count of pending inputs for a space."""
        return len(self.pending_inputs.get(space, []))

    def get_all_pending(self) -> Dict[SpaceType, int]:
        """Get pending counts for all spaces."""
        return {
            space: len(inputs)
            for space, inputs in self.pending_inputs.items()
        }

    async def flush_pending(self, space: SpaceType) -> List[InputEvent]:
        """
        Get and clear all pending inputs for a space.

        Args:
            space: The space to flush

        Returns:
            List of pending input events
        """
        pending = self.pending_inputs.get(space, [])
        self.pending_inputs[space] = []
        return pending

    def start_task(self, event: InputEvent) -> TaskInfo:
        """
        Mark a task as started.

        Args:
            event: The input event that started this task

        Returns:
            TaskInfo for the started task
        """
        task = TaskInfo(
            task_id=f"task_{time.time_ns()}",
            input_event=event,
            space=event.target_space,
            status=TaskStatus.IN_PROGRESS,
            started_at=time.time(),
        )
        self.active_tasks[event.target_space] = task
        logger.info(f"Started task for {event.target_space.value}: {event.text[:50]}")
        return task

    def complete_task(
        self,
        space: SpaceType,
        result: Optional[str] = None,
        error: Optional[str] = None,
    ) -> Optional[TaskInfo]:
        """
        Mark a task as completed.

        Args:
            space: The space where task completed
            result: Optional result string
            error: Optional error message

        Returns:
            The completed TaskInfo, or None if no active task
        """
        task = self.active_tasks.pop(space, None)
        if task:
            task.status = TaskStatus.COMPLETED if not error else TaskStatus.FAILED
            task.completed_at = time.time()
            task.result = result
            task.error = error

            # Notify callback
            if self._on_task_complete:
                try:
                    self._on_task_complete(task)
                except Exception as e:
                    logger.error(f"Task complete callback error: {e}")

            logger.info(f"Completed task for {space.value}")

        return task

    def cancel_task(self, space: SpaceType) -> Optional[TaskInfo]:
        """
        Cancel an active task.

        Args:
            space: The space where to cancel

        Returns:
            The cancelled TaskInfo, or None
        """
        task = self.active_tasks.pop(space, None)
        if task:
            task.status = TaskStatus.CANCELLED
            task.completed_at = time.time()
            logger.info(f"Cancelled task for {space.value}")
        return task

    def is_space_busy(self, space: SpaceType) -> bool:
        """Check if a space has an active task."""
        return space in self.active_tasks

    def get_active_task(self, space: SpaceType) -> Optional[TaskInfo]:
        """Get the active task for a space."""
        return self.active_tasks.get(space)

    def on_correction(self, callback: Callable[[InputEvent, InputEvent], Any]) -> None:
        """Set callback for correction events."""
        self._on_correction = callback

    def on_task_complete(self, callback: Callable[[TaskInfo], Any]) -> None:
        """Set callback for task completion events."""
        self._on_task_complete = callback


# Singleton instance
_event_buffer: Optional[EventBuffer] = None


def get_event_buffer() -> EventBuffer:
    """Get or create the global event buffer."""
    global _event_buffer
    if _event_buffer is None:
        _event_buffer = EventBuffer()
    return _event_buffer


def reset_event_buffer() -> None:
    """Reset the event buffer (for testing)."""
    global _event_buffer
    _event_buffer = None


__all__ = [
    "EventBuffer",
    "InputEvent",
    "TaskInfo",
    "TaskStatus",
    "CORRECTION_KEYWORDS",
    "CORRECTION_WINDOW_MS",
    "get_event_buffer",
    "reset_event_buffer",
]
