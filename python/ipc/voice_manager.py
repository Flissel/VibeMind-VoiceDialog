"""
VoiceManager — extracted voice-related methods from ElectronBackend.

Manages the full voice lifecycle: OpenAI Realtime session, VoiceBridge,
background initialization of Minibook/Schedule/Messaging, tool call
dispatch, and coordinated shutdown.
"""

import asyncio
import os
import threading
import subprocess
from typing import Dict

from electron_backend import debug_log


class VoiceManager:
    """Handles all voice dialog lifecycle for the Electron backend."""

    def __init__(self, backend):
        self.backend = backend
        self.send_message = backend.send_message

    # ========================================================================
    # VOICE DIALOG
    # ========================================================================

    async def start_voice(self):
        """Start voice dialog session with OpenAI Realtime API."""
        self.backend._main_loop = asyncio.get_running_loop()
        debug_log(f"start_voice() called (active={self.backend.voice_active}, stopping={self.backend._voice_stopping}, "
                  f"session={self.backend.openai_realtime_session is not None}, bridge={self.backend.voice_bridge is not None})")

        from electron_backend import HAS_OPENAI_REALTIME
        debug_log(f"HAS_OPENAI_REALTIME: {HAS_OPENAI_REALTIME}")

        # Cancel any still-running start_voice task to prevent concurrent connect() calls
        # IMPORTANT: Skip if old_task is the current task (self-reference from
        # message handler storing the task before the body runs).
        current_task = asyncio.current_task()
        old_task = self.backend._voice_start_task
        if old_task and old_task is not current_task and not old_task.done():
            debug_log("Cancelling previous start_voice task before new start")
            self.backend._start_cancelled = True
            old_task.cancel()
            try:
                await asyncio.wait_for(asyncio.shield(old_task), timeout=5.0)
            except (asyncio.CancelledError, asyncio.TimeoutError, Exception):
                debug_log("Previous start_voice cancel timed out — proceeding anyway")
            self.backend._start_cancelled = False
        elif old_task is current_task:
            debug_log("start_voice: old_task is current task — skipping self-cancel")

        if not HAS_OPENAI_REALTIME:
            self.send_message({
                "type": "voice_error",
                "error": "OpenAI Realtime voice module not available (check voice/ package)"
            })
            return

        await self._start_voice_openai_realtime()

    async def _start_voice_openai_realtime(self):
        """
        Start voice with OpenAI Realtime API.

        Uses speech-to-speech with native function calling.
        The send_intent tool routes to the orchestrator.

        Startup order (optimized for fastest voice output):
        1. WebSocket connection (DNS needs free executor)
        2. Audio start + greeting (Rachel speaks immediately)
        3. VoiceBridge creation (Redis/backend - can be slow, runs in background)
        """
        from electron_backend import OpenAIRealtimeVoiceSession, create_voice_bridge_v2

        session = None  # Track for cleanup on CancelledError
        try:
            import time as _time
            _t_total = _time.time()
            debug_log("Initializing OpenAI Realtime voice session...")

            # Reset cancellation flag for this start attempt
            self.backend._start_cancelled = False

            # 0. Clean up any previous session DIRECTLY (not via stop_voice,
            #    which may return immediately if _voice_stopping is True from
            #    a concurrent stop call).
            old_session = self.backend.openai_realtime_session
            old_bridge = self.backend.voice_bridge
            if old_session or old_bridge:
                debug_log("Cleaning up previous session before restart...")
                if old_session:
                    self.backend.openai_realtime_session = None
                    try:
                        await asyncio.wait_for(old_session.disconnect(), timeout=5.0)
                    except (asyncio.TimeoutError, Exception) as e:
                        debug_log(f"Old session disconnect: {e}")
                if old_bridge:
                    self.backend.voice_bridge = None
                    try:
                        await old_bridge.shutdown()
                    except Exception as e:
                        debug_log(f"Old bridge shutdown: {e}")
                self.backend.voice_active = False
                debug_log("Previous session cleaned up")
                self.backend._start_cancelled = False  # Reset after cleanup

            # 1. Check API key first
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                debug_log("ERROR: OPENAI_API_KEY not set for Realtime voice")
                self.send_message({
                    "type": "voice_error",
                    "error": "OPENAI_API_KEY not set. Required for VOICE_PROVIDER=openai_realtime"
                })
                return

            # 2. Get Rachel's system prompt
            from spaces.ideas.agents.rachel_agent import RACHEL_VOICE_PROMPT
            system_prompt = RACHEL_VOICE_PROMPT

            # 3. Create OpenAI Realtime session (lightweight, no network yet)
            #    Use local var to avoid race with concurrent stop_voice()
            _t0 = _time.time()
            session = OpenAIRealtimeVoiceSession(
                api_key=api_key,
                system_prompt=system_prompt,
                on_tool_call=self._handle_realtime_tool_call,
                on_user_transcript=self._handle_user_transcript,
                on_agent_transcript=self._handle_agent_response,
                on_session_end=self._handle_realtime_session_end,
                on_error=self._handle_realtime_error,
            )
            debug_log(f"OpenAI Realtime session created ({_time.time() - _t0:.2f}s)")

            # 4. Connect WebSocket FIRST — before anything that touches Redis!
            #    VoiceBridgeV2 starts Redis connections that can exhaust the
            #    default ThreadPoolExecutor, blocking DNS resolution.
            #    Send status to UI so user sees progress (connection can take 15-20s).
            _t0 = _time.time()
            self.send_message({
                "type": "voice_status",
                "status": "connecting",
                "message": "Verbinde mit OpenAI Realtime..."
            })
            await session.connect()
            debug_log(f"WebSocket connected ({_time.time() - _t0:.2f}s)")

            # Check if stop_voice was called during our connect() wait
            if self.backend._start_cancelled:
                debug_log("Voice start cancelled during connect — aborting")
                await session.disconnect()
                return

            # 5. Start audio + greeting IMMEDIATELY after WebSocket connects.
            #    Rachel speaks right away while VoiceBridge initializes.
            self.backend.openai_realtime_session = session
            _t0 = _time.time()
            await session.start()
            debug_log(f"Audio capture + greeting started ({_time.time() - _t0:.2f}s)")

            # Check again after start()
            if self.backend._start_cancelled:
                debug_log("Voice start cancelled during audio init — aborting")
                await session.disconnect()
                self.backend.openai_realtime_session = None
                return

            self.backend.voice_active = True
            self.send_message({
                "type": "voice_started",
                "agent_name": "Rachel",
                "mode": "openai_realtime"
            })

            debug_log(f"Voice ACTIVE — Rachel speaking ({_time.time() - _t_total:.2f}s)")

            # 6. Pre-warm orchestrator in background so first voice command is fast.
            #    Without this, get_orchestrator() initializes lazily on first
            #    send_intent call, adding 2-5s to the first command.
            prewarm_task = asyncio.create_task(self._prewarm_orchestrator())
            prewarm_task.add_done_callback(self._log_task_exception)

            # 7. Create VoiceBridge in background (needed for tool calls).
            #    This can be slow (Redis connections, backend agents) but
            #    audio is already flowing so the user hears Rachel immediately.
            bg_task = asyncio.create_task(self._init_voice_bridge_background())
            bg_task.add_done_callback(self._log_task_exception)

            # 8. Initialize Minibook (inter-space collaboration) if enabled.
            #    Registers space agents and starts polling workers.
            if os.getenv("MINIBOOK_ENABLED", "false").lower() == "true":
                mb_task = asyncio.create_task(self._init_minibook_background())
                mb_task.add_done_callback(self._log_task_exception)

            # 9. Initialize Schedule Space (APScheduler) if enabled.
            #    Loads active tasks from DB and starts the scheduler.
            if os.getenv("SCHEDULE_ENABLED", "false").lower() == "true":
                sched_task = asyncio.create_task(self._init_schedule_background())
                sched_task.add_done_callback(self._log_task_exception)

            # 10. Initialize Messaging Bridge (Voice ↔ WhatsApp/Telegram) if enabled.
            #     Connects IncomingMessageHandler to Clawdbot bridge for
            #     relevance-filtered incoming message notifications.
            if os.getenv("MESSAGING_BRIDGE_ENABLED", "false").lower() == "true":
                msg_task = asyncio.create_task(self._init_messaging_bridge_background())
                msg_task.add_done_callback(self._log_task_exception)

            # 11. Initialize Flowzen (Blaue Rose) — background activity tracker.
            if os.getenv("FLOWZEN_ENABLED", "false").lower() == "true":
                fz_task = asyncio.create_task(self._init_flowzen_background())
                fz_task.add_done_callback(self._log_task_exception)

        except asyncio.CancelledError:
            debug_log("OpenAI Realtime start CANCELLED (task killed by stop/restart)")
            # Clean up the local session if it was connected
            if session:
                try:
                    await session.disconnect()
                except Exception:
                    pass
            raise  # Re-raise so the task shows as cancelled
        except Exception as e:
            debug_log(f"OpenAI Realtime start failed: {e}")
            import traceback
            debug_log(traceback.format_exc())
            self.send_message({
                "type": "voice_error",
                "error": str(e)
            })

    async def _prewarm_orchestrator(self):
        """Pre-warm the IntentOrchestrator so first voice command is fast.

        Without this, get_orchestrator() lazily initializes on first
        send_intent call, adding 2-5s to the user's first request.
        """
        import time as _time
        try:
            _t0 = _time.time()
            debug_log("Background: Pre-warming IntentOrchestrator...")
            from swarm.orchestrator import get_orchestrator
            _orch = get_orchestrator()
            debug_log(f"Background: IntentOrchestrator ready ({_time.time() - _t0:.2f}s)")
        except Exception as e:
            debug_log(f"Background: Orchestrator pre-warm failed (non-fatal): {e}")

    async def _init_voice_bridge_background(self):
        """Initialize VoiceBridgeV2 in the background (non-blocking for audio)."""
        from electron_backend import create_voice_bridge_v2

        import time as _time
        try:
            _t0 = _time.time()
            debug_log("Background: Initializing VoiceBridgeV2...")
            bridge = await asyncio.wait_for(
                create_voice_bridge_v2(model_client=None, event_manager=None),
                timeout=30.0
            )
            # Check if voice was stopped during init
            if self.backend.voice_active:
                self.backend.voice_bridge = bridge
                debug_log(f"Background: VoiceBridgeV2 ready ({_time.time() - _t0:.2f}s)")
            else:
                debug_log("Background: Voice stopped during VoiceBridge init — discarding")
                try:
                    await bridge.shutdown()
                except Exception:
                    pass
        except asyncio.TimeoutError:
            debug_log("Background: VoiceBridgeV2 TIMEOUT (30s) — tool calls will use direct orchestrator")
        except Exception as e:
            debug_log(f"Background: VoiceBridgeV2 failed: {e} — tool calls will use direct orchestrator")

    async def _init_minibook_background(self):
        """Initialize Minibook inter-space collaboration in the background."""
        import time as _time
        try:
            _t0 = _time.time()
            debug_log("Background: Initializing Minibook...")

            from spaces.minibook.tools.minibook_client import get_minibook_client
            from spaces.minibook.tools.collaboration_tools import register_all_space_agents
            from spaces.minibook.workers.minibook_workers import (
                get_discussion_poller,
                create_space_responders,
            )

            client = get_minibook_client()

            # Check if Minibook is reachable (retry up to 5 times for Docker startup)
            status = None
            for attempt in range(5):
                status = client.get_status()
                if status.get("success"):
                    break
                debug_log(f"Background: Minibook not ready (attempt {attempt+1}/5): {status.get('error', '?')}")
                await asyncio.sleep(3)

            if not status or not status.get("success"):
                debug_log(f"Background: Minibook not reachable after 5 attempts — skipping")
                return

            # Create collaboration project and register all space agents
            project_id = register_all_space_agents(client)
            debug_log(f"Background: Minibook agents registered, project={project_id}")

            # Start DiscussionPollerWorker in its OWN thread so it doesn't
            # starve when the voice WebSocket dominates the main event loop.
            def _get_session():
                return self.backend.openai_realtime_session

            poller = get_discussion_poller(
                realtime_session_getter=_get_session,
            )

            def _run_poller_thread():
                """Run poller in a dedicated thread with its own event loop."""
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(poller.poll_loop())
                except Exception as e:
                    debug_log(f"Poller thread error: {e}")
                finally:
                    loop.close()

            poller_thread = threading.Thread(
                target=_run_poller_thread, daemon=True, name="minibook-poller"
            )
            poller_thread.start()

            # Start SpaceMinibookResponders — each in its OWN thread.
            # Without this, the main event loop (dominated by voice WebSocket
            # audio events every ~20ms) starves the responder polling tasks.
            responders = create_space_responders()
            for space_key, responder in responders.items():
                def _run_responder_thread(r=responder, key=space_key):
                    """Run responder in a dedicated thread with its own event loop."""
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    try:
                        loop.run_until_complete(r.poll_and_respond())
                    except Exception as e:
                        debug_log(f"Responder {key} thread error: {e}")
                    finally:
                        loop.close()

                resp_thread = threading.Thread(
                    target=_run_responder_thread, daemon=True,
                    name=f"minibook-resp-{space_key}",
                )
                resp_thread.start()

            debug_log(
                f"Background: Minibook ready — {len(responders)} space responders "
                f"({_time.time() - _t0:.2f}s)"
            )

            # ── MinibookHub: Central Execution (when USE_MINIBOOK_HUB=true) ──
            if os.getenv("USE_MINIBOOK_HUB", "false").lower() in ("true", "1"):
                try:
                    from swarm.orchestrator import get_orchestrator
                    from spaces.minibook.minibook_hub import MinibookHub
                    from spaces.minibook.enrichment.pipeline import create_enrichment_pipeline
                    from spaces.minibook.rachel_interface import RachelInterface
                    from spaces.minibook.result_aggregator import ResultAggregator
                    from spaces.minibook.config import get_config as get_minibook_config

                    orch = get_orchestrator()
                    mb_config = get_minibook_config()

                    # Rachel Interface — passive dashboard
                    rachel = RachelInterface()

                    # Register all known agents in Rachel
                    from spaces.minibook.tools.collaboration_tools import SPACE_AGENT_REGISTRY
                    for space_key, agent_info in SPACE_AGENT_REGISTRY.items():
                        rachel.register_agent(agent_info["name"], space_key)

                    # Enrichment Pipeline — classifier reused from orchestrator
                    pipeline = create_enrichment_pipeline(
                        classifier=orch.classifier,
                        rachel_interface=rachel,
                        enrichment_model=mb_config.enrichment_model,
                        use_llm_routing=mb_config.enrichment_enabled,
                    )

                    # Result Aggregator — sync-wait + async-poll
                    aggregator = ResultAggregator(
                        realtime_session_getter=_get_session,
                        rachel_interface=rachel,
                        sync_timeout=mb_config.hub_sync_timeout,
                        async_timeout=mb_config.hub_async_timeout,
                    )

                    # MinibookHub — central dispatch
                    hub = MinibookHub(
                        client=client,
                        enrichment_pipeline=pipeline,
                        rachel_interface=rachel,
                        result_aggregator=aggregator,
                        sync_timeout=mb_config.hub_sync_timeout,
                    )

                    # Wire into orchestrator
                    orch.set_minibook_hub(hub)

                    debug_log(
                        f"Background: MinibookHub ACTIVATED — all intents route through Minibook "
                        f"(sync={mb_config.hub_sync_timeout}s, async={mb_config.hub_async_timeout}s, "
                        f"model={mb_config.enrichment_model})"
                    )

                except Exception as hub_err:
                    debug_log(f"Background: MinibookHub init failed: {hub_err} — using direct execution")
                    import traceback
                    debug_log(traceback.format_exc())

        except Exception as e:
            debug_log(f"Background: Minibook init failed: {e} — collaboration disabled")

    async def _init_schedule_background(self):
        """Initialize the Schedule Space (APScheduler) in the background."""
        import time as _time
        try:
            _t0 = _time.time()
            debug_log("Background: Initializing Schedule Space...")

            from spaces.schedule.workers.schedule_worker import ScheduleWorker
            from spaces.schedule.tools.schedule_tools import (
                set_electron_sender,
                set_schedule_worker,
            )

            # Set Electron IPC sender for schedule tools
            set_electron_sender(self.send_message)

            # Session + orchestrator getters for the worker
            def _get_session():
                return self.backend.openai_realtime_session

            def _get_orchestrator():
                from swarm.orchestrator import get_orchestrator
                return get_orchestrator()

            # Create and start ScheduleWorker
            worker = ScheduleWorker(
                realtime_session_getter=_get_session,
                orchestrator_getter=_get_orchestrator,
            )
            await worker.start()

            # Wire worker into schedule tools (so add_job/remove_job work live)
            set_schedule_worker(worker)

            self.backend._schedule_worker = worker
            debug_log(
                f"Background: Schedule Space ready — {worker.job_count} active jobs "
                f"({_time.time() - _t0:.2f}s)"
            )

        except Exception as e:
            debug_log(f"Background: Schedule init failed: {e} — scheduling disabled")
            import traceback
            debug_log(traceback.format_exc())

    async def _init_messaging_bridge_background(self):
        """Initialize Messaging Bridge (Voice <-> WhatsApp/Telegram) in background."""
        import time as _time
        try:
            _t0 = _time.time()
            debug_log("Background: Initializing Messaging Bridge...")

            from spaces.desktop.messaging.relevance_filter import RelevanceFilter
            from spaces.desktop.messaging.incoming_handler import (
                IncomingMessageHandler,
                set_incoming_handler,
            )

            # Create handler with voice session getter
            def _get_session():
                return self.backend.openai_realtime_session

            handler = IncomingMessageHandler(
                relevance_filter=RelevanceFilter(),
                voice_session_getter=_get_session,
            )

            # Register globally (for other modules to access)
            set_incoming_handler(handler)

            # Register with ClawdbotBridge (if available)
            try:
                from spaces.desktop.Automation_ui.backend.app.services.clawdbot_bridge import (
                    get_clawdbot_bridge,
                )
                bridge = await get_clawdbot_bridge()
                bridge.set_incoming_handler(handler)
                debug_log("Background: Messaging handler registered with Clawdbot bridge")
            except Exception as e:
                debug_log(f"Background: Clawdbot bridge not available: {e}")

            debug_log(
                f"Background: Messaging Bridge ready ({_time.time() - _t0:.2f}s)"
            )

        except Exception as e:
            debug_log(f"Background: Messaging Bridge init failed: {e}")

    async def _init_flowzen_background(self):
        """Initialize Flowzen activity tracker with periodic Brain summary."""
        try:
            from spaces.flowzen.activity_tracker import get_activity_tracker
            from spaces.flowzen.brain_bridge import get_brain_bridge

            tracker = get_activity_tracker()
            bridge = get_brain_bridge()

            # Wire Rose <-> Brain callbacks
            bridge.set_rose_callback(tracker.on_brain_response)
            tracker.set_brain_callback(lambda summary: asyncio.ensure_future(bridge.process_summary(summary)))

            # Set Electron IPC sender if available
            if hasattr(self, 'backend') and hasattr(self.backend, '_send_to_electron'):
                tracker.set_electron_sender(self.backend._send_to_electron)

            # Start periodic summary loop
            asyncio.create_task(self._flowzen_periodic_loop(tracker))

            debug_log("Flowzen (Blaue Rose): background tracker initialized")
        except Exception as e:
            debug_log(f"Flowzen: background init failed: {e}")

    async def _flowzen_periodic_loop(self, tracker):
        """Run send_periodic_summary() every 30 minutes."""
        import asyncio as _asyncio
        from spaces.flowzen.config import get_config

        interval = get_config().summary_interval_minutes * 60  # seconds
        debug_log(f"Flowzen: periodic summary loop started (every {interval}s)")

        while True:
            await _asyncio.sleep(interval)
            try:
                tracker.send_periodic_summary()
            except Exception as e:
                debug_log(f"Flowzen: periodic summary error: {e}")

    def _log_task_exception(self, task: asyncio.Task):
        """Callback to log unhandled exceptions from background tasks."""
        if task.cancelled():
            return
        exc = task.exception()
        if exc:
            debug_log(f"Background task failed: {exc}")

    async def _handle_realtime_tool_call(self, call_id: str, name: str, arguments: Dict) -> str:
        """
        Handle tool calls from OpenAI Realtime API (async).

        send_intent: Fire-and-forget — returns immediately, result delivered
                     async via inject_system_message().
        check_results: Poll NotificationQueue for pending results.

        Args:
            call_id: Unique call ID from OpenAI
            name: Tool name ('send_intent' or 'check_results')
            arguments: Tool arguments dict

        Returns:
            Result string for voice response
        """
        if name == "send_intent":
            user_request = arguments.get("user_request", "")
            debug_log(f"[REALTIME TOOL] send_intent (async): {user_request}")

            if not user_request:
                return "I didn't understand that. What would you like?"

            # Start dispatch in a pure background thread — completely
            # decoupled from the voice event loop. The thread sleeps 1.5s
            # (so Rachel finishes speaking), runs the orchestrator with its
            # own event loop, then delivers results back via main loop.
            thread = threading.Thread(
                target=self._dispatch_in_thread,
                args=(user_request,),
                daemon=True,
            )
            thread.start()
            debug_log(f"[DISPATCH] Background thread launched")

            return "Ich kuemmere mich darum."

        elif name == "check_results":
            debug_log("[REALTIME TOOL] check_results")
            try:
                from swarm.orchestrator.notification_queue import get_notification_queue
                queue = get_notification_queue()
                notifications = queue.get_and_clear()

                if not notifications:
                    return "No new results."

                parts = []
                for n in notifications:
                    result_str = str(n.result)
                    if len(result_str) > 300:
                        result_str = result_str[:300] + "..."
                    parts.append(result_str)

                return "\n".join(parts)

            except Exception as e:
                debug_log(f"check_results error: {e}")
                return "Failed to retrieve results."

        else:
            debug_log(f"[REALTIME TOOL] Unknown tool: {name}")
            return f"Unbekanntes Tool: {name}"

    def _dispatch_in_thread(self, user_request: str) -> None:
        """
        Complete dispatch in a pure background thread.

        Completely decoupled from the voice event loop:
        - time.sleep(1.5) instead of asyncio.sleep
        - Own event loop for the orchestrator
        - Result delivery via run_coroutine_threadsafe back to main loop

        This avoids the problem where asyncio.create_task() doesn't get
        scheduled because the voice WebSocket event loop is too busy.
        """
        import time as _time

        try:
            debug_log(f"[DISPATCH] Thread ALIVE — sleeping 1.5s for Rachel to speak...")

            # Wait for Rachel to finish speaking "Ich kuemmere mich darum"
            _time.sleep(1.5)

            debug_log("[DISPATCH] Thread: running orchestrator...")
            result = self._run_orchestrator_blocking(user_request)
            debug_log(f"[DISPATCH] Thread: orchestrator done, delivering result...")

            # Deliver result on main event loop
            if self.backend._main_loop and not self.backend._main_loop.is_closed():
                asyncio.run_coroutine_threadsafe(
                    self._deliver_dispatch_result(result),
                    self.backend._main_loop,
                )
            else:
                debug_log("[DISPATCH] Main loop closed — cannot deliver result")

        except Exception as e:
            debug_log(f"[DISPATCH] Thread error: {e}")
            import traceback
            traceback.print_exc()

    def _run_orchestrator_blocking(self, user_request: str):
        """
        Run orchestrator with its own event loop (called from background thread).

        Creates a fresh event loop because process_intent() is async but
        internally calls synchronous HTTP (IntentClassifier).
        """
        from swarm.orchestrator import get_orchestrator

        orchestrator = get_orchestrator()
        new_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(new_loop)
        try:
            result = new_loop.run_until_complete(
                orchestrator.process_intent(user_request)
            )
            return result
        except Exception as e:
            debug_log(f"[DISPATCH] Orchestrator error: {e}")
            import traceback
            traceback.print_exc()
            return None
        finally:
            new_loop.close()

    async def _deliver_dispatch_result(self, result) -> None:
        """
        Deliver orchestrator result via voice injection.
        Runs on the main event loop (scheduled via run_coroutine_threadsafe).
        """
        try:
            if not result:
                debug_log("Dispatch: no result from orchestrator")
                await self._inject_voice_result(
                    "The request could not be processed. Please try again."
                )
                return

            debug_log(
                f"Dispatch result: {result.event_type} -> "
                f"{result.response_hint[:200]}{'...' if len(result.response_hint) > 200 else ''}"
            )

            # Store in context for Smart Rachel
            if not result.is_conversational and not result.error:
                try:
                    from swarm.orchestrator.system_context_store import get_system_context_store
                    context_store = get_system_context_store()
                    context_store.store(
                        event_type=result.event_type,
                        result=result.response_hint,
                    )
                except Exception:
                    pass

            # Notify Electron UI
            if not result.is_conversational:
                self.send_message({
                    "type": "task_queued",
                    "task_type": "backend_agent",
                    "domain": "auto",
                })

            # Deliver result to Rachel via voice injection
            if result.error:
                await self._inject_voice_result(
                    f"There was a problem: {result.error}"
                )
            elif result.response_hint:
                await self._inject_voice_result(result.response_hint)

        except Exception as e:
            debug_log(f"Dispatch delivery error: {e}")
            import traceback
            traceback.print_exc()

    async def _inject_voice_result(self, text: str) -> None:
        """Inject result text into Rachel's voice session, with NotificationQueue fallback."""
        session = self.backend.openai_realtime_session
        if session:
            try:
                await session.inject_system_message(text)
                return
            except Exception as e:
                debug_log(f"Voice injection failed: {e}")

        # Fallback: queue for next user input
        try:
            from swarm.orchestrator.notification_queue import get_notification_queue
            queue = get_notification_queue()
            queue.add_notification(
                job_id=f"async-{id(text)}",
                event_type="async.result",
                result=text,
            )
            debug_log("Result queued in NotificationQueue (voice injection fallback)")
        except Exception as e:
            debug_log(f"Could not deliver result: {e}")

    def _handle_realtime_session_end(self):
        """Handle OpenAI Realtime session ending (server-initiated disconnect)."""
        debug_log("OpenAI Realtime session ended (server-initiated)")
        try:
            loop = asyncio.get_event_loop()
            loop.call_soon_threadsafe(
                lambda: asyncio.create_task(self.stop_voice())
            )
        except Exception as e:
            debug_log(f"Could not schedule stop_voice: {e}")
            self.backend.voice_active = False

    def _handle_realtime_error(self, error_msg: str):
        """Handle OpenAI Realtime errors."""
        debug_log(f"OpenAI Realtime error: {error_msg}")
        self.send_message({
            "type": "voice_error",
            "error": error_msg
        })

    async def stop_voice(self):
        """Stop voice dialog session (with re-entrance guard)."""
        debug_log(f"stop_voice() called (active={self.backend.voice_active}, stopping={self.backend._voice_stopping})")
        # Signal any pending start_voice to abort
        self.backend._start_cancelled = True

        # Cancel running start_voice task (kills connect() mid-flight)
        # Timeout ensures stop_voice never hangs if connect() is stuck on dead WebSocket
        start_task = self.backend._voice_start_task
        if start_task and not start_task.done():
            debug_log("stop_voice: cancelling running start_voice task")
            start_task.cancel()
            try:
                await asyncio.wait_for(asyncio.shield(start_task), timeout=5.0)
            except (asyncio.CancelledError, asyncio.TimeoutError, Exception):
                debug_log("stop_voice: start_task cancel timed out — proceeding anyway")
        self.backend._voice_start_task = None

        if getattr(self.backend, '_voice_stopping', False):
            debug_log("stop_voice: already stopping — returning early")
            return
        self.backend._voice_stopping = True
        try:
            await self._stop_voice_impl()
        finally:
            self.backend._voice_stopping = False
            debug_log("stop_voice() complete")

    async def _stop_voice_impl(self):
        """Internal stop implementation.

        IMPORTANT: Capture local references to session/bridge before async
        disconnect.  A concurrent start_voice() may replace
        self.backend.openai_realtime_session while we are awaiting disconnect().
        Only clear the instance vars if they still point to the objects
        we stopped — otherwise a new session was started and we must not
        clobber it.
        """
        # Capture references BEFORE any await
        session_to_stop = self.backend.openai_realtime_session
        bridge_to_stop = self.backend.voice_bridge

        # Stop OpenAI Realtime session if active (with timeout to prevent hanging)
        if session_to_stop:
            try:
                await asyncio.wait_for(
                    session_to_stop.disconnect(),
                    timeout=8.0,
                )
                debug_log("OpenAI Realtime session disconnected")
            except asyncio.TimeoutError:
                debug_log("OpenAI Realtime disconnect TIMED OUT (8s) — forcing cleanup")
                # Force-clear state even if disconnect() hung
                session_to_stop._is_running = False
                session_to_stop._is_connected = False
                session_to_stop._audio_manager.cleanup()
            except Exception as e:
                debug_log(f"Error disconnecting OpenAI Realtime: {e}")
            # Only clear if a new start_voice hasn't replaced the session
            if self.backend.openai_realtime_session is session_to_stop:
                self.backend.openai_realtime_session = None

        # Stop VoiceBridgeV2 if active
        if bridge_to_stop:
            try:
                await bridge_to_stop.shutdown()
                debug_log("VoiceBridgeV2 shutdown complete")
            except Exception as e:
                debug_log(f"Error shutting down VoiceBridgeV2: {e}")
            if self.backend.voice_bridge is bridge_to_stop:
                self.backend.voice_bridge = None

        # Only send voice_stopped if no new session was started during shutdown
        if self.backend.openai_realtime_session is None:
            self.backend.voice_active = False
            self.send_message({"type": "voice_stopped"})
        else:
            debug_log("stop_voice_impl: new session active — skipping voice_stopped")

    async def cleanup(self):
        """Coordinated shutdown of all services. Budget: 12s total."""
        from electron_backend import _shutdown_event

        debug_log("cleanup() starting...")

        # Signal all daemon threads to stop their loops
        _shutdown_event.set()

        # 1. Stop voice session + VoiceBridgeV2 (5s budget)
        try:
            await asyncio.wait_for(self._stop_voice_impl(), timeout=5.0)
            debug_log("cleanup: voice stopped")
        except asyncio.TimeoutError:
            debug_log("cleanup: voice stop timed out (5s)")
        except Exception as e:
            debug_log(f"cleanup: voice stop error: {e}")

        # 2. Stop Automation UI subprocess (3s budget)
        if hasattr(self.backend, '_automation_ui_proc') and self.backend._automation_ui_proc:
            try:
                self.backend._automation_ui_proc.terminate()
                self.backend._automation_ui_proc.wait(timeout=3)
                debug_log("cleanup: automation_ui stopped")
            except subprocess.TimeoutExpired:
                try:
                    self.backend._automation_ui_proc.kill()
                    debug_log("cleanup: automation_ui force-killed")
                except Exception:
                    pass
            except Exception as e:
                debug_log(f"cleanup: automation_ui stop error: {e}")

        # 2b. Stop eyeTerm (camera + MJPEG stream on port 8099)
        for attr in ('_eyeterm_headless', '_eyeterm_app'):
            et = getattr(self.backend, attr, None)
            if et:
                try:
                    et.stop()
                    debug_log(f"cleanup: {attr} stopped")
                except Exception as e:
                    debug_log(f"cleanup: {attr} stop error: {e}")
                setattr(self.backend, attr, None)

        # 3. Stop Rowboat update checker
        if hasattr(self.backend, '_rowboat_update_checker'):
            try:
                self.backend._rowboat_update_checker.stop()
                debug_log("cleanup: update checker stopped")
            except Exception:
                pass

        # 4. Close MongoDB publisher connection
        try:
            from publishing import get_ideas_publisher
            pub = get_ideas_publisher()
            if hasattr(pub, 'close'):
                pub.close()
                debug_log("cleanup: MongoDB publisher closed")
        except Exception:
            pass

        # 5. Force reset EventBus (closes Redis)
        try:
            from swarm.event_bus import force_reset_event_bus
            force_reset_event_bus()
            debug_log("cleanup: EventBus reset")
        except Exception as e:
            debug_log(f"cleanup: EventBus reset error: {e}")

        # 6. Cancel all remaining asyncio tasks (2s budget)
        pending = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        if pending:
            debug_log(f"cleanup: cancelling {len(pending)} remaining tasks...")
            for task in pending:
                task.cancel()
            try:
                await asyncio.wait_for(
                    asyncio.gather(*pending, return_exceptions=True),
                    timeout=2.0,
                )
            except asyncio.TimeoutError:
                debug_log("cleanup: task cancellation timed out (2s)")

        debug_log("cleanup() complete")

    def _handle_user_transcript(self, text: str):
        """Handle transcribed user speech."""
        from electron_backend import HAS_SESSION_TOOLS, mark_user_speech

        debug_log(f"[USER SPEECH] {text}")

        # Track user speech time to suppress "Bist du noch da?" keepalives
        if HAS_SESSION_TOOLS and mark_user_speech:
            mark_user_speech()

        self.send_message({
            "type": "user_transcript",
            "text": text
        })

        # Parse voice commands for navigation
        self._parse_voice_command(text)

    def _handle_agent_response(self, text: str):
        """Handle agent text response."""
        debug_log(f"[AGENT RESPONSE] {text}")
        self.send_message({
            "type": "agent_response",
            "text": text
        })

    def _parse_voice_command(self, text: str):
        """Parse voice commands for bubble navigation."""
        text_lower = text.lower()

        # Voice command parsing and execution code will be added here
        # This is a placeholder for future voice command implementation

        # Navigate between bubbles based on text match (simplified example)
        # For now, this responds with transcript but doesn't actually enter a different bubble

        if "enter" in text_lower or "go to" in text_lower or "open" in text_lower:
            for bubble in self.backend.bubbles.values():
                if bubble.title.lower() in text_lower:
                    self.send_message({
                        "type": "navigate_to_bubble",
                        "bubble_id": bubble.id
                    })
                    break

        elif "exit" in text_lower or "back" in text_lower or "leave" in text_lower:
            if self.backend.current_bubble_id:
                self.send_message({"type": "exit_bubble"})
