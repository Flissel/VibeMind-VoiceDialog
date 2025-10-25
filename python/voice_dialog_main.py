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

# Import Client Tools Manager and Agents
from tools.client_tools_manager import ClientToolsManager
from agents.research_agent import ResearchAgent
from agents.code_agent import CodeAgent
from agents.data_agent import DataAgent
from agents.system_agent import SystemAgent


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

    # Initialize Client Tools Manager
    print("Initializing client tools...")
    tools_manager = ClientToolsManager()

    # Register agents
    tools_manager.register_agent("research", ResearchAgent())
    tools_manager.register_agent("code", CodeAgent())
    tools_manager.register_agent("data", DataAgent())
    tools_manager.register_agent("system", SystemAgent())

    # Register tools (map tool names to agents)
    tools_manager.register_tool("web_search", "research")
    tools_manager.register_tool("generate_code", "code")
    tools_manager.register_tool("analyze_data", "data")
    tools_manager.register_tool("list_files", "system")

    print()
    print("Registered client tools:")
    for tool_name, agent_name in tools_manager.list_registered_tools().items():
        print(f"  - {tool_name} -> {agent_name}")
    print()

    # Create ElevenLabs client
    client = ElevenLabs(api_key=config.elevenlabs_api_key)

    # Create audio interface (uses default system audio devices)
    audio_interface = DefaultAudioInterface()

    # Create conversation with client tools
    conversation = Conversation(
        client=client,
        agent_id=config.elevenlabs_agent_id,
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
