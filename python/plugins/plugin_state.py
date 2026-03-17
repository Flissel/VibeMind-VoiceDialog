"""
Plugin State Repository - SQLite persistence for plugin enable/disable state.

Stores which plugins the user has accepted, rejected, or toggled,
along with the last version they have seen.
"""

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Default DB path (same as main vibemind.db)
_DEFAULT_DB_DIR = Path(__file__).resolve().parent.parent


class PluginStateRepository:
    """Manages plugin state in SQLite."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or (_DEFAULT_DB_DIR / "vibemind.db")
        self._ensure_table()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_table(self):
        """Create plugin_state table if it doesn't exist."""
        conn = self._get_conn()
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS plugin_state (
                    plugin_id TEXT PRIMARY KEY,
                    enabled INTEGER DEFAULT 0,
                    version_seen TEXT,
                    accepted_at TIMESTAMP,
                    rejected_at TIMESTAMP
                )
            """)
            conn.commit()
        finally:
            conn.close()

    def is_enabled(self, plugin_id: str) -> bool:
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT enabled FROM plugin_state WHERE plugin_id = ?",
                (plugin_id,),
            ).fetchone()
            return bool(row["enabled"]) if row else False
        finally:
            conn.close()

    def get_version_seen(self, plugin_id: str) -> Optional[str]:
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT version_seen FROM plugin_state WHERE plugin_id = ?",
                (plugin_id,),
            ).fetchone()
            return row["version_seen"] if row else None
        finally:
            conn.close()

    def has_state(self, plugin_id: str) -> bool:
        """Returns True if the user has ever accepted or rejected this plugin."""
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT 1 FROM plugin_state WHERE plugin_id = ?",
                (plugin_id,),
            ).fetchone()
            return row is not None
        finally:
            conn.close()

    def accept(self, plugin_id: str, version: str) -> bool:
        now = datetime.now(timezone.utc).isoformat()
        conn = self._get_conn()
        try:
            conn.execute(
                """INSERT INTO plugin_state (plugin_id, enabled, version_seen, accepted_at)
                   VALUES (?, 1, ?, ?)
                   ON CONFLICT(plugin_id)
                   DO UPDATE SET enabled = 1, version_seen = ?, accepted_at = ?""",
                (plugin_id, version, now, version, now),
            )
            conn.commit()
            logger.info(f"Plugin '{plugin_id}' accepted (v{version})")
            return True
        except Exception as e:
            logger.error(f"Failed to accept plugin '{plugin_id}': {e}")
            return False
        finally:
            conn.close()

    def reject(self, plugin_id: str, version: str) -> bool:
        now = datetime.now(timezone.utc).isoformat()
        conn = self._get_conn()
        try:
            conn.execute(
                """INSERT INTO plugin_state (plugin_id, enabled, version_seen, rejected_at)
                   VALUES (?, 0, ?, ?)
                   ON CONFLICT(plugin_id)
                   DO UPDATE SET enabled = 0, version_seen = ?, rejected_at = ?""",
                (plugin_id, version, now, version, now),
            )
            conn.commit()
            logger.info(f"Plugin '{plugin_id}' rejected (v{version})")
            return True
        except Exception as e:
            logger.error(f"Failed to reject plugin '{plugin_id}': {e}")
            return False
        finally:
            conn.close()

    def toggle(self, plugin_id: str, enabled: bool) -> bool:
        conn = self._get_conn()
        try:
            conn.execute(
                "UPDATE plugin_state SET enabled = ? WHERE plugin_id = ?",
                (1 if enabled else 0, plugin_id),
            )
            conn.commit()
            logger.info(f"Plugin '{plugin_id}' toggled to {'enabled' if enabled else 'disabled'}")
            return True
        except Exception as e:
            logger.error(f"Failed to toggle plugin '{plugin_id}': {e}")
            return False
        finally:
            conn.close()

    def get_all_states(self) -> Dict[str, dict]:
        """Returns {plugin_id: {enabled, version_seen}} for all known plugins."""
        conn = self._get_conn()
        try:
            rows = conn.execute("SELECT * FROM plugin_state").fetchall()
            return {
                row["plugin_id"]: {
                    "enabled": bool(row["enabled"]),
                    "version_seen": row["version_seen"],
                    "accepted_at": row["accepted_at"],
                    "rejected_at": row["rejected_at"],
                }
                for row in rows
            }
        finally:
            conn.close()
