"""
Question Listener - Receives questions from Backend Agents.

Subscribes to events:questions stream and queues for Rachel.

Architecture:
    Backend Agent → _ask_question() → events:questions
                                            ↓
                                    QuestionListener
                                            ↓
                                    QuestionQueue
                                            ↓
                            Rachel.process_input() checks queue
"""

import logging
import sys
from typing import Optional, Any

logger = logging.getLogger(__name__)


def _debug_print(msg: str):
    """Print debug message to stderr for visibility in Electron."""
    print(f"[Python DEBUG] [QuestionListener] {msg}", file=sys.stderr)


class QuestionListener:
    """
    Listens to events:questions stream and queues for Rachel.

    Backend agents publish questions via _ask_question().
    Rachel checks the QuestionQueue on every user input.
    """

    STREAM = "events:questions"

    def __init__(self, question_queue: Any = None):
        """
        Initialize QuestionListener.

        Args:
            question_queue: Optional pre-configured QuestionQueue
        """
        self._question_queue = question_queue
        self._event_bus = None
        self._running = False

    @property
    def event_bus(self):
        """Lazy-load EventBus."""
        if self._event_bus is None:
            from swarm.event_bus import get_event_bus
            self._event_bus = get_event_bus()
        return self._event_bus

    @property
    def question_queue(self):
        """Lazy-load QuestionQueue."""
        if self._question_queue is None:
            from swarm.orchestrator.question_queue import get_question_queue
            self._question_queue = get_question_queue()
        return self._question_queue

    def set_question_queue(self, queue):
        """Set the question queue instance."""
        self._question_queue = queue

    async def start(self) -> None:
        """Start listening for questions."""
        if self._running:
            _debug_print("Already running, skipping start")
            return

        await self.event_bus.subscribe(self.STREAM, self._handle_question)
        self._running = True

        _debug_print(f"Subscribed to {self.STREAM}")
        logger.info(f"[QuestionListener] Subscribed to {self.STREAM}")

    async def stop(self) -> None:
        """Stop listening."""
        self._running = False
        _debug_print("Stopped")
        logger.info("[QuestionListener] Stopped")

    async def _handle_question(self, event) -> None:
        """
        Handle incoming question event.

        Args:
            event: SwarmEvent from events:questions stream
        """
        try:
            payload = event.payload
            job_id = event.job_id or ""

            question = payload.get("question", "")
            if not question:
                logger.warning("[QuestionListener] Received empty question, ignoring")
                return

            self.question_queue.add_question(
                job_id=job_id,
                question=question,
                options=payload.get("options", []),
                context=payload.get("context", ""),
                agent=payload.get("agent", ""),
                event_type=event.event_type,
                priority=payload.get("priority", 0)
            )

            _debug_print(f"Queued question: {question[:50]}... (job={job_id})")
            logger.debug(f"[QuestionListener] Queued: {event.event_type} (job={job_id})")

        except Exception as e:
            _debug_print(f"Error handling question: {e}")
            logger.error(f"[QuestionListener] Error: {e}")

    @property
    def is_running(self) -> bool:
        """Check if listener is running."""
        return self._running


# Singleton
_question_listener: Optional[QuestionListener] = None


def get_question_listener(question_queue: Any = None) -> QuestionListener:
    """
    Get or create question listener singleton.

    Args:
        question_queue: Optional QuestionQueue to use

    Returns:
        QuestionListener instance
    """
    global _question_listener
    if _question_listener is None:
        _question_listener = QuestionListener(question_queue)
    return _question_listener


def reset_question_listener() -> None:
    """Reset the question listener singleton (for testing)."""
    global _question_listener
    if _question_listener is not None:
        _question_listener._running = False
    _question_listener = None


__all__ = [
    "QuestionListener",
    "get_question_listener",
    "reset_question_listener",
]
