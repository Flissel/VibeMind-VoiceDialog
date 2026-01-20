"""
Context Inspector for Agent Simulation.

Inspects Rachel's context sources during simulation:
- NotificationQueue (immediate task results, 5-min timeout)
- SystemContextStore (10-min window of recent actions)
- ConversationMemory (long-term SQLite history)
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


@dataclass
class ContextSnapshot:
    """Snapshot of all context sources at a point in time."""
    timestamp: float
    notification_count: int
    notification_content: List[str] = field(default_factory=list)
    system_context_count: int = 0
    system_context_entries: List[Dict[str, Any]] = field(default_factory=list)
    has_conversation_memory: bool = False
    conversation_memory_count: int = 0
    current_bubble: Optional[str] = None
    current_space: Optional[str] = None


class ContextInspector:
    """Inspects Rachel's context sources during simulation."""

    def __init__(self):
        self._notification_queue = None
        self._system_context_store = None
        self._conversation_memory = None
        self._bubble_tools = None
        self._initialized = False

    def _initialize(self):
        """Lazy initialization of context sources."""
        if self._initialized:
            return

        # NotificationQueue
        try:
            from swarm.orchestrator import get_notification_queue
            self._notification_queue = get_notification_queue()
            logger.debug("ContextInspector: NotificationQueue initialized")
        except Exception as e:
            logger.warning(f"ContextInspector: NotificationQueue unavailable: {e}")

        # SystemContextStore
        try:
            from swarm.orchestrator.system_context_store import get_system_context_store
            self._system_context_store = get_system_context_store()
            logger.debug("ContextInspector: SystemContextStore initialized")
        except Exception as e:
            logger.warning(f"ContextInspector: SystemContextStore unavailable: {e}")

        # ConversationMemory
        try:
            from swarm.executive.conversation_memory import ConversationMemory
            from data.database import get_database
            self._conversation_memory = ConversationMemory(get_database())
            logger.debug("ContextInspector: ConversationMemory initialized")
        except Exception as e:
            logger.warning(f"ContextInspector: ConversationMemory unavailable: {e}")

        # Bubble tools for current state
        try:
            from tools import bubble_tools
            self._bubble_tools = bubble_tools
            logger.debug("ContextInspector: bubble_tools initialized")
        except Exception as e:
            logger.warning(f"ContextInspector: bubble_tools unavailable: {e}")

        self._initialized = True

    def snapshot(self) -> ContextSnapshot:
        """Capture current state of all context sources."""
        self._initialize()

        snapshot = ContextSnapshot(timestamp=time.time(), notification_count=0)

        # NotificationQueue
        if self._notification_queue:
            try:
                # Access internal pending list (read-only, don't clear)
                if hasattr(self._notification_queue, '_pending'):
                    pending = list(self._notification_queue._pending)
                    snapshot.notification_count = len(pending)
                    snapshot.notification_content = [
                        f"{n.event_type}: {str(n.result)[:50]}"
                        for n in pending[:5]  # Limit to 5
                    ]
            except Exception as e:
                logger.debug(f"NotificationQueue snapshot error: {e}")

        # SystemContextStore
        if self._system_context_store:
            try:
                if hasattr(self._system_context_store, '_entries'):
                    events = list(self._system_context_store._entries)
                    snapshot.system_context_count = len(events)
                    snapshot.system_context_entries = [
                        {
                            "event_type": e.event_type,
                            "result": str(e.result)[:50] if e.result else "",
                            "age_seconds": time.time() - e.timestamp
                        }
                        for e in events[:5]
                    ]
            except Exception as e:
                logger.debug(f"SystemContextStore snapshot error: {e}")

        # ConversationMemory
        if self._conversation_memory:
            snapshot.has_conversation_memory = True
            try:
                # Try to get count from DB
                if hasattr(self._conversation_memory, 'db'):
                    rows = self._conversation_memory.db.fetch_all(
                        "SELECT COUNT(*) as count FROM conversation_memory"
                    )
                    if rows:
                        snapshot.conversation_memory_count = rows[0]['count']
            except Exception as e:
                logger.debug(f"ConversationMemory snapshot error: {e}")

        # Current bubble/space state
        if self._bubble_tools:
            try:
                if hasattr(self._bubble_tools, '_current_bubble_db_id'):
                    bubble_id = self._bubble_tools._current_bubble_db_id
                    if bubble_id:
                        # Try to get bubble name
                        from data.repository import IdeaRepository
                        from data.database import get_database
                        repo = IdeaRepository(get_database())
                        bubble = repo.get_by_id(bubble_id)
                        if bubble:
                            snapshot.current_bubble = bubble.title
            except Exception as e:
                logger.debug(f"Current bubble snapshot error: {e}")

        return snapshot

    def check_context_contains(self, query: str) -> Dict[str, bool]:
        """
        Check if any context source contains relevant info.

        Args:
            query: Text to search for in context sources

        Returns:
            Dict with source names and whether they contain the query
        """
        self._initialize()
        results = {
            "notification_queue": False,
            "system_context": False,
            "conversation_memory": False,
        }

        query_lower = query.lower()

        # Check NotificationQueue
        if self._notification_queue:
            try:
                if hasattr(self._notification_queue, '_pending'):
                    for n in self._notification_queue._pending:
                        if query_lower in str(n.result).lower():
                            results["notification_queue"] = True
                            break
                        if query_lower in n.event_type.lower():
                            results["notification_queue"] = True
                            break
            except Exception:
                pass

        # Check SystemContextStore
        if self._system_context_store:
            try:
                relevant = self._system_context_store.get_relevant(query, limit=5)
                results["system_context"] = len(relevant) > 0
            except Exception:
                pass

        # Check ConversationMemory (simplified - just check if it has entries)
        if self._conversation_memory:
            try:
                if hasattr(self._conversation_memory, 'db'):
                    rows = self._conversation_memory.db.fetch_all(
                        "SELECT user_input FROM conversation_memory ORDER BY timestamp DESC LIMIT 10"
                    )
                    for row in rows:
                        if query_lower in row['user_input'].lower():
                            results["conversation_memory"] = True
                            break
            except Exception:
                pass

        return results

    def check_current_bubble(self, expected_name: str) -> bool:
        """
        Check if the current bubble matches expected name.

        Args:
            expected_name: Expected bubble name (fuzzy match)

        Returns:
            True if current bubble matches
        """
        self._initialize()

        if not self._bubble_tools:
            return False

        try:
            if hasattr(self._bubble_tools, '_current_bubble_db_id'):
                bubble_id = self._bubble_tools._current_bubble_db_id
                if not bubble_id:
                    return False

                from data.repository import IdeaRepository
                from data.database import get_database
                repo = IdeaRepository(get_database())
                bubble = repo.get_by_id(bubble_id)

                if bubble and bubble.title:
                    # Fuzzy match
                    expected_lower = expected_name.lower()
                    actual_lower = bubble.title.lower()
                    return (
                        expected_lower in actual_lower or
                        actual_lower in expected_lower
                    )
        except Exception as e:
            logger.debug(f"check_current_bubble error: {e}")

        return False

    def get_recent_actions(self, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Get recent actions from SystemContextStore.

        Args:
            limit: Maximum number of actions to return

        Returns:
            List of action dictionaries
        """
        self._initialize()

        if not self._system_context_store:
            return []

        try:
            if hasattr(self._system_context_store, '_entries'):
                events = list(self._system_context_store._entries)[:limit]
                return [
                    {
                        "event_type": e.event_type,
                        "result": str(e.result)[:100] if e.result else "",
                        "timestamp": e.timestamp,
                        "age_seconds": time.time() - e.timestamp
                    }
                    for e in events
                ]
        except Exception as e:
            logger.debug(f"get_recent_actions error: {e}")

        return []

    def get_pending_notifications(self) -> List[Dict[str, Any]]:
        """
        Get pending notifications (without clearing them).

        Returns:
            List of notification dictionaries
        """
        self._initialize()

        if not self._notification_queue:
            return []

        try:
            if hasattr(self._notification_queue, '_pending'):
                return [
                    {
                        "event_type": n.event_type,
                        "result": str(n.result)[:100] if n.result else "",
                        "job_id": n.job_id if hasattr(n, 'job_id') else None,
                    }
                    for n in self._notification_queue._pending
                ]
        except Exception as e:
            logger.debug(f"get_pending_notifications error: {e}")

        return []


__all__ = [
    "ContextInspector",
    "ContextSnapshot",
]
