"""
Event Bus - Redis Streams for VibeMind Swarm Communication

Handles event publishing and subscribing between:
- Rachel (Voice Agent) → Backend Swarm
- Backend Swarm → Rachel (Status Updates)
"""

import json
import uuid
import asyncio
import logging
import os
from dataclasses import dataclass, field
from typing import Callable, Dict, Any, Optional, List
from pathlib import Path
from datetime import datetime

# Load environment variables
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass

logger = logging.getLogger(__name__)


@dataclass
class SwarmEvent:
    """Event structure for Redis Streams."""
    stream: str           # "events:tasks", "events:status", "events:jobs"
    event_type: str       # "code.generate", "task.progress", etc.
    payload: Dict[str, Any]
    job_id: Optional[str] = None
    timestamp: float = field(default_factory=lambda: datetime.now().timestamp())

    def to_dict(self) -> Dict[str, str]:
        """Convert to Redis-compatible dict (all values as strings)."""
        return {
            "type": self.event_type,
            "payload": json.dumps(self.payload),
            "job_id": self.job_id or "",
            "timestamp": str(self.timestamp),
        }

    @classmethod
    def from_redis(cls, stream: str, data: Dict[bytes, bytes]) -> "SwarmEvent":
        """Create from Redis stream message."""
        return cls(
            stream=stream,
            event_type=data.get(b"type", b"").decode(),
            payload=json.loads(data.get(b"payload", b"{}").decode()),
            job_id=data.get(b"job_id", b"").decode() or None,
            timestamp=float(data.get(b"timestamp", b"0").decode() or 0),
        )


class EventBus:
    """
    Redis Streams Event Bus for VibeMind.

    Streams:
    - events:tasks - Rachel → Backend (task requests)
    - events:tasks:coding - Coding-specific tasks
    - events:tasks:desktop - Desktop automation tasks
    - events:tasks:ideas - Idea/bubble tasks
    - events:status - Backend → Rachel (status updates)
    - events:jobs - Job state tracking
    - events:reasoning - Execution reasoning for thinking panel
    """

    # Stream names
    STREAM_TASKS = "events:tasks"
    STREAM_TASKS_CODING = "events:tasks:coding"
    STREAM_TASKS_DESKTOP = "events:tasks:desktop"
    STREAM_TASKS_IDEAS = "events:tasks:ideas"
    STREAM_STATUS = "events:status"
    STREAM_JOBS = "events:jobs"
    STREAM_REASONING = "events:reasoning"

    @staticmethod
    def get_user_stream(base_stream: str, user_id: str = None) -> str:
        """
        Get stream name with optional user isolation prefix.

        For multi-user support, each user can have isolated streams:
        - Without user_id: "events:tasks:ideas"
        - With user_id: "events:user:alice:tasks:ideas"

        Args:
            base_stream: Base stream name (e.g., "events:tasks:ideas")
            user_id: Optional user identifier for isolation

        Returns:
            Stream name, optionally prefixed for user isolation
        """
        if not user_id:
            return base_stream

        # Insert user prefix after "events:"
        # events:tasks:ideas -> events:user:alice:tasks:ideas
        if base_stream.startswith("events:"):
            suffix = base_stream[7:]  # Remove "events:" prefix
            return f"events:user:{user_id}:{suffix}"

        # Fallback for non-standard stream names
        return f"events:user:{user_id}:{base_stream}"

    def __init__(self, redis_url: str = None):
        """
        Initialize Event Bus.

        Args:
            redis_url: Redis connection URL (default: from env or localhost)
        """
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379")
        self._redis = None
        self._redis_loop = None  # Track which event loop the connection belongs to
        self._subscriptions: Dict[str, List[Callable]] = {}
        self._listener_tasks: List[asyncio.Task] = []
        self._running = False
        self._reconnect_attempts = 0
        self._max_reconnect_attempts = 5

    async def _get_redis(self):
        """
        Get Redis connection, creating new one if needed.

        Handles event loop changes by recreating connection.
        Raises ConnectionError if Redis is not available.
        """
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = None

        # Check if we need to reset connection (event loop changed)
        # This is expected behavior when VoiceBridgeV2 runs in a separate thread
        if self._redis is not None and self._redis_loop != current_loop:
            logger.debug("[EventBus] Event loop changed, recreating Redis connection")
            # Just discard the reference and let Python garbage collect it
            # Don't call disconnect() - it's async and causes RuntimeWarning
            self._redis = None
            self._redis_loop = None

        if self._redis is None:
            try:
                import redis.asyncio as redis_async
                self._redis = redis_async.from_url(
                    self.redis_url,
                    decode_responses=False,  # We handle decoding ourselves
                    socket_connect_timeout=5.0,
                    socket_timeout=5.0,
                )
                # Test connection
                await self._redis.ping()
                self._redis_loop = current_loop
                self._reconnect_attempts = 0
                logger.info(f"EventBus connected to Redis: {self.redis_url}")
            except ImportError:
                logger.error("redis package not installed. Run: pip install redis[hiredis]")
                raise
            except Exception as e:
                logger.error(f"Redis connection failed: {e}")
                self._redis = None
                self._redis_loop = None
                raise ConnectionError(f"Redis unavailable: {e}") from e

        # Final safety check
        if self._redis is None:
            raise ConnectionError("Redis connection is None after initialization")

        return self._redis

    @property
    async def redis(self):
        """Lazy-load async Redis connection (backward compatible)."""
        return await self._get_redis()

    async def _reconnect(self) -> bool:
        """
        Attempt to reconnect to Redis.

        Returns:
            True if reconnection successful, False otherwise
        """
        if self._reconnect_attempts >= self._max_reconnect_attempts:
            logger.error(f"[EventBus] Max reconnection attempts ({self._max_reconnect_attempts}) reached")
            return False

        self._reconnect_attempts += 1
        logger.info(f"[EventBus] Reconnection attempt {self._reconnect_attempts}/{self._max_reconnect_attempts}")

        # Close existing connection (safely handle event loop issues)
        if self._redis:
            # Just discard the reference and let Python garbage collect it
            # Don't call disconnect() - it's async and causes RuntimeWarning
            self._redis = None
            self._redis_loop = None

        # Wait before retry (exponential backoff)
        await asyncio.sleep(min(2 ** self._reconnect_attempts, 30))

        try:
            await self._get_redis()
            return True
        except Exception as e:
            logger.error(f"[EventBus] Reconnection failed: {e}")
            return False

    async def publish(self, event: SwarmEvent) -> str:
        """
        Publish event to Redis stream with automatic retry on connection errors.

        Args:
            event: SwarmEvent to publish

        Returns:
            job_id (generated if not provided)

        Raises:
            ConnectionError: If Redis is unavailable after all retries
        """
        job_id = event.job_id or str(uuid.uuid4())
        event.job_id = job_id

        last_error = None
        for attempt in range(3):  # Try up to 3 times
            try:
                r = await self._get_redis()
                # Double-check r is not None (should never happen after _get_redis fix)
                if r is None:
                    raise ConnectionError("Redis connection is None")

                message_id = await r.xadd(
                    event.stream,
                    event.to_dict(),
                )
                logger.debug(f"Published to {event.stream}: {event.event_type} (job={job_id}, msg={message_id})")
                return job_id

            except ConnectionError as e:
                last_error = e
                logger.warning(f"[EventBus] Connection error on publish (attempt {attempt + 1}/3): {e}")
                if attempt < 2:
                    # Reset and retry
                    self._redis = None
                    self._redis_loop = None
                    await asyncio.sleep(0.5 * (attempt + 1))
                    continue
                break

            except Exception as e:
                last_error = e
                error_str = str(e).lower()

                # Check for event loop errors - need to reset connection
                if "event loop" in error_str or "closed" in error_str:
                    logger.warning(f"[EventBus] Event loop error on publish, resetting connection: {e}")
                    self._redis = None
                    self._redis_loop = None
                    if attempt < 2:
                        await asyncio.sleep(0.1 * (attempt + 1))
                        continue

                # Check for connection errors - try reconnect
                if "connection" in error_str or "timeout" in error_str or "unavailable" in error_str:
                    logger.warning(f"[EventBus] Connection error on publish (attempt {attempt + 1}/3): {e}")
                    self._redis = None
                    self._redis_loop = None
                    if attempt < 2:
                        await asyncio.sleep(0.5 * (attempt + 1))
                        continue

                logger.error(f"[EventBus] Failed to publish event: {e}")
                break

        raise last_error if last_error else ConnectionError("Failed to publish event after retries")

    async def subscribe(self, stream: str, handler: Callable[[SwarmEvent], Any]):
        """
        Subscribe to a stream with an async handler.

        Args:
            stream: Stream name to subscribe to
            handler: Async function to handle events
        """
        if stream not in self._subscriptions:
            self._subscriptions[stream] = []
        self._subscriptions[stream].append(handler)
        logger.info(f"Subscribed to stream: {stream}")

    async def start_listeners(self):
        """Start all stream listeners."""
        if self._running:
            return

        self._running = True

        for stream in self._subscriptions:
            task = asyncio.create_task(self._listen_stream(stream))
            self._listener_tasks.append(task)
            logger.info(f"Started listener for: {stream}")

    async def stop_listeners(self):
        """Stop all stream listeners."""
        self._running = False

        for task in self._listener_tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        self._listener_tasks.clear()
        logger.info("All listeners stopped")

    async def _listen_stream(self, stream: str):
        """
        Internal listener for a stream.

        Uses XREAD with blocking to efficiently wait for new messages.
        Handles connection errors and event loop changes automatically.
        """
        last_id = "$"  # Start from new messages only
        consecutive_errors = 0
        max_consecutive_errors = 10

        while self._running:
            try:
                r = await self._get_redis()

                # Block for 1 second, then check if still running
                messages = await r.xread(
                    {stream: last_id},
                    block=1000,
                    count=10,
                )

                consecutive_errors = 0  # Reset on success

                if not messages:
                    continue

                for stream_name, stream_messages in messages:
                    stream_name = stream_name.decode() if isinstance(stream_name, bytes) else stream_name

                    for msg_id, data in stream_messages:
                        last_id = msg_id.decode() if isinstance(msg_id, bytes) else msg_id

                        try:
                            event = SwarmEvent.from_redis(stream_name, data)

                            # Call all handlers for this stream
                            handlers = self._subscriptions.get(stream, [])
                            for handler in handlers:
                                try:
                                    result = handler(event)
                                    if asyncio.iscoroutine(result):
                                        await result
                                except Exception as e:
                                    logger.error(f"Handler error for {stream}: {e}")

                        except Exception as e:
                            logger.error(f"Failed to parse event: {e}")

            except asyncio.CancelledError:
                break
            except ConnectionError as e:
                # Redis connection unavailable - wait and retry
                consecutive_errors += 1
                if consecutive_errors == 1:
                    logger.warning(f"[EventBus] Redis unavailable for {stream}, will retry...")
                if consecutive_errors >= max_consecutive_errors:
                    logger.error(f"[EventBus] Redis unavailable after {consecutive_errors} attempts, stopping listener for {stream}")
                    break
                await asyncio.sleep(min(2 ** consecutive_errors, 30))
            except OSError as e:
                # Windows-specific: WinError 995 during shutdown
                error_str = str(e)
                if "995" in error_str or "abgebrochen" in error_str.lower() or "aborted" in error_str.lower():
                    logger.info(f"[EventBus] Listener for {stream} stopped (shutdown)")
                    break
                # Other OSError - continue with normal error handling
                consecutive_errors += 1
                logger.error(f"[EventBus] OSError in listener for {stream}: {e}")
                if consecutive_errors >= max_consecutive_errors:
                    break
                await asyncio.sleep(min(2 ** consecutive_errors, 30))
            except Exception as e:
                error_str = str(e).lower()
                consecutive_errors += 1

                # Check for event loop errors - need to reset connection
                if "event loop" in error_str or "closed" in error_str:
                    logger.warning(f"[EventBus] Event loop error in listener, resetting connection: {e}")
                    self._redis = None
                    self._redis_loop = None
                    await asyncio.sleep(0.5)
                    continue

                logger.error(f"Listener error for {stream}: {e}")

                if consecutive_errors >= max_consecutive_errors:
                    logger.error(f"[EventBus] Too many consecutive errors ({consecutive_errors}), stopping listener for {stream}")
                    break

                # Exponential backoff
                await asyncio.sleep(min(2 ** consecutive_errors, 30))

    async def get_stream_info(self, stream: str) -> Dict:
        """Get information about a stream."""
        try:
            r = await self._get_redis()
            info = await r.xinfo_stream(stream)
            return {
                "length": info.get(b"length", 0),
                "first_entry": info.get(b"first-entry"),
                "last_entry": info.get(b"last-entry"),
            }
        except Exception:
            return {"length": 0, "first_entry": None, "last_entry": None}

    async def close(self):
        """Close Redis connection."""
        await self.stop_listeners()
        if self._redis:
            # Just discard the reference and let Python garbage collect it
            # Don't call disconnect() - it's async and causes RuntimeWarning
            self._redis = None
            self._redis_loop = None
            logger.info("EventBus closed")


# Singleton instance
_event_bus: Optional[EventBus] = None


def get_event_bus(redis_url: str = None) -> EventBus:
    """Get or create EventBus singleton."""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus(redis_url)
    return _event_bus


async def reset_event_bus():
    """Reset the singleton (for testing or on event loop change)."""
    global _event_bus
    if _event_bus:
        try:
            await _event_bus.close()
        except Exception as e:
            logger.debug(f"[EventBus] Error during reset: {e}")
        _event_bus = None


def force_reset_event_bus():
    """Force reset the singleton synchronously (use when event loop is closed)."""
    global _event_bus
    if _event_bus:
        _event_bus._redis = None
        _event_bus._redis_loop = None
        _event_bus._running = False
        _event_bus._listener_tasks.clear()
    _event_bus = None
    logger.info("[EventBus] Force reset complete")


def get_user_stream(base_stream: str, user_id: str = None) -> str:
    """
    Module-level helper to get user-isolated stream name.

    Convenience function that delegates to EventBus.get_user_stream().

    Args:
        base_stream: Base stream name (e.g., "events:tasks:ideas")
        user_id: Optional user identifier for isolation

    Returns:
        Stream name, optionally prefixed for user isolation
    """
    return EventBus.get_user_stream(base_stream, user_id)


__all__ = [
    "EventBus",
    "SwarmEvent",
    "get_event_bus",
    "reset_event_bus",
    "force_reset_event_bus",
    "get_user_stream",
]
