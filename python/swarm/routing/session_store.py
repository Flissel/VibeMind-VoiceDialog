"""SQLite-backed session store for HybridRouter."""

import json
import logging
import sqlite3
from typing import List, Optional

from .types import SessionKey, SessionEntry, RouteResult

logger = logging.getLogger(__name__)


class SessionStore:
    """Manages routing sessions in SQLite."""

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            import os
            # Use a dedicated session-only SQLite file (not the legacy vibemind.db).
            # Session routing is ephemeral — no need to migrate to Supabase.
            db_path = os.path.join(
                os.path.expanduser("~"),
                ".vibemind_sessions.db"
            )
        self._db_path = db_path
        self._ensure_tables()

    def _ensure_tables(self):
        """Create tables if they don't exist (for standalone/test usage)."""
        conn = sqlite3.connect(self._db_path)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_key TEXT PRIMARY KEY, agent_id TEXT NOT NULL,
                    channel TEXT NOT NULL, canonical_id TEXT,
                    space_state TEXT, last_route TEXT,
                    last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS session_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_key TEXT NOT NULL, speaker TEXT NOT NULL,
                    text TEXT NOT NULL, event_type TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
        finally:
            conn.close()

    def get_or_create(self, key: SessionKey) -> SessionEntry:
        """Load existing session or create new one."""
        conn = sqlite3.connect(self._db_path)
        try:
            row = conn.execute(
                "SELECT session_key, agent_id, channel, canonical_id, space_state, last_route, last_active "
                "FROM sessions WHERE session_key = ?",
                (key.key,)
            ).fetchone()

            if row:
                last_route = None
                if row[5]:
                    try:
                        lr = json.loads(row[5])
                        last_route = RouteResult(**lr)
                    except Exception:
                        pass
                return SessionEntry(
                    session_key=row[0], agent_id=row[1], channel=row[2],
                    canonical_id=row[3],
                    space_state=json.loads(row[4]) if row[4] else None,
                    last_route=last_route, last_active=row[6],
                )

            # Create new session
            conn.execute(
                "INSERT INTO sessions (session_key, agent_id, channel, canonical_id) VALUES (?, ?, ?, ?)",
                (key.key, key.agent_id, key.channel, key.peer_id)
            )
            conn.commit()
            return SessionEntry(
                session_key=key.key, agent_id=key.agent_id, channel=key.channel,
                canonical_id=key.peer_id,
            )
        finally:
            conn.close()

    def update_last_route(self, key: SessionKey, route: RouteResult):
        """Store the last routing decision for DroPE integration."""
        conn = sqlite3.connect(self._db_path)
        try:
            route_json = json.dumps({
                "space": route.space, "agent": route.agent,
                "event_type": route.event_type, "matched_by": route.matched_by,
                "tier": route.tier,
            })
            conn.execute(
                "UPDATE sessions SET last_route = ?, last_active = CURRENT_TIMESTAMP "
                "WHERE session_key = ?",
                (route_json, key.key)
            )
            conn.commit()
        finally:
            conn.close()

    def append_history(self, key: SessionKey, speaker: str, text: str, event_type: str = ""):
        """Add a routing turn to session history."""
        conn = sqlite3.connect(self._db_path)
        try:
            conn.execute(
                "INSERT INTO session_history (session_key, speaker, text, event_type) VALUES (?, ?, ?, ?)",
                (key.key, speaker, text, event_type)
            )
            # Keep only last 20 entries per session
            conn.execute("""
                DELETE FROM session_history WHERE id NOT IN (
                    SELECT id FROM session_history WHERE session_key = ?
                    ORDER BY timestamp DESC LIMIT 20
                ) AND session_key = ?
            """, (key.key, key.key))
            conn.commit()
        finally:
            conn.close()

    def get_cross_space_context(self, canonical_id: str) -> List[SessionEntry]:
        """Get all sessions for a user across all spaces."""
        conn = sqlite3.connect(self._db_path)
        try:
            rows = conn.execute(
                "SELECT session_key, agent_id, channel, canonical_id, space_state, last_route, last_active "
                "FROM sessions WHERE canonical_id = ? ORDER BY last_active DESC",
                (canonical_id,)
            ).fetchall()
            return [
                SessionEntry(
                    session_key=r[0], agent_id=r[1], channel=r[2],
                    canonical_id=r[3],
                    space_state=json.loads(r[4]) if r[4] else None,
                    last_route=None, last_active=r[6],
                )
                for r in rows
            ]
        finally:
            conn.close()
