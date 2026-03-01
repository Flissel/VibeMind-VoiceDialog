"""
Voice Layer Package for VibeMind

Provides voice I/O abstraction supporting multiple providers:
- OpenAI Realtime API (default) - Speech-to-Speech with native function calling
- ElevenLabs Conversational AI (legacy fallback)

The voice layer ONLY handles audio I/O and speech interaction.
All backend logic (Orchestrator, Agents, Tools) remains unchanged.

Architecture:
    Microphone → AudioManager → OpenAIRealtimeVoiceSession → WebSocket
                                         ↓ (send_intent tool call)
                                    Orchestrator → Backend Agents
                                         ↓ (status/results)
                                    TTS Response → Speaker
"""

from voice.session_config import (
    create_session_config,
    SEND_INTENT_TOOL,
    DEFAULT_VOICE,
    DEFAULT_MODEL,
)
from voice.audio_manager import AudioManager
from voice.openai_realtime import OpenAIRealtimeVoiceSession

__all__ = [
    "OpenAIRealtimeVoiceSession",
    "AudioManager",
    "create_session_config",
    "SEND_INTENT_TOOL",
    "DEFAULT_VOICE",
    "DEFAULT_MODEL",
]
