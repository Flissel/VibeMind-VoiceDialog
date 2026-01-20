"""
Context providers for VibeMind swarm.

Provides contextual information about the current state
(current bubble, ideas, etc.) for use in intent classification
and response generation.
"""

from .bubble_context_provider import (
    BubbleContextProvider,
    get_bubble_context_provider,
)

from .real_time_state import (
    SystemState,
    RealTimeStateStore,
    get_real_time_state,
    reset_real_time_state,
)

__all__ = [
    # Bubble context
    "BubbleContextProvider",
    "get_bubble_context_provider",
    # Real-time state
    "SystemState",
    "RealTimeStateStore",
    "get_real_time_state",
    "reset_real_time_state",
]
