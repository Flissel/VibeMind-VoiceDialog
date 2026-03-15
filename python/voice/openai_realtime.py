"""
OpenAI Realtime Voice Session for VibeMind

OpenAI Realtime API voice session for VibeMind.
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
import queue  # Thread-safe queue for audio from sounddevice thread
import socket
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Callable, Dict, Any

from openai import AsyncOpenAI

# Fix Windows console encoding for German umlauts in stderr debug prints
if sys.platform == "win32":
    try:
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

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
        self._connection_manager = None
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
        # Uses thread-safe queue.Queue because sounddevice callback runs in a separate thread
        self._audio_queue: queue.Queue = queue.Queue(maxsize=100)

        # Session timing
        self._session_start_time: float = 0
        self._reconnect_count: int = 0

        # Server-side turn detection active?  When True, the server
        # handles speech_started/stopped events and response.create —
        # client-side VAD is disabled to avoid empty-buffer conflicts.
        self._server_vad_active: bool = False

        # Transcript accumulation
        self._current_user_transcript = ""
        self._current_agent_transcript = ""

        # Function call accumulation
        self._function_call_args: Dict[str, str] = {}  # call_id → accumulated args

        # Pre-create the AsyncOpenAI client (no network, just object setup).
        # This avoids a 10s+ delay in connect() on Windows where the
        # AsyncOpenAI constructor + import is unexpectedly slow.
        self._client = AsyncOpenAI(api_key=self._api_key)

        logger.info(
            f"OpenAIRealtimeVoiceSession initialized: "
            f"model={self._model}, voice={self._voice}"
        )

    # Retry config for connect()
    MAX_CONNECT_RETRIES = 3
    CONNECT_TIMEOUTS = [30.0, 40.0, 50.0]  # Generous timeouts (user's network takes ~17s)

    async def connect(self) -> None:
        """
        Open WebSocket connection and configure session.

        Establishes connection to OpenAI Realtime API and sends
        session.update with voice config, tools, and system prompt.
        Waits for session.created from server before returning to
        ensure the connection is fully stable.

        Retries up to MAX_CONNECT_RETRIES times with increasing timeouts.
        """
        if self._is_connected:
            logger.warning("Already connected")
            return

        _t0 = time.time()

        def _dbg(msg):
            elapsed = time.time() - _t0
            print(f"[Python DEBUG] [RealtimeVoice] [{elapsed:.3f}s] {msg}", file=sys.stderr, flush=True)

        # Ensure the event loop has a dedicated ThreadPoolExecutor so
        # DNS resolution inside the websockets library doesn't get starved
        # by other tasks sharing the default pool (stdin reader, Redis, etc.)
        loop = asyncio.get_running_loop()
        if loop._default_executor is None or getattr(loop, '_vibemind_executor_set', False) is False:
            _dbg("Setting dedicated ThreadPoolExecutor(max_workers=8) on event loop")
            loop.set_default_executor(ThreadPoolExecutor(max_workers=8))
            loop._vibemind_executor_set = True

        # Pre-resolve DNS asynchronously so the websocket library finds
        # the IP in the OS cache.  IMPORTANT: Must NOT use blocking
        # dns_event.wait() here — that freezes the entire event loop.
        _dbg("Pre-resolving api.openai.com DNS...")
        try:
            dns_result = await asyncio.wait_for(
                loop.run_in_executor(
                    None, socket.getaddrinfo, "api.openai.com", 443, socket.AF_INET
                ),
                timeout=10.0,
            )
            ip = dns_result[0][4][0]
            _dbg(f"DNS resolved: api.openai.com → {ip}")
        except asyncio.TimeoutError:
            _dbg("DNS pre-resolve timed out (proceeding anyway)")
        except Exception as e:
            _dbg(f"DNS pre-resolve failed: {e}")

        last_error = None
        for attempt in range(self.MAX_CONNECT_RETRIES):
            ws_timeout = self.CONNECT_TIMEOUTS[min(attempt, len(self.CONNECT_TIMEOUTS) - 1)]
            try:
                if attempt > 0:
                    wait_secs = 2 ** attempt  # 2s, 4s
                    _dbg(f"Retry {attempt + 1}/{self.MAX_CONNECT_RETRIES} in {wait_secs}s (timeout={ws_timeout}s)...")
                    await asyncio.sleep(wait_secs)

                _dbg(f"Connecting to {self._model} via BETA path (attempt {attempt + 1}, timeout={ws_timeout}s)...")
                self._connection_manager = self._client.beta.realtime.connect(
                    model=self._model,
                )
                _dbg("Connection manager created, opening WebSocket...")

                # Open the WebSocket connection with timeout.
                self._connection = await asyncio.wait_for(
                    self._connection_manager.__aenter__(),
                    timeout=ws_timeout,
                )
                _dbg("WebSocket connected!")

                # Wait for session.created from server before configuring.
                _dbg("Waiting for session.created from server...")
                first_event = await asyncio.wait_for(
                    self._connection.recv(),
                    timeout=10.0,
                )
                if first_event.type == "session.created":
                    _dbg("session.created received — connection stable")
                else:
                    _dbg(f"First event was {first_event.type} (expected session.created)")

                # Configure session
                session_config = create_session_config(
                    system_prompt=self._system_prompt,
                    voice=self._voice,
                    tools=self._tools,
                )

                # Log config keys (not full prompt, just structure)
                config_summary = {k: (type(v).__name__ if k == 'instructions' else v) for k, v in session_config.items()}
                _dbg(f"Sending session.update with config: {config_summary}")
                await self._connection.session.update(session=session_config)

                # Wait for session.updated confirmation
                _dbg("Waiting for session.updated confirmation...")
                update_event = await asyncio.wait_for(
                    self._connection.recv(),
                    timeout=10.0,
                )
                if update_event.type == "session.updated":
                    # Log key config fields from the server response
                    session = getattr(update_event, 'session', None)
                    if session:
                        td = getattr(session, 'turn_detection', None)
                        mods = getattr(session, 'modalities', None) or getattr(session, 'output_modalities', None)
                        _dbg(f"session.updated confirmed — turn_detection={td}, modalities={mods}")
                        # Track if server handles turn detection (semantic_vad or server_vad)
                        # When active, disable client-side VAD to avoid empty-buffer conflicts
                        if td is not None:
                            self._server_vad_active = True
                            _dbg("Server-side turn detection ACTIVE — client-side VAD disabled")
                        else:
                            self._server_vad_active = False
                            _dbg("No server turn detection — client-side VAD ACTIVE")
                    else:
                        _dbg("session.updated confirmed — session fully configured!")
                elif update_event.type == "error":
                    err_detail = getattr(update_event, 'error', None) or getattr(update_event, 'message', None)
                    _dbg(f"session.update ERROR from server: {err_detail}")
                    # Log full event for debugging
                    try:
                        _dbg(f"Full error event: {update_event}")
                    except Exception:
                        pass
                else:
                    _dbg(f"Got {update_event.type} instead of session.updated (proceeding anyway)")

                self._is_connected = True
                self._session_start_time = time.time()
                _dbg(f"Connection complete ({time.time() - _t0:.2f}s total)")
                return  # Success — exit retry loop

            except asyncio.CancelledError:
                # Task was cancelled (stop_voice) — clean up and propagate immediately
                _dbg(f"CANCELLED on attempt {attempt + 1} — stopping retries")
                if self._connection_manager:
                    try:
                        await asyncio.wait_for(
                            self._connection_manager.__aexit__(None, None, None),
                            timeout=3.0,
                        )
                    except (asyncio.TimeoutError, Exception):
                        _dbg("WebSocket cleanup timed out during cancel — forcing")
                    self._connection_manager = None
                raise

            except asyncio.TimeoutError:
                _dbg(f"TIMEOUT on attempt {attempt + 1}/{self.MAX_CONNECT_RETRIES} ({ws_timeout}s)")
                last_error = ConnectionError(f"OpenAI Realtime connection timed out (attempt {attempt + 1})")
                # Clean up failed connection manager
                if self._connection_manager:
                    try:
                        await self._connection_manager.__aexit__(None, None, None)
                    except Exception:
                        pass
                    self._connection_manager = None
                continue

            except Exception as e:
                _dbg(f"CONNECTION FAILED on attempt {attempt + 1}: {type(e).__name__}: {e}")
                import traceback
                traceback.print_exc(file=sys.stderr)
                last_error = e
                if self._connection_manager:
                    try:
                        await self._connection_manager.__aexit__(None, None, None)
                    except Exception:
                        pass
                    self._connection_manager = None
                continue

        # All retries exhausted
        _dbg(f"All {self.MAX_CONNECT_RETRIES} connection attempts failed!")
        logger.error(f"Connection failed after {self.MAX_CONNECT_RETRIES} retries: {last_error}")
        self._is_connected = False
        if self._on_error:
            self._on_error(f"Connection failed after {self.MAX_CONNECT_RETRIES} retries")
        raise ConnectionError(f"OpenAI Realtime connection failed after {self.MAX_CONNECT_RETRIES} retries") from last_error

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

        # Start event processing and audio sending tasks IMMEDIATELY.
        # These can begin processing WebSocket events while audio initializes.
        self._event_task = asyncio.create_task(self._event_loop())
        self._audio_send_task = asyncio.create_task(self._audio_send_loop())

        # Trigger greeting IMMEDIATELY to keep the WebSocket alive.
        # Audio output will buffer the greeting audio and play it once
        # PortAudio initialization completes (which can take 30+ seconds
        # on Windows first use, enumerating WASAPI/DirectSound devices).
        if self._connection:
            await self._connection.response.create(
                response={
                    "instructions": (
                        "Begruesse den User kurz und freundlich. "
                        "Sag z.B. 'Hey! Ich bin Rachel, deine VibeMind Assistentin. Was kann ich fuer dich tun?'"
                    ),
                }
            )
            print("[Python DEBUG] [RealtimeVoice] Greeting triggered (audio buffered until device ready)", file=sys.stderr, flush=True)

        # Start audio I/O in thread executor (non-blocking).
        async def _init_audio():
            try:
                loop = asyncio.get_running_loop()
                print("[Python DEBUG] [RealtimeVoice] Starting audio I/O (in executor)...", file=sys.stderr, flush=True)
                _t0_audio = time.time()
                await loop.run_in_executor(None, self._audio_manager.start_capture)
                await loop.run_in_executor(None, self._audio_manager.start_playback)
                _audio_dur = time.time() - _t0_audio
                print(f"[Python DEBUG] [RealtimeVoice] Audio I/O ready ({_audio_dur:.1f}s)", file=sys.stderr, flush=True)
            except Exception as e:
                print(f"[Python DEBUG] [RealtimeVoice] Audio init error: {e}", file=sys.stderr, flush=True)
                logger.error(f"Audio init error: {e}")

        self._audio_init_task = asyncio.create_task(_init_audio())

        print("[Python DEBUG] [RealtimeVoice] Voice session ACTIVE - audio initializing in background", file=sys.stderr, flush=True)
        logger.info("Voice session started - audio initializing")

    async def disconnect(self) -> None:
        """
        Gracefully disconnect the session.

        Stops audio, cancels tasks, closes WebSocket.
        """
        logger.info("Disconnecting voice session...")
        self._is_running = False

        # Stop audio
        self._audio_manager.cleanup()

        # Cancel event-loop tasks with timeout (WebSocket ops can stall)
        for task in [self._event_task, self._audio_send_task]:
            if task and not task.done():
                task.cancel()
                try:
                    await asyncio.wait_for(asyncio.shield(task), timeout=3.0)
                except (asyncio.CancelledError, asyncio.TimeoutError, Exception):
                    pass

        # Cancel audio init task separately — it may be stuck in
        # run_in_executor (PortAudio blocks for 30s+ on Windows and
        # can't be cancelled from Python). Just cancel and move on.
        audio_init = getattr(self, '_audio_init_task', None)
        if audio_init and not audio_init.done():
            audio_init.cancel()
            # Don't await — the executor thread will finish on its own.
            # _is_running=False prevents greeting from being triggered.

        # Close WebSocket via connection manager (with timeout — can stall on dead connection)
        if hasattr(self, '_connection_manager') and self._connection_manager:
            try:
                await asyncio.wait_for(
                    self._connection_manager.__aexit__(None, None, None),
                    timeout=5.0,
                )
            except asyncio.TimeoutError:
                logger.warning("WebSocket close timed out (5s) — forcing cleanup")
            except Exception as e:
                logger.debug(f"WebSocket close: {e}")
            self._connection_manager = None
            self._connection = None

        self._is_connected = False

        # NOTE: Do NOT call _on_session_end here. disconnect() is called from
        # stop_voice() which handles voice_stopped. Calling it here would cause
        # duplicate voice_stopped messages. _on_session_end is only called from
        # _handle_unexpected_disconnect for server-initiated disconnects.

        logger.info(
            f"Voice session disconnected "
            f"(duration: {time.time() - self._session_start_time:.0f}s, "
            f"reconnects: {self._reconnect_count})"
        )

    async def inject_system_message(self, text: str) -> None:
        """
        Inject a context message into the active session and trigger Rachel to speak it.

        Silently adds a system message to the conversation history.
        Rachel sees it as context on her next turn — no forced response,
        no interruption, no 'already_has_active_response' errors.

        Used by _dispatch_in_thread and DiscussionPollerWorker to deliver
        async results.

        Args:
            text: The result text to add to conversation context
        """
        if not self._is_connected or not self._connection:
            logger.warning("Cannot inject system message - not connected")
            return

        try:
            await self._connection.conversation.item.create(
                item={
                    "type": "message",
                    "role": "system",
                    "content": [{"type": "input_text", "text": f"[RESULT]: {text}"}],
                }
            )
            # NO response.create() — Rachel picks this up naturally
            # on the next user turn. No interruption, no race condition.
            print(f"[Python DEBUG] [RealtimeVoice] Result injected into context: {text[:80]}...", file=sys.stderr, flush=True)
            logger.info(f"Injected system message (silent): {text[:80]}...")
        except Exception as e:
            logger.error(f"Error injecting system message: {e}")

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
                    "output_modalities": ["audio"],
                    "instructions": f"Sage dem User folgendes: {text}",
                }
            )
            logger.debug(f"Sent text response: {text[:50]}...")

        except Exception as e:
            logger.error(f"Error sending text response: {e}")

    def _on_mic_audio(self, base64_audio: str) -> None:
        """
        Callback from AudioManager when a mic chunk is ready.

        Puts the base64-encoded audio into the thread-safe queue.
        This is called from the sounddevice callback thread.
        """
        if self._is_running:
            try:
                self._audio_queue.put_nowait(base64_audio)
            except queue.Full:
                pass  # Drop chunk if queue is full

    # Client-side silence detection thresholds
    # FALLBACK only — used when server-side turn_detection (semantic_vad)
    # is disabled or fails.  When semantic_vad is active the server handles
    # turn-taking; these thresholds serve as a safety net with a generous
    # silence window (2s) so the user is never cut off mid-sentence.
    #
    # Tuned for HyperX QuadCast 2 at ~57% volume:
    #   Background noise ≈ 30-60 RMS, speech ≈ 150-5000+ RMS
    SILENCE_RMS_THRESHOLD = 80       # Below this RMS = silence (int16 range 0-32768)
    SPEECH_RMS_THRESHOLD = 150       # Above this RMS = speech detected
    SILENCE_DURATION_MS = 2000       # Silence duration to trigger commit (ms) — generous fallback
    MIN_SPEECH_DURATION_MS = 300     # Minimum speech before we consider it real

    async def _audio_send_loop(self) -> None:
        """
        Continuously send audio chunks from queue to WebSocket.

        Also implements client-side silence detection as a FALLBACK when
        server-side turn_detection (semantic_vad) is disabled.  When
        server VAD is active, the server handles speech boundaries and
        response.create — client-side VAD is skipped entirely.
        """
        chunks_sent = 0
        last_log_time = time.time()

        # Client-side VAD state (only used when _server_vad_active is False)
        is_speaking = False
        speech_start_time = 0.0
        last_speech_time = 0.0
        silence_commit_pending = False

        while self._is_running:
            try:
                # Poll thread-safe queue (non-blocking to stay async-friendly)
                try:
                    base64_audio = self._audio_queue.get_nowait()
                except queue.Empty:
                    # No audio available - yield to event loop
                    await asyncio.sleep(0.02)  # 20ms polling interval

                    # Client-side silence check while idle (only if no server VAD)
                    if not self._server_vad_active and is_speaking and not silence_commit_pending:
                        now = time.time()
                        silence_ms = (now - last_speech_time) * 1000
                        if silence_ms > self.SILENCE_DURATION_MS:
                            speech_ms = (now - speech_start_time) * 1000
                            if speech_ms > self.MIN_SPEECH_DURATION_MS:
                                silence_commit_pending = True

                    if self._should_reconnect():
                        await self._handle_session_timeout()
                    continue

                # Send to OpenAI Realtime
                if self._connection and self._is_connected:
                    await self._connection.input_audio_buffer.append(
                        audio=base64_audio
                    )
                    chunks_sent += 1

                    now = time.time()
                    rms = self._audio_manager.last_rms

                    # --- Client-side silence detection (FALLBACK only) ---
                    # When server-side turn detection is active (semantic_vad),
                    # skip all client-side VAD logic — the server handles it.
                    if not self._server_vad_active:
                        if rms >= self.SPEECH_RMS_THRESHOLD:
                            # Speech detected
                            if not is_speaking:
                                is_speaking = True
                                speech_start_time = now
                                silence_commit_pending = False
                                print(f"[Python DEBUG] [RealtimeVoice] CLIENT VAD: Speech STARTED (RMS={rms:.0f})", file=sys.stderr, flush=True)
                                # Notify UI
                                if self._on_vad_speech_started:
                                    self._on_vad_speech_started()
                            last_speech_time = now

                        elif rms < self.SILENCE_RMS_THRESHOLD and is_speaking:
                            # Silence detected while speaking
                            silence_ms = (now - last_speech_time) * 1000
                            if silence_ms > self.SILENCE_DURATION_MS and not silence_commit_pending:
                                speech_ms = (now - speech_start_time) * 1000
                                if speech_ms > self.MIN_SPEECH_DURATION_MS:
                                    silence_commit_pending = True

                        # Commit buffer when silence detected after speech
                        if silence_commit_pending:
                            silence_commit_pending = False
                            is_speaking = False
                            speech_duration = time.time() - speech_start_time
                            print(
                                f"[Python DEBUG] [RealtimeVoice] CLIENT VAD: Speech STOPPED "
                                f"({speech_duration:.1f}s) — committing buffer + requesting response",
                                file=sys.stderr, flush=True,
                            )
                            if self._on_vad_speech_stopped:
                                self._on_vad_speech_stopped()

                            try:
                                # Commit audio buffer (creates user message)
                                await self._connection.input_audio_buffer.commit()
                                # Trigger model response
                                await self._connection.response.create()
                            except Exception as commit_err:
                                err_str = str(commit_err)
                                if "already_has_active_response" in err_str:
                                    logger.debug("Response already active, skipping create")
                                else:
                                    print(f"[Python DEBUG] [RealtimeVoice] Commit/response error: {commit_err}", file=sys.stderr, flush=True)

                    # Log progress every 5 seconds
                    if now - last_log_time > 5.0:
                        vad_mode = "server" if self._server_vad_active else "client"
                        print(
                            f"[Python DEBUG] [RealtimeVoice] Audio: {chunks_sent} chunks sent, "
                            f"queue={self._audio_queue.qsize()}, RMS={rms:.0f}, VAD={vad_mode}",
                            file=sys.stderr, flush=True,
                        )
                        last_log_time = now

            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[Python DEBUG] [RealtimeVoice] Audio send error: {type(e).__name__}: {e}", file=sys.stderr, flush=True)
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
        event_count = 0
        try:
            print("[Python DEBUG] [RealtimeVoice] Event loop started, waiting for events...", file=sys.stderr, flush=True)
            async for event in self._connection:
                if not self._is_running:
                    break

                event_count += 1
                # Always log important events (VAD, errors, responses), sample the rest
                is_important = event.type in (
                    "input_audio_buffer.speech_started",
                    "input_audio_buffer.speech_stopped",
                    "response.created",
                    "response.done",
                    "response.function_call_arguments.done",
                    "error",
                )
                if event_count <= 5 or is_important or event_count % 100 == 0:
                    print(f"[Python DEBUG] [RealtimeVoice] Event #{event_count}: {event.type}", file=sys.stderr, flush=True)

                try:
                    await self._handle_event(event)
                except Exception as e:
                    print(f"[Python DEBUG] [RealtimeVoice] Event handler error: {type(e).__name__}: {e}", file=sys.stderr, flush=True)
                    logger.error(f"Event handler error: {e}", exc_info=True)

        except asyncio.CancelledError:
            logger.debug("Event loop cancelled")
        except Exception as e:
            print(f"[Python DEBUG] [RealtimeVoice] Event loop CRASHED: {type(e).__name__}: {e}", file=sys.stderr, flush=True)
            import traceback
            traceback.print_exc(file=sys.stderr)
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

        # === Audio Events (Beta: response.audio.*, GA: response.output_audio.*) ===
        if event_type in ("response.audio.delta", "response.output_audio.delta"):
            # Received audio chunk - enqueue for playback
            if hasattr(event, "delta") and event.delta:
                self._audio_manager.enqueue_audio(event.delta)

        # === Transcript Events (Beta: response.audio_transcript.*, GA: response.output_audio_transcript.*) ===
        elif event_type in ("response.audio_transcript.delta", "response.output_audio_transcript.delta"):
            # Agent speech transcript (incremental)
            if hasattr(event, "delta"):
                self._current_agent_transcript += event.delta

        elif event_type in ("response.audio_transcript.done", "response.output_audio_transcript.done"):
            # Agent transcript complete
            transcript = self._current_agent_transcript.strip()
            if transcript:
                print(f"[Python DEBUG] [RealtimeVoice] Rachel: {transcript[:100]}", file=sys.stderr, flush=True)
                logger.info(f"Agent: {transcript}")
                if self._on_agent_transcript:
                    self._on_agent_transcript(transcript)
            self._current_agent_transcript = ""

        elif event_type in (
            "conversation.item.input_audio_transcription.completed",
            "conversation.item.input_audio_transcription.delta",
        ):
            # User speech transcript
            transcript = getattr(event, "transcript", "")
            if transcript:
                print(f"[Python DEBUG] [RealtimeVoice] User: {transcript[:100]}", file=sys.stderr, flush=True)
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
            # Function call complete - execute it as a background task.
            # IMPORTANT: Do NOT await here — the event loop must stay free
            # to process audio/transcript events while the tool call runs.
            # Awaiting would block the entire event loop if the SDK's
            # conversation.item.create or response.create calls stall.
            call_id = getattr(event, "call_id", "")
            name = getattr(event, "name", "")
            args_str = getattr(event, "arguments", "") or self._function_call_args.get(call_id, "")

            # Clean up accumulator
            self._function_call_args.pop(call_id, None)

            asyncio.create_task(self._execute_function_call(call_id, name, args_str))

        # === VAD Events (server_vad — currently disabled, kept as fallback) ===
        elif event_type == "input_audio_buffer.speech_started":
            print("[Python DEBUG] [RealtimeVoice] SERVER VAD: Speech STARTED", file=sys.stderr, flush=True)
            # Clear playback to allow interruption
            self._audio_manager.clear_playback_buffer()
            if self._on_vad_speech_started:
                self._on_vad_speech_started()

        elif event_type == "input_audio_buffer.speech_stopped":
            print("[Python DEBUG] [RealtimeVoice] SERVER VAD: Speech STOPPED", file=sys.stderr, flush=True)
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
                error_code = error_msg.get("code", "")
            else:
                error_text = str(error_msg)
                error_code = ""

            # Non-critical errors that can be safely ignored
            if "already_has_active_response" in error_text or error_code == "conversation_already_has_active_response":
                logger.debug(f"Non-critical: {error_text}")
                return

            logger.error(f"Server error: {error_text}")
            if self._on_error:
                self._on_error(error_text)

        # === Rate Limit Events ===
        elif event_type == "rate_limits.updated":
            logger.debug("Rate limits updated")

        # === Informational events (no action needed) ===
        elif event_type in (
            "input_audio_buffer.committed",
            "conversation.item.created",
            "conversation.item.added",
            "conversation.item.done",
            "response.output_item.added",
            "response.output_item.done",
            "response.content_part.added",
            "response.content_part.done",
            "response.audio.done",
            "response.output_audio.done",
        ):
            logger.debug(f"Event: {event_type}")

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
        print(f"[Python DEBUG] [RealtimeVoice] _execute_function_call START: {name}", file=sys.stderr, flush=True)

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
                # If the tool handler is async, await it directly on the event loop.
                # This allows the handler to create_task() for async dispatches.
                # If sync, run in executor to avoid blocking.
                if asyncio.iscoroutinefunction(self._on_tool_call):
                    result = await self._on_tool_call(call_id, name, arguments)
                else:
                    loop = asyncio.get_running_loop()
                    result = await loop.run_in_executor(
                        None, self._on_tool_call, call_id, name, arguments
                    )
                result = str(result) if result else "Erledigt."
            except Exception as e:
                logger.error(f"Tool execution error: {e}")
                result = f"Fehler bei der Ausfuehrung: {str(e)}"

        print(f"[Python DEBUG] [RealtimeVoice] Tool result ready, sending back: {result[:80]}", file=sys.stderr, flush=True)

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
            try:
                await self._connection.response.create()
            except Exception as resp_err:
                err_str = str(resp_err)
                if "already_has_active_response" in err_str:
                    # Model already generating a response - safe to skip
                    logger.debug("Response already active, skipping create")
                else:
                    raise

            print(f"[Python DEBUG] [RealtimeVoice] _execute_function_call DONE: result sent to OpenAI", file=sys.stderr, flush=True)
            logger.info(f"Tool result sent: {result[:100]}")

        except Exception as e:
            print(f"[Python DEBUG] [RealtimeVoice] _execute_function_call ERROR: {e}", file=sys.stderr, flush=True)
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

        # Close old connection via connection manager (with timeout)
        if hasattr(self, '_connection_manager') and self._connection_manager:
            try:
                await asyncio.wait_for(
                    self._connection_manager.__aexit__(None, None, None),
                    timeout=5.0,
                )
            except (asyncio.TimeoutError, Exception):
                pass

        # Reconnect
        try:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(api_key=self._api_key)
            self._connection_manager = client.beta.realtime.connect(
                model=self._model
            )
            self._connection = await self._connection_manager.__aenter__()

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
