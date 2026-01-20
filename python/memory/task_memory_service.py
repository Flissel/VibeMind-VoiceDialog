"""
System-wide Task Memory Service using Supermemory.

Tracks all task events with timestamps for:
- Time-based queries ("What did I do today?")
- Cross-session context
- Task analytics
"""

import os
import logging
import time
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class TaskEvent:
    """Represents a task execution event."""
    task_id: str
    event_type: str  # "created", "started", "completed", "failed", "cancelled"
    intent_type: str  # "idea.create", "bubble.delete", etc.
    timestamp: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)
    result: Optional[str] = None
    duration_ms: Optional[int] = None


class TaskMemoryService:
    """
    Async service for storing and retrieving task events from Supermemory.

    Container Tags:
    - vibemind-tasks: All task events
    - vibemind-tasks-{date}: Daily partitions
    - vibemind-session-{id}: Session-specific tasks
    """

    CONTAINER_TAG = "vibemind-tasks"

    def __init__(self):
        # Check if feature is enabled before initializing
        use_feature = os.getenv("USE_TASK_MEMORY", "false").lower() == "true"

        self._client = None
        self._available = False

        if not use_feature:
            logger.debug("[TaskMemoryService] Disabled via USE_TASK_MEMORY=false")
            return

        api_key = os.getenv("SUPERMEMORY_API_KEY")
        if not api_key:
            logger.warning("[TaskMemoryService] USE_TASK_MEMORY=true but SUPERMEMORY_API_KEY not set")
            return

        # Lazy import to avoid startup delay
        try:
            from supermemory import AsyncSupermemory
            self._client = AsyncSupermemory(api_key=api_key)
            self._available = True
            logger.info("[TaskMemoryService] Initialized with Supermemory SDK")
        except ImportError:
            logger.warning("[TaskMemoryService] USE_TASK_MEMORY=true but supermemory package not installed")

    @property
    def is_available(self) -> bool:
        """Check if service is available."""
        return self._available and self._client is not None

    async def store_task_created(
        self,
        task_id: str,
        intent_type: str,
        payload: Dict[str, Any],
        session_id: Optional[str] = None
    ) -> Optional[str]:
        """Store task creation event."""
        if not self.is_available:
            return None

        now = datetime.utcnow()
        title = payload.get("title", payload.get("name", task_id))
        content = f"Task created: {intent_type} - {title}"

        try:
            response = await self._client.documents.create(
                content=content,
                container_tag=self.CONTAINER_TAG,
                custom_id=f"task_{task_id}_created",
                metadata={
                    "event_type": "task_created",
                    "task_id": task_id,
                    "intent_type": intent_type,
                    "payload": payload,
                    "timestamp": now.isoformat(),
                    "date": now.strftime("%Y-%m-%d"),
                    "session_id": session_id,
                }
            )
            logger.debug(f"[TaskMemory] Stored task_created: {task_id}")
            return getattr(response, 'id', str(response))
        except Exception as e:
            logger.warning(f"[TaskMemory] Failed to store task_created: {e}")
            return None

    async def store_task_completed(
        self,
        task_id: str,
        intent_type: str,
        result: str,
        duration_ms: int,
        session_id: Optional[str] = None
    ) -> Optional[str]:
        """Store task completion event."""
        if not self.is_available:
            return None

        now = datetime.utcnow()
        result_preview = result[:200] if result else "OK"
        content = f"Task completed: {intent_type} in {duration_ms}ms - Result: {result_preview}"

        try:
            response = await self._client.documents.create(
                content=content,
                container_tag=self.CONTAINER_TAG,
                custom_id=f"task_{task_id}_completed",
                metadata={
                    "event_type": "task_completed",
                    "task_id": task_id,
                    "intent_type": intent_type,
                    "result": result[:1000] if result else None,  # Truncate long results
                    "duration_ms": duration_ms,
                    "timestamp": now.isoformat(),
                    "date": now.strftime("%Y-%m-%d"),
                    "session_id": session_id,
                }
            )
            logger.debug(f"[TaskMemory] Stored task_completed: {task_id} ({duration_ms}ms)")
            return getattr(response, 'id', str(response))
        except Exception as e:
            logger.warning(f"[TaskMemory] Failed to store task_completed: {e}")
            return None

    async def store_task_failed(
        self,
        task_id: str,
        intent_type: str,
        error: str,
        session_id: Optional[str] = None
    ) -> Optional[str]:
        """Store task failure event."""
        if not self.is_available:
            return None

        now = datetime.utcnow()
        content = f"Task failed: {intent_type} - Error: {error}"

        try:
            response = await self._client.documents.create(
                content=content,
                container_tag=self.CONTAINER_TAG,
                custom_id=f"task_{task_id}_failed",
                metadata={
                    "event_type": "task_failed",
                    "task_id": task_id,
                    "intent_type": intent_type,
                    "error": error,
                    "timestamp": now.isoformat(),
                    "date": now.strftime("%Y-%m-%d"),
                    "session_id": session_id,
                }
            )
            logger.debug(f"[TaskMemory] Stored task_failed: {task_id}")
            return getattr(response, 'id', str(response))
        except Exception as e:
            logger.warning(f"[TaskMemory] Failed to store task_failed: {e}")
            return None

    async def search_tasks(
        self,
        query: str,
        days_back: int = 7,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Search tasks by semantic query."""
        if not self.is_available:
            return []

        try:
            response = await self._client.search.documents(
                q=query,
                container_tags=[self.CONTAINER_TAG],
                top_k=limit
            )
            results = []
            for r in getattr(response, 'results', []):
                results.append(r.to_dict() if hasattr(r, 'to_dict') else dict(r))
            return results
        except Exception as e:
            logger.warning(f"[TaskMemory] Search failed: {e}")
            return []

    async def get_tasks_today(self) -> List[Dict[str, Any]]:
        """Get all tasks from today."""
        today = datetime.utcnow().strftime("%Y-%m-%d")
        return await self.search_tasks(f"tasks from {today}")

    async def get_recent_tasks(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get most recent tasks."""
        return await self.search_tasks("recent task completed", limit=limit)

    async def get_task_timeline(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> List[Dict[str, Any]]:
        """Get task timeline for date range."""
        query = f"tasks from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"
        return await self.search_tasks(query, limit=100)

    async def delete_session_tasks(self, session_id: str) -> bool:
        """Delete all tasks for a session (reset)."""
        if not self.is_available:
            return False

        try:
            # Note: bulk_delete may not be available in all SDK versions
            # Fallback to individual deletion if needed
            await self._client.documents.bulk_delete(
                container_tags=[f"vibemind-session-{session_id}"]
            )
            logger.info(f"[TaskMemory] Deleted tasks for session: {session_id}")
            return True
        except Exception as e:
            logger.warning(f"[TaskMemory] Failed to delete session tasks: {e}")
            return False


# Singleton instance
_service: Optional[TaskMemoryService] = None


def get_task_memory_service() -> Optional[TaskMemoryService]:
    """Get or create TaskMemoryService singleton."""
    global _service

    # Check if feature is enabled
    if os.getenv("USE_TASK_MEMORY", "true").lower() != "true":
        return None

    if _service is None:
        try:
            _service = TaskMemoryService()
        except Exception as e:
            logger.warning(f"[TaskMemory] Could not initialize: {e}")
            return None
    return _service


def reset_task_memory_service():
    """Reset singleton (for testing)."""
    global _service
    _service = None
