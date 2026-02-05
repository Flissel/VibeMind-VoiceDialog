"""
Conversion AI Repository - Database operations for AI personalities

Phase 13: Conversion AI System

Stores and retrieves:
- AI personalities (name, style, traits)
- User preferences (learned over time)
- Intent analysis logs (for improvement)
"""

import json
import uuid
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

from .database import Database, get_database

logger = logging.getLogger(__name__)


def generate_id() -> str:
    """Generate a unique ID for new entities."""
    return str(uuid.uuid4())[:8]


class ConversionAIRepository:
    """Repository for Conversion AI personality and preference operations."""

    def __init__(self, db: Optional[Database] = None):
        self.db = db or get_database()
        self._ensure_tables()

    def _ensure_tables(self):
        """Ensure required tables exist."""
        try:
            # Check if tables exist
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS conversion_ai_personalities (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    style TEXT DEFAULT 'casual',
                    verbosity TEXT DEFAULT 'concise',
                    traits TEXT,
                    language TEXT DEFAULT 'de',
                    created_at TEXT,
                    updated_at TEXT
                )
            """)

            self.db.execute("""
                CREATE TABLE IF NOT EXISTS user_preferences (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    preference_key TEXT NOT NULL,
                    preference_value TEXT,
                    confidence REAL DEFAULT 0.5,
                    learned_at TEXT,
                    UNIQUE(user_id, preference_key)
                )
            """)

            self.db.execute("""
                CREATE TABLE IF NOT EXISTS intent_analysis_log (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    user_input TEXT NOT NULL,
                    hypotheses TEXT,
                    selected_intent TEXT,
                    was_correct INTEGER,
                    created_at TEXT
                )
            """)

            logger.debug("Conversion AI tables ensured")
        except Exception as e:
            logger.warning(f"Could not ensure tables: {e}")

    # ==========================================================================
    # PERSONALITY OPERATIONS
    # ==========================================================================

    async def get_personality(self, user_id: str) -> Optional['AIPersonality']:
        """
        Get personality for a user.

        Args:
            user_id: User identifier

        Returns:
            AIPersonality or None if not found
        """
        try:
            row = self.db.fetch_one(
                "SELECT * FROM conversion_ai_personalities WHERE user_id = ?",
                (user_id,)
            )
            if row:
                from swarm.conversion.conversion_ai import AIPersonality
                data = dict(row)
                return AIPersonality(
                    name=data["name"],
                    style=data.get("style", "casual"),
                    verbosity=data.get("verbosity", "concise"),
                    traits=json.loads(data.get("traits", "[]")),
                    language=data.get("language", "de"),
                )
        except Exception as e:
            logger.warning(f"Failed to get personality: {e}")

        return None

    async def save_personality(self, user_id: str, personality: 'AIPersonality') -> bool:
        """
        Save or update personality for a user.

        Args:
            user_id: User identifier
            personality: AIPersonality to save

        Returns:
            True if saved successfully
        """
        try:
            now = datetime.now().isoformat()

            # Check if exists
            existing = await self.get_personality(user_id)

            if existing:
                # Update
                self.db.execute(
                    """
                    UPDATE conversion_ai_personalities SET
                        name = ?,
                        style = ?,
                        verbosity = ?,
                        traits = ?,
                        language = ?,
                        updated_at = ?
                    WHERE user_id = ?
                    """,
                    (
                        personality.name,
                        personality.style,
                        personality.verbosity,
                        json.dumps(personality.traits),
                        personality.language,
                        now,
                        user_id,
                    )
                )
            else:
                # Insert
                self.db.execute(
                    """
                    INSERT INTO conversion_ai_personalities
                        (id, user_id, name, style, verbosity, traits, language, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        generate_id(),
                        user_id,
                        personality.name,
                        personality.style,
                        personality.verbosity,
                        json.dumps(personality.traits),
                        personality.language,
                        now,
                        now,
                    )
                )

            return True
        except Exception as e:
            logger.error(f"Failed to save personality: {e}")
            return False

    async def delete_personality(self, user_id: str) -> bool:
        """Delete personality for a user."""
        try:
            self.db.execute(
                "DELETE FROM conversion_ai_personalities WHERE user_id = ?",
                (user_id,)
            )
            return True
        except Exception as e:
            logger.error(f"Failed to delete personality: {e}")
            return False

    # ==========================================================================
    # PREFERENCE OPERATIONS
    # ==========================================================================

    async def get_preference(self, user_id: str, key: str) -> Optional[Dict[str, Any]]:
        """
        Get a specific preference for a user.

        Args:
            user_id: User identifier
            key: Preference key

        Returns:
            Dict with value and confidence, or None
        """
        try:
            row = self.db.fetch_one(
                "SELECT * FROM user_preferences WHERE user_id = ? AND preference_key = ?",
                (user_id, key)
            )
            if row:
                data = dict(row)
                return {
                    "value": data.get("preference_value"),
                    "confidence": data.get("confidence", 0.5),
                    "learned_at": data.get("learned_at"),
                }
        except Exception as e:
            logger.warning(f"Failed to get preference: {e}")

        return None

    async def get_all_preferences(self, user_id: str) -> Dict[str, Any]:
        """
        Get all preferences for a user.

        Args:
            user_id: User identifier

        Returns:
            Dict mapping preference keys to their values
        """
        preferences = {}
        try:
            rows = self.db.fetch_all(
                "SELECT * FROM user_preferences WHERE user_id = ?",
                (user_id,)
            )
            for row in rows:
                data = dict(row)
                preferences[data["preference_key"]] = {
                    "value": data.get("preference_value"),
                    "confidence": data.get("confidence", 0.5),
                }
        except Exception as e:
            logger.warning(f"Failed to get preferences: {e}")

        return preferences

    async def set_preference(
        self,
        user_id: str,
        key: str,
        value: str,
        confidence: float = 0.5
    ) -> bool:
        """
        Set or update a preference for a user.

        Args:
            user_id: User identifier
            key: Preference key
            value: Preference value
            confidence: Confidence level (0.0-1.0)

        Returns:
            True if saved successfully
        """
        try:
            now = datetime.now().isoformat()

            # Use UPSERT pattern
            self.db.execute(
                """
                INSERT INTO user_preferences (id, user_id, preference_key, preference_value, confidence, learned_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, preference_key) DO UPDATE SET
                    preference_value = excluded.preference_value,
                    confidence = excluded.confidence,
                    learned_at = excluded.learned_at
                """,
                (generate_id(), user_id, key, value, confidence, now)
            )

            return True
        except Exception as e:
            logger.error(f"Failed to set preference: {e}")
            return False

    async def increment_preference_confidence(
        self,
        user_id: str,
        key: str,
        increment: float = 0.1
    ) -> bool:
        """
        Increment confidence for a learned preference.

        Args:
            user_id: User identifier
            key: Preference key
            increment: Amount to increase confidence (capped at 1.0)

        Returns:
            True if updated
        """
        try:
            self.db.execute(
                """
                UPDATE user_preferences
                SET confidence = MIN(1.0, confidence + ?)
                WHERE user_id = ? AND preference_key = ?
                """,
                (increment, user_id, key)
            )
            return True
        except Exception as e:
            logger.warning(f"Failed to increment confidence: {e}")
            return False

    # ==========================================================================
    # INTENT ANALYSIS LOG OPERATIONS
    # ==========================================================================

    async def log_analysis(
        self,
        session_id: str,
        user_input: str,
        hypotheses: List[Dict[str, Any]],
        selected_intent: str,
    ) -> str:
        """
        Log an intent analysis for later review/improvement.

        Args:
            session_id: Session identifier
            user_input: Original user input
            hypotheses: List of hypothesis dicts
            selected_intent: The intent that was selected

        Returns:
            Log entry ID
        """
        try:
            log_id = generate_id()
            now = datetime.now().isoformat()

            self.db.execute(
                """
                INSERT INTO intent_analysis_log
                    (id, session_id, user_input, hypotheses, selected_intent, was_correct, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    log_id,
                    session_id,
                    user_input,
                    json.dumps(hypotheses),
                    selected_intent,
                    None,  # was_correct set later via feedback
                    now,
                )
            )

            return log_id
        except Exception as e:
            logger.warning(f"Failed to log analysis: {e}")
            return ""

    async def mark_analysis_correct(self, log_id: str, was_correct: bool) -> bool:
        """
        Mark an intent analysis as correct or incorrect.

        Used for feedback loop to improve classification.

        Args:
            log_id: Log entry ID
            was_correct: Whether the selected intent was correct

        Returns:
            True if updated
        """
        try:
            self.db.execute(
                "UPDATE intent_analysis_log SET was_correct = ? WHERE id = ?",
                (1 if was_correct else 0, log_id)
            )
            return True
        except Exception as e:
            logger.warning(f"Failed to mark analysis: {e}")
            return False

    async def get_analysis_stats(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get statistics about intent analysis accuracy.

        Args:
            session_id: Optional filter by session

        Returns:
            Dict with accuracy statistics
        """
        try:
            if session_id:
                rows = self.db.fetch_all(
                    "SELECT was_correct FROM intent_analysis_log WHERE session_id = ? AND was_correct IS NOT NULL",
                    (session_id,)
                )
            else:
                rows = self.db.fetch_all(
                    "SELECT was_correct FROM intent_analysis_log WHERE was_correct IS NOT NULL"
                )

            if not rows:
                return {"total": 0, "correct": 0, "incorrect": 0, "accuracy": 0.0}

            total = len(rows)
            correct = sum(1 for row in rows if row[0] == 1)
            incorrect = total - correct

            return {
                "total": total,
                "correct": correct,
                "incorrect": incorrect,
                "accuracy": correct / total if total > 0 else 0.0,
            }
        except Exception as e:
            logger.warning(f"Failed to get stats: {e}")
            return {"total": 0, "correct": 0, "incorrect": 0, "accuracy": 0.0}

    # ==========================================================================
    # CORRECTION OPERATIONS (Phase 17 - Evaluation Framework)
    # ==========================================================================

    def log_correction(
        self,
        original_log_id: str,
        session_id: str,
        original_input: str,
        original_intent: str,
        original_payload: Dict[str, Any],
        corrected_intent: Optional[str] = None,
        corrected_payload: Optional[Dict[str, Any]] = None,
        user_explanation: Optional[str] = None,
    ) -> str:
        """
        Log a user correction for training data.

        Args:
            original_log_id: Reference to intent_analysis_log entry
            session_id: Session identifier
            original_input: Original user utterance
            original_intent: What the classifier predicted
            original_payload: Predicted payload
            corrected_intent: What the user actually meant
            corrected_payload: Correct payload
            user_explanation: User's description of their intent

        Returns:
            Correction entry ID
        """
        try:
            # Ensure corrections table exists
            self.db.execute("""
                CREATE TABLE IF NOT EXISTS intent_corrections (
                    id TEXT PRIMARY KEY,
                    original_log_id TEXT,
                    session_id TEXT,
                    original_input TEXT NOT NULL,
                    original_intent TEXT NOT NULL,
                    original_payload TEXT,
                    corrected_intent TEXT,
                    corrected_payload TEXT,
                    user_explanation TEXT,
                    created_at TEXT,
                    used_for_training INTEGER DEFAULT 0
                )
            """)

            correction_id = generate_id()
            now = datetime.now().isoformat()

            self.db.execute(
                """
                INSERT INTO intent_corrections
                    (id, original_log_id, session_id, original_input, original_intent,
                     original_payload, corrected_intent, corrected_payload,
                     user_explanation, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    correction_id,
                    original_log_id,
                    session_id,
                    original_input,
                    original_intent,
                    json.dumps(original_payload) if original_payload else None,
                    corrected_intent,
                    json.dumps(corrected_payload) if corrected_payload else None,
                    user_explanation,
                    now,
                )
            )

            logger.info(f"Logged correction {correction_id}: {original_intent} -> {corrected_intent}")
            return correction_id

        except Exception as e:
            logger.error(f"Failed to log correction: {e}")
            return ""

    def get_corrections(
        self,
        limit: int = 100,
        unused_only: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Get corrections for training.

        Args:
            limit: Maximum number of corrections to return
            unused_only: Only return corrections not yet used for training

        Returns:
            List of correction dicts
        """
        try:
            if unused_only:
                rows = self.db.fetch_all(
                    "SELECT * FROM intent_corrections WHERE used_for_training = 0 ORDER BY created_at DESC LIMIT ?",
                    (limit,)
                )
            else:
                rows = self.db.fetch_all(
                    "SELECT * FROM intent_corrections ORDER BY created_at DESC LIMIT ?",
                    (limit,)
                )

            corrections = []
            for row in rows:
                data = dict(row)
                # Parse JSON fields
                if data.get("original_payload"):
                    try:
                        data["original_payload"] = json.loads(data["original_payload"])
                    except:
                        pass
                if data.get("corrected_payload"):
                    try:
                        data["corrected_payload"] = json.loads(data["corrected_payload"])
                    except:
                        pass
                corrections.append(data)

            return corrections

        except Exception as e:
            logger.warning(f"Failed to get corrections: {e}")
            return []

    def mark_corrections_used(self, correction_ids: List[str]) -> bool:
        """
        Mark corrections as used for training.

        Args:
            correction_ids: List of correction IDs to mark

        Returns:
            True if successful
        """
        try:
            for cid in correction_ids:
                self.db.execute(
                    "UPDATE intent_corrections SET used_for_training = 1 WHERE id = ?",
                    (cid,)
                )
            return True
        except Exception as e:
            logger.error(f"Failed to mark corrections: {e}")
            return False


# Singleton
_conversion_ai_repository: Optional[ConversionAIRepository] = None


def get_conversion_ai_repository() -> ConversionAIRepository:
    """Get or create ConversionAIRepository singleton."""
    global _conversion_ai_repository
    if _conversion_ai_repository is None:
        _conversion_ai_repository = ConversionAIRepository()
    return _conversion_ai_repository


# Alias for realtime_evaluator compatibility
def get_conversion_ai_repo() -> ConversionAIRepository:
    """Alias for get_conversion_ai_repository."""
    return get_conversion_ai_repository()


__all__ = [
    "ConversionAIRepository",
    "get_conversion_ai_repository",
    "get_conversion_ai_repo",
]
