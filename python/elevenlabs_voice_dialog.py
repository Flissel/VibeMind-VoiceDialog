"""
ElevenLabs Voice Dialog Client
Simple wrapper for ElevenLabs Conversational AI
"""

import os
import asyncio
from typing import Optional, Callable, Any
from elevenlabs.client import ElevenLabs
from elevenlabs.conversational_ai.conversation import Conversation
from elevenlabs.conversational_ai.default_audio_interface import DefaultAudioInterface
import sounddevice as sd
import numpy as np


class VoiceDialog:
    """
    Simple client for ElevenLabs Conversational AI
    Handles microphone input → Agent → Audio output
    """

    def __init__(
        self,
        agent_id: str,
        api_key: Optional[str] = None,
        on_agent_response: Optional[Callable] = None,
        on_user_transcript: Optional[Callable] = None,
        client_tools: Optional[Any] = None
    ):
        """
        Initialize Voice Dialog client

        Args:
            agent_id: ElevenLabs agent ID
            api_key: ElevenLabs API key (or from env)
            on_agent_response: Callback when agent responds (audio_chunk)
            on_user_transcript: Callback when user speech transcribed (text)
            client_tools: Optional ClientTools instance for agent tool calls
        """
        self.agent_id = agent_id
        self.api_key = api_key or os.getenv("ELEVENLABS_API_KEY")

        if not self.api_key:
            raise ValueError("ELEVENLABS_API_KEY not found")

        self.client = ElevenLabs(api_key=self.api_key)
        self.conversation = None
        self.is_active = False
        self.client_tools = client_tools

        # Callbacks
        self.on_agent_response = on_agent_response
        self.on_user_transcript = on_user_transcript

    async def start_conversation(self):
        """
        Start a voice conversation with ElevenLabs agent
        """
        print(f"[VoiceDialog] Starting conversation with agent {self.agent_id}")

        # Create audio interface for real-time audio input/output
        audio_interface = DefaultAudioInterface()

        # Create conversation with optional client tools
        conversation_params = {
            "client": self.client,
            "agent_id": self.agent_id,
            "requires_auth": False,
            "audio_interface": audio_interface,
        }

        if self.client_tools:
            conversation_params["client_tools"] = self.client_tools

        self.conversation = Conversation(**conversation_params)

        # Start session
        await self.conversation.start_session()
        self.is_active = True

        print("[VoiceDialog] Conversation started - ready for voice input")

    async def send_audio(self, audio_data: np.ndarray):
        """
        Send audio from microphone to agent

        Args:
            audio_data: Audio samples (numpy array)
        """
        if not self.is_active or not self.conversation:
            print("[VoiceDialog] Conversation not active")
            return

        # Convert to bytes if needed
        if isinstance(audio_data, np.ndarray):
            audio_bytes = audio_data.tobytes()
        else:
            audio_bytes = audio_data

        await self.conversation.send_audio(audio_bytes)

    def play_agent_response(self, audio_chunk: bytes):
        """
        Play audio response from agent

        Args:
            audio_chunk: Audio data from agent
        """
        if self.on_agent_response:
            self.on_agent_response(audio_chunk)
        else:
            # Default: play via sounddevice
            audio_np = np.frombuffer(audio_chunk, dtype=np.float32)
            sd.play(audio_np, samplerate=22050)

    async def end_conversation(self):
        """
        End the conversation
        """
        if self.conversation:
            await self.conversation.end_session()
            self.is_active = False
            print("[VoiceDialog] Conversation ended")

    def __del__(self):
        """Cleanup"""
        if self.is_active:
            try:
                asyncio.run(self.end_conversation())
            except:
                pass
