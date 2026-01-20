"""
Voice Bridge V2 for VibeMind - Voice Interface + Backend Agents

Architecture:
- Rachel: Pure voice interface (only send_intent tool)
- Orchestrator: Classifies intent, seeds events to Redis
- Backend Agents: Execute tools and publish status
- Status Listener: Receives status, triggers Rachel TTS

Flow:
1. User speaks → Rachel receives text
2. Rachel calls send_intent(user_request)
3. Orchestrator classifies → seeds event to Redis
4. Backend Agent executes tool → publishes status
5. Status Listener → Rachel speaks result
"""

import asyncio
import logging
import os
import sys
import time
import uuid
from typing import Dict, Any, Optional, Callable, List
from dataclasses import dataclass

from swarm.navigation import SpaceType
from swarm.event_buffer import InputEvent, get_event_buffer
from swarm.tts_queue import TTSQueue, TTSPriority, get_tts_queue

logger = logging.getLogger(__name__)


def _debug_print(msg: str):
    """Print debug message to stderr for visibility in Electron."""
    print(f"[Python DEBUG] [VoiceBridgeV2] {msg}", file=sys.stderr)

# Environment variable to enable/disable auto-debugging
ENABLE_AUTO_DEBUG = os.getenv("ENABLE_AUTO_DEBUG", "true").lower() == "true"
AUTO_DEBUG_MIN_MESSAGES = int(os.getenv("AUTO_DEBUG_MIN_MESSAGES", "5"))


@dataclass
class VoiceBridgeResult:
    """Result from voice bridge processing."""
    response: str
    agent_name: str
    space: SpaceType
    was_navigation: bool = False
    task_queued: bool = False
    error: Optional[str] = None


class VoiceBridgeV2:
    """
    Voice Bridge with Rachel as Pure Voice Interface.

    Features:
    - Rachel as voice-only interface (no tool execution)
    - IntentOrchestrator for event classification and seeding
    - Backend agents for tool execution
    - Status listener for voice feedback
    """

    def __init__(
        self,
        model_client=None,
        event_manager=None,
    ):
        """
        Initialize voice bridge.

        Args:
            model_client: LLM client for Rachel and Orchestrator
            event_manager: Redis event manager (optional)
        """
        self.model_client = model_client
        self.event_manager = event_manager

        # Core components
        self.event_buffer = get_event_buffer()
        self.tts_queue = get_tts_queue()

        # Rachel - voice interface
        self.rachel = None

        # Orchestrator for intent classification
        self._orchestrator = None

        # Backend agents
        self._ideas_agent = None
        self._desktop_agent = None
        self._coding_agent = None

        # Event bus and listeners
        self._event_bus = None
        self._status_listener = None

        # NotificationQueue for deferred feedback
        self._notification_queue = None

        # Running state
        self._running = False

        # Backend availability flag (set during _start_backend_agents)
        self._backend_available = False

        # Callbacks
        self._on_response: Optional[Callable] = None
        self._tts_callback: Optional[Callable] = None

        # Session tracking for debugging
        self._session_id: str = str(uuid.uuid4())
        self._message_count: int = 0

        # Post-session analyzer (lazy loaded)
        self._analyzer = None

        logger.info("VoiceBridgeV2 initialized (Voice Interface + Backend Agents)")

    async def initialize(self) -> None:
        """
        Initialize all components:
        1. Setup model client
        2. Create NotificationQueue (shared between Rachel and StatusListener)
        3. Create orchestrator
        4. Create Rachel (voice interface)
        5. Start backend agents
        6. Start status listener
        """
        # 1. Setup model client
        if self.model_client is None:
            try:
                from swarm.cloud_client import get_model_client
                self.model_client = get_model_client()
                logger.info("Loaded Cloud client (OpenRouter)")
            except Exception as e:
                logger.warning(f"Cloud client not available: {e}")
                try:
                    from swarm.ollama_client import get_ollama_client
                    ollama = get_ollama_client()
                    self.model_client = ollama.client
                    logger.info(f"Fallback to Ollama: {ollama.model}")
                except Exception as e2:
                    logger.error(f"No LLM client available: {e2}")

        # 2. Create NotificationQueue (shared between Rachel and StatusListener)
        await self._setup_notification_queue()

        # 3. Create orchestrator
        await self._setup_orchestrator()

        # 4. Create Rachel (voice interface)
        await self._setup_rachel()

        # 5. Setup TTS queue
        await self.tts_queue.start_processing()

        # 6. Start backend agents and listeners (skip if FORCE_SYNC_MODE)
        # StatusListener now subscribes BEFORE start_listeners() in _start_backend_agents()
        force_sync = os.getenv("FORCE_SYNC_MODE", "false").lower() == "true"
        if not force_sync:
            await self._start_backend_agents()
            # Note: StatusListener is now set up inside _start_backend_agents()
            _debug_print(f"MODE: Redis async (backend_available={self._backend_available})")
        else:
            _debug_print("MODE: SYNC (FORCE_SYNC_MODE=true - tools execute directly)")
            logger.info("FORCE_SYNC_MODE=true - skipping backend agents (using direct tool execution)")

        self._running = True
        logger.info("VoiceBridgeV2 fully initialized")

    async def _setup_notification_queue(self) -> None:
        """Setup the notification queue for deferred feedback."""
        from swarm.orchestrator import get_notification_queue
        self._notification_queue = get_notification_queue()
        logger.info("NotificationQueue initialized (deferred feedback)")

    async def _setup_orchestrator(self) -> None:
        """Setup the intent orchestrator."""
        from swarm.orchestrator import get_orchestrator
        self._orchestrator = get_orchestrator(self.model_client)
        logger.info("IntentOrchestrator initialized")

    async def _setup_rachel(self) -> None:
        """Setup Rachel as the voice interface with NotificationQueue."""
        from swarm.user_agents.rachel import create_rachel_agent

        self.rachel = create_rachel_agent(
            model_client=self.model_client,
            orchestrator=self._orchestrator,
            notification_queue=self._notification_queue
        )

        tools = self.rachel.get_tools()
        logger.info(f"Rachel (Voice Interface) initialized with {len(tools)} tool(s)")

    async def _start_backend_agents(self) -> None:
        """Start all backend agents."""
        try:
            from swarm.backend_agents import (
                get_ideas_agent,
                get_desktop_agent,
                get_coding_agent
            )
            from swarm.event_bus import get_event_bus
            from swarm.listeners import get_status_listener

            # Get event bus
            self._event_bus = get_event_bus()

            # Create agents
            self._ideas_agent = get_ideas_agent()
            self._desktop_agent = get_desktop_agent()
            self._coding_agent = get_coding_agent()

            # Step 1: Subscribe all agents to their streams (no listeners yet)
            await self._ideas_agent.start()
            await self._desktop_agent.start()
            await self._coding_agent.start()

            # Step 2: Subscribe StatusListener BEFORE starting listeners
            # This ensures events:status gets a listener task
            self._status_listener = get_status_listener(
                notification_queue=self._notification_queue,
                tts_callback=self._tts_callback
            )
            await self._status_listener.start()
            _debug_print("StatusListener SUBSCRIBED to events:status")

            # Step 3: NOW start all listeners (includes events:status)
            await self._event_bus.start_listeners()

            self._backend_available = True
            _debug_print("Backend agents STARTED: IdeasAgent, DesktopAgent, CodingAgent + StatusListener")
            logger.info("Backend agents started: IdeasAgent, DesktopAgent, CodingAgent + StatusListener")

        except Exception as e:
            # Set flag to indicate backend is not available
            self._backend_available = False
            _debug_print(f"Backend agents FAILED: {e} - falling back to SYNC mode")
            logger.warning(f"Backend agents not available: {e}")
            logger.info("VoiceBridgeV2 running in SYNC mode - tools execute directly (no Redis)")
            # Don't raise - Orchestrator has sync fallback

    async def _setup_status_listener(self) -> None:
        """Setup status listener with NotificationQueue for deferred feedback."""
        try:
            from swarm.listeners import get_status_listener

            self._status_listener = get_status_listener(
                notification_queue=self._notification_queue,
                tts_callback=self._tts_callback  # Optional legacy TTS
            )
            await self._status_listener.start()

            logger.info("Status listener started (deferred feedback via NotificationQueue)")

        except Exception as e:
            logger.warning(f"Status listener not available: {e}")

    def set_tts_callback(self, callback: Callable) -> None:
        """Set the TTS callback for voice output."""
        self._tts_callback = callback
        if self._status_listener:
            self._status_listener.set_tts_callback(callback)

    async def start_event_listeners(self) -> None:
        """Start listening for backend status events."""
        if self._status_listener:
            try:
                await self._status_listener.start()
                logger.info("Status listener started")
            except Exception as e:
                logger.warning(f"Could not start status listener: {e}")

    async def handle_voice_input(self, text: str) -> VoiceBridgeResult:
        """
        Process voice input through Rachel.

        Rachel is the voice interface that sends intent to the orchestrator.
        Backend agents execute the actual tools.

        Args:
            text: Transcribed voice input

        Returns:
            VoiceBridgeResult with response and metadata
        """
        timestamp = time.time()
        logger.info(f"Voice input: {text}")

        if not self.rachel:
            return VoiceBridgeResult(
                response="Rachel ist noch nicht bereit. Bitte warte einen Moment.",
                agent_name="system",
                space=SpaceType.IDEAS,
                error="Rachel not initialized",
            )

        # Create input event (target_space defaults to IDEAS)
        input_event = InputEvent(
            text=text,
            timestamp=timestamp,
            target_space=SpaceType.IDEAS,
        )

        # Track message count for debugging
        self._message_count += 1

        # Process through Rachel
        try:
            response = await self.rachel.process_input(input_event)

            # Notify callback if set
            if self._on_response:
                try:
                    result = self._on_response(response)
                    if asyncio.iscoroutine(result):
                        await result
                except Exception as e:
                    logger.error(f"Response callback error: {e}")

            return VoiceBridgeResult(
                response=response,
                agent_name="rachel",
                space=SpaceType.IDEAS,
                task_queued=True,  # Intent was sent to backend
            )

        except Exception as e:
            logger.error(f"Rachel processing error: {e}")
            return VoiceBridgeResult(
                response=f"Es gab einen Fehler: {str(e)}",
                agent_name="system",
                space=SpaceType.IDEAS,
                error=str(e),
            )

    def handle_voice_input_sync(self, text: str) -> str:
        """
        Synchronous wrapper for voice input.

        Args:
            text: Input text

        Returns:
            Response text
        """
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, self.handle_voice_input(text))
                    result = future.result()
                    return result.response
            result = loop.run_until_complete(self.handle_voice_input(text))
            return result.response
        except RuntimeError:
            loop = asyncio.new_event_loop()
            result = loop.run_until_complete(self.handle_voice_input(text))
            loop.close()
            return result.response

    def as_elevenlabs_tool(self) -> Callable:
        """Return function for ElevenLabs ClientTools."""
        def process_command(params: Dict[str, Any]) -> str:
            text = params.get("command", params.get("text", ""))
            if not text:
                return "Ich habe dich nicht verstanden."
            return self.handle_voice_input_sync(text)
        return process_command

    async def shutdown(self) -> None:
        """Shutdown all components gracefully."""
        self._running = False

        # Run post-session analysis if enabled
        if ENABLE_AUTO_DEBUG and self._message_count >= AUTO_DEBUG_MIN_MESSAGES:
            await self._run_post_session_analysis()

        # Stop TTS queue
        await self.tts_queue.stop_processing()

        # Stop backend agents
        if self._ideas_agent:
            await self._ideas_agent.stop()
        if self._desktop_agent:
            await self._desktop_agent.stop()
        if self._coding_agent:
            await self._coding_agent.stop()

        # Stop status listener
        if self._status_listener:
            await self._status_listener.stop()

        # Close event bus
        if self._event_bus:
            await self._event_bus.close()

        logger.info("VoiceBridgeV2 shutdown complete")

    async def _run_post_session_analysis(self) -> None:
        """Run post-session analysis to identify issues."""
        try:
            from swarm.debugging import analyze_session, get_diagnostic_report_path

            logger.info(f"[PostSession] Running analysis for session {self._session_id}")

            # Lazy load analyzer
            if self._analyzer is None:
                from swarm.debugging import get_post_session_analyzer
                self._analyzer = get_post_session_analyzer()

            # Run analysis
            report = self._analyzer.analyze(self._session_id)

            # Save report
            report_path = get_diagnostic_report_path(self._session_id)
            report.save(report_path)

            # Log findings
            if report.top_issue:
                logger.info(
                    f"[PostSession] TOP ISSUE: {report.top_issue.title} "
                    f"(severity: {report.top_issue.severity.value}, "
                    f"confidence: {report.top_issue.confidence:.0%})"
                )
            else:
                logger.info("[PostSession] No significant issues detected")

            logger.info(f"[PostSession] Report saved to: {report_path}")

        except ImportError as e:
            logger.debug(f"[PostSession] Debugging module not available: {e}")
        except Exception as e:
            logger.warning(f"[PostSession] Analysis failed: {e}")

    def on_response(self, callback: Callable) -> None:
        """Set callback for response events."""
        self._on_response = callback

    @property
    def session_id(self) -> str:
        """Get the current session ID."""
        return self._session_id

    @property
    def current_agent_name(self) -> str:
        """Get current agent name (always Rachel)."""
        return "rachel"

    @property
    def current_space(self) -> SpaceType:
        """Get current space (always IDEAS for V2)."""
        return SpaceType.IDEAS

    @property
    def tools_count(self) -> int:
        """Get the number of tools Rachel has (always 1: send_intent)."""
        if self.rachel:
            return len(self.rachel.get_tools())
        return 0

    def on_space_change(self, callback: Callable) -> None:
        """Set callback for space change events (V2 doesn't navigate, so no-op)."""
        # V2 doesn't support navigation, always stays in IDEAS space
        pass

    @property
    def space_registry(self):
        """Mock space registry for console_mode_v2 compatibility."""
        class MockSpaceRegistry:
            def get_busy_spaces(self):
                return []
            def all_spaces(self):
                class MockSpace:
                    display_name = "IDEAS"
                    def is_busy(self):
                        return False
                return [MockSpace()]
        return MockSpaceRegistry()


async def create_voice_bridge_v2(
    model_client=None,
    event_manager=None,
) -> VoiceBridgeV2:
    """
    Create and initialize VoiceBridgeV2.

    Args:
        model_client: Optional pre-configured model client
        event_manager: Optional event manager

    Returns:
        Initialized VoiceBridgeV2 instance
    """
    bridge = VoiceBridgeV2(
        model_client=model_client,
        event_manager=event_manager,
    )
    await bridge.initialize()
    return bridge


__all__ = [
    "VoiceBridgeV2",
    "VoiceBridgeResult",
    "create_voice_bridge_v2",
]
