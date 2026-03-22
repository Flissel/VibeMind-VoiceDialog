"""
StreamListenerDispatcher — Parallel fan-out to all domain listeners.

Evaluates ALL listeners in parallel via asyncio.gather and returns
a ConfidenceDistribution with the winner.
"""

import time
import asyncio
import logging
from typing import List, Optional

from .models import (
    ListenerEvaluation,
    ConfidenceDistribution,
    EvalContext,
    StreamListenerConfig,
)
from llm_config import get_model, get_client
from .base_listener import BaseStreamListener

logger = logging.getLogger(__name__)

_logger = logging.getLogger(__name__)


class StreamListenerDispatcher:
    """
    Fan-out dispatcher: evaluates all StreamListeners in parallel
    and returns a confidence distribution.
    """

    def __init__(self, config: Optional[StreamListenerConfig] = None):
        self._config = config or StreamListenerConfig(
            model=get_model("stream_listener"),
        )
        self._listeners: List[BaseStreamListener] = []
        self._shared_client = None

    def register_listener(self, listener: BaseStreamListener) -> None:
        """Register a domain listener."""
        # Inject shared client
        if self._shared_client:
            listener.set_client(self._shared_client)
        self._listeners.append(listener)
        logger.info(f"[StreamDispatcher] Registered listener: {listener.name}")

    def _ensure_shared_client(self) -> None:
        """Create shared client for all listeners via llm_config."""
        if self._shared_client is not None:
            return

        try:
            self._shared_client = get_client("stream_listener")
            # Inject into all registered listeners
            for listener in self._listeners:
                listener.set_client(self._shared_client)
            logger.info("[StreamDispatcher] Shared LLM client created via llm_config")
        except Exception as e:
            logger.error(f"[StreamDispatcher] Failed to create shared client: {e}")

    async def evaluate_all(
        self, text: str, context: EvalContext
    ) -> ConfidenceDistribution:
        """
        Evaluate ALL listeners in parallel and return confidence distribution.

        Args:
            text: User input text
            context: Conversation history and state

        Returns:
            ConfidenceDistribution with all evaluations and winner
        """
        self._ensure_shared_client()
        start = time.perf_counter()

        if not self._listeners:
            logger.warning("[StreamDispatcher] No listeners registered!")
            return ConfidenceDistribution(
                evaluations=[],
                winner=None,
                is_ambiguous=False,
                total_latency_ms=0.0,
            )

        # Fan out to ALL listeners in parallel
        tasks = [
            asyncio.wait_for(
                listener.evaluate(
                    text, context,
                    model=self._config.model,
                    temperature=self._config.temperature,
                ),
                timeout=self._config.timeout_seconds,
            )
            for listener in self._listeners
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Collect successful evaluations
        evaluations: List[ListenerEvaluation] = []
        for i, result in enumerate(results):
            if isinstance(result, ListenerEvaluation):
                evaluations.append(result)
            elif isinstance(result, Exception):
                listener_name = self._listeners[i].name if i < len(self._listeners) else "?"
                err_type = type(result).__name__
                err_msg = str(result) or "(no message)"
                logger.warning(f"[StreamDispatcher] {listener_name} failed: {err_type}: {err_msg}")
                _logger.debug(f"[STREAM LISTENER] {listener_name} ERROR: {err_type}: {err_msg}")
                evaluations.append(ListenerEvaluation(
                    space=listener_name,
                    confidence=0.0,
                    event_type="none",
                    reasoning=f"{err_type}: {err_msg}",
                ))

        # Sort by confidence (highest first)
        evaluations.sort(key=lambda e: e.confidence, reverse=True)

        # Determine winner
        winner = None
        if evaluations and evaluations[0].confidence >= self._config.min_confidence:
            winner = evaluations[0]

        # Check ambiguity (top-2 too close)
        is_ambiguous = (
            len(evaluations) >= 2
            and evaluations[0].confidence >= self._config.min_confidence
            and (evaluations[0].confidence - evaluations[1].confidence) < self._config.ambiguity_threshold
        )

        total_ms = (time.perf_counter() - start) * 1000

        distribution = ConfidenceDistribution(
            evaluations=evaluations,
            winner=winner,
            is_ambiguous=is_ambiguous,
            total_latency_ms=total_ms,
        )

        # Log distribution
        _logger.debug(f"[STREAM LISTENER] {distribution.log_distribution()} ({total_ms:.0f}ms)")

        return distribution


# Singleton
_dispatcher: Optional[StreamListenerDispatcher] = None


def get_stream_listener_dispatcher() -> StreamListenerDispatcher:
    """Get or create the StreamListenerDispatcher singleton with all listeners."""
    global _dispatcher
    if _dispatcher is None:
        _dispatcher = StreamListenerDispatcher()
        _register_all_listeners(_dispatcher)
    return _dispatcher


def reset_stream_listener_dispatcher() -> None:
    """Reset singleton (for testing)."""
    global _dispatcher
    _dispatcher = None


def _register_all_listeners(dispatcher: StreamListenerDispatcher) -> None:
    """Register all domain listeners."""
    from .listeners.ideas_listener import IdeasStreamListener
    from .listeners.coding_listener import CodingStreamListener
    from .listeners.desktop_listener import DesktopStreamListener
    from .listeners.roarboot_listener import RoarbootStreamListener
    from .listeners.research_listener import ResearchStreamListener
    from .listeners.minibook_listener import MinibookStreamListener
    from .listeners.shuttles_listener import ShuttlesStreamListener
    from .listeners.conversational_listener import ConversationalStreamListener

    dispatcher.register_listener(IdeasStreamListener())
    dispatcher.register_listener(CodingStreamListener())
    dispatcher.register_listener(DesktopStreamListener())
    dispatcher.register_listener(RoarbootStreamListener())
    dispatcher.register_listener(ResearchStreamListener())
    dispatcher.register_listener(MinibookStreamListener())
    dispatcher.register_listener(ShuttlesStreamListener())
    dispatcher.register_listener(ConversationalStreamListener())

    logger.info(f"[StreamDispatcher] Registered {len(dispatcher._listeners)} listeners")
