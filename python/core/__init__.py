"""
VibeMind Core Module

Shared components used across all spaces:
- database: Data layer (models, repositories)
- llm: LLM clients (OpenRouter, Ollama)
- event_bus: Event system (Redis, routing)
- orchestrator: Intent classification and routing
- voice: Voice interface (VoiceBridgeV2)
- memory: Memory services (Supermemory integration)
"""

__all__ = [
    "database",
    "llm",
    "event_bus",
    "orchestrator",
    "voice",
    "memory",
]
