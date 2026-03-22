"""
Conversation-based routing using Supermemory.

Stores each user interaction and uses semantic search
to improve intent classification based on past conversations.

This enables:
1. Learning from user's past intents for better routing
2. Context-aware classification (similar past requests)
3. Per-user conversation history for personalization
"""

import os
import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class PastIntent:
    """A similar past intent found via semantic search."""
    past_input: str
    past_intent: str
    confidence: float
    timestamp: Optional[str] = None


class ConversationRouter:
    """
    Uses Supermemory Conversations API for:
    1. Storing user conversations per session
    2. Semantic search for similar past intents
    3. Context enrichment for intent classification

    Container Tag Strategy:
    - vibemind-user-{user_id}: All conversations for a user
    - session-{session_id}: Session-specific tagging

    Conversation ID Format:
    - {user_id}_{session_id}_{timestamp}: Unique per interaction
    """

    def __init__(self, user_id: str, session_id: str):
        """
        Initialize ConversationRouter for a specific user session.

        Args:
            user_id: Unique user identifier
            session_id: Current session identifier
        """
        self.user_id = user_id
        self.session_id = session_id
        self.container_tag = f"vibemind-user-{user_id}"
        self.session_tag = f"session-{session_id}"

        self._client = None
        self._available = False

        # Check if RAG classifier is enabled (ConversationRouter is used for context-aware routing)
        use_feature = os.getenv("USE_RAG_CLASSIFIER", "false").lower() == "true"

        if not use_feature:
            logger.debug("[ConversationRouter] Disabled via USE_RAG_CLASSIFIER=false")
            return

        api_key = os.getenv("SUPERMEMORY_API_KEY")
        if not api_key:
            logger.warning("[ConversationRouter] USE_RAG_CLASSIFIER=true but SUPERMEMORY_API_KEY not set")
            return

        try:
            from supermemory import AsyncSupermemory
            self._client = AsyncSupermemory(api_key=api_key)
            self._available = True
            logger.info(f"[ConversationRouter] Initialized for user:{user_id}, session:{session_id}")
        except ImportError:
            logger.warning("[ConversationRouter] USE_RAG_CLASSIFIER=true but supermemory package not installed")
        except Exception as e:
            logger.warning(f"[ConversationRouter] Initialization failed: {e}")

    @property
    def is_available(self) -> bool:
        """Check if the router is available."""
        return self._available and self._client is not None

    async def store_interaction(
        self,
        user_input: str,
        classified_intent: str,
        confidence: float,
        agent_response: str,
        parameters: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Store interaction for future context retrieval.

        Args:
            user_input: What the user said
            classified_intent: The intent that was classified (e.g., "idea.create")
            confidence: Classification confidence (0.0 - 1.0)
            agent_response: What Rachel responded
            parameters: Extracted parameters (optional)

        Returns:
            True if stored successfully
        """
        if not self.is_available:
            return False

        now = datetime.utcnow()
        conversation_id = f"{self.user_id}_{self.session_id}_{now.strftime('%Y%m%d%H%M%S')}"

        try:
            # Format conversation as content string (SDK uses memories.add, not conversations.ingest)
            conversation_content = f"user: {user_input}\nassistant: {agent_response}"

            await self._client.memories.add(
                content=conversation_content,
                container_tag=self.container_tag,
                metadata={
                    "conversation_id": conversation_id,
                    "session_tag": self.session_tag,
                    "intent": classified_intent,
                    "confidence": confidence,
                    "parameters": json.dumps(parameters) if parameters else "{}",
                    "timestamp": now.isoformat(),
                    "user_id": self.user_id,
                    "session_id": self.session_id,
                    # Domain extraction for filtering
                    "domain": classified_intent.split(".")[0] if "." in classified_intent else "unknown"
                }
            )
            logger.debug(f"[ConversationRouter] Stored: {user_input[:30]}... → {classified_intent}")
            return True
        except Exception as e:
            logger.warning(f"[ConversationRouter] Failed to store interaction: {e}")
            return False

    async def get_similar_past_intents(
        self,
        current_input: str,
        limit: int = 3,
        domain_filter: Optional[str] = None
    ) -> List[PastIntent]:
        """
        Find similar past interactions for context.

        Args:
            current_input: The current user input
            limit: Maximum number of results
            domain_filter: Optional domain filter (e.g., "idea", "desktop")

        Returns:
            List of similar past intents
        """
        if not self.is_available:
            return []

        try:
            # Search in user's conversations
            tags = [self.container_tag]

            response = await self._client.search.execute(
                q=current_input,
                container_tags=tags,
                limit=limit * 2  # Get more for filtering
            )

            results = []
            # Null-safe handling - response or response.results may be None
            results_list = getattr(response, 'results', None) or []
            for r in results_list:
                meta = getattr(r, 'metadata', None) or {}
                if not isinstance(meta, dict):
                    continue

                intent = meta.get('intent')
                if not intent:
                    continue

                # Apply domain filter if specified
                if domain_filter:
                    doc_domain = meta.get('domain', '')
                    if doc_domain != domain_filter:
                        continue

                results.append(PastIntent(
                    past_input=(getattr(r, 'content', '') or '')[:100],
                    past_intent=intent,
                    confidence=meta.get('confidence', 0.0),
                    timestamp=meta.get('timestamp')
                ))

                if len(results) >= limit:
                    break

            logger.debug(f"[ConversationRouter] Found {len(results)} similar past intents")
            return results

        except Exception as e:
            logger.warning(f"[ConversationRouter] Search failed: {e}")
            return []

    async def get_routing_context(
        self,
        user_input: str,
        limit: int = 3
    ) -> str:
        """
        Build context string for RAG classifier.

        Returns formatted string with similar past intents
        to help classifier make better routing decisions.

        Args:
            user_input: Current user input
            limit: Max similar intents to include

        Returns:
            Formatted context string (empty if no matches)
        """
        logger.debug("get_routing_context: user_input=%s limit=%s", user_input[:50], limit)
        similar = await self.get_similar_past_intents(user_input, limit)

        if not similar:
            return ""

        lines = ["[ÄHNLICHE VERGANGENE ANFRAGEN]"]
        for s in similar:
            conf_str = f"{s.confidence:.0%}" if s.confidence else "?"
            lines.append(f"- '{s.past_input[:50]}' → {s.past_intent} ({conf_str})")

        return "\n".join(lines)

    async def get_user_intent_patterns(self, limit: int = 10) -> Dict[str, int]:
        """
        Get the user's most common intent patterns.

        Useful for understanding user behavior and
        potentially adjusting routing weights.

        Returns:
            Dict mapping intent_type to count
        """
        if not self.is_available:
            return {}

        try:
            # Search for all user interactions
            response = await self._client.search.execute(
                q=f"user {self.user_id} intent",
                container_tags=[self.container_tag],
                limit=100
            )

            # Count intents
            from collections import Counter
            intent_counts: Counter = Counter()

            # Null-safe handling
            results_list = getattr(response, 'results', None) or []
            for r in results_list:
                meta = getattr(r, 'metadata', None) or {}
                if isinstance(meta, dict):
                    intent = meta.get('intent')
                    if intent:
                        intent_counts[intent] += 1

            return dict(intent_counts.most_common(limit))

        except Exception as e:
            logger.warning(f"[ConversationRouter] Failed to get patterns: {e}")
            return {}

    async def get_session_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get recent interactions from current session.

        Args:
            limit: Maximum interactions to return

        Returns:
            List of recent interactions
        """
        if not self.is_available:
            return []

        try:
            response = await self._client.search.execute(
                q=f"session {self.session_id}",
                container_tags=[self.session_tag],
                limit=limit
            )

            history = []
            # Null-safe handling
            results_list = getattr(response, 'results', None) or []
            for r in results_list:
                meta = getattr(r, 'metadata', None) or {}
                if isinstance(meta, dict):
                    history.append({
                        "input": getattr(r, 'content', '') or '',
                        "intent": meta.get('intent'),
                        "confidence": meta.get('confidence'),
                        "timestamp": meta.get('timestamp')
                    })

            return history

        except Exception as e:
            logger.warning(f"[ConversationRouter] Failed to get session history: {e}")
            return []

    async def clear_session(self) -> bool:
        """
        Clear all conversations from current session.

        Returns:
            True if cleared successfully
        """
        if not self.is_available:
            return False

        try:
            await self._client.documents.bulk_delete(
                container_tags=[self.session_tag]
            )
            logger.info(f"[ConversationRouter] Cleared session: {self.session_id}")
            return True
        except Exception as e:
            logger.warning(f"[ConversationRouter] Failed to clear session: {e}")
            return False


# Factory function for creating routers
_routers: Dict[str, ConversationRouter] = {}


def get_conversation_router(user_id: str, session_id: str) -> ConversationRouter:
    """
    Get or create a ConversationRouter for a user session.

    Uses caching to avoid creating multiple instances for the same session.

    Args:
        user_id: User identifier
        session_id: Session identifier

    Returns:
        ConversationRouter instance
    """
    key = f"{user_id}:{session_id}"
    if key not in _routers:
        _routers[key] = ConversationRouter(user_id, session_id)
    return _routers[key]


def reset_conversation_routers():
    """Reset all cached routers (for testing)."""
    global _routers
    _routers = {}


__all__ = [
    "ConversationRouter",
    "PastIntent",
    "get_conversation_router",
    "reset_conversation_routers",
]
