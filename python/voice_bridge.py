"""
Voice Bridge - Connects speech input/output with agent system and visuals
Audio from TTS will drive the visual animations via AudioAnalyzer
"""

import asyncio
import io
import sys
import numpy as np
from typing import Optional, Callable
import speech_recognition as sr
from elevenlabs import ElevenLabs, VoiceSettings
from agent_orchestrator import get_orchestrator


def safe_print(text: str):
    """
    Safely print text, handling Unicode characters that Windows console can't encode
    Strips emoji and special Unicode characters to prevent UnicodeEncodeError
    """
    try:
        # Try to encode with console encoding
        text.encode(sys.stdout.encoding or 'utf-8')
        print(text)
    except (UnicodeEncodeError, AttributeError):
        # Fallback: encode to ASCII, replacing problematic characters
        safe_text = text.encode('ascii', 'replace').decode('ascii')
        print(safe_text)


# ElevenLabs premade voice name to ID mapping
VOICE_IDS = {
    "Rachel": "21m00Tcm4TlvDq8ikWAM",
    "Domi": "AZnzlk1XvdvUeBnXmlld",
    "Bella": "EXAVITQu4vr4xnSDxMaL",
    "Antoni": "ErXwobaYiN019PkySvjV",
    "Elli": "MF3mGyEYCl7XYWbV9V6O",
    "Josh": "TxGEqnHWrfWFTfGW9XjX",
    "Arnold": "VR6AewLTigWG4xSOukaG",
    "Adam": "pNInz6obpgDQGcFmaJgB",
    "Sam": "yoZ06aMxZJJ28mfd3POQ",
}


class VoiceBridge:
    """
    Bridge between voice I/O, agents, and visual system

    Flow:
    1. User speaks → Speech-to-text
    2. Text → Agent system
    3. Agent response → ElevenLabs TTS
    4. TTS audio → AudioAnalyzer (drives visuals!)
    """

    def __init__(self, elevenlabs_api_key: Optional[str] = None, openai_api_key: Optional[str] = None):
        """
        Initialize voice bridge

        Args:
            elevenlabs_api_key: ElevenLabs API key for TTS
            openai_api_key: OpenAI API key for agents (optional, demo mode without it)
        """
        self.elevenlabs_api_key = elevenlabs_api_key
        self.openai_api_key = openai_api_key

        # Speech recognition
        self.recognizer = sr.Recognizer()
        self.microphone = None

        # TTS client
        self.tts_client = None
        if elevenlabs_api_key:
            self.tts_client = ElevenLabs(api_key=elevenlabs_api_key)

        # Agent orchestrator
        self.orchestrator = None

        # Callbacks
        self.audio_callback: Optional[Callable] = None  # Called with audio chunks for visuals
        self.text_callback: Optional[Callable] = None   # Called with text transcriptions
        self.response_callback: Optional[Callable] = None  # Called with agent responses

        # State
        self.listening = False
        self.speaking = False

    async def initialize(self):
        """Initialize all systems"""
        print("[VOICE BRIDGE] Initializing...")

        # Initialize agent orchestrator
        self.orchestrator = await get_orchestrator(api_key=self.openai_api_key)

        # Set up microphone
        try:
            self.microphone = sr.Microphone()
            with self.microphone as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
            print("[VOICE BRIDGE] Microphone ready")
        except Exception as e:
            print(f"[VOICE BRIDGE] Warning: Microphone error: {e}")

        print("[VOICE BRIDGE] Ready!")

    def set_audio_callback(self, callback: Callable):
        """
        Set callback for audio chunks (feeds into visual system)

        Args:
            callback: Function(audio_chunk: np.ndarray) called with audio data
        """
        self.audio_callback = callback

    def set_text_callback(self, callback: Callable):
        """
        Set callback for transcribed text

        Args:
            callback: Function(text: str) called with recognized speech
        """
        self.text_callback = callback

    def set_response_callback(self, callback: Callable):
        """
        Set callback for agent responses

        Args:
            callback: Function(text: str) called with agent response text
        """
        self.response_callback = callback

    async def listen_once(self) -> Optional[str]:
        """
        Listen for one phrase from microphone

        Returns:
            Transcribed text or None
        """
        if not self.microphone:
            print("[VOICE BRIDGE] No microphone available")
            return None

        print("[VOICE BRIDGE] Listening...")
        self.listening = True

        try:
            with self.microphone as source:
                audio = self.recognizer.listen(source, timeout=5.0)

            # Transcribe
            print("[VOICE BRIDGE] Transcribing...")
            text = self.recognizer.recognize_google(audio)

            safe_print(f"[VOICE BRIDGE] Recognized: {text}")

            if self.text_callback:
                self.text_callback(text)

            return text

        except sr.WaitTimeoutError:
            print("[VOICE BRIDGE] Listening timeout")
            return None
        except sr.UnknownValueError:
            print("[VOICE BRIDGE] Could not understand audio")
            return None
        except Exception as e:
            print(f"[VOICE BRIDGE] Error: {e}")
            return None
        finally:
            self.listening = False

    async def speak(self, text: str, voice: str = "Rachel"):
        """
        Speak text using TTS and feed audio to visual system

        Args:
            text: Text to speak
            voice: ElevenLabs voice name or voice_id
        """
        safe_print(f"[VOICE BRIDGE] Speaking: {text[:50]}...")
        self.speaking = True

        try:
            if self.tts_client:
                # Resolve voice name to ID if needed
                voice_id = VOICE_IDS.get(voice, voice)  # Use name→ID mapping or assume it's already an ID

                # Generate speech with ElevenLabs (using current API)
                audio_stream = self.tts_client.text_to_speech.stream(
                    text=text,
                    voice_id=voice_id,
                    model_id="eleven_multilingual_v2",  # Updated from deprecated eleven_monolingual_v1
                    voice_settings=VoiceSettings(
                        stability=0.5,
                        similarity_boost=0.75,
                    ),
                )

                # Stream audio chunks to visual system AND play them
                audio_chunks = []
                for chunk in audio_stream:
                    if chunk:
                        audio_chunks.append(chunk)

                        # Convert to numpy array for AudioAnalyzer
                        # Note: ElevenLabs returns PCM audio
                        audio_array = np.frombuffer(chunk, dtype=np.int16).astype(np.float32) / 32768.0

                        # Feed to visual system!
                        if self.audio_callback:
                            self.audio_callback(audio_array)

                # Also play the audio (optional, can be done via sounddevice)
                # For now, we're primarily feeding visuals
                print(f"[VOICE BRIDGE] Streamed {len(audio_chunks)} audio chunks to visuals")

            else:
                # Demo mode without API key - just print
                safe_print(f"[VOICE BRIDGE] [Demo TTS]: {text}")

                # Generate fake audio for demo (sine wave)
                sample_rate = 44100
                duration = len(text) * 0.1  # ~0.1 sec per character
                t = np.linspace(0, duration, int(sample_rate * duration))

                # Generate varied frequencies based on text
                frequency = 200 + (hash(text) % 400)  # 200-600 Hz
                demo_audio = np.sin(2 * np.pi * frequency * t).astype(np.float32) * 0.3

                # Feed in chunks to visual system
                chunk_size = 2048
                for i in range(0, len(demo_audio), chunk_size):
                    chunk = demo_audio[i:i+chunk_size]
                    if len(chunk) == chunk_size and self.audio_callback:
                        self.audio_callback(chunk)
                    await asyncio.sleep(0.02)  # Simulate streaming

        except Exception as e:
            print(f"[VOICE BRIDGE] TTS Error: {e}")
        finally:
            self.speaking = False

    async def process_voice_input(self, text: Optional[str] = None):
        """
        Process voice input through the full pipeline

        Args:
            text: Optional text (if None, will listen from microphone)
        """
        # 1. Get text (from mic or direct)
        if text is None:
            text = await self.listen_once()
            if not text:
                return

        # 2. Send to agents
        safe_print(f"[VOICE BRIDGE] -> Agents: {text}")
        response = await self.orchestrator.process_user_input(text)

        if self.response_callback:
            self.response_callback(response)

        # 3. Speak response (this feeds audio to visuals!)
        await self.speak(response)

    async def shutdown(self):
        """Cleanup"""
        if self.orchestrator:
            await self.orchestrator.shutdown()
        print("[VOICE BRIDGE] Shutdown complete")


# Global instance
_voice_bridge: Optional[VoiceBridge] = None


async def get_voice_bridge(
    elevenlabs_api_key: Optional[str] = None,
    openai_api_key: Optional[str] = None
) -> VoiceBridge:
    """
    Get or create global voice bridge

    Args:
        elevenlabs_api_key: ElevenLabs API key
        openai_api_key: OpenAI API key

    Returns:
        VoiceBridge instance
    """
    global _voice_bridge
    if _voice_bridge is None:
        _voice_bridge = VoiceBridge(elevenlabs_api_key, openai_api_key)
        await _voice_bridge.initialize()
    return _voice_bridge
