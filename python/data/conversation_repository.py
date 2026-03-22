"""Conversation Repository — CRUD operations for conversation sessions and messages."""

import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

from .database import Database, get_database
from .models import ConversationSession, ConversationMessage
from .repository_utils import generate_id

logger = logging.getLogger(__name__)


class ConversationRepository:
    """Repository for conversation history CRUD operations"""

    def __init__(self, db: Optional[Database] = None):
        self.db = db or get_database()

    # Session operations

    def create_session(
        self,
        agent_id: Optional[str] = None,
        metadata: Dict[str, Any] = None,
    ) -> ConversationSession:
        """Start a new conversation session"""
        logger.debug("create_session: agent_id=%s", agent_id)
        session = ConversationSession(
            id=generate_id(),
            started_at=datetime.now(),
            agent_id=agent_id,
            metadata=metadata or {},
        )

        data = session.to_dict()
        self.db.execute(
            """
            INSERT INTO conversation_sessions (id, started_at, ended_at, summary, agent_id, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                data["id"],
                data["started_at"],
                data["ended_at"],
                data["summary"],
                data["agent_id"],
                data["metadata"],
            ),
        )

        return session

    def end_session(
        self,
        session_id: str,
        summary: Optional[str] = None,
    ) -> Optional[ConversationSession]:
        """End a conversation session"""
        session = self.get_session(session_id)
        if not session:
            return None

        session.ended_at = datetime.now()
        session.summary = summary

        self.db.execute(
            """
            UPDATE conversation_sessions SET ended_at = ?, summary = ?
            WHERE id = ?
            """,
            (session.ended_at.isoformat(), session.summary, session_id),
        )

        return session

    def get_session(self, session_id: str) -> Optional[ConversationSession]:
        """Get session by ID"""
        row = self.db.fetch_one("SELECT * FROM conversation_sessions WHERE id = ?", (session_id,))
        return ConversationSession.from_dict(dict(row)) if row else None

    def list_sessions(
        self,
        limit: int = 20,
        offset: int = 0,
    ) -> List[ConversationSession]:
        """List recent conversation sessions"""
        rows = self.db.fetch_all(
            "SELECT * FROM conversation_sessions ORDER BY started_at DESC LIMIT ? OFFSET ?",
            (limit, offset)
        )
        return [ConversationSession.from_dict(dict(row)) for row in rows]

    # Message operations

    def add_message(
        self,
        session_id: str,
        speaker: str,
        text: str,
        metadata: Dict[str, Any] = None,
    ) -> ConversationMessage:
        """Add a message to conversation history"""
        message = ConversationMessage(
            id=generate_id(),
            session_id=session_id,
            speaker=speaker,
            text=text,
            timestamp=datetime.now(),
            metadata=metadata or {},
        )

        data = message.to_dict()
        self.db.execute(
            """
            INSERT INTO conversation_history (id, session_id, speaker, text, timestamp, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                data["id"],
                data["session_id"],
                data["speaker"],
                data["text"],
                data["timestamp"],
                data["metadata"],
            ),
        )

        return message

    def get_session_messages(
        self,
        session_id: str,
        limit: int = 100,
    ) -> List[ConversationMessage]:
        """Get all messages for a session"""
        rows = self.db.fetch_all(
            "SELECT * FROM conversation_history WHERE session_id = ? ORDER BY timestamp ASC LIMIT ?",
            (session_id, limit)
        )
        return [ConversationMessage.from_dict(dict(row)) for row in rows]

    def get_recent_messages(
        self,
        limit: int = 50,
    ) -> List[ConversationMessage]:
        """Get most recent messages across all sessions"""
        rows = self.db.fetch_all(
            "SELECT * FROM conversation_history ORDER BY timestamp DESC LIMIT ?",
            (limit,)
        )
        return [ConversationMessage.from_dict(dict(row)) for row in rows]

    def search_messages(
        self,
        query: str,
        limit: int = 20,
    ) -> List[ConversationMessage]:
        """Search messages by text content"""
        rows = self.db.fetch_all(
            "SELECT * FROM conversation_history WHERE text LIKE ? ORDER BY timestamp DESC LIMIT ?",
            (f"%{query}%", limit)
        )
        return [ConversationMessage.from_dict(dict(row)) for row in rows]

    def count_messages(self, session_id: Optional[str] = None) -> int:
        """Count messages, optionally filtered by session"""
        if session_id:
            row = self.db.fetch_one(
                "SELECT COUNT(*) FROM conversation_history WHERE session_id = ?",
                (session_id,)
            )
        else:
            row = self.db.fetch_one("SELECT COUNT(*) FROM conversation_history")
        return row[0] if row else 0
