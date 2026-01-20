"""
ElevenLabs Input Processing - Enhanced metadata extraction for VibeMind

Extracts transcript + metadata from ElevenLabs conversation events
for improved intent analysis and context enrichment.
"""

import logging
from dataclasses import dataclass
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class ElevenLabsInput:
    """
    Enhanced input structure for ElevenLabs conversation events.

    Contains transcript plus all available metadata for context enrichment.
    """
    # Core transcript data
    transcript: str
    transcript_confidence: float = 0.0

    # Language detection
    detected_language: str = "unknown"

    # Audio metadata
    audio_duration: float = 0.0

    # User identification
    user_id: Optional[str] = None

    # Intent detection (if available from ElevenLabs)
    intent_detected: Optional[str] = None
    intent_confidence: Optional[float] = None

    # Session context
    conversation_id: str = ""
    session_metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.session_metadata is None:
            self.session_metadata = {}

    def has_confident_transcript(self, threshold: float = 0.8) -> bool:
        """Check if transcript confidence is above threshold."""
        return self.transcript_confidence >= threshold

    def has_detected_intent(self) -> bool:
        """Check if ElevenLabs detected an intent."""
        return self.intent_detected is not None and self.intent_confidence is not None

    def get_intent_confidence(self) -> float:
        """Get intent confidence, defaulting to 0.0 if not available."""
        return self.intent_confidence or 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging/serialization."""
        return {
            "transcript": self.transcript,
            "transcript_confidence": self.transcript_confidence,
            "detected_language": self.detected_language,
            "audio_duration": self.audio_duration,
            "user_id": self.user_id,
            "intent_detected": self.intent_detected,
            "intent_confidence": self.intent_confidence,
            "conversation_id": self.conversation_id,
            "session_metadata": self.session_metadata,
        }


def extract_elevenlabs_metadata(conversation_event: Dict[str, Any]) -> ElevenLabsInput:
    """
    Extract all available metadata from ElevenLabs conversation event.

    Args:
        conversation_event: Raw event from ElevenLabs API

    Returns:
        ElevenLabsInput with extracted metadata
    """
    try:
        # Extract user message data
        user_message = conversation_event.get("user_message", {})
        message_metadata = user_message.get("metadata", {})

        # Extract agent response data (for intent detection if available)
        agent_response = conversation_event.get("agent_response", {})
        agent_metadata = agent_response.get("metadata", {})

        # Build ElevenLabsInput
        elevenlabs_input = ElevenLabsInput(
            transcript=user_message.get("message", ""),
            transcript_confidence=float(message_metadata.get("transcript_confidence", 0.0)),
            detected_language=message_metadata.get("detected_language", "unknown"),
            audio_duration=float(message_metadata.get("audio_duration", 0.0)),
            user_id=message_metadata.get("user_id"),
            intent_detected=agent_metadata.get("intent_detected"),
            intent_confidence=float(agent_metadata.get("intent_confidence", 0.0)) if agent_metadata.get("intent_confidence") else None,
            conversation_id=conversation_event.get("conversation_id", ""),
            session_metadata=conversation_event.get("metadata", {}),
        )

        # Log extraction for debugging
        logger.debug(f"Extracted ElevenLabs metadata: transcript_confidence={elevenlabs_input.transcript_confidence}, "
                    f"intent={elevenlabs_input.intent_detected} ({elevenlabs_input.intent_confidence})")

        return elevenlabs_input

    except Exception as e:
        logger.error(f"Error extracting ElevenLabs metadata: {e}")
        # Return minimal input on error
        return ElevenLabsInput(
            transcript=conversation_event.get("user_message", {}).get("message", ""),
            session_metadata={"error": str(e)}
        )


def validate_elevenlabs_input(elevenlabs_input: ElevenLabsInput) -> bool:
    """
    Validate ElevenLabsInput for required fields and sanity checks.

    Args:
        elevenlabs_input: Input to validate

    Returns:
        True if valid, False otherwise
    """
    # Must have transcript
    if not elevenlabs_input.transcript or not elevenlabs_input.transcript.strip():
        logger.warning("ElevenLabsInput validation failed: missing transcript")
        return False

    # Transcript confidence should be reasonable
    if elevenlabs_input.transcript_confidence < 0.0 or elevenlabs_input.transcript_confidence > 1.0:
        logger.warning(f"ElevenLabsInput validation failed: invalid transcript_confidence {elevenlabs_input.transcript_confidence}")
        return False

    # Intent confidence should be reasonable if present
    if elevenlabs_input.intent_confidence is not None:
        if elevenlabs_input.intent_confidence < 0.0 or elevenlabs_input.intent_confidence > 1.0:
            logger.warning(f"ElevenLabsInput validation failed: invalid intent_confidence {elevenlabs_input.intent_confidence}")
            return False

    return True


# TEST MARKER - ElevenLabs Metadata Integration
def test_elevenlabs_metadata_extraction():
    """
    Test function for ElevenLabs metadata extraction.
    Used during development and testing.
    """
    # Sample conversation event
    sample_event = {
        "conversation_id": "conv_123",
        "user_message": {
            "message": "Erstelle eine neue Idee für ein Projekt",
            "metadata": {
                "transcript_confidence": 0.95,
                "detected_language": "de",
                "audio_duration": 2.3,
                "user_id": "user_456"
            }
        },
        "agent_response": {
            "message": "Ich erstelle eine neue Idee...",
            "metadata": {
                "intent_detected": "idea.create",
                "intent_confidence": 0.87
            }
        },
        "metadata": {
            "session_start": "2024-01-01T10:00:00Z",
            "agent_version": "1.0"
        }
    }

    # Extract metadata
    extracted = extract_elevenlabs_metadata(sample_event)

    # Validate
    is_valid = validate_elevenlabs_input(extracted)

    print(f"Extraction test: valid={is_valid}")
    print(f"Transcript: {extracted.transcript}")
    print(f"Confidence: {extracted.transcript_confidence}")
    print(f"Intent: {extracted.intent_detected} ({extracted.intent_confidence})")

    return extracted, is_valid


if __name__ == "__main__":
    # Run test when executed directly
    test_elevenlabs_metadata_extraction()