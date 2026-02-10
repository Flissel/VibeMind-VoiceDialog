"""
Chat Archive Module

Automatically archives all incoming messages to SQLite.
Integrated into the client - no separate process needed.
"""

import sqlite3
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Default database path
DEFAULT_DB_PATH = Path(__file__).parent.parent / "chat_archive.db"


class ChatArchive:
    """SQLite-based chat archive."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DEFAULT_DB_PATH
        self._initialized = False

    def _ensure_initialized(self):
        """Initialize database on first use."""
        if self._initialized:
            return

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Messages table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id TEXT UNIQUE,
                platform TEXT NOT NULL,
                sender TEXT NOT NULL,
                sender_name TEXT,
                recipient TEXT,
                content TEXT,
                media_type TEXT,
                media_url TEXT,
                timestamp_received DATETIME DEFAULT CURRENT_TIMESTAMP,
                timestamp_original TEXT,
                raw_payload TEXT,
                conversation_id TEXT,
                is_group BOOLEAN DEFAULT FALSE,
                group_name TEXT
            )
        """)

        # Contacts table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone TEXT UNIQUE,
                name TEXT,
                first_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
                message_count INTEGER DEFAULT 0,
                platform TEXT
            )
        """)

        # Conversations table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT UNIQUE,
                platform TEXT,
                participants TEXT,
                started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_message_at DATETIME,
                message_count INTEGER DEFAULT 0,
                is_group BOOLEAN DEFAULT FALSE,
                group_name TEXT
            )
        """)

        # Indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_sender ON messages(sender)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp_received)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id)")

        conn.commit()
        conn.close()

        self._initialized = True
        logger.info(f"Chat archive initialized: {self.db_path}")

    def archive(self, payload: Dict[str, Any]) -> bool:
        """Archive a message payload."""
        self._ensure_initialized()

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        now = datetime.now().isoformat()

        # Extract fields
        sender = payload.get('from') or payload.get('sender') or payload.get('phone') or 'Unknown'
        sender_name = payload.get('name') or payload.get('senderName') or payload.get('pushName')
        content = payload.get('content') or payload.get('text') or payload.get('message') or payload.get('body') or ''
        platform = payload.get('platform') or 'whatsapp'
        message_id = payload.get('id') or payload.get('messageId') or payload.get('msgId')
        recipient = payload.get('to') or payload.get('recipient')
        timestamp_original = payload.get('timestamp') or payload.get('time')
        conversation_id = payload.get('chatId') or payload.get('conversationId') or sender
        is_group = payload.get('isGroup', False) or payload.get('isGroupMsg', False)
        group_name = payload.get('groupName') or payload.get('chatName') if is_group else None
        media_type = payload.get('mediaType') or payload.get('type')
        media_url = payload.get('mediaUrl') or payload.get('media')

        try:
            # Insert message
            cursor.execute("""
                INSERT OR IGNORE INTO messages
                (message_id, platform, sender, sender_name, recipient, content,
                 media_type, media_url, timestamp_original, raw_payload,
                 conversation_id, is_group, group_name)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                message_id, platform, sender, sender_name, recipient, content,
                media_type, media_url, timestamp_original, json.dumps(payload),
                conversation_id, is_group, group_name
            ))

            # Update contact
            cursor.execute("""
                INSERT INTO contacts (phone, name, platform, message_count, last_seen)
                VALUES (?, ?, ?, 1, ?)
                ON CONFLICT(phone) DO UPDATE SET
                    name = COALESCE(excluded.name, contacts.name),
                    last_seen = excluded.last_seen,
                    message_count = contacts.message_count + 1
            """, (sender, sender_name, platform, now))

            # Update conversation
            cursor.execute("""
                INSERT INTO conversations (conversation_id, platform, participants, last_message_at, message_count, is_group, group_name)
                VALUES (?, ?, ?, ?, 1, ?, ?)
                ON CONFLICT(conversation_id) DO UPDATE SET
                    last_message_at = excluded.last_message_at,
                    message_count = conversations.message_count + 1
            """, (conversation_id, platform, sender, now, is_group, group_name))

            conn.commit()
            logger.debug(f"Archived message from {sender}")
            return True

        except Exception as e:
            logger.error(f"Archive error: {e}")
            return False
        finally:
            conn.close()

    def get_stats(self) -> Dict[str, Any]:
        """Get archive statistics."""
        self._ensure_initialized()

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM messages")
        total_messages = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM contacts")
        total_contacts = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM conversations")
        total_conversations = cursor.fetchone()[0]

        conn.close()

        return {
            'total_messages': total_messages,
            'total_contacts': total_contacts,
            'total_conversations': total_conversations
        }


# Singleton instance
_archive: Optional[ChatArchive] = None


def get_archive() -> ChatArchive:
    """Get or create ChatArchive singleton."""
    global _archive
    if _archive is None:
        _archive = ChatArchive()
    return _archive


def archive_message(payload: Dict[str, Any]) -> bool:
    """Convenience function to archive a message."""
    return get_archive().archive(payload)
