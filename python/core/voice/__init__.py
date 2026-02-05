"""
VibeMind Core Voice Module

Voice interface (VoiceBridgeV2) and TTS queue.
Re-exports from legacy swarm/ module for backward compatibility.
"""

# Re-export from legacy swarm module
from swarm.voice_bridge_v2 import (
    VoiceBridgeV2,
    VoiceBridgeResult,
    create_voice_bridge_v2,
)
from swarm.tts_queue import (
    TTSQueue,
    TTSPriority,
    get_tts_queue,
)
from swarm.navigation import SpaceType

__all__ = [
    # Voice Bridge
    "VoiceBridgeV2",
    "VoiceBridgeResult",
    "create_voice_bridge_v2",
    # TTS Queue
    "TTSQueue",
    "TTSPriority",
    "get_tts_queue",
    # Navigation
    "SpaceType",
]
