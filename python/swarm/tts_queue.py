"""
TTS Output Queue for VibeMind Event Buffer System

Priority-based queue for Text-to-Speech output.
Ensures only one agent speaks at a time with proper priority.

Priority levels:
1 - Urgent (errors, interrupts)
2 - User Agent responses (Rachel, Antoni, Adam)
3 - Worker status updates
4 - Background notifications
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Optional, Callable, Any, List
from enum import IntEnum

logger = logging.getLogger(__name__)


class TTSPriority(IntEnum):
    """Priority levels for TTS output."""
    URGENT = 1  # Errors, interrupts
    USER_AGENT = 2  # User Agent responses
    WORKER_STATUS = 3  # Worker progress updates
    BACKGROUND = 4  # Notifications


@dataclass(order=True)
class TTSItem:
    """
    An item in the TTS queue.

    Ordered by: priority (ascending), then timestamp (ascending)
    """
    priority: int
    timestamp: float = field(compare=True)
    text: str = field(compare=False)
    agent_name: str = field(compare=False, default="")
    item_id: str = field(compare=False, default_factory=lambda: f"tts_{time.time_ns()}")


class TTSQueue:
    """
    Priority-based TTS output queue.

    Features:
    - Priority-based ordering (urgent > user agent > worker > background)
    - Only one item speaks at a time
    - Can interrupt lower-priority items
    - Rate limiting to avoid overlap
    """

    def __init__(
        self,
        speak_callback: Optional[Callable[[str], Any]] = None,
        min_gap_seconds: float = 0.5,
    ):
        """
        Initialize TTS queue.

        Args:
            speak_callback: Async function to speak text
            min_gap_seconds: Minimum gap between utterances
        """
        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self._speak_callback = speak_callback
        self._min_gap = min_gap_seconds

        # State
        self._is_speaking = False
        self._current_item: Optional[TTSItem] = None
        self._last_speak_time: float = 0
        self._running = False
        self._process_task: Optional[asyncio.Task] = None

        # Pending interrupts
        self._pending_interrupt: Optional[TTSItem] = None

        logger.info("TTSQueue initialized")

    async def enqueue(
        self,
        text: str,
        priority: TTSPriority = TTSPriority.USER_AGENT,
        agent_name: str = "",
    ) -> TTSItem:
        """
        Add text to the TTS queue.

        Args:
            text: Text to speak
            priority: Priority level
            agent_name: Name of speaking agent

        Returns:
            The created TTSItem
        """
        item = TTSItem(
            priority=priority.value,
            timestamp=time.time(),
            text=text,
            agent_name=agent_name,
        )

        # Check for urgent interrupt
        if priority == TTSPriority.URGENT and self._is_speaking:
            self._pending_interrupt = item
            logger.info(f"Urgent interrupt queued: {text[:50]}")
        else:
            await self._queue.put(item)
            logger.debug(f"Queued TTS (p={priority.name}): {text[:50]}...")

        return item

    async def speak_now(
        self,
        text: str,
        agent_name: str = "",
        interrupt: bool = False,
    ) -> None:
        """
        Speak text immediately (bypasses queue if interrupt=True).

        Args:
            text: Text to speak
            agent_name: Name of speaking agent
            interrupt: If True, interrupts current speech
        """
        if interrupt:
            await self.enqueue(text, TTSPriority.URGENT, agent_name)
        else:
            await self.enqueue(text, TTSPriority.USER_AGENT, agent_name)

    async def start_processing(self) -> None:
        """Start the queue processing loop."""
        if self._running:
            return

        self._running = True
        self._process_task = asyncio.create_task(self._process_loop())
        logger.info("TTSQueue processing started")

    async def stop_processing(self) -> None:
        """Stop the queue processing loop."""
        self._running = False
        if self._process_task:
            self._process_task.cancel()
            try:
                await self._process_task
            except asyncio.CancelledError:
                pass
        logger.info("TTSQueue processing stopped")

    async def _process_loop(self) -> None:
        """Main processing loop."""
        while self._running:
            try:
                # Check for pending interrupt
                if self._pending_interrupt:
                    item = self._pending_interrupt
                    self._pending_interrupt = None
                    await self._speak_item(item)
                    continue

                # Wait for next item
                try:
                    item = await asyncio.wait_for(
                        self._queue.get(),
                        timeout=0.5
                    )
                    await self._speak_item(item)
                except asyncio.TimeoutError:
                    continue

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"TTSQueue error: {e}")

    async def _speak_item(self, item: TTSItem) -> None:
        """
        Speak a single item.

        Args:
            item: The item to speak
        """
        # Respect minimum gap
        elapsed = time.time() - self._last_speak_time
        if elapsed < self._min_gap:
            await asyncio.sleep(self._min_gap - elapsed)

        self._is_speaking = True
        self._current_item = item

        try:
            if self._speak_callback:
                logger.debug(f"Speaking ({item.agent_name}): {item.text[:50]}...")
                result = self._speak_callback(item.text)
                if asyncio.iscoroutine(result):
                    await result
            else:
                # No callback - just log
                logger.info(f"[TTS] {item.agent_name}: {item.text}")

        except Exception as e:
            logger.error(f"TTS speak error: {e}")

        finally:
            self._is_speaking = False
            self._current_item = None
            self._last_speak_time = time.time()

    def set_speak_callback(self, callback: Callable[[str], Any]) -> None:
        """Set the speak callback function."""
        self._speak_callback = callback

    def is_speaking(self) -> bool:
        """Check if currently speaking."""
        return self._is_speaking

    def get_current_speaker(self) -> Optional[str]:
        """Get name of currently speaking agent."""
        if self._current_item:
            return self._current_item.agent_name
        return None

    def get_queue_size(self) -> int:
        """Get number of items in queue."""
        return self._queue.qsize()

    async def clear_queue(self) -> int:
        """
        Clear all pending items from queue.

        Returns:
            Number of items cleared
        """
        count = 0
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
                count += 1
            except asyncio.QueueEmpty:
                break
        logger.info(f"Cleared {count} items from TTS queue")
        return count


# Singleton instance
_tts_queue: Optional[TTSQueue] = None


def get_tts_queue() -> TTSQueue:
    """Get or create the global TTS queue."""
    global _tts_queue
    if _tts_queue is None:
        _tts_queue = TTSQueue()
    return _tts_queue


def reset_tts_queue() -> None:
    """Reset the TTS queue (for testing)."""
    global _tts_queue
    _tts_queue = None


__all__ = [
    "TTSQueue",
    "TTSItem",
    "TTSPriority",
    "get_tts_queue",
    "reset_tts_queue",
]
