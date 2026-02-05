"""
Voice Dialog Main Entry Point
Dynamic multi-agent voice conversation with ElevenLabs

Supports switching between:
- Multiverse agent (bubble navigation)
- Bubble-specific agents (idea management within spaces)
"""

import os
import sys
import signal
import threading
import time
from config import ConfigManager
from elevenlabs.client import ElevenLabs
from elevenlabs.conversational_ai.conversation import Conversation
from elevenlabs.conversational_ai.default_audio_interface import DefaultAudioInterface

# Import Client Tools Manager and tools
from tools.client_tools_manager import ClientToolsManager
from tools.hello_world_tools import write_hello_desktop, write_hello_writer
from tools.workspace_tools import register_workspace_tools
from tools.conversation_tools import register_conversation_tools
from tools.browser_worker import register_browser_tools
from tools.idea_tools import register_idea_tools
from tools.memory_tools import register_memory_tools
from tools.bubble_tools import register_bubble_tools, get_pending_agent_switch
from tools.session_tools import (
    register_session_tools,
    mark_session_start,
    mark_session_end,
    mark_interaction,
    should_auto_restart
)
from tools.summary_tools import register_summary_tools
from tools.supermemory_tools import register_supermemory_tools, set_session_id, get_session_id
# Try to import coding tools (optional - requires coding engine)
try:
    from tools.coding_tools import register_coding_tools
    HAS_CODING_TOOLS = True
except ImportError:
    HAS_CODING_TOOLS = False
    register_coding_tools = None

# Try to import navigation tools for voice-controlled UI navigation
try:
    from tools.navigation_tools import register_navigation_tools
    HAS_NAVIGATION_TOOLS = True
except ImportError:
    HAS_NAVIGATION_TOOLS = False
    register_navigation_tools = None

# Try to import desktop tools for Adam (requires MoireTracker v2)
try:
    from tools.desktop_tools import register_desktop_tools
    HAS_DESKTOP_TOOLS = True
except ImportError:
    HAS_DESKTOP_TOOLS = False
    register_desktop_tools = None

# Try to import Moire tools for advanced OCR (requires MoireServer on port 8766)
try:
    from tools.moire_tools import register_moire_tools
    HAS_MOIRE_TOOLS = True
except ImportError:
    HAS_MOIRE_TOOLS = False
    register_moire_tools = None

# Global state for agent switching
_current_conversation = None
_should_exit = False
_last_switch_info = None  # Store switch info for main loop


def _install_exception_handlers():
    """Install exception handlers for better crash visibility.

    - faulthandler: Shows traceback on segfaults/hangs
    - threading.excepthook: Logs exceptions in background threads
    - sys.excepthook: Logs unhandled exceptions in main thread
    """
    import faulthandler
    import traceback
    import logging

    logger = logging.getLogger(__name__)

    # Enable faulthandler for segfaults and SIGABRT
    faulthandler.enable()

    # Also enable dump on SIGUSR1 (Unix) or after timeout
    try:
        # Write crash dumps to stderr by default
        faulthandler.register(signal.SIGUSR1)
    except (AttributeError, ValueError):
        # SIGUSR1 not available on Windows
        pass

    # Threading excepthook (Python 3.8+)
    def thread_excepthook(args):
        """Log uncaught exceptions in threads."""
        thread_name = args.thread.name if args.thread else "Unknown"
        logger.error(f"[THREAD CRASH] {thread_name}: {args.exc_type.__name__}: {args.exc_value}")
        logger.error("".join(traceback.format_tb(args.exc_traceback)))
        # Also print to stderr for visibility
        print(f"\n[THREAD CRASH] {thread_name}: {args.exc_type.__name__}: {args.exc_value}", file=sys.stderr)
        traceback.print_tb(args.exc_traceback, file=sys.stderr)

    threading.excepthook = thread_excepthook

    # Override sys.excepthook for main thread
    original_excepthook = sys.excepthook
    def main_excepthook(exc_type, exc_value, exc_tb):
        """Log unhandled exceptions in main thread."""
        logger.error(f"[MAIN CRASH] {exc_type.__name__}: {exc_value}")
        logger.error("".join(traceback.format_tb(exc_tb)))
        original_excepthook(exc_type, exc_value, exc_tb)

    sys.excepthook = main_excepthook

    print("[Exception handlers installed: faulthandler + threading.excepthook]")


def setup_tools_manager():
    """Initialize and register all client tools."""
    tools_manager = ClientToolsManager()

    # Register hello world tools
    def hello_desktop_wrapper(params):
        result = write_hello_desktop()
        return result

    def hello_writer_wrapper(params):
        result = write_hello_writer()
        return result

    tools_manager.register_with_observer("write_hello_desktop", hello_desktop_wrapper)
    tools_manager.register_with_observer("write_hello_writer", hello_writer_wrapper)

    # Register all tool sets
    register_workspace_tools(tools_manager)
    register_conversation_tools(tools_manager)
    register_browser_tools(tools_manager)
    register_idea_tools(tools_manager)
    register_memory_tools(tools_manager)
    register_bubble_tools(tools_manager)
    register_session_tools(tools_manager)
    register_summary_tools(tools_manager)
    register_supermemory_tools(tools_manager)
    
    # Register coding tools if available (for Antoni agent)
    if HAS_CODING_TOOLS and register_coding_tools:
        register_coding_tools(tools_manager)
        print("  Coding tools registered for Antoni")

    # Register navigation tools if available (for Multiverse voice navigation)
    if HAS_NAVIGATION_TOOLS and register_navigation_tools:
        register_navigation_tools(tools_manager)
        print("  Navigation tools registered for voice UI control")

    # Register desktop tools if available (for Adam - requires MoireTracker v2)
    if HAS_DESKTOP_TOOLS and register_desktop_tools:
        register_desktop_tools(tools_manager)
        print("  Desktop tools registered for Adam")

    # Register Moire tools if available (advanced OCR via MoireServer)
    if HAS_MOIRE_TOOLS and register_moire_tools:
        register_moire_tools(tools_manager)
        print("  Moire tools registered for advanced OCR")

    return tools_manager


def agent_switch_watcher():
    """
    Background thread that watches for agent switch signals.
    When a switch is detected, stores the info and ends the current conversation.
    """
    global _current_conversation, _should_exit, _last_switch_info

    while not _should_exit:
        switch_info = get_pending_agent_switch()
        if switch_info and _current_conversation:
            print(f"\n[Agent Switch] Detected switch to: {switch_info['bubble_title']}")
            _last_switch_info = switch_info  # Store for main loop
            try:
                _current_conversation.end_session()
            except Exception as e:
                print(f"[Agent Switch] Error ending session: {e}")
        time.sleep(0.1)  # Poll every 100ms


def get_and_clear_switch_info():
    """Get stored switch info and clear it."""
    global _last_switch_info
    info = _last_switch_info
    _last_switch_info = None
    return info


def run_conversation(client, agent_id, agent_name, tools_manager, audio_interface):
    """
    Run a single conversation session with the specified agent.

    Returns:
        dict or None: Switch info if agent switch requested, None otherwise
    """
    global _current_conversation

    print()
    print(f"Connecting to: {agent_name}")
    print(f"Agent ID: {agent_id}")
    print()

    # Create conversation
    conversation = Conversation(
        client=client,
        agent_id=agent_id,
        requires_auth=False,
        audio_interface=audio_interface,
        client_tools=tools_manager.get_client_tools(),
    )

    _current_conversation = conversation

    # Start the conversation and mark session start for timeout tracking
    conversation.start_session()
    mark_session_start()

    # Wait for it to end (will be triggered by watcher thread on switch)
    conversation_id = conversation.wait_for_session_end()

    # Mark session end for cleanup
    mark_session_end()
    _current_conversation = None

    print(f"Session ended: {conversation_id}")

    # Check if there's a pending switch (stored by watcher thread)
    switch_info = get_and_clear_switch_info()
    return switch_info


def main():
    """Main entry point for voice dialog with dynamic agent switching."""
    global _should_exit

    # Install exception handlers for better crash visibility
    _install_exception_handlers()

    # Load configuration
    config_manager = ConfigManager()
    config = config_manager.get_config()

    if not config.elevenlabs_api_key:
        print("ERROR: ELEVENLABS_API_KEY not set in .env")
        sys.exit(1)

    # Get Multiverse agent ID (with fallback)
    multiverse_agent_id = os.getenv("AGENT_MULTIVERSE")
    if not multiverse_agent_id:
        print("WARNING: AGENT_MULTIVERSE not set, falling back to AGENT_CONVERSATIONAL_MEMORY")
        multiverse_agent_id = config.agent_conversational_memory

    if not multiverse_agent_id:
        print("ERROR: No agent ID configured. Set AGENT_MULTIVERSE or AGENT_CONVERSATIONAL_MEMORY in .env")
        sys.exit(1)

    print("=" * 60)
    print("VibeMind Voice Dialog - Dynamic Multi-Agent")
    print("=" * 60)
    print()
    print("Architecture:")
    print("  - Multiverse agent: Navigate and manage spaces (bubbles)")
    print("  - Bubble agents: Work on ideas within specific spaces")
    print()
    print("Voice commands:")
    print("  - 'Show my spaces' - List all bubbles")
    print("  - 'Create a space for cooking' - Create new bubble")
    print("  - 'Enter my cooking space' - Switch to bubble agent")
    print("  - 'Go back' or 'Exit' - Return to multiverse")
    print()

    # Initialize tools
    print("Initializing tools...")
    tools_manager = setup_tools_manager()
    print("Tools registered.")
    print()

    # Create ElevenLabs client
    client = ElevenLabs(api_key=config.elevenlabs_api_key)

    # Create audio interface (reused across conversations)
    audio_interface = DefaultAudioInterface()

    # Start agent switch watcher thread
    watcher_thread = threading.Thread(target=agent_switch_watcher, daemon=True)
    watcher_thread.start()

    # Signal handler for clean exit
    def signal_handler(sig, frame):
        global _should_exit, _current_conversation
        print("\nShutting down...")
        _should_exit = True
        if _current_conversation:
            try:
                _current_conversation.end_session()
            except:
                pass
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    # Current agent state
    current_agent_id = multiverse_agent_id
    current_agent_name = "Multiverse (Rachel)"

    print("Starting voice dialog...")
    print("Press Ctrl+C to exit")
    print()

    # Main conversation loop
    while not _should_exit:
        try:
            # Run conversation with current agent
            switch_info = run_conversation(
                client=client,
                agent_id=current_agent_id,
                agent_name=current_agent_name,
                tools_manager=tools_manager,
                audio_interface=audio_interface,
            )

            if switch_info:
                # Switch to new agent
                current_agent_id = switch_info["agent_id"]
                bubble_title = switch_info["bubble_title"]

                if switch_info["bubble_id"]:
                    current_agent_name = f"{bubble_title} (Rachel)"
                else:
                    current_agent_name = "Multiverse (Rachel)"

                print()
                print("=" * 40)
                print(f"Switched to: {current_agent_name}")
                print("=" * 40)
            else:
                # Conversation ended without switch request
                # This could be a network issue or manual end
                print("Conversation ended. Reconnecting to multiverse...")
                current_agent_id = multiverse_agent_id
                current_agent_name = "Multiverse (Rachel)"
                time.sleep(1)  # Brief pause before reconnecting

        except Exception as e:
            print(f"Error in conversation: {e}")
            print("Reconnecting in 2 seconds...")
            time.sleep(2)

    print("Goodbye!")


if __name__ == "__main__":
    main()
