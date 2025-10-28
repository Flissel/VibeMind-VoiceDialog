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

# Import Client Tools Manager and Hello World Tools
from tools.client_tools_manager import ClientToolsManager
from tools.hello_world_tools import write_hello_desktop, write_hello_writer


def main():
    """Main entry point for voice dialog"""

    # Load configuration
    config_manager = ConfigManager()
    config = config_manager.get_config()

    if not config.agent_conversational_memory:
        print("ERROR: AGENT_CONVERSATIONAL_MEMORY not set in .env")
        sys.exit(1)

    if not config.elevenlabs_api_key:
        print("ERROR: ELEVENLABS_API_KEY not set in .env")
        sys.exit(1)

    print("=" * 50)
    print("VibeMind Voice Dialog - ElevenLabs")
    print("=" * 50)
    print()
    print(f"Starting Agent: Conversational Memory (Rachel)")
    print(f"Agent ID: {config.agent_conversational_memory}")
    print()

    # Initialize Client Tools Manager
    print("Registering hello world test tools...")
    tools_manager = ClientToolsManager()

    # Register hello world tools directly (no agent routing needed for simple test functions)
    def hello_desktop_wrapper(params):
        """Wrapper for write_hello_desktop that returns ElevenLabs-compatible response"""
        result = write_hello_desktop()
        return {"status": "success", "message": result}

    def hello_writer_wrapper(params):
        """Wrapper for write_hello_writer that returns ElevenLabs-compatible response"""
        result = write_hello_writer()
        return {"status": "success", "message": result}

    # Register with ClientTools
    tools_manager.client_tools.register("write_hello_desktop", hello_desktop_wrapper)
    tools_manager.client_tools.register("write_hello_writer", hello_writer_wrapper)

    print()
    print("Registered client tools:")
    print("  - write_hello_desktop (Desktop Worker test)")
    print("  - write_hello_writer (Project Writer test)")
    print()

    # Create ElevenLabs client
    client = ElevenLabs(api_key=config.elevenlabs_api_key)

    # Create audio interface (uses default system audio devices)
    audio_interface = DefaultAudioInterface()

    # Create conversation with client tools
    conversation = Conversation(
        client=client,
        agent_id=config.agent_conversational_memory,
        requires_auth=False,
        audio_interface=audio_interface,
        client_tools=tools_manager.get_client_tools(),
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
