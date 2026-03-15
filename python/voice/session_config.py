"""
OpenAI Realtime API Session Configuration

Defines the session config and tool definitions for the
OpenAI Realtime voice connection.

Audio Format: PCM 16-bit, 24kHz, mono, little-endian
VAD: Client-side silence detection (server_vad disabled)
"""

import os
from typing import Dict, Any, List, Optional

# Defaults
DEFAULT_MODEL = "gpt-4o-realtime-preview"
DEFAULT_VOICE = "alloy"
DEFAULT_SAMPLE_RATE = 24000
SAMPLE_RATE = DEFAULT_SAMPLE_RATE  # Alias for convenience
DEFAULT_CHANNELS = 1

# Available voices for OpenAI Realtime
AVAILABLE_VOICES = ["alloy", "ash", "ballad", "coral", "echo", "sage", "shimmer", "verse"]


# =============================================================================
# Tool Definition: send_intent
# =============================================================================
# Single tool for all user intents. The OpenAI Realtime model uses
# Rachel's system prompt to understand context, and the IntentClassifier
# in the backend handles fine-grained routing.

SEND_INTENT_TOOL = {
    "type": "function",
    "name": "send_intent",
    "description": (
        "Sende den Wunsch des Users an das VibeMind System zur Ausfuehrung. "
        "Die Ausfuehrung laeuft asynchron — du erhaeltst das Ergebnis automatisch "
        "sobald es fertig ist. Verwende dieses Tool fuer ALLE Aktionen: "
        "Bubbles verwalten, Ideen erstellen, Desktop-Automatisierung, "
        "Code-Generierung, Recherche, Rowboat-Projekte. "
        "Das System erkennt automatisch welcher Bereich zustaendig ist."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "user_request": {
                "type": "string",
                "description": (
                    "Was der User moechte, in natuerlicher Sprache. "
                    "Beispiele: 'Zeig mir meine Bubbles', 'Erstelle eine Bubble Marketing', "
                    "'Oeffne Chrome', 'Erstelle eine React App'"
                ),
            }
        },
        "required": ["user_request"],
    },
}

# =============================================================================
# Tool Definition: check_results
# =============================================================================
# Secondary tool for Rachel to explicitly poll for async results.
# Results are also pushed automatically via inject_system_message,
# but this tool lets Rachel proactively check on long-running tasks.

CHECK_RESULTS_TOOL = {
    "type": "function",
    "name": "check_results",
    "description": (
        "Pruefe ob neue Ergebnisse von laufenden Aufgaben vorliegen. "
        "Verwende dieses Tool wenn der User fragt 'Gibt es Neuigkeiten?', "
        "'Was ist mit meiner Anfrage?', oder wenn du laenger keine "
        "Rueckmeldung bekommen hast. Ergebnisse kommen auch automatisch — "
        "dieses Tool ist fuer explizite Nachfragen."
    ),
    "parameters": {
        "type": "object",
        "properties": {},
    },
}


def create_session_config(
    system_prompt: str,
    voice: Optional[str] = None,
    model: Optional[str] = None,
    tools: Optional[List[Dict[str, Any]]] = None,
    vad_type: str = "server_vad",
    vad_threshold: float = 0.5,
    silence_duration_ms: int = 500,
    prefix_padding_ms: int = 300,
) -> Dict[str, Any]:
    """
    Create OpenAI Realtime session configuration.

    Args:
        system_prompt: System instructions for the voice agent (Rachel's prompt)
        voice: Voice to use (default: from env or 'alloy')
        model: Model to use (default: from env or 'gpt-4o-realtime-preview')
        tools: List of tool definitions (default: [SEND_INTENT_TOOL])
        vad_type: VAD type - 'server_vad' or 'semantic_vad'
        vad_threshold: VAD sensitivity threshold (0.0-1.0)
        silence_duration_ms: Silence before end-of-turn (ms)
        prefix_padding_ms: Audio to include before speech start (ms)

    Returns:
        Session configuration dict for session.update event
    """
    voice = voice or os.getenv("OPENAI_REALTIME_VOICE", DEFAULT_VOICE)
    model = model or os.getenv("OPENAI_REALTIME_MODEL", DEFAULT_MODEL)

    if voice not in AVAILABLE_VOICES:
        voice = DEFAULT_VOICE

    if tools is None:
        tools = [SEND_INTENT_TOOL, CHECK_RESULTS_TOOL]

    # Build turn_detection config based on type
    if vad_type == "semantic_vad":
        turn_detection_config = {
            "type": "semantic_vad",
            "eagerness": "auto",
            "create_response": True,
            "interrupt_response": True,
        }
    else:
        turn_detection_config = {
            "type": "server_vad",
            "threshold": vad_threshold,
            "prefix_padding_ms": prefix_padding_ms,
            "silence_duration_ms": silence_duration_ms,
            "create_response": True,
            "interrupt_response": True,
        }

    # Beta format — flat fields for gpt-4o-realtime-preview via
    # client.beta.realtime.connect().  The beta WebSocket protocol expects
    # flat session fields (input_audio_format, voice, modalities, etc.)
    # rather than the nested GA REST format (audio.input.format...).
    #
    # Turn detection: Use semantic_vad (AI-based) instead of server_vad
    # or None.  semantic_vad understands speech patterns and pauses,
    # so the user can think mid-sentence without being cut off.
    # "eagerness: low" = Rachel waits longer before assuming user is done.
    #
    # NOTE: server_vad was found to silently discard audio.  semantic_vad
    # is a different system and does not have this issue.
    # Client-side silence detection (openai_realtime.py) serves as a
    # 2-second fallback safety net in case semantic_vad fails.
    use_semantic_vad = os.getenv("VOICE_TURN_DETECTION", "semantic_vad")

    if use_semantic_vad == "semantic_vad":
        td_config = {
            "type": "semantic_vad",
            "eagerness": os.getenv("VOICE_VAD_EAGERNESS", "low"),
            "create_response": True,
            "interrupt_response": True,
        }
    elif use_semantic_vad == "server_vad":
        td_config = {
            "type": "server_vad",
            "threshold": vad_threshold,
            "prefix_padding_ms": prefix_padding_ms,
            "silence_duration_ms": silence_duration_ms,
            "create_response": True,
            "interrupt_response": True,
        }
    else:
        td_config = None  # Client-side only

    config = {
        "modalities": ["text", "audio"],
        "instructions": system_prompt,
        "voice": voice,
        "input_audio_format": "pcm16",
        "output_audio_format": "pcm16",
        "input_audio_transcription": {
            "model": "whisper-1",
        },
        "turn_detection": td_config,
        "tools": tools,
        "tool_choice": "auto",
    }

    return config


def get_model() -> str:
    """Get the configured Realtime model name."""
    return os.getenv("OPENAI_REALTIME_MODEL", DEFAULT_MODEL)


def get_voice() -> str:
    """Get the configured voice name."""
    voice = os.getenv("OPENAI_REALTIME_VOICE", DEFAULT_VOICE)
    if voice not in AVAILABLE_VOICES:
        return DEFAULT_VOICE
    return voice
