"""EyeTerm IPC handlers."""

import asyncio
import logging
import os

logger = logging.getLogger(__name__)


def debug_log(msg):
    from electron_backend import debug_log as _debug_log
    _debug_log(msg)


class EyeTermHandlers:
    """Handles EyeTerm IPC messages."""

    def __init__(self, backend):
        self.backend = backend
        self.send_message = backend.send_message

    async def handle_eyeterm_start(self, message: dict):
        """Start eyeTerm in a background thread."""
        if hasattr(self.backend, '_eyeterm_app') and self.backend._eyeterm_app:
            self.send_message({"type": "eyeterm_status", "status": "already_running"})
            return
        if hasattr(self.backend, '_eyeterm_headless') and self.backend._eyeterm_headless:
            self.send_message({"type": "eyeterm_status", "status": "already_running"})
            return
        try:
            import threading
            from spaces.desktop.eyeterm.config import AppConfig
            from spaces.desktop.eyeterm.app import EyeTermApp

            config = AppConfig.from_env()
            # Enable streaming for Electron embedding
            config.stream.enabled = True
            config.stream.port = int(os.environ.get("EYETERM_STREAM_PORT", "8099"))
            # Apply cursor config from env
            config.cursor.enabled = os.environ.get("EYETERM_CURSOR_ENABLED", "false").lower() == "true"

            self.backend._eyeterm_app = EyeTermApp(config)

            # Wire command router to IntentOrchestrator for complex tasks
            self._wire_eyeterm_orchestrator()

            thread = threading.Thread(
                target=self.backend._eyeterm_app.run,
                name="eyeterm-main",
                daemon=True,
            )
            thread.start()
            self.send_message({"type": "eyeterm_status", "status": "started"})
            debug_log("eyeTerm started in background thread")
        except Exception as e:
            debug_log(f"eyeTerm start failed: {e}")
            self.send_message({"type": "eyeterm_status", "status": "error", "message": str(e)})

    def _wire_eyeterm_orchestrator(self):
        """Wire eyeTerm's CommandRouter to route complex tasks through VibeMind orchestrator."""
        if not hasattr(self.backend, '_eyeterm_app') or not self.backend._eyeterm_app:
            return

        async def _route_to_orchestrator(transcript, gaze_context):
            """Route complex task through IntentOrchestrator (same path as chat panel)."""
            try:
                from swarm.orchestrator import get_orchestrator
                orchestrator = get_orchestrator()
                if orchestrator:
                    result = await orchestrator.process_intent(
                        text=transcript,
                        user_id="eyeterm",
                        session_id="eyeterm",
                        extra_context=gaze_context,
                    )
                    if result and result.response_hint:
                        debug_log(f"eyeTerm agent result: {result.response_hint[:100]}")
            except Exception as e:
                debug_log(f"eyeTerm orchestrator routing failed: {e}")

        def _agent_team_callback(transcript, gaze_context):
            """Thread-safe callback to route to async orchestrator."""
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.run_coroutine_threadsafe(
                        _route_to_orchestrator(transcript, gaze_context), loop
                    )
            except Exception as e:
                debug_log(f"eyeTerm agent callback failed: {e}")

        self.backend._eyeterm_app._command_router._on_agent_team = _agent_team_callback

    async def handle_eyeterm_stop(self):
        """Stop eyeTerm — properly release camera, MJPEG server, and all threads."""
        stopped = False

        # Stop EyeTermApp instance (IPC-started)
        app = getattr(self.backend, '_eyeterm_app', None)
        if app:
            try:
                app._running = False
                app._cleanup()
            except Exception as e:
                debug_log(f"eyeTerm app cleanup error: {e}")
            self.backend._eyeterm_app = None
            stopped = True

        # Stop EyeTermHeadless instance (autostart)
        headless = getattr(self.backend, '_eyeterm_headless', None)
        if headless:
            try:
                headless.stop()
            except Exception as e:
                debug_log(f"eyeTerm headless stop error: {e}")
            self.backend._eyeterm_headless = None
            stopped = True

        if stopped:
            self.send_message({"type": "eyeterm_status", "status": "stopped"})
        else:
            self.send_message({"type": "eyeterm_status", "status": "not_running"})

    async def handle_eyeterm_toggle_cursor(self):
        """Toggle eyeTerm cursor control."""
        if hasattr(self.backend, '_eyeterm_app') and self.backend._eyeterm_app:
            driver = self.backend._eyeterm_app._cursor_driver
            if driver:
                state = driver.toggle()
                self.send_message({
                    "type": "eyeterm_cursor_status",
                    "success": True,
                    "enabled": state,
                })
                return
        self.send_message({"type": "eyeterm_cursor_status", "success": False, "message": "eyeTerm not running"})

    async def handle_eyeterm_calibrate(self):
        """Trigger eyeTerm calibration (non-blocking for headless mode)."""
        # Headless instance (primary)
        if hasattr(self.backend, '_eyeterm_headless') and self.backend._eyeterm_headless:
            success = self.backend._eyeterm_headless.calibrate()
            self.send_message({
                "type": "eyeterm_calibrate_result",
                "success": success,
                "message": "Kalibrierung gestartet" if success else "eyeTerm nicht bereit",
            })
            return
        # App instance (legacy)
        if hasattr(self.backend, '_eyeterm_app') and self.backend._eyeterm_app:
            self.backend._eyeterm_app._run_calibration()
            self.send_message({"type": "eyeterm_calibrate_result", "success": True})
            return
        self.send_message({"type": "eyeterm_calibrate_result", "success": False, "message": "eyeTerm not running"})
