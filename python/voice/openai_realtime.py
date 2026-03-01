"""
OpenAI Realtime Voice Session for VibeMind

Replaces ElevenLabs Conversational AI with OpenAI Realtime API.
Provides speech-to-speech interaction with native function calling.

Architecture:
    Microphone → AudioManager → WebSocket (input_audio_buffer.append)
                                    ↕
                          OpenAI Realtime API
                           (gpt-4o-realtime)
                                    ↕
    Speaker ← AudioManager ← WebSocket (response.audio.delta)
                                    ↓
                          Function calls → send_intent()
                                    ↓
                          Orchestrator → Backend Agents

Session Lifecycle:
    1. connect()           - Opens WebSocket, configures session
    2. start()             - Starts mic capture + event processing
    3. [running]           - Audio streams bidirectionally
    4. disconnect()        - Graceful shutdown

Key Events:
    → input_audio_buffer.append     - Send mic audio to server
    ← response.audio.delta          - Receive speech audio
    ← response.audio_transcript.delta - Receive text transcript
    ← response.function_call_arguments.done - Execute tool
    ← input_audio_buffer.speech_started/stopped - VAD events
    ← error                         - Handle errors
"""

import asyncio
import base64
import json
import logging
import os
import time
from typing import Optional, Callable, Dict, Any

from voice.audio_manager import AudioManager
from voice.session_config import (
    create_session_config,
    SEND_INTENT_TOOL,
    DEFAULT_MODEL,
    DEFAULT_VOICE,
    SAMPLE_RATE,
)

logger = logging.getLogger(__name__)


class OpenAIRealtimeVoiceSession:
    """
    OpenAI Realtime API voice session.

    Manages the full voice interaction loop:
    - WebSocket connection to OpenAI Realtime
    - Microphone capture → base64 → WebSocket
    - WebSocket audio → speaker playback
    - Function call handling (send_intent)
    - Automatic reconnection on timeout (30-min limit)

    Usage:
        session = OpenAIRealtimeVoiceSession(
            api_key="sk-...",
            system_prompt=RACHEL_VOICE_PROMPT,
            on_tool_call=handle_tool_call,
        )
        await session.connect()
        await session.start()
        # ... session runs until disconnect
        await session.disconnect()
    """

    # OpenAI Realtime session timeout (30 minutes)
    SESSION_TIMEOUT_SECONDS = 30 * 60

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        voice: Optional[str] = None,
        system_prompt: str = "",
        tools: Optional[list] = None,
        on_tool_call: Optional[Callable[[str, str, Dict], str]] = None,
        on_user_transcript: Optional[Callable[[str], None]] = None,
        on_agent_transcript: Optional[Callable[[str], None]] = None,
        on_session_end: Optional[Callable[[], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
        on_vad_speech_started: Optional[Callable[[], None]] = None,
        on_vad_speech_stopped: Optional[Callable[[], None]] = None,
    ):
        """
        Initialize OpenAI Realtime voice session.

        Args:
            api_key: OpenAI API key (or from OPENAI_API_KEY env)
            model: Model name (default: gpt-4o-realtime-preview)
            voice: Voice name (default: alloy)
            system_prompt: System instructions for the voice agent
            tools: Tool definitions (default: [SEND_INTENT_TOOL])
            on_tool_call: Callback(call_id, name, arguments) -> result string
            on_user_transcript: Callback(text) when user speech is transcribed
            on_agent_transcript: Callback(text) when agent speech is transcribed
            on_session_end: Callback when session ends
            on_error: Callback(error_message) on errors
            on_vad_speech_started: Callback when user starts speaking
            on_vad_speech_stopped: Callback when user stops speaking
        """
        self._api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self._api_key:
            raise ValueError("OPENAI_API_KEY not found")

        self._model = model or os.getenv("OPENAI_REALTIME_MODEL", DEFAULT_MODEL)
        self._voice = voice or os.getenv("OPENAI_REALTIME_VOICE", DEFAULT_VOICE)
        self._system_prompt = system_prompt
        self._tools = tools or [SEND_INTENT_TOOL]

        # Callbacks
        self._on_tool_call = on_tool_call
        self._on_user_transcript = on_user_transcript
        self._on_agent_transcript = on_agent_transcript
        self._on_session_end = on_session_end
        self._on_error = on_error
        self._on_vad_speech_started = on_vad_speech_started
        self._on_vad_speech_stopped = on_vad_speech_stopped

        # Connection state
        self._connection = None
        self._is_connected = False
        self._is_running = False
        self._event_task: Optional[asyncio.Task] = None
        self._audio_send_task: Optional[asyncio.Task] = None

        # Audio manager
        self._audio_manager = AudioManager(
            sample_rate=SAMPLE_RATE,
            on_audio_chunk=None,  # Set during start()
        )

        # Audio send queue (mic chunks → WebSocket)
        self._audio_queue: asyncio.Queue = asyncio.Queue()

        # Session timing
        self._session_start_time: float = 0
        self._reconnect_count: int = 0

        # Transcript accumulation
        self._current_user_transcript = ""
        self._current_agent_transcript = ""

        # Function call accumulation
        self._function_call_args: Dict[str, str] = {}  # call_id → accumulated args

        logger.info(
            f"OpenAIRealtimeVoiceSession initialized: "
            f"model={self._model}, voice={self._voice}"
        )

    async def connect(self) -> None:
        """
        Open WebSocket connection and configure session.

        Establishes connection to OpenAI Realtime API and sends
        session.update with voice config, tools, and system prompt.
        """
        if self._is_connected:
            logger.warning("Already connected")
            return

        try:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(api_key=self._api_key)

            logger.info(f"Connecting to OpenAI Realtime: model={self._model}")
            self._connection = await client.realtime.connect(
                model=self._model
            ).__aenter__()

            # Configure session
            session_config = create_session_config(
                system_prompt=self._system_prompt,
                voice=self._voice,
                tools=self._tools,
            )

            await self._connection.session.update(session=session_config)
            logger.info("Session configured successfully")

            self._is_connected = True
            self._session_start_time = time.time()

        except Exception as e:
            logger.error(f"Connection failed: {e}")
            self._is_connected = False
            if self._on_error:
                self._on_error(f"Connection failed: {e}")
            raise

    async def start(self) -> None:
        """
        Start the voice session.

        Begins microphone capture and event processing loop.
        This method returns immediately - processing happens in background tasks.
        """
        if not self._is_connected:
            raise RuntimeError("Not connected. Call connect() first.")

        if self._is_running:
            logger.warning("Session already running")
            return

        self._is_running = True

        # Set up audio callback to queue chunks
        self._audio_manager.set_audio_callback(self._on_mic_audio)

        # Start audio I/O
        self._audio_manager.start_capture()
        self._audio_manager.start_playback()

        # Start event processing and audio sending tasks
        self._event_task = asyncio.create_task(self._event_loop())
        self._audio_send_task = asyncio.create_task(self._audio_send_loop())

        logger.info("Voice session started - listening for speech")

    async def disconnect(self) -> None:
        """
        Gracefully disconnect the session.

        Stops audio, cancels tasks, closes WebSocket.
        """
        logger.info("Disconnecting voice session...")
        self._is_running = False

        # Stop audio
        self._audio_manager.cleanup()

        # Cancel tasks
        for task in [self._event_task, self._audio_send_task]:
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        # Close WebSocket
        if self._connection:
            try:
                await self._connection.__aexit__(None, None, None)
            except Exception as e:
                logger.debug(f"WebSocket close: {e}")
            self._connection = None

        self._is_connected = False

        if self._on_session_end:
            self._on_session_end()

        logger.info(
            f"Voice session disconnected "
            f"(duration: {time.time() - self._session_start_time:.0f}s, "
            f"reconnects: {self._reconnect_count})"
        )

    async def send_text_response(self, text: str) -> None:
        """
        Send a text response to be spoken by the model.

        Used by TTSQueue/StatusListener to inject responses
        (e.g., task completion notifications) into the voice stream.

        Args:
            text: Text to be spoken
        """
        if not self._is_connected or not self._connection:
            logger.warning("Cannot send text response - not connected")
            return

        try:
            # Create a response with the text as a user message
            await self._connection.response.create(
                response={
                    "modalities": ["text", "audio"],
                    "instructions": f"Sage dem User folgendes: {text}",
                }
            )
            logger.debug(f"Sent text response: {text[:50]}...")

        except Exception as e:
            logger.error(f"Error sending text response: {e}")

    def _on_mic_audio(self, base64_audio: str) -> None:
        """
        Callback from AudioManager when a mic chunk is ready.

        Puts the base64-encoded audio into the async queue.
        This is called from the sounddevice callback thread.
        """
        if self._is_running:
            try:
                self._audio_queue.put_nowait(base64_audio)
            except asyncio.QueueFull:
                pass  # Drop chunk if queue is full

    async def _audio_send_loop(self) -> None:
        """
        Continuously send audio chunks from queue to WebSocket.

        Reads from the async queue and sends input_audio_buffer.append events.
        """
        while self._is_running:
            try:
                # Wait for audio chunk with timeout
                try:
                    base64_audio = await asyncio.wait_for(
                        self._audio_queue.get(), timeout=0.5
                    )
                except asyncio.TimeoutError:
                    # Check session timeout
                    if self._should_reconnect():
                        await self._handle_session_timeout()
                    continue

                # Send to OpenAI Realtime
                if self._connection and self._is_connected:
                    await self._connection.input_audio_buffer.append(
                        audio=base64_audio
                    )

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Audio send error: {e}")
                await asyncio.sleep(0.1)

    async def _event_loop(self) -> None:
        """
        Process server events from the OpenAI Realtime WebSocket.

        Dispatches events to appropriate handlers:
        - Audio playback
        - Transcript logging
        - Function call execution
        - VAD events
        - Errors
        """
        try:
            async for event in self._connection:
                if not self._is_running:
                    break

                try:
                    await self._handle_event(event)
                except Exception as e:
                    logger.error(f"Event handler error: {e}", exc_info=True)

        except asyncio.CancelledError:
            logger.debug("Event loop cancelled")
        except Exception as e:
            logger.error(f"Event loop error: {e}")
            if self._is_running:
                # Unexpected disconnect - try to reconnect
                await self._handle_unexpected_disconnect(e)

    async def _handle_event(self, event) -> None:
        """
        Dispatch a single server event.

        Args:
            event: Event object from the OpenAI Realtime connection
        """
        event_type = event.type

        # === Audio Events ===
        if event_type == "response.audio.delta":
            # Received audio chunk - enqueue for playback
            if hasattr(event, "delta") and event.delta:
                self._audio_manager.enqueue_audio(event.delta)

        # === Transcript Events ===
        elif event_type == "response.audio_transcript.delta":
            # Agent speech transcript (incremental)
            if hasattr(event, "delta"):
                self._current_agent_transcript += event.delta

        elif event_type == "response.audio_transcript.done":
            # Agent transcript complete
            transcript = self._current_agent_transcript.strip()
            if transcript:
                logger.info(f"Agent: {transcript}")
                if self._on_agent_transcript:
                    self._on_agent_transcript(transcript)
            self._current_agent_transcript = ""

        elif event_type == "conversation.item.input_audio_transcription.completed":
            # User speech transcript
            transcript = getattr(event, "transcript", "")
            if transcript:
                logger.info(f"User: {transcript}")
                if self._on_user_transcript:
                    self._on_user_transcript(transcript)

        # === Function Call Events ===
        elif event_type == "response.function_call_arguments.delta":
            # Accumulate function call arguments
            call_id = getattr(event, "call_id", "")
            if call_id:
                self._function_call_args.setdefault(call_id, "")
                self._function_call_args[call_id] += getattr(event, "delta", "")

        elif event_type == "response.function_call_arguments.done":
            # Function call complete - execute it
            call_id = getattr(event, "call_id", "")
            name = getattr(event, "name", "")
            args_str = getattr(event, "arguments", "") or self._function_call_args.get(call_id, "")

            # Clean up accumulator
            self._function_call_args.pop(call_id, None)

            await self._execute_function_call(call_id, name, args_str)

        # === VAD Events ===
        elif event_type == "input_audio_buffer.speech_started":
            logger.debug("VAD: Speech started")
            # Clear playback to allow interruption
            self._audio_manager.clear_playback_buffer()
            if self._on_vad_speech_started:
                self._on_vad_speech_started()

        elif event_type == "input_audio_buffer.speech_stopped":
            logger.debug("VAD: Speech stopped")
            if self._on_vad_speech_stopped:
                self._on_vad_speech_stopped()

        # === Session Events ===
        elif event_type == "session.created":
            logger.info("Session created")

        elif event_type == "session.updated":
            logger.info("Session configuration updated")

        elif event_type == "response.done":
            # Response complete
            logger.debug("Response complete")

        elif event_type == "response.created":
            logger.debug("Response started")

        # === Error Events ===
        elif event_type == "error":
            error_msg = getattr(event, "error", {})
            if isinstance(error_msg, dict):
                error_text = error_msg.get("message", str(error_msg))
            else:
                error_text = str(error_msg)

            logger.error(f"Server error: {error_text}")
            if self._on_error:
                self._on_error(error_text)

        # === Rate Limit Events ===
        elif event_type == "rate_limits.updated":
            logger.debug("Rate limits updated")

        else:
            logger.debug(f"Unhandled event: {event_type}")

    async def _execute_function_call(
        self, call_id: str, name: str, arguments_str: str
    ) -> None:
        """
        Execute a function call from the model and return result.

        Args:
            call_id: Unique ID for this function call
            name: Function name (e.g., 'send_intent')
            arguments_str: JSON string of function arguments
        """
        logger.info(f"Function call: {name}({arguments_str[:100]})")

        try:
            arguments = json.loads(arguments_str) if arguments_str else {}
        except json.JSONDecodeError:
            arguments = {}
            logger.warning(f"Could not parse function args: {arguments_str}")

        # Execute via callback
        result = "Fehler: Tool nicht verfuegbar"

        if self._on_tool_call:
            try:
                result = self._on_tool_call(call_id, name, arguments)
                if asyncio.iscoroutine(result):
                    result = await result
                result = str(result) if result else "Erledigt."
            except Exception as e:
                logger.error(f"Tool execution error: {e}")
                result = f"Fehler bei der Ausfuehrung: {str(e)}"

        # Send result back to OpenAI Realtime
        try:
            # Create a conversation item with the function call output
            await self._connection.conversation.item.create(
                item={
                    "type": "function_call_output",
                    "call_id": call_id,
                    "output": result,
                }
            )

            # Trigger a new response from the model
            await self._connection.response.create()

            logger.info(f"Tool result sent: {result[:100]}")

        except Exception as e:
            logger.error(f"Error sending tool result: {e}")

    def _should_reconnect(self) -> bool:
        """Check if session is approaching the 30-minute timeout."""
        if self._session_start_time == 0:
            return False

        elapsed = time.time() - self._session_start_time
        # Reconnect 60 seconds before timeout
        return elapsed > (self.SESSION_TIMEOUT_SECONDS - 60)

    async def _handle_session_timeout(self) -> None:
        """
        Handle approaching session timeout with silent reconnect.

        Disconnects and reconnects without disrupting the user experience.
        """
        logger.info("Session approaching timeout - reconnecting...")
        self._reconnect_count += 1

        # Stop audio briefly
        self._audio_manager.stop_capture()

        # Close old connection
        if self._connection:
            try:
                await self._connection.__aexit__(None, None, None)
            except Exception:
                pass

        # Reconnect
        try:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(api_key=self._api_key)
            self._connection = await client.realtime.connect(
                model=self._model
            ).__aenter__()

            # Reconfigure session
            session_config = create_session_config(
                system_prompt=self._system_prompt,
                voice=self._voice,
                tools=self._tools,
            )
            await self._connection.session.update(session=session_config)

            self._session_start_time = time.time()

            # Resume audio
            self._audio_manager.start_capture()

            logger.info(f"Reconnected successfully (#{self._reconnect_count})")

        except Exception as e:
            logger.error(f"Reconnection failed: {e}")
            if self._on_error:
                self._on_error(f"Reconnection failed: {e}")
            self._is_running = False

    async def _handle_unexpected_disconnect(self, error: Exception) -> None:
        """
        Handle unexpected disconnection with retry.

        Args:
            error: The exception that caused the disconnect
        """
        logger.warning(f"Unexpected disconnect: {error}")

        max_retries = 3
        for attempt in range(1, max_retries + 1):
            if not self._is_running:
                return

            wait_time = attempt * 2  # 2, 4, 6 seconds
            logger.info(f"Retry {attempt}/{max_retries} in {wait_time}s...")
            await asyncio.sleep(wait_time)

            try:
                await self.connect()
                # Restart event loop (audio is still running)
                self._event_task = asyncio.create_task(self._event_loop())
                logger.info("Reconnected after unexpected disconnect")
                return

            except Exception as e:
                logger.error(f"Retry {attempt} failed: {e}")

        # All retries failed
        logger.error("All reconnection attempts failed")
        self._is_running = False
        if self._on_error:
            self._on_error("Connection lost after multiple retries")
        if self._on_session_end:
            self._on_session_end()

    # === Public Properties ===

    @property
    def is_connected(self) -> bool:
        """Whether the WebSocket connection is active."""
        return self._is_connected

    @property
    def is_running(self) -> bool:
        """Whether the voice session is actively running."""
        return self._is_running

    @property
    def session_duration(self) -> float:
        """Seconds since session started."""
        if self._session_start_time:
            return time.time() - self._session_start_time
        return 0

    @property
    def audio_manager(self) -> AudioManager:
        """Access the audio manager for direct control."""
        return self._audio_manager

    async def wait_for_end(self) -> None:
        """
        Block until the session ends.

        Useful for standalone mode where the session should run
        until manually stopped or disconnected.
        """
        while self._is_running:
            await asyncio.sleep(0.5)
