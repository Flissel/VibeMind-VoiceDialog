"""
Real-Time Evaluator - Live evaluation of intent classification with user feedback.

Tracks classifications during live conversations and allows users to
provide feedback via voice commands like "Das war falsch" or "Ja genau".
"""

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class LiveClassification:
    """Tracking of a single live classification for feedback."""
    id: str
    session_id: str
    user_input: str
    predicted_intent: str
    predicted_payload: Dict[str, Any]
    confidence: float
    timestamp: datetime
    feedback: Optional[str] = None     # "correct" | "incorrect" | None
    correction: Optional[str] = None   # User's intended action
    corrected_intent: Optional[str] = None  # Correct intent if known


def generate_id() -> str:
    """Generate a short unique ID."""
    return str(uuid.uuid4())[:8]


class RealtimeEvaluator:
    """
    Evaluates live conversations and collects user feedback.

    Tracks every classification and allows users to mark them as
    correct or incorrect via voice commands.
    """

    def __init__(self, repo=None):
        """
        Initialize the realtime evaluator.

        Args:
            repo: ConversionAIRepository instance (optional)
        """
        self._repo = repo
        self._last_classification: Optional[LiveClassification] = None
        self._session_classifications: List[LiveClassification] = []
        self._pending_correction: bool = False

    @property
    def repo(self):
        """Get or create repository."""
        if self._repo is None:
            try:
                from data.conversion_ai_repository import get_conversion_ai_repo
                self._repo = get_conversion_ai_repo()
            except ImportError as e:
                logger.warning(f"ConversionAIRepository not available: {e}")
        return self._repo

    def on_classification(
        self,
        session_id: str,
        user_input: str,
        result: Dict[str, Any]
    ) -> str:
        """
        Called after each intent classification.

        Args:
            session_id: Current conversation session ID
            user_input: Original user utterance
            result: Classification result with event_type, payload, confidence

        Returns:
            Log entry ID for later feedback
        """
        logger.debug("on_classification called with session_id=%s, user_input=%s", session_id, user_input[:80])
        classification = LiveClassification(
            id=generate_id(),
            session_id=session_id,
            user_input=user_input,
            predicted_intent=result.get("event_type", "conversation.unknown"),
            predicted_payload=result.get("payload", {}),
            confidence=result.get("confidence", 0.0),
            timestamp=datetime.now(),
        )

        # Log to database if available
        if self.repo:
            try:
                log_id = self.repo.log_analysis(
                    session_id=session_id,
                    user_input=user_input,
                    hypotheses=[result],
                    selected_intent=result.get("event_type", "conversation.unknown")
                )
                classification.id = log_id
            except Exception as e:
                logger.error(f"Failed to log classification: {e}")

        self._last_classification = classification
        self._session_classifications.append(classification)
        self._pending_correction = False

        logger.debug(
            f"Tracked classification: '{user_input[:50]}...' -> {classification.predicted_intent}"
        )

        return classification.id

    def on_feedback(
        self,
        feedback_type: str,
        correction: Optional[str] = None,
        corrected_intent: Optional[str] = None
    ) -> str:
        """
        Process user feedback on the last classification.

        Args:
            feedback_type: "correct" or "incorrect"
            correction: User's explanation of what they meant
            corrected_intent: The correct intent if known

        Returns:
            Response message for Rachel to speak
        """
        logger.debug("on_feedback called with feedback_type=%s, correction=%s", feedback_type, correction)
        if not self._last_classification:
            return "Kein vorheriger Intent zum Bewerten vorhanden."

        is_correct = feedback_type == "correct"

        # Update classification
        self._last_classification.feedback = feedback_type
        self._last_classification.correction = correction
        self._last_classification.corrected_intent = corrected_intent

        # Update database if available
        if self.repo:
            try:
                self.repo.mark_analysis_correct(
                    log_id=self._last_classification.id,
                    was_correct=is_correct
                )
            except Exception as e:
                logger.error(f"Failed to update feedback: {e}")

        if not is_correct:
            # Log correction for training
            self._log_correction(self._last_classification, correction, corrected_intent)
            self._pending_correction = True

            if correction:
                return f"Verstanden, du meintest: {correction}. Danke fuer die Korrektur!"
            else:
                return "Danke fuer die Korrektur! Was meintest du stattdessen?"

        return "Danke fuer das Feedback!"

    def on_clarification(self, clarification: str, intended_intent: Optional[str] = None) -> str:
        """
        Process user clarification after incorrect feedback.

        Args:
            clarification: User's explanation
            intended_intent: The intent they intended

        Returns:
            Response message
        """
        logger.debug("on_clarification called with clarification=%s", clarification[:80] if clarification else None)
        if not self._last_classification:
            return "Ich bin nicht sicher worauf sich das bezieht."

        self._last_classification.correction = clarification
        self._last_classification.corrected_intent = intended_intent

        # Update correction in database
        self._log_correction(
            self._last_classification,
            clarification,
            intended_intent
        )

        self._pending_correction = False
        return f"Verstanden! Ich habe mir gemerkt: {clarification}"

    def _log_correction(
        self,
        classification: LiveClassification,
        correction: Optional[str],
        corrected_intent: Optional[str]
    ) -> None:
        """
        Log a correction for future training.

        Args:
            classification: The misclassified utterance
            correction: User's explanation
            corrected_intent: Correct intent
        """
        if not self.repo:
            logger.warning("No repository available for logging correction")
            return

        try:
            # Insert into corrections table
            self.repo.log_correction(
                original_log_id=classification.id,
                session_id=classification.session_id,
                original_input=classification.user_input,
                original_intent=classification.predicted_intent,
                original_payload=classification.predicted_payload,
                corrected_intent=corrected_intent,
                user_explanation=correction,
            )
            logger.info(
                f"Logged correction: '{classification.user_input[:30]}...' "
                f"({classification.predicted_intent} -> {corrected_intent or 'unknown'})"
            )
        except Exception as e:
            logger.error(f"Failed to log correction: {e}")

    def get_session_stats(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get accuracy statistics for the current or specified session.

        Args:
            session_id: Session to get stats for (defaults to current)

        Returns:
            Dict with total, correct, incorrect, accuracy
        """
        logger.debug("get_session_stats called with session_id=%s", session_id)
        if session_id and self.repo:
            try:
                return self.repo.get_analysis_stats(session_id=session_id)
            except Exception as e:
                logger.error(f"Failed to get session stats: {e}")

        # Calculate from in-memory classifications
        classifications = [
            c for c in self._session_classifications
            if session_id is None or c.session_id == session_id
        ]

        total = len(classifications)
        correct = sum(1 for c in classifications if c.feedback == "correct")
        incorrect = sum(1 for c in classifications if c.feedback == "incorrect")
        pending = total - correct - incorrect

        return {
            "total": total,
            "correct": correct,
            "incorrect": incorrect,
            "pending": pending,
            "accuracy": correct / total if total > 0 else 0.0,
        }

    def get_live_dashboard_data(self) -> Dict[str, Any]:
        """
        Get data for live dashboard display.

        Returns:
            Dict with current stats and recent activity
        """
        logger.debug("get_live_dashboard_data called")
        if self.repo:
            try:
                stats = self.repo.get_analysis_stats()
            except Exception:
                stats = self.get_session_stats()
        else:
            stats = self.get_session_stats()

        recent_classifications = self._session_classifications[-5:]
        recent_errors = [
            c for c in self._session_classifications
            if c.feedback == "incorrect"
        ][-5:]

        return {
            "total_classifications": stats.get("total", 0),
            "accuracy": stats.get("accuracy", 0.0),
            "pending_feedback": len([
                c for c in self._session_classifications
                if c.feedback is None
            ]),
            "recent_classifications": [
                {
                    "input": c.user_input[:50],
                    "intent": c.predicted_intent,
                    "confidence": c.confidence,
                    "feedback": c.feedback,
                }
                for c in recent_classifications
            ],
            "recent_errors": [
                {
                    "input": c.user_input[:50],
                    "predicted": c.predicted_intent,
                    "correction": c.correction,
                }
                for c in recent_errors
            ],
        }

    def format_stats_for_voice(self, session_id: Optional[str] = None) -> str:
        """
        Format statistics for voice output.

        Args:
            session_id: Session to get stats for

        Returns:
            German text Rachel can speak
        """
        logger.debug("format_stats_for_voice called with session_id=%s", session_id)
        stats = self.get_session_stats(session_id)

        total = stats.get("total", 0)
        correct = stats.get("correct", 0)
        accuracy = stats.get("accuracy", 0.0)

        if total == 0:
            return "Ich habe noch keine Statistiken. Bitte gib mir Feedback nach meinen Aktionen."

        return (
            f"Heute habe ich {total} Anfragen bearbeitet. "
            f"Davon waren {correct} richtig, das entspricht einer Genauigkeit von {accuracy * 100:.0f} Prozent."
        )

    def is_pending_correction(self) -> bool:
        """Check if we're waiting for a correction clarification."""
        return self._pending_correction

    def get_last_classification(self) -> Optional[LiveClassification]:
        """Get the most recent classification."""
        return self._last_classification

    def clear_session(self) -> None:
        """Clear session data (e.g., when starting new conversation)."""
        self._session_classifications = []
        self._last_classification = None
        self._pending_correction = False


# Singleton instance
_evaluator: Optional[RealtimeEvaluator] = None


def get_realtime_evaluator() -> RealtimeEvaluator:
    """Get or create RealtimeEvaluator singleton."""
    global _evaluator
    if _evaluator is None:
        _evaluator = RealtimeEvaluator()
    return _evaluator


__all__ = [
    "LiveClassification",
    "RealtimeEvaluator",
    "get_realtime_evaluator",
]
