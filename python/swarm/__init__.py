"""
VibeMind Swarm Package

AutoGen 0.4 Swarm implementation for multi-agent voice dialog.
Uses Ollama for local LLM inference and Redis for event streams.

Architecture:
- Navigation Layer: Space switching (like Electron multiverse)
- User Agents: Rachel, Antoni, Adam for user interaction
- Workers: Autonomous task execution per space
- Event Buffer: Input queuing and correction detection
- TTS Queue: Priority-based speech output
"""

from .ollama_client import get_ollama_client, OllamaModelClient
from .event_streams import RedisEventManager, InMemoryEventStore, get_event_manager
from .navigation import (
    NavigationLayer,
    NavigationEvent,
    SpaceType,
    get_navigation_layer,
)
from .space import Space, SpaceConfig, SpaceRegistry, get_space_registry
from .event_buffer import (
    EventBuffer,
    InputEvent,
    TaskInfo,
    TaskStatus,
    get_event_buffer,
)
from .tts_queue import TTSQueue, TTSItem, TTSPriority, get_tts_queue

__all__ = [
    # Ollama
    "get_ollama_client",
    "OllamaModelClient",
    # Event Streams
    "RedisEventManager",
    "InMemoryEventStore",
    "get_event_manager",
    # Navigation
    "NavigationLayer",
    "NavigationEvent",
    "SpaceType",
    "get_navigation_layer",
    # Spaces
    "Space",
    "SpaceConfig",
    "SpaceRegistry",
    "get_space_registry",
    # Event Buffer
    "EventBuffer",
    "InputEvent",
    "TaskInfo",
    "TaskStatus",
    "get_event_buffer",
    # TTS Queue
    "TTSQueue",
    "TTSItem",
    "TTSPriority",
    "get_tts_queue",
]
