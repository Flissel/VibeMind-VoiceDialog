"""
MoireTracker v2 Core Module

Enthält:
- EventQueue: Task/Action/Result Queue System
- OpenRouterClient: Unified LLM API für verschiedene Modelle
"""

from .event_queue import (
    EventQueue,
    get_event_queue,
    TaskEvent,
    ActionEvent,
    ValidationEvent,
    TaskStatus,
    ActionStatus,
    EventType
)

from .openrouter_client import (
    OpenRouterClient,
    get_openrouter_client,
    ModelType,
    LLMResponse
)

__all__ = [
    "EventQueue",
    "get_event_queue",
    "TaskEvent",
    "ActionEvent", 
    "ValidationEvent",
    "TaskStatus",
    "ActionStatus",
    "EventType",
    "OpenRouterClient",
    "get_openrouter_client",
    "ModelType",
    "LLMResponse"
]