"""
Voice Dialog Main Entry Point
Simple voice conversation with ElevenLabs agent using DefaultAudioInterface
"""

import os
import sys
import signal
from config import ConfigManager
from elevenlabs.client import ElevenLabs
from elevenlabs.conversational_ai.conversation import Conversation
from elevenlabs.conversational_ai.default_audio_interface import DefaultAudioInterface


def main():
    """Main entry point for voice dialog"""

    # Load configuration
    config_manager = ConfigManager()
    config = config_manager.get_config()

    if not config.elevenlabs_agent_id:
        print("ERROR: ELEVENLABS_AGENT_ID not set in .env")
        sys.exit(1)

    if not config.elevenlabs_api_key:
        print("ERROR: ELEVENLABS_API_KEY not set in .env")
        sys.exit(1)

    print("=" * 50)
    print("VibeMind Voice Dialog - ElevenLabs")
    print("=" * 50)
    print()
    print(f"Agent ID: {config.elevenlabs_agent_id}")
    print()

    # Create ElevenLabs client
    client = ElevenLabs(api_key=config.elevenlabs_api_key)

    # Create audio interface (uses default system audio devices)
    audio_interface = DefaultAudioInterface()

    # Create conversation
    conversation = Conversation(
        client=client,
        agent_id=config.elevenlabs_agent_id,
        requires_auth=False,
        audio_interface=audio_interface,
    )

    # Setup signal handler for clean shutdown
    signal.signal(
        signal.SIGINT,
        lambda sig, frame: conversation.end_session()
    )

    print("Starting conversation...")
    print()
    print("Speak into your microphone to talk with the agent")
    print("The agent will respond through your speakers")
    print("Press Ctrl+C to exit")
    print()

    # Start the conversation (blocking call)
    conversation.start_session()

    # Wait for conversation to end
    conversation_id = conversation.wait_for_session_end()

    print()
    print(f"Conversation ended. ID: {conversation_id}")
    print("Goodbye!")


if __name__ == "__main__":
    main()
