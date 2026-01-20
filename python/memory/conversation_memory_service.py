"""
Conversation Memory Service using Supermemory v4 Conversations API.

Stores Rachel conversations for:
- Cross-session context ("Was haben wir letztens besprochen?")
- Conversation search ("Finde das Gespraech ueber Marketing")
- Agent handoff context
"""

import os
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)


class ConversationMemoryService:
    """
    Stores Rachel conversations in Supermemory for cross-session context.

    Uses Supermemory v4 Conversations API for structured conversation storage.
    """

    CONTAINER_TAG = "vibemind-conversations"

    def __init__(self):
        # Check if feature is enabled before initializing
        use_feature = os.getenv("USE_CONVERSATION_MEMORY", "false").lower() == "true"

        self._client = None
        self._available = False

        if not use_feature:
            logger.debug("[ConversationMemory] Disabled via USE_CONVERSATION_MEMORY=false")
            return

        api_key = os.getenv("SUPERMEMORY_API_KEY")
        if not api_key:
            logger.warning("[ConversationMemory] USE_CONVERSATION_MEMORY=true but SUPERMEMORY_API_KEY not set")
            return

        try:
            from supermemory import AsyncSupermemory
            self._client = AsyncSupermemory(api_key=api_key)
            self._available = True
            logger.info("[ConversationMemory] Initialized with Supermemory SDK")
        except ImportError:
            logger.warning("[ConversationMemory] USE_CONVERSATION_MEMORY=true but supermemory package not installed")

    @property
    def is_available(self) -> bool:
        """Check if service is available."""
        return self._available and self._client is not None

    async def store_conversation(
        self,
        session_id: str,
        messages: List[Dict[str, str]],
        summary: Optional[str] = None,
        agent_name: str = "rachel"
    ) -> Optional[str]:
        """
        Store a conversation exchange using v4 Conversations API.

        Args:
            session_id: Unique session identifier
            messages: List of message dicts with 'role' and 'content' keys
            summary: Optional conversation summary
            agent_name: Name of the agent (default: rachel)

        Returns:
            Conversation ID if successful, None otherwise
        """
        if not self.is_available:
            return None

        if not messages:
            return None

        try:
            # Format messages for Supermemory v4 API
            formatted_messages = []
            for msg in messages:
                formatted_messages.append({
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", ""),
                    "name": msg.get("agent", agent_name)
                })

            response = await self._client.conversations.ingest(
                conversation_id=f"session_{session_id}",
                container_tags=[self.CONTAINER_TAG, f"vibemind-session-{session_id}"],
                messages=formatted_messages,
                metadata={
                    "session_id": session_id,
                    "timestamp": datetime.utcnow().isoformat(),
                    "message_count": len(messages),
                    "agent": agent_name,
                    "summary": summary
                }
            )
            logger.debug(f"[ConversationMemory] Stored {len(messages)} messages for session {session_id}")
            return getattr(response, 'id', f"session_{session_id}")
        except Exception as e:
            logger.warning(f"[ConversationMemory] Failed to store conversation: {e}")
            return None

    async def store_message_pair(
        self,
        session_id: str,
        user_message: str,
        assistant_response: str,
        agent_name: str = "rachel"
    ) -> Optional[str]:
        """
        Store a single user-assistant message pair.

        Convenience method for storing individual exchanges.
        """
        messages = [
            {"role": "user", "content": user_message},
            {"role": "assistant", "content": assistant_response, "agent": agent_name}
        ]
        return await self.store_conversation(session_id, messages, agent_name=agent_name)

    async def search_conversations(
        self,
        query: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Search past conversations semantically."""
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
            logger.warning(f"[ConversationMemory] Search failed: {e}")
            return []

    async def get_recent_conversations(
        self,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Get most recent conversations."""
        return await self.search_conversations("recent conversation", limit)

    async def get_conversation_context(
        self,
        query: str,
        limit: int = 3
    ) -> str:
        """
        Get conversation context formatted for LLM prompts.

        Returns a formatted string suitable for injection into prompts.
        """
        results = await self.search_conversations(query, limit)
        if not results:
            return ""

        context_parts = ["Relevante fruhere Gespraeche:"]
        for r in results:
            content = r.get("content", "")
            metadata = r.get("metadata", {})
            timestamp = metadata.get("timestamp", "unbekannt")
            context_parts.append(f"- [{timestamp}] {content[:200]}...")

        return "\n".join(context_parts)

    async def get_session_history(
        self,
        session_id: str
    ) -> List[Dict[str, Any]]:
        """Get all conversations from a specific session."""
        return await self.search_conversations(f"session_{session_id}", limit=50)

    async def delete_session_conversations(self, session_id: str) -> bool:
        """Delete all conversations for a session."""
        if not self.is_available:
            return False

        try:
            await self._client.documents.bulk_delete(
                container_tags=[f"vibemind-session-{session_id}"]
            )
            logger.info(f"[ConversationMemory] Deleted conversations for session: {session_id}")
            return True
        except Exception as e:
            logger.warning(f"[ConversationMemory] Failed to delete session: {e}")
            return False


# Singleton instance
_service: Optional[ConversationMemoryService] = None


def get_conversation_memory_service() -> Optional[ConversationMemoryService]:
    """Get or create ConversationMemoryService singleton."""
    global _service

    # Check if feature is enabled
    if os.getenv("USE_CONVERSATION_MEMORY", "true").lower() != "true":
        return None

    if _service is None:
        try:
            _service = ConversationMemoryService()
        except Exception as e:
            logger.warning(f"[ConversationMemory] Could not initialize: {e}")
            return None
    return _service


def reset_conversation_memory_service():
    """Reset singleton (for testing)."""
    global _service
    _service = None
