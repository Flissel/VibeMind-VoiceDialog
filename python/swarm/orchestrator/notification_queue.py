"""
Notification Queue - Stores pending task results for next voice input.

The NotificationQueue enables async feedback without TTS injection:
1. Backend agent completes task
2. StatusListener adds result to NotificationQueue
3. On next user input, Rachel checks queue
4. Rachel includes pending results in her response

This approach is compatible with the voice Conversational AI layer.
"""

import logging
import sys
import time
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


def _debug_print(msg: str):
    """Print debug message to stderr for visibility in Electron."""
    print(f"[Python DEBUG] [NotificationQueue] {msg}", file=sys.stderr)


@dataclass
class Notification:
    """A pending task notification."""
    job_id: str
    event_type: str
    result: Any
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


class NotificationQueue:
    """
    Stores pending task results for the next voice input.

    Thread-safe queue that accumulates completed task results.
    Rachel checks this queue before processing each user input
    and includes pending notifications in her response context.
    """

    def __init__(self, max_age_seconds: float = 300.0):
        """
        Initialize the notification queue.

        Args:
            max_age_seconds: Maximum age of notifications before auto-cleanup (default: 5 min)
        """
        self._pending: List[Notification] = []
        self._max_age = max_age_seconds

    def add_notification(
        self,
        job_id: str,
        event_type: str,
        result: Any,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Notification:
        """
        Add a task completion notification to the queue.

        Args:
            job_id: The job ID that completed
            event_type: Original event type (e.g., "bubble.create")
            result: The task result
            metadata: Optional additional metadata

        Returns:
            The created Notification object
        """
        # Clean up old notifications first
        self._cleanup_old()

        notification = Notification(
            job_id=job_id,
            event_type=event_type,
            result=result,
            metadata=metadata or {}
        )
        self._pending.append(notification)

        # Log to both logger and stderr for visibility
        msg = f"ADDED: {event_type} (job={job_id[:8]}...) - queue size: {len(self._pending)}"
        logger.info(f"NotificationQueue: {msg}")
        _debug_print(msg)
        return notification

    def get_and_clear(self) -> List[Notification]:
        """
        Get all pending notifications and clear the queue.

        This is the main method Rachel calls before processing input.

        Returns:
            List of all pending notifications
        """
        # Clean up old notifications first
        self._cleanup_old()

        notifications = self._pending.copy()
        self._pending = []

        if notifications:
            # Log what Rachel is retrieving
            types = [n.event_type for n in notifications]
            msg = f"RETRIEVED: {len(notifications)} notifications - {types}"
            logger.info(f"NotificationQueue: {msg}")
            _debug_print(msg)
        else:
            # Log when queue is checked but empty (helps debug timing)
            logger.debug("NotificationQueue: Rachel checked queue - empty")

        return notifications

    def peek(self) -> List[Notification]:
        """
        Peek at pending notifications without clearing.

        Returns:
            List of all pending notifications (queue not cleared)
        """
        self._cleanup_old()
        return self._pending.copy()

    def has_pending(self) -> bool:
        """Check if there are pending notifications."""
        self._cleanup_old()
        return len(self._pending) > 0

    def count(self) -> int:
        """Get number of pending notifications."""
        self._cleanup_old()
        return len(self._pending)

    def clear(self) -> int:
        """
        Clear all pending notifications.

        Returns:
            Number of notifications cleared
        """
        count = len(self._pending)
        self._pending = []
        logger.info(f"NotificationQueue: Cleared {count} notifications")
        return count

    def _cleanup_old(self) -> int:
        """
        Remove notifications older than max_age_seconds.

        Returns:
            Number of notifications removed
        """
        if not self._pending:
            return 0

        cutoff = time.time() - self._max_age
        old_count = len(self._pending)
        self._pending = [n for n in self._pending if n.timestamp > cutoff]
        removed = old_count - len(self._pending)

        if removed > 0:
            logger.debug(f"NotificationQueue: Cleaned up {removed} old notifications")

        return removed

    def format_for_context(self, notifications: Optional[List[Notification]] = None) -> str:
        """
        Format notifications as context string for the LLM.

        Args:
            notifications: List of notifications to format (or use pending if None)

        Returns:
            Formatted string for LLM context
        """
        if notifications is None:
            notifications = self.peek()

        if not notifications:
            return ""

        lines = []
        for n in notifications:
            # Format result (truncate if too long)
            result_str = str(n.result)
            if len(result_str) > 200:
                result_str = result_str[:200] + "..."

            # Human-readable event type
            event_readable = n.event_type.replace(".", " ").replace("_", " ").title()

            lines.append(f"- {event_readable}: {result_str}")

        return "\n".join(lines)


# Singleton instance
_notification_queue: Optional[NotificationQueue] = None


def get_notification_queue() -> NotificationQueue:
    """Get or create the global NotificationQueue instance."""
    global _notification_queue
    if _notification_queue is None:
        _notification_queue = NotificationQueue()
    return _notification_queue


def reset_notification_queue() -> None:
    """Reset the notification queue (for testing)."""
    global _notification_queue
    _notification_queue = None


__all__ = [
    "NotificationQueue",
    "Notification",
    "get_notification_queue",
    "reset_notification_queue",
]
