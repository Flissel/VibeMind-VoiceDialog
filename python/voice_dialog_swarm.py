"""
Voice Dialog with AutoGen Swarm

Alternative entry point using AutoGen 0.4 Swarm pattern.
Uses local Ollama for LLM and optional Redis for event streams.

Usage:
    # Ollama only (console mode)
    python voice_dialog_swarm.py --console

    # Event Buffer System (non-blocking, parallel workers)
    python voice_dialog_swarm.py --v2

    # With ElevenLabs voice (requires API key)
    python voice_dialog_swarm.py

    # Check Ollama connection
    python voice_dialog_swarm.py --check
"""

import os
import sys
import signal
import asyncio
import argparse
import logging
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

# Load environment variables from .env file
from dotenv import load_dotenv
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path, override=True)

# Configure logging with filtering for cleaner output
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# Suppress verbose AutoGen, HTTP client, and tool initialization logs
_noisy_loggers = [
    "autogen_core",
    "autogen_core.events",
    "autogen_agentchat",
    "autogen_ext",
    "httpx",
    "httpcore",
    "openai",
    "asyncio",
]
# Suppress tool loading warnings (optional dependencies)
_tool_loggers = [
    "tools",
    "tools.handoff_tools",
    "tools.claude_tools",
    "tools.desktop_tools",
]
for _logger_name in _noisy_loggers:
    logging.getLogger(_logger_name).setLevel(logging.WARNING)
for _logger_name in _tool_loggers:
    logging.getLogger(_logger_name).setLevel(logging.ERROR)

# Global state
_should_exit = False


async def check_ollama():
    """Check if Ollama is available and list models."""
    from swarm.ollama_client import get_ollama_client

    print("Checking Ollama connection...")
    client = get_ollama_client()

    is_healthy = await client.health_check()
    if is_healthy:
        print("Ollama is running and ready!")
        return True
    else:
        print("ERROR: Cannot connect to Ollama.")
        print("Make sure Ollama is running: ollama serve")
        print("And you have a model: ollama pull llama3.1")
        return False


async def console_mode():
    """
    Run in console mode (no voice).

    Uses Ollama directly for testing the Swarm agents.
    """
    from swarm.voice_bridge import create_voice_bridge

    print()
    print("=" * 60)
    print("VibeMind Swarm - Console Mode")
    print("=" * 60)
    print()
    print("Type your commands. The Swarm agents will process them.")
    print("Type 'quit' or 'exit' to stop.")
    print()

    # Check Ollama first
    if not await check_ollama():
        return

    print("\nInitializing Swarm team...")

    try:
        bridge = await create_voice_bridge()
        print("Swarm team ready!")
        print()

        while not _should_exit:
            try:
                # Get user input
                user_input = input("You: ").strip()

                if not user_input:
                    continue

                if user_input.lower() in ("quit", "exit", "bye"):
                    print("Goodbye!")
                    break

                # Process through Swarm
                print("Processing...")
                result = await bridge.handle_voice_input_async(user_input)

                # Print response (handle encoding issues)
                try:
                    print(f"\n[{result.agent_name}]: {result.response}")
                    if result.tool_calls > 0:
                        print(f"  (Used {result.tool_calls} tool(s), {result.handoffs} handoff(s))")
                except UnicodeEncodeError:
                    # Fallback for Windows encoding issues
                    safe_response = result.response.encode('ascii', 'ignore').decode('ascii')
                    print(f"\n[{result.agent_name}]: {safe_response}")
                    if result.tool_calls > 0:
                        print(f"  (Used {result.tool_calls} tool(s), {result.handoffs} handoff(s))")
                print()

            except KeyboardInterrupt:
                print("\nInterrupted. Goodbye!")
                break
            except EOFError:
                print("\nGoodbye!")
                break

    except Exception as e:
        logger.error(f"Error in console mode: {e}")
        raise


async def voice_mode():
    """
    Run with ElevenLabs voice integration.

    Registers Swarm bridge as a ClientTool for the voice agent.
    """
    from config import ConfigManager
    from elevenlabs.client import ElevenLabs
    from elevenlabs.conversational_ai.conversation import Conversation
    from elevenlabs.conversational_ai.default_audio_interface import DefaultAudioInterface
    from tools.client_tools_manager import ClientToolsManager
    from swarm.voice_bridge import create_voice_bridge

    # Load configuration
    config_manager = ConfigManager()
    config = config_manager.get_config()

    if not config.elevenlabs_api_key:
        print("ERROR: ELEVENLABS_API_KEY not set in .env")
        print("Use --console mode for testing without voice.")
        sys.exit(1)

    # Get agent ID
    agent_id = os.getenv("AGENT_MULTIVERSE") or os.getenv("AGENT_RACHEL")
    if not agent_id:
        print("ERROR: AGENT_MULTIVERSE or AGENT_RACHEL not set in .env")
        sys.exit(1)

    print()
    print("=" * 60)
    print("VibeMind Swarm - Voice Mode")
    print("=" * 60)
    print()

    # Check Ollama
    if not await check_ollama():
        sys.exit(1)

    print("\nInitializing Swarm team...")
    bridge = await create_voice_bridge()
    print("Swarm team ready!")

    # Create tools manager with Swarm bridge
    tools_manager = ClientToolsManager()

    # Register the Swarm bridge as a tool
    tools_manager.register_with_observer(
        "process_command",
        bridge.as_elevenlabs_tool(),
    )

    # Also register event query tools for status checks
    from swarm.tools.event_query_tools import (
        get_task_status_summary,
        list_active_tasks,
    )

    tools_manager.register_with_observer("get_task_status", lambda p: get_task_status_summary())
    tools_manager.register_with_observer("list_tasks", lambda p: list_active_tasks())

    print("Tools registered.")

    # Create ElevenLabs client
    client = ElevenLabs(api_key=config.elevenlabs_api_key)
    audio_interface = DefaultAudioInterface()

    print()
    print("Starting voice dialog...")
    print("Speak to interact with the Swarm agents.")
    print("Press Ctrl+C to exit.")
    print()

    # Signal handler
    def signal_handler(sig, frame):
        global _should_exit
        print("\nShutting down...")
        _should_exit = True

    signal.signal(signal.SIGINT, signal_handler)

    # Main loop
    while not _should_exit:
        try:
            # Create conversation
            conversation = Conversation(
                client=client,
                agent_id=agent_id,
                requires_auth=False,
                audio_interface=audio_interface,
                client_tools=tools_manager.get_client_tools(),
            )

            # Run conversation
            conversation.start_session()
            conversation_id = conversation.wait_for_session_end()
            print(f"Session ended: {conversation_id}")

        except Exception as e:
            logger.error(f"Conversation error: {e}")
            if not _should_exit:
                print("Reconnecting in 2 seconds...")
                await asyncio.sleep(2)

    print("Goodbye!")


async def demo_mode():
    """
    Quick demo of Swarm capabilities.
    """
    from swarm.voice_bridge import create_voice_bridge

    print()
    print("=" * 60)
    print("VibeMind Swarm - Demo Mode")
    print("=" * 60)
    print()

    if not await check_ollama():
        return

    print("\nInitializing Swarm team...")
    bridge = await create_voice_bridge()
    print("Swarm team ready!")
    print()

    # Demo commands
    demo_commands = [
        "List my spaces",
        "Create a new space called 'Python Projects'",
        "Enter the Python Projects space",
        "Add a note about learning FastAPI",
        "What notes do I have here?",
        "Exit this space",
    ]

    for cmd in demo_commands:
        print(f"\n> {cmd}")
        result = await bridge.handle_voice_input_async(cmd)
        print(f"[{result.agent_name}]: {result.response}")
        await asyncio.sleep(1)

    print("\n" + "=" * 60)
    print("Demo complete!")


async def console_mode_v2():
    """
    Console mode with Event Buffer System.

    Features:
    - Navigation between spaces (Ideas/Coding/Desktop)
    - Non-blocking input processing
    - Parallel worker execution
    - Correction detection
    """
    from swarm.voice_bridge_v2 import create_voice_bridge_v2
    from swarm.navigation import SpaceType

    print()
    print("=" * 60)
    print("VibeMind Swarm V2 - Event Buffer System")
    print("=" * 60)
    print()
    print("Features:")
    print("  - Navigation: 'geh zu desktop', 'wechsel zu coding'")
    print("  - Korrektur: 'nein', 'eigentlich', 'stopp'")
    print("  - Parallel workers in background")
    print()
    print("Commands: 'quit', 'status', 'spaces'")
    print()

    # Check Ollama first
    if not await check_ollama():
        return

    print("\nInitializing Event Buffer System...")

    try:
        bridge = await create_voice_bridge_v2()
        print("System ready!")
        print(f"Current Space: {bridge.current_space.value} ({bridge.current_agent_name})")
        print()

        # Space change callback
        def on_space_change(event):
            print(f"\n[Navigation] {event.from_space.value} → {event.to_space.value}")

        bridge.on_space_change(on_space_change)

        while not _should_exit:
            try:
                # Show current space in prompt
                space = bridge.current_space.value
                agent = bridge.current_agent_name
                user_input = input(f"[{space}/{agent}] You: ").strip()

                if not user_input:
                    continue

                # Meta commands
                if user_input.lower() in ("quit", "exit", "bye"):
                    print("Goodbye!")
                    break

                if user_input.lower() == "status":
                    from swarm import get_event_buffer
                    eb = get_event_buffer()
                    pending = eb.get_all_pending()
                    print(f"\nPending tasks: {pending}")
                    busy = bridge.space_registry.get_busy_spaces()
                    print(f"Busy spaces: {[s.name for s in busy]}")
                    continue

                if user_input.lower() == "spaces":
                    for s in bridge.space_registry.all_spaces():
                        status = "busy" if s.is_busy() else "ready"
                        print(f"  {s.display_name}: {status}")
                    continue

                # Process through Event Buffer System
                print("Processing...")
                result = await bridge.handle_voice_input(user_input)

                # Print response
                if result.was_navigation:
                    print(f"\n[Navigation]: {result.response}")
                elif result.task_queued:
                    print(f"\n[{result.agent_name}]: {result.response}")
                    print("  (Task queued for later)")
                else:
                    print(f"\n[{result.agent_name}]: {result.response}")

                if result.error:
                    print(f"  (Error: {result.error})")

                print()

            except KeyboardInterrupt:
                print("\nInterrupted. Goodbye!")
                break
            except EOFError:
                print("\nGoodbye!")
                break

        # Cleanup
        await bridge.shutdown()

    except Exception as e:
        logger.error(f"Error in console mode v2: {e}")
        import traceback
        traceback.print_exc()
        raise


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="VibeMind Voice Dialog with AutoGen Swarm"
    )
    parser.add_argument(
        "--console",
        action="store_true",
        help="Run in console mode (no voice)",
    )
    parser.add_argument(
        "--v2",
        action="store_true",
        help="Run with Event Buffer System (navigation, parallel workers)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check Ollama connection and exit",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run demo commands",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging (show all AutoGen internals)",
    )

    args = parser.parse_args()

    # Enable verbose logging if requested
    if args.verbose:
        for _logger_name in _noisy_loggers + _tool_loggers:
            logging.getLogger(_logger_name).setLevel(logging.DEBUG)
        logging.getLogger().setLevel(logging.DEBUG)
        print("[VERBOSE MODE] All logs enabled")

    if args.check:
        asyncio.run(check_ollama())
    elif args.demo:
        asyncio.run(demo_mode())
    elif args.v2:
        asyncio.run(console_mode_v2())
    elif args.console:
        asyncio.run(console_mode())
    else:
        asyncio.run(voice_mode())


if __name__ == "__main__":
    main()
