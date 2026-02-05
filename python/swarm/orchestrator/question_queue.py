"""
Question Queue for Backend → Rachel communication.

Backend agents can publish questions that Rachel will ask
the user at the next opportunity.

Architecture:
    Backend Agent → events:questions → QuestionListener → QuestionQueue
                                                              ↓
    Rachel.process_input() checks queue → asks user → answer_question()
"""

import logging
import time
import threading
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)


@dataclass
class PendingQuestion:
    """A question waiting for user response."""
    job_id: str
    question: str
    options: List[str] = field(default_factory=list)
    context: str = ""
    agent: str = ""
    event_type: str = ""
    timestamp: float = field(default_factory=time.time)
    priority: int = 0  # Higher = more urgent


class QuestionQueue:
    """
    Thread-safe queue for pending questions.

    Backend agents publish questions → QuestionListener queues them
    Rachel checks queue on every input → retrieves and clears
    """

    def __init__(self, max_age_seconds: float = 300.0):
        """
        Initialize question queue.

        Args:
            max_age_seconds: Questions older than this are auto-expired (default 5 min)
        """
        self._questions: List[PendingQuestion] = []
        self._lock = threading.Lock()
        self._max_age = max_age_seconds

    def add_question(
        self,
        job_id: str,
        question: str,
        options: List[str] = None,
        context: str = "",
        agent: str = "",
        event_type: str = "",
        priority: int = 0
    ) -> None:
        """
        Add a question to the queue.

        Args:
            job_id: Job ID for response correlation
            question: Question text to ask user
            options: Optional list of answer options
            context: Additional context for the question
            agent: Name of the agent asking
            event_type: Original event type
            priority: 0=normal, 1=high, 2=urgent
        """
        with self._lock:
            q = PendingQuestion(
                job_id=job_id,
                question=question,
                options=options or [],
                context=context,
                agent=agent,
                event_type=event_type,
                priority=priority
            )
            self._questions.append(q)
            logger.info(f"[QuestionQueue] Added: {question[:50]}... (job={job_id}, priority={priority})")

    def get_and_clear(self) -> List[PendingQuestion]:
        """
        Get all pending questions and clear the queue.

        Questions are sorted by priority (highest first).
        Expired questions are filtered out.

        Returns:
            List of pending questions
        """
        with self._lock:
            # Filter out expired questions
            now = time.time()
            valid = [q for q in self._questions if (now - q.timestamp) < self._max_age]

            expired_count = len(self._questions) - len(valid)
            if expired_count > 0:
                logger.debug(f"[QuestionQueue] Expired {expired_count} old questions")

            # Sort by priority (highest first)
            valid.sort(key=lambda q: q.priority, reverse=True)

            # Clear queue
            self._questions.clear()

            if valid:
                logger.info(f"[QuestionQueue] Retrieved {len(valid)} questions")

            return valid

    def has_pending(self) -> bool:
        """Check if there are pending questions."""
        with self._lock:
            return len(self._questions) > 0

    def pending_count(self) -> int:
        """Get count of pending questions."""
        with self._lock:
            return len(self._questions)

    def format_for_context(self, questions: List[PendingQuestion]) -> str:
        """
        Format questions for Rachel's LLM context.

        Args:
            questions: List of pending questions

        Returns:
            Formatted string for LLM context
        """
        if not questions:
            return ""

        lines = []
        for q in questions:
            # Build question line
            line = f"- [job={q.job_id}] {q.question}"

            # Add options if present
            if q.options:
                line += f" (Optionen: {', '.join(q.options)})"

            # Add context if present
            if q.context:
                line += f" [Kontext: {q.context}]"

            # Add agent info
            if q.agent:
                line += f" [von: {q.agent}]"

            lines.append(line)

        return "\n".join(lines)

    def peek(self) -> Optional[PendingQuestion]:
        """
        Peek at the highest priority question without removing.

        Returns:
            Highest priority question or None
        """
        with self._lock:
            if not self._questions:
                return None

            # Filter valid and sort
            now = time.time()
            valid = [q for q in self._questions if (now - q.timestamp) < self._max_age]
            if not valid:
                return None

            valid.sort(key=lambda q: q.priority, reverse=True)
            return valid[0]


# Singleton
_question_queue: Optional[QuestionQueue] = None


def get_question_queue() -> QuestionQueue:
    """Get or create the global question queue."""
    global _question_queue
    if _question_queue is None:
        _question_queue = QuestionQueue()
    return _question_queue


def reset_question_queue() -> None:
    """Reset the question queue singleton (for testing)."""
    global _question_queue
    _question_queue = None


__all__ = [
    "QuestionQueue",
    "PendingQuestion",
    "get_question_queue",
    "reset_question_queue",
]
