"""
StreamListener — LLM-based parallel intent routing.

Each Space has its own LLM listener that evaluates user input
and returns a confidence score. All listeners run in parallel,
the highest confidence wins.
"""

from .models import (
    EvalContext,
    ListenerEvaluation,
    ConfidenceDistribution,
    StreamListenerConfig,
)
from .base_listener import BaseStreamListener
from .dispatcher import (
    StreamListenerDispatcher,
    get_stream_listener_dispatcher,
    reset_stream_listener_dispatcher,
)

__all__ = [
    "EvalContext",
    "ListenerEvaluation",
    "ConfidenceDistribution",
    "StreamListenerConfig",
    "BaseStreamListener",
    "StreamListenerDispatcher",
    "get_stream_listener_dispatcher",
    "reset_stream_listener_dispatcher",
]
