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
        self._roarboot_agent = None

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
        import time
        start_time = time.time()

        # 1. Setup model client
        _debug_print("[VoiceBridgeV2] Step 1/6: Setting up model client...")
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
        _debug_print(f"[VoiceBridgeV2] Step 1/6 DONE ({time.time() - start_time:.2f}s)")

        # 2. Create NotificationQueue (shared between Rachel and StatusListener)
        _debug_print("[VoiceBridgeV2] Step 2/6: Setting up notification queue...")
        await self._setup_notification_queue()
        _debug_print(f"[VoiceBridgeV2] Step 2/6 DONE ({time.time() - start_time:.2f}s)")

        # 3. Create orchestrator
        _debug_print("[VoiceBridgeV2] Step 3/6: Setting up orchestrator...")
        await self._setup_orchestrator()
        _debug_print(f"[VoiceBridgeV2] Step 3/6 DONE ({time.time() - start_time:.2f}s)")

        # 4. Create Rachel (voice interface)
        _debug_print("[VoiceBridgeV2] Step 4/6: Setting up Rachel...")
        await self._setup_rachel()
        _debug_print(f"[VoiceBridgeV2] Step 4/6 DONE ({time.time() - start_time:.2f}s)")

        # 5. Setup TTS queue
        _debug_print("[VoiceBridgeV2] Step 5/6: Starting TTS queue...")
        await self.tts_queue.start_processing()
        _debug_print(f"[VoiceBridgeV2] Step 5/6 DONE ({time.time() - start_time:.2f}s)")

        # 6. Start backend agents and listeners (skip if FORCE_SYNC_MODE)
        # StatusListener now subscribes BEFORE start_listeners() in _start_backend_agents()
        force_sync = os.getenv("FORCE_SYNC_MODE", "false").lower() == "true"
        if not force_sync:
            _debug_print("[VoiceBridgeV2] Step 6/6: Starting backend agents...")
            await self._start_backend_agents()
            _debug_print(f"[VoiceBridgeV2] Step 6/6 DONE ({time.time() - start_time:.2f}s)")
            _debug_print(f"MODE: Redis async (backend_available={self._backend_available})")
        else:
            _debug_print("MODE: SYNC (FORCE_SYNC_MODE=true - tools execute directly)")
            logger.info("FORCE_SYNC_MODE=true - skipping backend agents (using direct tool execution)")

        self._running = True
        _debug_print(f"[VoiceBridgeV2] FULLY INITIALIZED in {time.time() - start_time:.2f}s")
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
        import time
        try:
            from swarm.backend_agents import (
                get_bubbles_agent,
                get_ideas_agent,
                get_desktop_agent,
                get_coding_agent,
                get_roarboot_agent,
            )
            from swarm.event_bus import get_event_bus
            from swarm.listeners import get_status_listener, get_question_listener

            t0 = time.time()

            # Get event bus
            _debug_print("[BackendAgents] Getting event bus...")
            self._event_bus = get_event_bus()
            _debug_print(f"[BackendAgents] Event bus ready ({time.time() - t0:.2f}s)")

            # Create agents
            _debug_print("[BackendAgents] Creating agents...")
            self._bubbles_agent = get_bubbles_agent()
            self._ideas_agent = get_ideas_agent()
            self._desktop_agent = get_desktop_agent()
            self._coding_agent = get_coding_agent()

            try:
                self._roarboot_agent = get_roarboot_agent()
            except Exception as e:
                _debug_print(f"[BackendAgents] RoarbootAgent not available: {e}")

            _debug_print(f"[BackendAgents] Agents created ({time.time() - t0:.2f}s)")

            # Step 1: Subscribe all agents to their streams (no listeners yet)
            _debug_print("[BackendAgents] Starting BubblesAgent...")
            await self._bubbles_agent.start()
            _debug_print(f"[BackendAgents] BubblesAgent started ({time.time() - t0:.2f}s)")

            _debug_print("[BackendAgents] Starting IdeasAgent...")
            await self._ideas_agent.start()
            _debug_print(f"[BackendAgents] IdeasAgent started ({time.time() - t0:.2f}s)")

            _debug_print("[BackendAgents] Starting DesktopAgent...")
            await self._desktop_agent.start()
            _debug_print(f"[BackendAgents] DesktopAgent started ({time.time() - t0:.2f}s)")

            _debug_print("[BackendAgents] Starting CodingAgent...")
            await self._coding_agent.start()
            _debug_print(f"[BackendAgents] CodingAgent started ({time.time() - t0:.2f}s)")

            if self._roarboot_agent:
                _debug_print("[BackendAgents] Starting RoarbootAgent...")
                await self._roarboot_agent.start()
                _debug_print(f"[BackendAgents] RoarbootAgent started ({time.time() - t0:.2f}s)")

            # Step 2: Subscribe StatusListener BEFORE starting listeners
            # This ensures events:status gets a listener task
            _debug_print("[BackendAgents] Starting StatusListener...")
            self._status_listener = get_status_listener(
                notification_queue=self._notification_queue,
                tts_callback=self._tts_callback
            )
            await self._status_listener.start()
            _debug_print(f"[BackendAgents] StatusListener SUBSCRIBED ({time.time() - t0:.2f}s)")

            # Step 2.5: Subscribe QuestionListener for backend questions
            _debug_print("[BackendAgents] Starting QuestionListener...")
            self._question_listener = get_question_listener()
            await self._question_listener.start()
            _debug_print(f"[BackendAgents] QuestionListener SUBSCRIBED ({time.time() - t0:.2f}s)")

            # Step 3: NOW start all listeners (includes events:status)
            _debug_print("[BackendAgents] Starting event bus listeners...")
            await self._event_bus.start_listeners()
            _debug_print(f"[BackendAgents] Event bus listeners started ({time.time() - t0:.2f}s)")

            self._backend_available = True
            agents_list = "BubblesAgent, IdeasAgent, DesktopAgent, CodingAgent"
            if self._roarboot_agent:
                agents_list += ", RoarbootAgent"
            _debug_print(f"Backend agents STARTED: {agents_list} + Listeners")
            logger.info(f"Backend agents started: {agents_list} + Listeners")

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

    async def handle_voice_input(
        self,
        text: str,
        domain_hint: Optional[str] = None
    ) -> VoiceBridgeResult:
        """
        Process voice input through Rachel.

        Rachel is the voice interface that sends intent to the orchestrator.
        Backend agents execute the actual tools.

        Args:
            text: Transcribed voice input
            domain_hint: Optional domain hint (ideas, bubbles, desktop, coding, shuttles)
                        If provided, skips domain detection and routes directly.

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
        # Include domain_hint for direct routing
        input_event = InputEvent(
            text=text,
            timestamp=timestamp,
            target_space=SpaceType.IDEAS,
            domain_hint=domain_hint,
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
        if hasattr(self, '_bubbles_agent') and self._bubbles_agent:
            await self._bubbles_agent.stop()
        if self._ideas_agent:
            await self._ideas_agent.stop()
        if self._desktop_agent:
            await self._desktop_agent.stop()
        if self._coding_agent:
            await self._coding_agent.stop()
        if self._roarboot_agent:
            await self._roarboot_agent.stop()

        # Stop status listener
        if self._status_listener:
            await self._status_listener.stop()

        # Stop question listener
        if hasattr(self, '_question_listener') and self._question_listener:
            await self._question_listener.stop()

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
