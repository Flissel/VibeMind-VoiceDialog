"""
Structured JSON logging for intent classification.

Logs each classification to a JSONL file for later analysis.
Tracks latency, post-processing rules, and context.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


class IntentLogger:
    """
    Structured JSON logging for intent classification.

    Writes one JSON object per line (JSONL format) to daily log files.
    """

    def __init__(self, log_dir: str = "logs/intents"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._current_date = None
        self._current_file = None
        logger.info(f"IntentLogger initialized, writing to {self.log_dir}")

    def _get_log_file(self) -> Path:
        """Get current log file path, rotating daily."""
        today = datetime.now().strftime("%Y-%m-%d")
        if self._current_date != today:
            self._current_date = today
            self._current_file = self.log_dir / f"intents_{today}.jsonl"
        return self._current_file

    def log_classification(
        self,
        session_id: str,
        user_input: str,
        classification: Dict[str, Any],
        latency_ms: float,
        original_intent: Optional[str] = None,
        rules_applied: Optional[List[str]] = None,
        context: Optional[Dict[str, Any]] = None,
        llm_model: Optional[str] = None,
        tokens_in: Optional[int] = None,
        tokens_out: Optional[int] = None
    ):
        """
        Log a single intent classification.

        Args:
            session_id: Unique session identifier
            user_input: Original user utterance
            classification: Final classification result (event_type, payload, etc.)
            latency_ms: Time taken for classification in milliseconds
            original_intent: Intent before post-processing (if different)
            rules_applied: List of post-processing rules that fired
            context: Additional context (current_bubble, ideas_count, etc.)
            llm_model: Model used for classification
            tokens_in: Input tokens used
            tokens_out: Output tokens generated
        """
        # Build entry
        entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "session_id": session_id,
            "user_input": user_input,
            "classification": {
                "event_type": classification.get("event_type"),
                "payload": classification.get("payload", {}),
                "is_multi_step": classification.get("is_multi_step", False),
                "response_hint": classification.get("response_hint", "")
            },
            "metrics": {
                "latency_ms": round(latency_ms, 2),
                "llm_model": llm_model,
                "tokens_in": tokens_in,
                "tokens_out": tokens_out
            },
            "post_processing": {
                "original_intent": original_intent,
                "rules_applied": rules_applied or [],
                "was_corrected": (
                    original_intent is not None and
                    original_intent != classification.get("event_type")
                )
            },
            "context": context or {}
        }

        # Handle multi-step classifications
        if classification.get("is_multi_step"):
            entry["classification"]["steps"] = classification.get("steps", [])

        # HybridRouter routing info (if provided)
        if context and "route" in context:
            route = context["route"]
            entry["routing"] = {
                "space": route.get("space"),
                "agent": route.get("agent"),
                "tier": route.get("tier"),
                "matched_by": route.get("matched_by"),
                "cached": route.get("cached", False),
                "route_ms": route.get("route_ms"),
            }

        # Write to file
        try:
            log_file = self._get_log_file()
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error(f"Failed to write intent log: {e}")

    def log_error(
        self,
        session_id: str,
        user_input: str,
        error: str,
        latency_ms: float
    ):
        """Log a classification error."""
        entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "session_id": session_id,
            "user_input": user_input,
            "error": error,
            "metrics": {
                "latency_ms": round(latency_ms, 2)
            }
        }

        try:
            log_file = self._get_log_file()
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error(f"Failed to write error log: {e}")


# Singleton instance
_intent_logger: Optional[IntentLogger] = None


def get_intent_logger() -> IntentLogger:
    """Get or create IntentLogger singleton."""
    global _intent_logger
    if _intent_logger is None:
        _intent_logger = IntentLogger()
    return _intent_logger


__all__ = ["IntentLogger", "get_intent_logger"]
