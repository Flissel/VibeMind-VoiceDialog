"""
SystemContextStore - Short-term knowledge store for Rachel.

Stores completed task results with semantic tags.
Returns relevant context based on user's current request.

This enables "Smart Rachel" - she knows about recent system events
but only uses that knowledge when it's relevant to the user's question.
"""

import time
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ContextEntry:
    """A single context entry in the store."""
    event_type: str
    result: str
    timestamp: float = field(default_factory=time.time)
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def payload(self) -> Dict[str, Any]:
        """
        Get the tool arguments/payload from metadata.

        Phase 8B: Added for compatibility with Rule 21 context lookup.
        Returns tool_args stored in metadata during tool execution.
        """
        return self.metadata.get("tool_args", {})


class SystemContextStore:
    """
    Short-term knowledge store for Rachel.

    Stores completed task results with semantic tags.
    Returns relevant context based on user's current request.

    Example:
        store = SystemContextStore()
        store.store("bubble.create", "Space Alpha wurde erstellt")

        # Later, when user asks about spaces:
        relevant = store.get_relevant("Welche Spaces habe ich?")
        # Returns the recent bubble.create entry
    """

    def __init__(self, max_entries: int = 50, max_age_seconds: int = 600):
        """
        Initialize the context store.

        Args:
            max_entries: Maximum number of entries to keep
            max_age_seconds: Auto-expire entries older than this (default 10 min)
        """
        self._entries: List[ContextEntry] = []
        self._max_entries = max_entries
        self._max_age = max_age_seconds

    def store(self,
              event_type: str,
              result: str,
              tags: Optional[List[str]] = None,
              metadata: Optional[Dict[str, Any]] = None) -> ContextEntry:
        """
        Store a completed task result.

        Args:
            event_type: The event type (e.g., "bubble.create", "idea.list")
            result: The result string (what Rachel would say)
            tags: Optional custom tags for relevance matching
            metadata: Optional additional metadata

        Returns:
            The created ContextEntry
        """
        self._cleanup()

        entry = ContextEntry(
            event_type=event_type,
            result=result,
            tags=tags or self._auto_tags(event_type),
            metadata=metadata or {}
        )

        self._entries.append(entry)
        logger.debug(f"Stored context: {event_type} -> {result[:50]}...")

        # Trim if too many entries
        if len(self._entries) > self._max_entries:
            self._entries = self._entries[-self._max_entries:]

        return entry

    def get_relevant(self, user_request: str, limit: int = 3) -> List[ContextEntry]:
        """
        Get context entries relevant to the user's request.

        Args:
            user_request: The user's natural language request
            limit: Maximum number of entries to return

        Returns:
            List of relevant ContextEntry objects, sorted by relevance
        """
        logger.debug("get_relevant called: request=%s, limit=%s", user_request[:60], limit)
        self._cleanup()

        if not self._entries:
            return []

        # Simple keyword-based relevance
        request_lower = user_request.lower()
        scored = []

        for entry in self._entries:
            score = self._relevance_score(entry, request_lower)
            if score > 0:
                scored.append((score, entry))

        # Sort by score (highest first), then by recency
        scored.sort(key=lambda x: (-x[0], -x[1].timestamp))

        return [entry for _, entry in scored[:limit]]

    def get_recent(self, limit: int = 5) -> List[ContextEntry]:
        """
        Get most recent entries (for 'was hast du gemacht?' queries).

        Args:
            limit: Maximum number of entries to return

        Returns:
            List of recent ContextEntry objects (newest first)
        """
        self._cleanup()
        return list(reversed(self._entries[-limit:]))

    def get_recent_events(self, event_type: str, limit: int = 5) -> List[ContextEntry]:
        """
        Get recent entries filtered by event type.

        Phase 8B: Added for Rule 21 context-sensitive command handling.
        Enables looking up recent bubble.create events for "Geh rein" commands.

        Args:
            event_type: Filter by this event type (e.g., "bubble.create")
            limit: Maximum number of entries to return

        Returns:
            List of matching ContextEntry objects (newest first)
        """
        self._cleanup()
        matching = [e for e in self._entries if e.event_type == event_type]
        return list(reversed(matching[-limit:]))

    def _relevance_score(self, entry: ContextEntry, request_lower: str) -> float:
        """
        Calculate relevance score for an entry.

        Higher scores = more relevant to the user's request.
        """
        score = 0.0

        # Check tags
        for tag in entry.tags:
            if tag in request_lower:
                score += 2.0

        # Check event type keywords
        event_parts = entry.event_type.split(".")
        for part in event_parts:
            if part in request_lower:
                score += 1.5

        # Check result content
        result_lower = entry.result.lower()
        request_words = request_lower.split()
        for word in request_words:
            if len(word) > 3 and word in result_lower:
                score += 0.5

        # Recency bonus (newer = higher)
        age = time.time() - entry.timestamp
        if age < 60:
            score += 1.0
        elif age < 300:
            score += 0.5

        # Special queries that want ALL context
        status_keywords = [
            "was hast du", "was ist passiert", "status", "uebersicht",
            "was habe ich", "zusammenfassung", "was war", "gemacht"
        ]
        if any(kw in request_lower for kw in status_keywords):
            score += 1.0

        return score

    def _auto_tags(self, event_type: str) -> List[str]:
        """Generate tags from event type for relevance matching."""
        tags = []

        if event_type.startswith("bubble."):
            tags.extend(["space", "bubble", "spaces", "raum"])
        elif event_type.startswith("idea."):
            tags.extend(["idee", "ideen", "notiz", "note"])
        elif event_type.startswith("code."):
            tags.extend(["code", "projekt", "app", "generierung", "programmieren"])
        elif event_type.startswith("desktop."):
            tags.extend(["desktop", "app", "fenster", "programm"])

        return tags

    def _cleanup(self):
        """Remove expired entries."""
        now = time.time()
        self._entries = [
            e for e in self._entries
            if (now - e.timestamp) < self._max_age
        ]

    def clear(self):
        """Clear all entries."""
        self._entries = []
        logger.debug("Context store cleared")

    def __len__(self) -> int:
        """Return number of entries."""
        return len(self._entries)

    def __bool__(self) -> bool:
        """Return True if there are entries."""
        return len(self._entries) > 0


# Singleton
_context_store: Optional[SystemContextStore] = None


def get_system_context_store() -> SystemContextStore:
    """Get or create SystemContextStore singleton."""
    global _context_store
    if _context_store is None:
        _context_store = SystemContextStore()
        logger.info("SystemContextStore initialized")
    return _context_store


__all__ = [
    "SystemContextStore",
    "ContextEntry",
    "get_system_context_store",
]
