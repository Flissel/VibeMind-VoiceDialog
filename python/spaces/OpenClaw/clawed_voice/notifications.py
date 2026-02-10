"""
OpenClaw Notification Queue

Redis-based queue for storing task results from OpenClaw.
Rachel can retrieve these asynchronously.
"""

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, List, Optional

from .config import get_config

logger = logging.getLogger(__name__)

# Redis stream name
STREAM_NAME = "notifications:openclaw"


@dataclass
class Notification:
    """
    A notification from an OpenClaw task.

    Attributes:
        job_id: Unique job identifier
        task_type: Type of task (messaging.whatsapp, web.search, etc.)
        status: completed, failed, pending
        result: Task result data
        timestamp: When notification was created
        read: Whether notification has been read
    """
    job_id: str
    task_type: str
    status: str
    result: Dict[str, Any]
    timestamp: float = field(default_factory=time.time)
    read: bool = False
    message_id: Optional[str] = None

    def to_redis(self) -> Dict[str, str]:
        """Convert to Redis-compatible dict (all string values)."""
        return {
            "job_id": self.job_id,
            "task_type": self.task_type,
            "status": self.status,
            "result": json.dumps(self.result),
            "timestamp": str(self.timestamp),
            "read": "1" if self.read else "0",
        }

    @classmethod
    def from_redis(cls, msg_id: str, data: Dict[bytes, bytes]) -> "Notification":
        """Create from Redis stream message."""
        return cls(
            job_id=data.get(b"job_id", b"").decode(),
            task_type=data.get(b"task_type", b"").decode(),
            status=data.get(b"status", b"").decode(),
            result=json.loads(data.get(b"result", b"{}").decode()),
            timestamp=float(data.get(b"timestamp", b"0").decode()),
            read=data.get(b"read", b"0").decode() == "1",
            message_id=msg_id.decode() if isinstance(msg_id, bytes) else msg_id,
        )

    def summary(self) -> str:
        """Create human-readable summary for voice output."""
        if self.status == "completed":
            if self.task_type.startswith("messaging."):
                platform = self.task_type.split(".")[-1]
                return f"{platform.title()} Nachricht gesendet"
            elif self.task_type == "web.search":
                count = len(self.result.get("results", []))
                return f"Websuche: {count} Ergebnisse"
            elif self.task_type == "web.fetch":
                return "Webseite abgerufen"
            elif self.task_type.startswith("browser."):
                action = self.task_type.split(".")[-1]
                return f"Browser {action} erfolgreich"
            else:
                return "Aufgabe abgeschlossen"
        elif self.status == "failed":
            error = self.result.get("error", "Unbekannter Fehler")
            return f"Fehlgeschlagen: {error}"
        else:
            return f"Status: {self.status}"


class NotificationQueue:
    """
    Redis-based notification queue.

    Stores OpenClaw task results for later retrieval by Rachel.
    """

    def __init__(self, redis_url: Optional[str] = None):
        config = get_config()
        self.redis_url = redis_url or config.redis_url
        self._redis = None
        self._sync_redis = None

    async def _get_redis(self):
        """Get async Redis connection."""
        if self._redis is None:
            try:
                import redis.asyncio as redis_async
                self._redis = redis_async.from_url(
                    self.redis_url,
                    decode_responses=False,
                )
            except ImportError:
                raise ImportError("redis package required: pip install redis")
        return self._redis

    def _get_sync_redis(self):
        """Get sync Redis connection."""
        if self._sync_redis is None:
            try:
                import redis
                self._sync_redis = redis.from_url(
                    self.redis_url,
                    decode_responses=False,
                )
            except ImportError:
                raise ImportError("redis package required: pip install redis")
        return self._sync_redis

    async def add(
        self,
        task_type: str,
        result: Dict[str, Any],
        status: str = "completed",
        job_id: Optional[str] = None,
    ) -> str:
        """
        Add notification to queue.

        Args:
            task_type: Type of task
            result: Task result
            status: Status string
            job_id: Optional job ID (generated if not provided)

        Returns:
            Job ID
        """
        job_id = job_id or str(uuid.uuid4())

        notification = Notification(
            job_id=job_id,
            task_type=task_type,
            status=status,
            result=result,
        )

        r = await self._get_redis()
        msg_id = await r.xadd(STREAM_NAME, notification.to_redis())

        logger.info(f"Added notification: {job_id} ({task_type}) -> {status}")
        return job_id

    def add_sync(
        self,
        task_type: str,
        result: Dict[str, Any],
        status: str = "completed",
        job_id: Optional[str] = None,
    ) -> str:
        """Synchronous version of add()."""
        job_id = job_id or str(uuid.uuid4())

        notification = Notification(
            job_id=job_id,
            task_type=task_type,
            status=status,
            result=result,
        )

        r = self._get_sync_redis()
        r.xadd(STREAM_NAME, notification.to_redis())

        logger.info(f"Added notification: {job_id} ({task_type}) -> {status}")
        return job_id

    async def get_pending(self, limit: int = 10) -> List[Notification]:
        """
        Get pending (unread) notifications.

        Args:
            limit: Maximum number to return

        Returns:
            List of unread notifications
        """
        r = await self._get_redis()

        # Read latest messages
        messages = await r.xrevrange(STREAM_NAME, count=limit * 2)

        notifications = []
        for msg_id, data in messages:
            notif = Notification.from_redis(msg_id, data)
            if not notif.read:
                notifications.append(notif)
                if len(notifications) >= limit:
                    break

        # Return in chronological order
        return list(reversed(notifications))

    def get_pending_sync(self, limit: int = 10) -> List[Notification]:
        """Synchronous version of get_pending()."""
        r = self._get_sync_redis()

        messages = r.xrevrange(STREAM_NAME, count=limit * 2)

        notifications = []
        for msg_id, data in messages:
            notif = Notification.from_redis(msg_id, data)
            if not notif.read:
                notifications.append(notif)
                if len(notifications) >= limit:
                    break

        return list(reversed(notifications))

    async def get_by_job_id(self, job_id: str) -> Optional[Notification]:
        """Get notification by job ID."""
        r = await self._get_redis()

        # Scan stream for matching job_id
        messages = await r.xrange(STREAM_NAME)
        for msg_id, data in messages:
            if data.get(b"job_id", b"").decode() == job_id:
                return Notification.from_redis(msg_id, data)

        return None

    async def mark_read(self, job_id: str) -> bool:
        """
        Mark notification as read.

        Note: Redis streams don't support in-place updates,
        so we delete and re-add with read=True.
        """
        r = await self._get_redis()

        # Find the notification
        messages = await r.xrange(STREAM_NAME)
        for msg_id, data in messages:
            if data.get(b"job_id", b"").decode() == job_id:
                # Create updated notification
                notif = Notification.from_redis(msg_id, data)
                notif.read = True

                # Delete old, add new
                await r.xdel(STREAM_NAME, msg_id)
                await r.xadd(STREAM_NAME, notif.to_redis())

                logger.debug(f"Marked notification {job_id} as read")
                return True

        return False

    async def clear_old(self, max_age_hours: int = 24) -> int:
        """
        Clear notifications older than max_age_hours.

        Returns:
            Number of notifications deleted
        """
        r = await self._get_redis()
        cutoff = time.time() - (max_age_hours * 3600)

        messages = await r.xrange(STREAM_NAME)
        deleted = 0

        for msg_id, data in messages:
            timestamp = float(data.get(b"timestamp", b"0").decode())
            if timestamp < cutoff:
                await r.xdel(STREAM_NAME, msg_id)
                deleted += 1

        if deleted:
            logger.info(f"Cleared {deleted} old notifications")

        return deleted

    async def count(self) -> int:
        """Get total notification count."""
        r = await self._get_redis()
        return await r.xlen(STREAM_NAME)

    async def count_unread(self) -> int:
        """Get unread notification count."""
        notifications = await self.get_pending(limit=100)
        return len(notifications)


# Singleton
_queue: Optional[NotificationQueue] = None


def get_notification_queue() -> NotificationQueue:
    """Get or create NotificationQueue singleton."""
    global _queue
    if _queue is None:
        _queue = NotificationQueue()
    return _queue


__all__ = [
    "Notification",
    "NotificationQueue",
    "get_notification_queue",
    "STREAM_NAME",
]
