"""Route caching for HybridRouter -- EventType (permanent) + Classification (TTL)."""

import hashlib
import logging
import time
from typing import Any, Dict, Optional

from .types import SpaceBinding

logger = logging.getLogger(__name__)


class EventTypeCache:
    """Tier 1 cache: event_type prefix -> SpaceBinding. Permanent, invalidated on config reload."""

    def __init__(self):
        self._cache: Dict[str, SpaceBinding] = {}

    def put(self, event_type: str, binding: SpaceBinding):
        self._cache[event_type] = binding

    def get(self, event_type: str) -> Optional[SpaceBinding]:
        return self._cache.get(event_type)

    def clear(self):
        self._cache.clear()

    def size(self) -> int:
        return len(self._cache)

    def populate_from_bindings(self, prefix_bindings: Dict[str, SpaceBinding]):
        """Pre-populate cache with all known event_type prefixes."""
        self._cache.update(prefix_bindings)
        logger.info(f"EventTypeCache populated with {len(prefix_bindings)} entries")


class ClassificationCache:
    """Tier 4 cache: normalized user input hash -> classification result. TTL-based."""

    def __init__(self, ttl_seconds: int = 300, max_entries: int = 2000):
        self._ttl = ttl_seconds
        self._max = max_entries
        self._cache: Dict[str, tuple] = {}  # key -> (timestamp, value)

    def put(self, user_input: str, classification: dict):
        if len(self._cache) >= self._max:
            logger.info(f"ClassificationCache overflow ({self._max}), clearing")
            self._cache.clear()
        key = self._hash(user_input)
        self._cache[key] = (time.monotonic(), classification)

    def get(self, user_input: str) -> Optional[dict]:
        key = self._hash(user_input)
        entry = self._cache.get(key)
        if entry is None:
            return None
        timestamp, value = entry
        if time.monotonic() - timestamp > self._ttl:
            del self._cache[key]
            return None
        return value

    def clear(self):
        self._cache.clear()

    def size(self) -> int:
        return len(self._cache)

    @staticmethod
    def _hash(user_input: str) -> str:
        normalized = user_input.lower().strip()
        return hashlib.md5(normalized.encode()).hexdigest()
