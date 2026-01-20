"""
Real-time state tracking for Rachel's system awareness.

This module provides a singleton store that tracks:
- Current location (space/bubble)
- Active and completed tasks
- Last intent classification results

Rachel uses this context to provide informed responses about
what's happening in the system.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, List, Any

logger = logging.getLogger(__name__)


@dataclass
class SystemState:
    """Current system state for Rachel's context."""

    # Location tracking
    current_space: Optional[str] = None
    current_bubble: Optional[str] = None

    # Task tracking
    active_tasks: List[Dict[str, Any]] = field(default_factory=list)
    recent_completions: List[Dict[str, Any]] = field(default_factory=list)
    pending_notifications: int = 0

    # Intent tracking
    last_intent_confidence: float = 0.0
    last_intent_type: Optional[str] = None
    last_intent_text: Optional[str] = None


class RealTimeStateStore:
    """
    Singleton store for real-time system state.

    This store is updated by:
    - IntentOrchestrator: after intent classification
    - BubbleTools: after location changes (bubble.enter)
    - StatusListener: when tasks complete/fail

    Rachel reads this store to build context about the current
    system state for her responses.
    """

    MAX_RECENT_COMPLETIONS = 5
    MAX_ACTIVE_TASKS = 10

    def __init__(self):
        self._state = SystemState()
        logger.debug("[RealTimeState] Initialized")

    @property
    def state(self) -> SystemState:
        """Get current state (read-only access)."""
        return self._state

    def update_location(self, space: str, bubble: Optional[str] = None):
        """
        Update current location.

        Called after bubble.enter or space navigation.

        Args:
            space: Name of the current space
            bubble: Name of the current bubble within space (optional)
        """
        self._state.current_space = space
        self._state.current_bubble = bubble
        logger.debug(f"[RealTimeState] Location: {space}" +
                    (f"/{bubble}" if bubble else ""))

    def clear_location(self):
        """Clear location (e.g., when exiting a space)."""
        self._state.current_space = None
        self._state.current_bubble = None
        logger.debug("[RealTimeState] Location cleared")

    def update_intent_result(
        self,
        intent_type: str,
        confidence: float,
        original_text: Optional[str] = None
    ):
        """
        Store last intent classification result.

        Called by IntentOrchestrator after classification.

        Args:
            intent_type: The classified intent (e.g., "idea.create")
            confidence: Confidence score (0.0 - 1.0)
            original_text: The original user input
        """
        self._state.last_intent_type = intent_type
        self._state.last_intent_confidence = confidence
        self._state.last_intent_text = original_text
        logger.debug(f"[RealTimeState] Intent: {intent_type} ({confidence:.0%})")

    def add_active_task(self, task_id: str, intent_type: str, params: Optional[Dict] = None):
        """
        Track a new active task.

        Called when a task is queued for execution.

        Args:
            task_id: Unique task/job ID
            intent_type: The intent being executed
            params: Task parameters (optional)
        """
        task = {
            "id": task_id,
            "intent": intent_type,
            "params": params or {},
            "started": datetime.utcnow().isoformat()
        }
        self._state.active_tasks.append(task)

        # Keep list bounded
        if len(self._state.active_tasks) > self.MAX_ACTIVE_TASKS:
            self._state.active_tasks = self._state.active_tasks[-self.MAX_ACTIVE_TASKS:]

        logger.debug(f"[RealTimeState] Task started: {intent_type} ({task_id[:8]}...)")

    def complete_task(self, task_id: str, result: str, success: bool = True):
        """
        Move task from active to completed.

        Called by StatusListener when task completes.

        Args:
            task_id: The task ID
            result: Result message (truncated for storage)
            success: Whether the task succeeded
        """
        # Remove from active
        intent_type = "unknown"
        for task in self._state.active_tasks:
            if task["id"] == task_id:
                intent_type = task.get("intent", "unknown")
                break

        self._state.active_tasks = [
            t for t in self._state.active_tasks if t["id"] != task_id
        ]

        # Add to completed
        completion = {
            "id": task_id,
            "intent": intent_type,
            "result": result[:200] if result else "",  # Truncate long results
            "success": success,
            "completed": datetime.utcnow().isoformat()
        }
        self._state.recent_completions.append(completion)

        # Keep list bounded
        if len(self._state.recent_completions) > self.MAX_RECENT_COMPLETIONS:
            self._state.recent_completions = self._state.recent_completions[-self.MAX_RECENT_COMPLETIONS:]

        status = "completed" if success else "failed"
        logger.debug(f"[RealTimeState] Task {status}: {intent_type}")

    def update_notification_count(self, count: int):
        """Update pending notification count."""
        self._state.pending_notifications = count

    def get_rachel_context(self) -> str:
        """
        Format state for Rachel's system prompt.

        Returns a human-readable string that Rachel can use
        to understand the current system state.

        Returns:
            Formatted context string
        """
        lines = ["[SYSTEM STATE]"]

        # Location
        if self._state.current_space:
            loc = f"Aktueller Space: {self._state.current_space}"
            if self._state.current_bubble:
                loc += f" / Bubble: {self._state.current_bubble}"
            lines.append(loc)
        else:
            lines.append("Position: Hauptübersicht (kein Space aktiv)")

        # Active tasks
        if self._state.active_tasks:
            lines.append(f"Laufende Tasks: {len(self._state.active_tasks)}")
            for task in self._state.active_tasks[:3]:
                lines.append(f"  - {task['intent']} (läuft)")
            if len(self._state.active_tasks) > 3:
                lines.append(f"  ... und {len(self._state.active_tasks) - 3} weitere")

        # Recent completions
        if self._state.recent_completions:
            lines.append("Letzte Ergebnisse:")
            for comp in self._state.recent_completions[-3:]:
                status = "✓" if comp.get("success", True) else "✗"
                result_preview = comp.get("result", "")[:60]
                if result_preview:
                    lines.append(f"  {status} {comp['intent']}: {result_preview}")
                else:
                    lines.append(f"  {status} {comp['intent']}")

        # Last intent (with confidence warning if low)
        if self._state.last_intent_type:
            conf = self._state.last_intent_confidence
            conf_str = f"{conf:.0%}"
            if conf < 0.5:
                conf_str += " (unsicher!)"
            lines.append(f"Letzter Intent: {self._state.last_intent_type} ({conf_str})")

        # Pending notifications
        if self._state.pending_notifications > 0:
            lines.append(f"Wartende Benachrichtigungen: {self._state.pending_notifications}")

        return "\n".join(lines)

    def get_active_task_count(self) -> int:
        """Get number of active tasks."""
        return len(self._state.active_tasks)

    def get_active_task_ids(self) -> List[str]:
        """Get list of active task IDs."""
        return [t["id"] for t in self._state.active_tasks]

    def clear(self):
        """Clear all state (for testing or reset)."""
        self._state = SystemState()
        logger.debug("[RealTimeState] State cleared")


# Singleton instance
_store: Optional[RealTimeStateStore] = None


def get_real_time_state() -> RealTimeStateStore:
    """
    Get or create RealTimeStateStore singleton.

    Returns:
        The singleton RealTimeStateStore instance
    """
    global _store
    if _store is None:
        _store = RealTimeStateStore()
        logger.info("[RealTimeState] Service initialized")
    return _store


def reset_real_time_state():
    """Reset singleton (for testing)."""
    global _store
    if _store is not None:
        _store.clear()
    _store = None
