"""
User Profile Service using Supermemory.

Tracks user preferences and habits over sessions:
- Preferred formats (table, list, hierarchy)
- Common intents (most used commands)
- Working patterns (active hours, session length)
"""

import os
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from collections import Counter

logger = logging.getLogger(__name__)


@dataclass
class UserProfile:
    """User preferences and habits."""
    user_id: str
    preferences: Dict[str, Any] = field(default_factory=dict)
    habits: Dict[str, int] = field(default_factory=dict)  # intent_type -> count
    last_updated: datetime = field(default_factory=datetime.utcnow)


class UserProfileService:
    """
    Tracks user preferences and habits in Supermemory.

    Stored facts:
    - Preferred formats (table, list, hierarchy)
    - Common intents (most used commands)
    - Working patterns (active hours, session length)
    """

    CONTAINER_TAG = "vibemind-profiles"

    def __init__(self, user_id: str = "default"):
        self.user_id = user_id
        self._client = None
        self._available = False
        self._cache: Dict[str, Any] = {}

        # Check if feature is enabled before initializing
        use_feature = os.getenv("USE_USER_PROFILES", "false").lower() == "true"

        if not use_feature:
            logger.debug("[UserProfile] Disabled via USE_USER_PROFILES=false")
            return

        api_key = os.getenv("SUPERMEMORY_API_KEY")
        if not api_key:
            logger.warning("[UserProfile] USE_USER_PROFILES=true but SUPERMEMORY_API_KEY not set")
            return

        try:
            from supermemory import AsyncSupermemory
            self._client = AsyncSupermemory(api_key=api_key)
            self._available = True
            logger.info(f"[UserProfile] Initialized for user: {user_id}")
        except ImportError:
            logger.warning("[UserProfile] USE_USER_PROFILES=true but supermemory package not installed")

    @property
    def is_available(self) -> bool:
        """Check if service is available."""
        return self._available and self._client is not None

    async def update_preference(
        self,
        key: str,
        value: Any
    ) -> bool:
        """
        Update a user preference.

        Common preferences:
        - preferred_format: "table", "list", "hierarchy", "note"
        - language: "de", "en"
        - verbosity: "concise", "detailed"
        """
        if not self.is_available:
            return False

        content = f"User preference: {key} = {value}"

        try:
            await self._client.documents.create(
                content=content,
                container_tag=self.CONTAINER_TAG,
                custom_id=f"pref_{self.user_id}_{key}",
                metadata={
                    "type": "preference",
                    "user_id": self.user_id,
                    "key": key,
                    "value": value,
                    "timestamp": datetime.utcnow().isoformat()
                }
            )
            # Update local cache
            self._cache[f"pref_{key}"] = value
            logger.debug(f"[UserProfile] Updated preference: {key}={value}")
            return True
        except Exception as e:
            logger.warning(f"[UserProfile] Failed to update preference: {e}")
            return False

    async def get_preference(
        self,
        key: str,
        default: Any = None
    ) -> Any:
        """Get a user preference, using cache first."""
        cache_key = f"pref_{key}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        if not self.is_available:
            return default

        try:
            response = await self._client.search.documents(
                q=f"user {self.user_id} preference {key}",
                container_tags=[self.CONTAINER_TAG],
                top_k=1
            )
            results = getattr(response, 'results', [])
            if results:
                metadata = getattr(results[0], 'metadata', {})
                if isinstance(metadata, dict):
                    value = metadata.get('value', default)
                    self._cache[cache_key] = value
                    return value
            return default
        except Exception as e:
            logger.warning(f"[UserProfile] Failed to get preference: {e}")
            return default

    async def track_intent_usage(
        self,
        intent_type: str
    ) -> bool:
        """
        Track intent usage for habit learning.

        Stored as a document per usage for aggregation queries.
        """
        if not self.is_available:
            return False

        now = datetime.utcnow()
        content = f"User {self.user_id} used intent {intent_type}"

        try:
            await self._client.documents.create(
                content=content,
                container_tag=self.CONTAINER_TAG,
                custom_id=f"habit_{self.user_id}_{intent_type}_{now.strftime('%Y%m%d%H%M%S')}",
                metadata={
                    "type": "habit",
                    "user_id": self.user_id,
                    "intent_type": intent_type,
                    "timestamp": now.isoformat(),
                    "hour": now.hour,  # For time-of-day analysis
                    "weekday": now.weekday()  # For day-of-week analysis
                }
            )
            logger.debug(f"[UserProfile] Tracked intent usage: {intent_type}")
            return True
        except Exception as e:
            logger.warning(f"[UserProfile] Failed to track intent: {e}")
            return False

    async def get_top_intents(
        self,
        limit: int = 5
    ) -> List[str]:
        """Get most frequently used intents."""
        if not self.is_available:
            return []

        try:
            response = await self._client.search.documents(
                q=f"user {self.user_id} intent usage habit",
                container_tags=[self.CONTAINER_TAG],
                top_k=100  # Get many to aggregate
            )
            results = getattr(response, 'results', [])

            # Count intent types
            intent_counts: Counter = Counter()
            for r in results:
                metadata = getattr(r, 'metadata', {})
                if isinstance(metadata, dict) and metadata.get('type') == 'habit':
                    intent_type = metadata.get('intent_type')
                    if intent_type:
                        intent_counts[intent_type] += 1

            # Return top N
            return [intent for intent, _ in intent_counts.most_common(limit)]
        except Exception as e:
            logger.warning(f"[UserProfile] Failed to get top intents: {e}")
            return []

    async def get_user_context(self) -> str:
        """
        Get user context formatted for LLM prompts.

        Returns a string with preferences and habits suitable for
        injection into agent system prompts.
        """
        if not self.is_available:
            return ""

        try:
            response = await self._client.search.documents(
                q=f"user {self.user_id} preferences habits",
                container_tags=[self.CONTAINER_TAG],
                top_k=50
            )
            results = getattr(response, 'results', [])

            # Collect preferences and habits
            prefs: List[str] = []
            habits: List[str] = []

            for r in results:
                metadata = getattr(r, 'metadata', {})
                if not isinstance(metadata, dict):
                    continue

                if metadata.get("type") == "preference":
                    key = metadata.get('key')
                    value = metadata.get('value')
                    if key and value:
                        prefs.append(f"- {key}: {value}")
                elif metadata.get("type") == "habit":
                    intent = metadata.get("intent_type")
                    if intent:
                        habits.append(intent)

            # Build context string
            context_parts = ["User Profile:"]

            if prefs:
                context_parts.append("Preferences:")
                context_parts.extend(prefs[:10])  # Limit to 10

            if habits:
                top_habits = Counter(habits).most_common(5)
                context_parts.append("Most used commands: " + ", ".join([h[0] for h in top_habits]))

            return "\n".join(context_parts)
        except Exception as e:
            logger.warning(f"[UserProfile] Failed to get context: {e}")
            return ""

    async def learn_format_preference(
        self,
        chosen_format: str
    ) -> bool:
        """Learn user's format preference from their choice."""
        return await self.update_preference("preferred_format", chosen_format)

    async def get_preferred_format(self) -> Optional[str]:
        """Get user's preferred output format."""
        return await self.get_preference("preferred_format")

    async def clear_profile(self) -> bool:
        """Clear all user profile data."""
        if not self.is_available:
            return False

        try:
            await self._client.documents.bulk_delete(
                container_tags=[self.CONTAINER_TAG]
            )
            self._cache.clear()
            logger.info(f"[UserProfile] Cleared profile for user: {self.user_id}")
            return True
        except Exception as e:
            logger.warning(f"[UserProfile] Failed to clear profile: {e}")
            return False


# Singleton instance
_service: Optional[UserProfileService] = None


def get_user_profile_service(user_id: str = "default") -> Optional[UserProfileService]:
    """Get or create UserProfileService singleton."""
    global _service

    # Check if feature is enabled
    if os.getenv("USE_USER_PROFILES", "true").lower() != "true":
        return None

    if _service is None or _service.user_id != user_id:
        try:
            _service = UserProfileService(user_id)
        except Exception as e:
            logger.warning(f"[UserProfile] Could not initialize: {e}")
            return None
    return _service


def reset_user_profile_service():
    """Reset singleton (for testing)."""
    global _service
    _service = None
