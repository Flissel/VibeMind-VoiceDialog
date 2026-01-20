"""
Conversation Memory - Long-term history across sessions.

Stores conversation interactions beyond the 10-minute voice session window,
enabling context-aware responses across multiple sessions.

Features:
- Persist user interactions with intents and results
- Query recent context for LLM injection
- Session-based history retrieval
- Automatic cleanup of old entries
"""

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class Interaction:
    """A single user interaction with the system."""

    id: str = field(default_factory=lambda: f"int_{uuid.uuid4().hex[:8]}")
    session_id: str = ""
    user_input: str = ""
    intents: List[Dict[str, Any]] = field(default_factory=list)
    actions_taken: List[Dict[str, Any]] = field(default_factory=list)
    results: List[Dict[str, Any]] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "session_id": self.session_id,
            "user_input": self.user_input,
            "intents": self.intents,
            "actions_taken": self.actions_taken,
            "results": self.results,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Interaction":
        """Deserialize from dictionary."""
        return cls(
            id=data.get("id", ""),
            session_id=data.get("session_id", ""),
            user_input=data.get("user_input", ""),
            intents=data.get("intents", []),
            actions_taken=data.get("actions_taken", []),
            results=data.get("results", []),
            timestamp=datetime.fromisoformat(data["timestamp"]) if data.get("timestamp") else datetime.now(),
            metadata=data.get("metadata", {}),
        )


class ConversationMemory:
    """
    Long-term conversation history store.

    Persists interactions to SQLite for cross-session context.

    Usage:
        memory = ConversationMemory(db)

        # Store interaction
        await memory.store_interaction(
            session_id="session_123",
            user_input="Create a space for marketing",
            intents=[{"event_type": "bubble.create", "payload": {"title": "marketing"}}],
            actions_taken=[{"tool": "create_bubble", "params": {...}}],
            results=[{"success": True, "message": "Created space 'marketing'"}]
        )

        # Get recent context for LLM
        context = await memory.get_recent_context(limit=5)
    """

    TABLE_NAME = "conversation_memory"

    def __init__(self, db=None):
        """
        Initialize conversation memory.

        Args:
            db: Database instance (optional, will use default if None)
        """
        if db is None:
            from data.database import get_database
            db = get_database()
        self.db = db
        self._ensure_table()

    def _ensure_table(self) -> None:
        """Create the conversation_memory table if it doesn't exist."""
        try:
            self.db.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {self.TABLE_NAME} (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    user_input TEXT NOT NULL,
                    intents TEXT,
                    actions_taken TEXT,
                    results TEXT,
                    timestamp TEXT NOT NULL,
                    metadata TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            # Create indices for efficient queries
            self.db.execute(
                f"CREATE INDEX IF NOT EXISTS idx_conv_mem_session ON {self.TABLE_NAME}(session_id)"
            )
            self.db.execute(
                f"CREATE INDEX IF NOT EXISTS idx_conv_mem_timestamp ON {self.TABLE_NAME}(timestamp DESC)"
            )

            logger.debug("ConversationMemory table ensured")
        except Exception as e:
            logger.error(f"Failed to ensure conversation_memory table: {e}")

    async def store_interaction(
        self,
        session_id: str,
        user_input: str,
        intents: List[Dict[str, Any]],
        actions_taken: List[Dict[str, Any]],
        results: List[Dict[str, Any]],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Store a conversation interaction.

        Args:
            session_id: Current session identifier
            user_input: Original user voice/text input
            intents: List of classified intents
            actions_taken: List of tool executions
            results: List of action results
            metadata: Optional additional metadata

        Returns:
            Interaction ID
        """
        interaction_id = f"int_{uuid.uuid4().hex[:8]}"
        timestamp = datetime.now().isoformat()

        try:
            self.db.execute(
                f"""
                INSERT INTO {self.TABLE_NAME}
                (id, session_id, user_input, intents, actions_taken, results, timestamp, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    interaction_id,
                    session_id,
                    user_input,
                    json.dumps(intents, ensure_ascii=False),
                    json.dumps(actions_taken, ensure_ascii=False),
                    json.dumps(results, ensure_ascii=False),
                    timestamp,
                    json.dumps(metadata or {}, ensure_ascii=False),
                ),
            )

            logger.debug(f"Stored interaction {interaction_id} for session {session_id}")
            return interaction_id

        except Exception as e:
            logger.error(f"Failed to store interaction: {e}")
            return ""

    async def get_session_history(
        self,
        session_id: str,
        limit: int = 50,
    ) -> List[Interaction]:
        """
        Get conversation history for a specific session.

        Args:
            session_id: Session to query
            limit: Maximum interactions to return

        Returns:
            List of Interactions, newest first
        """
        try:
            rows = self.db.fetch_all(
                f"""
                SELECT * FROM {self.TABLE_NAME}
                WHERE session_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (session_id, limit),
            )

            return [self._row_to_interaction(row) for row in rows]

        except Exception as e:
            logger.error(f"Failed to get session history: {e}")
            return []

    async def get_recent_context(
        self,
        limit: int = 10,
        session_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get recent interactions formatted for LLM context injection.

        Args:
            limit: Maximum interactions to return
            session_id: Optional session filter

        Returns:
            List of simplified context dicts with input, intents, results
        """
        try:
            if session_id:
                rows = self.db.fetch_all(
                    f"""
                    SELECT user_input, intents, results FROM {self.TABLE_NAME}
                    WHERE session_id = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                    """,
                    (session_id, limit),
                )
            else:
                rows = self.db.fetch_all(
                    f"""
                    SELECT user_input, intents, results FROM {self.TABLE_NAME}
                    ORDER BY timestamp DESC
                    LIMIT ?
                    """,
                    (limit,),
                )

            context = []
            for row in rows:
                context.append(
                    {
                        "input": row["user_input"],
                        "intents": json.loads(row["intents"]) if row["intents"] else [],
                        "results": json.loads(row["results"]) if row["results"] else [],
                    }
                )

            return context

        except Exception as e:
            logger.error(f"Failed to get recent context: {e}")
            return []

    async def search_interactions(
        self,
        query: str,
        limit: int = 20,
    ) -> List[Interaction]:
        """
        Search interactions by user input text.

        Args:
            query: Text to search for
            limit: Maximum results

        Returns:
            List of matching Interactions
        """
        try:
            rows = self.db.fetch_all(
                f"""
                SELECT * FROM {self.TABLE_NAME}
                WHERE user_input LIKE ?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (f"%{query}%", limit),
            )

            return [self._row_to_interaction(row) for row in rows]

        except Exception as e:
            logger.error(f"Failed to search interactions: {e}")
            return []

    async def get_stats(
        self,
        session_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get conversation memory statistics.

        Args:
            session_id: Optional session filter

        Returns:
            Stats dict with counts and time ranges
        """
        try:
            if session_id:
                count_row = self.db.fetch_one(
                    f"SELECT COUNT(*) as total FROM {self.TABLE_NAME} WHERE session_id = ?",
                    (session_id,),
                )
                time_row = self.db.fetch_one(
                    f"""
                    SELECT MIN(timestamp) as oldest, MAX(timestamp) as newest
                    FROM {self.TABLE_NAME}
                    WHERE session_id = ?
                    """,
                    (session_id,),
                )
            else:
                count_row = self.db.fetch_one(
                    f"SELECT COUNT(*) as total FROM {self.TABLE_NAME}",
                )
                time_row = self.db.fetch_one(
                    f"""
                    SELECT MIN(timestamp) as oldest, MAX(timestamp) as newest
                    FROM {self.TABLE_NAME}
                    """,
                )

            session_count_row = self.db.fetch_one(
                f"SELECT COUNT(DISTINCT session_id) as sessions FROM {self.TABLE_NAME}",
            )

            return {
                "total_interactions": count_row["total"] if count_row else 0,
                "total_sessions": session_count_row["sessions"] if session_count_row else 0,
                "oldest_timestamp": time_row["oldest"] if time_row else None,
                "newest_timestamp": time_row["newest"] if time_row else None,
            }

        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {"total_interactions": 0, "total_sessions": 0}

    async def cleanup_old_entries(
        self,
        days: int = 30,
    ) -> int:
        """
        Remove entries older than specified days.

        Args:
            days: Delete entries older than this many days

        Returns:
            Number of entries deleted
        """
        try:
            cutoff = (datetime.now() - timedelta(days=days)).isoformat()

            # Get count first
            count_row = self.db.fetch_one(
                f"SELECT COUNT(*) as count FROM {self.TABLE_NAME} WHERE timestamp < ?",
                (cutoff,),
            )
            count = count_row["count"] if count_row else 0

            # Delete
            self.db.execute(
                f"DELETE FROM {self.TABLE_NAME} WHERE timestamp < ?",
                (cutoff,),
            )

            logger.info(f"Cleaned up {count} conversation memory entries older than {days} days")
            return count

        except Exception as e:
            logger.error(f"Failed to cleanup old entries: {e}")
            return 0

    def _row_to_interaction(self, row: Any) -> Interaction:
        """Convert database row to Interaction object."""
        return Interaction(
            id=row["id"],
            session_id=row["session_id"],
            user_input=row["user_input"],
            intents=json.loads(row["intents"]) if row["intents"] else [],
            actions_taken=json.loads(row["actions_taken"]) if row["actions_taken"] else [],
            results=json.loads(row["results"]) if row["results"] else [],
            timestamp=datetime.fromisoformat(row["timestamp"]) if row["timestamp"] else datetime.now(),
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
        )


__all__ = ["ConversationMemory", "Interaction"]
