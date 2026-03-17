"""Cross-channel identity linking for session continuity."""

import logging
import sqlite3
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class IdentityLinkResolver:
    """
    Resolves channel-specific peer IDs to canonical user IDs.
    Enables: voice user + chat user -> same session.
    """

    def __init__(self, db_path: Optional[str] = None):
        self._db_path = db_path
        # In-memory cache for fast lookups
        self._cache: Dict[Tuple[str, str], str] = {}

    def add_link(self, channel: str, peer_id: str, canonical_id: str):
        """Register a channel+peer -> canonical mapping."""
        self._cache[(channel, peer_id)] = canonical_id
        if self._db_path:
            self._persist(channel, peer_id, canonical_id)

    def resolve(self, channel: str, peer_id: str) -> str:
        """Resolve peer_id to canonical form. Returns peer_id unchanged if no link exists."""
        canonical = self._cache.get((channel, peer_id))
        if canonical:
            return canonical

        # Try DB if not in cache
        if self._db_path:
            canonical = self._load_from_db(channel, peer_id)
            if canonical:
                self._cache[(channel, peer_id)] = canonical
                return canonical

        return peer_id  # passthrough

    def _persist(self, channel: str, peer_id: str, canonical_id: str):
        """Save link to SQLite."""
        try:
            conn = sqlite3.connect(self._db_path)
            conn.execute(
                "INSERT OR REPLACE INTO identity_links (channel, peer_id, canonical_id) VALUES (?, ?, ?)",
                (channel, peer_id, canonical_id)
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning(f"Failed to persist identity link: {e}")

    def _load_from_db(self, channel: str, peer_id: str) -> Optional[str]:
        """Load link from SQLite."""
        try:
            conn = sqlite3.connect(self._db_path)
            row = conn.execute(
                "SELECT canonical_id FROM identity_links WHERE channel = ? AND peer_id = ?",
                (channel, peer_id)
            ).fetchone()
            conn.close()
            return row[0] if row else None
        except Exception:
            return None
