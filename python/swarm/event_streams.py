"""
Event Streams for VibeMind Swarm

Manages per-space event streams using Redis Streams.
Falls back to in-memory storage if Redis is unavailable.
"""

import os
import uuid
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Dict, List, Optional, Any, Union
from enum import Enum
import json
import asyncio

logger = logging.getLogger(__name__)

# Redis configuration
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
STREAM_PREFIX = "vibemind:events:"
GLOBAL_STREAM = "vibemind:events:global"
MAX_STREAM_LENGTH = 1000  # Max events per stream


class EventType(str, Enum):
    """Event types for space streams."""
    # Ideas Space Events
    IDEA_CREATED = "idea_created"
    IDEA_UPDATED = "idea_updated"
    IDEA_DELETED = "idea_deleted"
    BUBBLE_ENTERED = "bubble_entered"
    BUBBLE_EXITED = "bubble_exited"
    BUBBLE_CREATED = "bubble_created"
    BUBBLE_DELETED = "bubble_deleted"
    BUBBLE_SCORED = "bubble_scored"

    # Shuttle Events
    TRANSFER_INITIATED = "transfer_initiated"
    TRANSFER_COMPLETED = "transfer_completed"
    PROMOTION_STARTED = "promotion_started"
    PROMOTION_COMPLETED = "promotion_completed"

    # Coding Events
    CODE_GENERATION_STARTED = "code_generation_started"
    CODE_GENERATION_PROGRESS = "code_generation_progress"
    CODE_GENERATION_COMPLETED = "code_generation_completed"
    CODE_GENERATION_FAILED = "code_generation_failed"

    # Desktop Events
    TASK_STARTED = "task_started"
    TASK_PROGRESS = "task_progress"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"

    # General
    AGENT_HANDOFF = "agent_handoff"
    ERROR = "error"


@dataclass
class SpaceEvent:
    """Event published to per-space stream."""
    event_type: str
    agent: str
    payload: Dict[str, Any]
    space_id: str = "global"
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for Redis storage."""
        return {
            "event_id": self.event_id,
            "space_id": self.space_id,
            "event_type": self.event_type,
            "agent": self.agent,
            "payload": json.dumps(self.payload),
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SpaceEvent":
        """Create from Redis data."""
        payload = data.get("payload", "{}")
        if isinstance(payload, str):
            payload = json.loads(payload)

        return cls(
            event_id=data.get("event_id", str(uuid.uuid4())),
            space_id=data.get("space_id", "global"),
            event_type=data.get("event_type", "unknown"),
            agent=data.get("agent", "unknown"),
            payload=payload,
            timestamp=datetime.fromisoformat(data.get("timestamp", datetime.now().isoformat())),
        )


@dataclass
class TaskStatus:
    """Status of a running task."""
    task_id: str
    status: str  # "pending", "running", "completed", "failed"
    agent: str
    space_id: str
    progress: float = 0.0
    message: str = ""
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    started_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


class InMemoryEventStore:
    """
    In-memory fallback when Redis is unavailable.

    Thread-safe using asyncio locks.
    """

    def __init__(self, max_events: int = MAX_STREAM_LENGTH):
        self._streams: Dict[str, List[SpaceEvent]] = {}
        self._tasks: Dict[str, TaskStatus] = {}
        self._max_events = max_events
        self._lock = asyncio.Lock()

    async def publish_event(self, space_id: str, event: SpaceEvent) -> str:
        """Publish event to space stream."""
        async with self._lock:
            if space_id not in self._streams:
                self._streams[space_id] = []

            self._streams[space_id].append(event)

            # Trim if over limit
            if len(self._streams[space_id]) > self._max_events:
                self._streams[space_id] = self._streams[space_id][-self._max_events:]

            logger.debug(f"Published event {event.event_type} to {space_id}")
            return event.event_id

    async def query_events(
        self,
        space_id: str,
        since: Optional[datetime] = None,
        event_types: Optional[List[str]] = None,
        limit: int = 50,
    ) -> List[SpaceEvent]:
        """Query events from a space stream."""
        async with self._lock:
            events = self._streams.get(space_id, [])

            # Filter by timestamp
            if since:
                events = [e for e in events if e.timestamp >= since]

            # Filter by event type
            if event_types:
                events = [e for e in events if e.event_type in event_types]

            # Return most recent
            return events[-limit:]

    async def update_task_status(self, task_id: str, status: TaskStatus):
        """Update task status."""
        async with self._lock:
            self._tasks[task_id] = status

    async def get_task_status(self, task_id: str) -> Optional[TaskStatus]:
        """Get task status by ID."""
        async with self._lock:
            return self._tasks.get(task_id)

    async def list_active_tasks(self, space_id: Optional[str] = None) -> List[TaskStatus]:
        """List all active tasks."""
        async with self._lock:
            tasks = list(self._tasks.values())
            if space_id:
                tasks = [t for t in tasks if t.space_id == space_id]
            return [t for t in tasks if t.status in ("pending", "running")]

    async def clear(self):
        """Clear all data (for testing)."""
        async with self._lock:
            self._streams.clear()
            self._tasks.clear()


class RedisEventManager:
    """
    Redis-based event stream manager.

    Uses Redis Streams for event storage with automatic fallback to in-memory.
    """

    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url or REDIS_URL
        self._redis = None
        self._fallback = InMemoryEventStore()
        self._using_fallback = False

    async def connect(self) -> bool:
        """
        Connect to Redis.

        Returns:
            bool: True if connected to Redis, False if using fallback
        """
        try:
            import redis.asyncio as aioredis

            self._redis = aioredis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )

            # Test connection
            await self._redis.ping()
            self._using_fallback = False
            logger.info(f"Connected to Redis: {self.redis_url}")
            return True

        except ImportError:
            logger.warning("redis package not installed, using in-memory fallback")
            self._using_fallback = True
            return False
        except Exception as e:
            logger.warning(f"Redis connection failed ({e}), using in-memory fallback")
            self._using_fallback = True
            return False

    async def disconnect(self):
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()
            self._redis = None

    @property
    def is_redis_connected(self) -> bool:
        """Check if using Redis (vs fallback)."""
        return not self._using_fallback and self._redis is not None

    async def publish_event(self, space_id: str, event: SpaceEvent) -> str:
        """
        Publish event to space-specific stream.

        Args:
            space_id: Space identifier
            event: Event to publish

        Returns:
            Event ID
        """
        event.space_id = space_id

        if self._using_fallback:
            return await self._fallback.publish_event(space_id, event)

        try:
            stream_key = f"{STREAM_PREFIX}{space_id}"
            event_data = event.to_dict()

            # XADD with automatic ID and max length
            await self._redis.xadd(
                stream_key,
                event_data,
                maxlen=MAX_STREAM_LENGTH,
            )

            logger.debug(f"Published to Redis stream {stream_key}: {event.event_type}")
            return event.event_id

        except Exception as e:
            logger.error(f"Redis publish failed: {e}, using fallback")
            return await self._fallback.publish_event(space_id, event)

    async def query_events(
        self,
        space_id: str,
        since: Optional[datetime] = None,
        event_types: Optional[List[str]] = None,
        limit: int = 50,
    ) -> List[SpaceEvent]:
        """
        Query events from a space stream.

        Args:
            space_id: Space identifier
            since: Only events after this timestamp
            event_types: Filter by event types
            limit: Maximum events to return

        Returns:
            List of SpaceEvent objects
        """
        if self._using_fallback:
            return await self._fallback.query_events(space_id, since, event_types, limit)

        try:
            stream_key = f"{STREAM_PREFIX}{space_id}"

            # XREVRANGE for most recent first
            # Use "-" for start (oldest) and "+" for end (newest)
            start_id = "-"
            if since:
                # Convert datetime to Redis stream ID format (timestamp in ms)
                start_id = str(int(since.timestamp() * 1000))

            entries = await self._redis.xrevrange(
                stream_key,
                max="+",
                min=start_id,
                count=limit,
            )

            events = []
            for entry_id, data in entries:
                event = SpaceEvent.from_dict(data)
                if event_types is None or event.event_type in event_types:
                    events.append(event)

            return events

        except Exception as e:
            logger.error(f"Redis query failed: {e}, using fallback")
            return await self._fallback.query_events(space_id, since, event_types, limit)

    async def get_latest_events(
        self,
        spaces: Optional[List[str]] = None,
        limit: int = 10,
    ) -> Dict[str, List[SpaceEvent]]:
        """
        Get latest events from multiple spaces.

        Args:
            spaces: List of space IDs (None = all)
            limit: Events per space

        Returns:
            Dict mapping space_id to event list
        """
        result = {}

        if spaces is None:
            # Get all known spaces
            if self._using_fallback:
                spaces = list(self._fallback._streams.keys())
            else:
                try:
                    keys = await self._redis.keys(f"{STREAM_PREFIX}*")
                    spaces = [k.replace(STREAM_PREFIX, "") for k in keys]
                except Exception:
                    spaces = []

        for space_id in spaces:
            events = await self.query_events(space_id, limit=limit)
            if events:
                result[space_id] = events

        return result

    async def get_task_status_summary(self) -> str:
        """
        Get human-readable summary of active tasks.

        Used by Voice Agent to report status.
        """
        all_events = await self.get_latest_events(limit=5)

        if not all_events:
            return "No recent activity."

        summary_parts = []
        for space_id, events in all_events.items():
            if events:
                latest = events[0]
                summary_parts.append(
                    f"In {space_id}: {latest.event_type} by {latest.agent}"
                )

        return " | ".join(summary_parts) if summary_parts else "No recent activity."

    async def update_task_status(self, task_id: str, status: TaskStatus):
        """Update task status (stored in fallback for now)."""
        await self._fallback.update_task_status(task_id, status)

    async def get_task_status(self, task_id: str) -> Optional[TaskStatus]:
        """Get task status by ID."""
        return await self._fallback.get_task_status(task_id)

    async def list_active_tasks(self, space_id: Optional[str] = None) -> List[TaskStatus]:
        """List all active tasks."""
        return await self._fallback.list_active_tasks(space_id)


# Global event manager instance
_event_manager: Optional[RedisEventManager] = None


async def get_event_manager() -> RedisEventManager:
    """
    Get or create the global event manager.

    Connects to Redis on first call.
    """
    global _event_manager

    if _event_manager is None:
        _event_manager = RedisEventManager()
        await _event_manager.connect()

    return _event_manager


def get_event_manager_sync() -> RedisEventManager:
    """
    Get event manager synchronously (for non-async contexts).

    Note: Must have been initialized via get_event_manager() first.
    """
    global _event_manager

    if _event_manager is None:
        _event_manager = RedisEventManager()
        # Can't connect here (async), will connect on first use

    return _event_manager


async def reset_event_manager():
    """Reset the global event manager (for testing)."""
    global _event_manager

    if _event_manager is not None:
        await _event_manager.disconnect()
        _event_manager = None


__all__ = [
    "EventType",
    "SpaceEvent",
    "TaskStatus",
    "RedisEventManager",
    "InMemoryEventStore",
    "get_event_manager",
    "get_event_manager_sync",
    "reset_event_manager",
    "STREAM_PREFIX",
    "GLOBAL_STREAM",
]
