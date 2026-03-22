"""
VibeMind Electron Backend

Python backend that communicates with Electron main process via stdin/stdout JSON.
Manages bubble state, voice dialog, and canvas content.

Communication Protocol:
- Messages are JSON objects, one per line
- Input (stdin): Commands from Electron
- Output (stdout): Events and data to Electron
"""

import sys
import os
import json
import asyncio
import threading
import subprocess
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Callable, Any
import logging

# Fix Windows console encoding for German umlauts in debug output
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# Load .env file FIRST before any other imports that might need env vars
try:
    from dotenv import load_dotenv
    # Load from project root .env
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        # Debug: log key env vars
        force_sync = os.getenv("FORCE_SYNC_MODE", "false")
        use_v2 = os.getenv("USE_VOICE_BRIDGE_V2", "false")
        # Log before SpaceLogger is set up — emit JSON so main.js can parse it
        import json as _j
        print(_j.dumps({"log":True,"s":"system","l":"DEBUG","t":"","m":f".env loaded: FORCE_SYNC_MODE={force_sync}, USE_VOICE_BRIDGE_V2={use_v2}","n":"electron_backend"}), file=sys.stderr)
except ImportError:
    pass  # dotenv not installed — system env vars used

# Try to import requests for HTTP communication with Coding Engine
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

# ==============================================================================
# MODULE-LEVEL STATE (for tools to access)
# ==============================================================================
# These variables are set by the ElectronBackend instance and can be
# imported by tool modules like idea_tools.py
_current_bubble_id: Optional[int] = None
_bubbles: Dict[int, 'Bubble'] = {}
_backend_instance: Optional['ElectronBackend'] = None
_bubble_id_map: Dict[str, int] = {}  # db_uuid -> local_id

# Debug flag
DEBUG = True

# Global shutdown event — daemon threads check this to exit loops gracefully
_shutdown_event = threading.Event()

# Module logger — auto-detected as "system" space by SpaceLogger
_logger = logging.getLogger(__name__)

def debug_log(msg: str):
    """Log debug message via SpaceLogger (colored in terminal)."""
    if DEBUG:
        _logger.debug(msg)


def get_current_bubble_id() -> Optional[int]:
    """Get the current bubble ID. Used by tool modules."""
    return _current_bubble_id


def get_bubble_info(bubble_id: int) -> Optional[Dict]:
    """Get bubble info by ID. Used by tool modules."""
    if bubble_id in _bubbles:
        bubble = _bubbles[bubble_id]
        return {"id": bubble.id, "title": bubble.title}
    return None


def get_bubble_by_db_id(db_id: str) -> Optional[int]:
    """Get local bubble ID from database UUID."""
    return _bubble_id_map.get(db_id)


def get_backend() -> Optional['ElectronBackend']:
    """Get the backend instance. Used by tool modules."""
    return _backend_instance


# ==============================================================================
# LOGGING SETUP
# ==============================================================================
# Space-colored logging — single handler on root logger, outputs JSON when piped by Electron
from swarm.logging.space_logger import setup_space_logging
setup_space_logging()

logger = logging.getLogger(__name__)


# Try to import data layer for persistence
try:
    from data import CanvasRepository, CanvasNode as DBCanvasNode, CanvasEdge as DBCanvasEdge, IdeasRepository, ShuttlesRepository
    HAS_DATABASE = True
except ImportError:
    HAS_DATABASE = False
    logger.warning("Database not available - canvas will not persist")

# Try to import workspace tools for IPC connection
try:
    from tools.workspace_tools import set_electron_sender, set_bubble_position_getter
    HAS_WORKSPACE_TOOLS = True
except ImportError:
    HAS_WORKSPACE_TOOLS = False
    set_electron_sender = None
    set_bubble_position_getter = None
    logger.warning("Workspace tools not available")

# Try to import bubble_tools for syncing _current_bubble_db_id
try:
    import tools.bubble_tools as bubble_tools_module
    HAS_BUBBLE_TOOLS = True
except ImportError:
    HAS_BUBBLE_TOOLS = False
    bubble_tools_module = None
    logger.warning("Bubble tools not available for state sync")

# Try to import navigation_tools for voice-controlled navigation
try:
    from tools.navigation_tools import set_electron_sender as set_navigation_sender
    HAS_NAVIGATION_TOOLS = True
except ImportError:
    HAS_NAVIGATION_TOOLS = False
    set_navigation_sender = None
    logger.warning("Navigation tools not available")


# Import session tools for speech tracking
try:
    from tools.session_tools import mark_user_speech
    HAS_SESSION_TOOLS = True
except ImportError as e:
    HAS_SESSION_TOOLS = False
    mark_user_speech = None
    logger.warning(f"Session tools not available: {e}")

# Try to import coding tools and runner
try:
    from spaces.coding.tools.coding_tools import set_electron_sender as set_coding_sender, set_coding_engine_runner
    from coding_engine_runner import CodingEngineRunner, get_coding_engine_runner
    from data import ProjectsRepository, GenerationStatus
    HAS_CODING_ENGINE = True
except ImportError as e:
    HAS_CODING_ENGINE = False
    set_coding_sender = None
    set_coding_engine_runner = None
    CodingEngineRunner = None
    get_coding_engine_runner = None
    logger.warning(f"Coding engine not available: {e}")

# Try to import VoiceBridgeV2 for new async architecture
try:
    from swarm.voice_bridge_v2 import VoiceBridgeV2, create_voice_bridge_v2
    HAS_VOICE_BRIDGE_V2 = True
except ImportError as e:
    HAS_VOICE_BRIDGE_V2 = False
    VoiceBridgeV2 = None
    create_voice_bridge_v2 = None
    logger.warning(f"VoiceBridgeV2 not available: {e}")

# Try to import OpenAI Realtime voice session
try:
    from voice.openai_realtime import OpenAIRealtimeVoiceSession
    from voice.session_config import create_session_config, SEND_INTENT_TOOL
    HAS_OPENAI_REALTIME = True
except ImportError as e:
    HAS_OPENAI_REALTIME = False
    OpenAIRealtimeVoiceSession = None
    logger.warning(f"OpenAI Realtime voice not available: {e}")

# Voice provider: OpenAI Realtime API
VOICE_PROVIDER = "openai_realtime"


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================

@dataclass
class Bubble:
    """Represents a bubble/universe in the multiverse."""
    id: int
    title: str
    position: Dict[str, float] = field(default_factory=lambda: {"x": 0, "y": 0, "z": 0})
    color: int = 0x4488ff
    radius: float = 0.7
    content: List[Dict] = field(default_factory=list)  # Canvas nodes inside bubble
    db_id: Optional[str] = None  # Database UUID for this bubble

    def to_dict(self) -> dict:
        result = {
            "id": self.id,
            "title": self.title,
            "position": self.position,
            "color": self.color,
            "radius": self.radius,
        }
        # Include db_id for delete/update matching
        if self.db_id:
            result["db_id"] = self.db_id
        return result


class CanvasNode:
    """A node inside a bubble's canvas."""
    id: int
    type: str  # "note", "image", "link", "file"
    position: Dict[str, float]  # x, y coordinates
    content: Dict  # Type-specific content
    connections: List[int] = field(default_factory=list)  # Connected node IDs


# ==============================================================================
# BACKEND STATE
# ==============================================================================

class ElectronBackend:
    """Main backend managing state and communication."""

    def __init__(self):
        global _bubbles, _current_bubble_id, _backend_instance

        debug_log("ElectronBackend __init__ starting...")

        self.bubbles: Dict[int, Bubble] = {}
        self.next_bubble_id = 1
        self.next_node_id = 1
        self.current_bubble_id: Optional[int] = None  # Currently "inside" a bubble
        self.voice_active = False
        self._voice_stopping = False
        self._start_cancelled = False
        self._voice_start_task: Optional[asyncio.Task] = None  # Track running start_voice task

        # VoiceBridgeV2 (async architecture with NotificationQueue)
        self.voice_bridge = None

        # OpenAI Realtime voice session
        self.openai_realtime_session = None
        self._main_loop: Optional[asyncio.AbstractEventLoop] = None  # For thread-safe async dispatch
        
        # Project Preview State (Coding Engine Integration)
        self.active_previews: Dict[str, Dict] = {}  # project_id -> preview_info
        self.coding_engine_path = os.environ.get(
            'CODING_ENGINE_PATH', 
            str(Path(__file__).parent / 'spaces' / 'coding' / 'Coding_engine')
        )
        debug_log(f"Coding Engine path: {self.coding_engine_path}")
        
        # Coding Engine Runner for code generation
        self.coding_engine_runner = None
        if HAS_CODING_ENGINE:
            try:
                self.coding_engine_runner = CodingEngineRunner(
                    coding_engine_path=self.coding_engine_path,
                    on_status_update=lambda *a, **kw: None,  # Re-wired to ProjectManager below
                    on_issue_detected=lambda *a, **kw: None,
                    on_quality_update=lambda *a, **kw: None,
                )
                # Connect coding tools to our IPC and runner
                if set_coding_sender:
                    set_coding_sender(self.send_message)
                if set_coding_engine_runner:
                    set_coding_engine_runner(self.coding_engine_runner)
                debug_log("Coding Engine Runner initialized")
            except Exception as e:
                debug_log(f"Failed to initialize Coding Engine Runner: {e}")
                logger.warning(f"Failed to initialize Coding Engine Runner: {e}")
        
        # VNC Proxy Configuration for Cloud Production
        # Example: VNC_BASE_URL=https://preview.vibemind.io/vnc
        # This will generate URLs like: https://preview.vibemind.io/vnc/{project_id}
        self.vnc_base_url = os.environ.get('VNC_BASE_URL', None)
        self.vnc_use_proxy = self.vnc_base_url is not None
        
        # Fallback host for direct connection (when not using proxy)
        # Example: VNC_HOST=192.168.1.100 or VNC_HOST=localhost
        self.vnc_host = os.environ.get('VNC_HOST', 'localhost')
        
        debug_log(f"VNC Config: use_proxy={self.vnc_use_proxy}, base_url={self.vnc_base_url}, host={self.vnc_host}")

        # Sync with module-level state for tool access
        _bubbles = self.bubbles
        _backend_instance = self

        # Callbacks for voice
        self.on_user_transcript: Optional[Callable[[str], None]] = None
        self.on_agent_response: Optional[Callable[[str], None]] = None

        # Initialize database repository for canvas persistence
        self.canvas_repo: Optional[CanvasRepository] = None
        self.ideas_repo: Optional[IdeasRepository] = None
        self.shuttles_repo: Optional[ShuttlesRepository] = None
        if HAS_DATABASE:
            try:
                self.canvas_repo = CanvasRepository()
                self.ideas_repo = IdeasRepository()
                self.shuttles_repo = ShuttlesRepository()
                debug_log("Database repositories initialized")
            except Exception as e:
                debug_log(f"Failed to initialize repositories: {e}")
                logger.warning(f"Failed to initialize repositories: {e}")

        # Mapping from local int IDs to database string UUIDs
        self.node_id_map: Dict[int, str] = {}  # local_id -> db_uuid
        self.db_id_map: Dict[str, int] = {}    # db_uuid -> local_id
        self.bubble_id_map: Dict[str, int] = {}  # db_uuid -> local_id for bubbles

        # Connect workspace tools to our IPC
        if HAS_WORKSPACE_TOOLS and set_electron_sender:
            set_electron_sender(self.send_message)
            debug_log("Workspace tools connected to Electron IPC")
            logger.info("Workspace tools connected to Electron IPC")

        # Connect bubble position getter — deferred until CanvasManager is ready (see below)
            
        # Connect navigation tools to our IPC
        if HAS_NAVIGATION_TOOLS and set_navigation_sender:
            set_navigation_sender(self.send_message)
            debug_log("Navigation tools connected to Electron IPC")
            logger.info("Navigation tools connected to Electron IPC")

        # Connect Flowzen (Blaue Rose) activity tracker to Electron IPC
        if os.getenv("FLOWZEN_ENABLED", "false").lower() == "true":
            try:
                from spaces.flowzen.activity_tracker import get_activity_tracker
                tracker = get_activity_tracker()
                tracker.set_electron_sender(self.send_message)
                debug_log("Flowzen activity tracker connected to Electron IPC")
            except Exception:
                pass

        # ── IPC Handler Modules ──
        from ipc.n8n_handlers import N8nHandlers
        from ipc.clawport_handlers import ClawPortHandlers
        from ipc.exploration_handlers import ExplorationHandlers
        from ipc.eyeterm_handlers import EyeTermHandlers
        from ipc.project_manager import ProjectManager
        from ipc.shuttle_handlers import ShuttleHandlers
        from ipc.voice_manager import VoiceManager
        from ipc.canvas_manager import CanvasManager
        self._n8n = N8nHandlers(self)
        self._clawport = ClawPortHandlers(self)
        self._exploration = ExplorationHandlers(self)
        self._eyeterm = EyeTermHandlers(self)
        self._project_mgr = ProjectManager(self)
        self._shuttle = ShuttleHandlers(self)
        self._voice_mgr = VoiceManager(self)
        self._canvas_mgr = CanvasManager(self)
        debug_log("IPC handler modules loaded")

        # Connect bubble position getter now that CanvasManager is ready
        if HAS_WORKSPACE_TOOLS and set_bubble_position_getter:
            set_bubble_position_getter(self._canvas_mgr._get_bubble_position_by_db_id)
            debug_log("Bubble position getter connected")

        # Re-wire CodingEngineRunner callbacks to ProjectManager (now that it exists)
        if self.coding_engine_runner:
            self.coding_engine_runner.on_status_update = self._project_mgr.on_generation_status_update
            self.coding_engine_runner.on_issue_detected = self._project_mgr.on_issue_detected
            self.coding_engine_runner.on_quality_update = self._project_mgr.on_quality_summary_update

        # Load bubbles from database in background (sends node_added IPC per bubble)
        import threading
        threading.Thread(
            target=self._canvas_mgr._load_bubbles_from_db,
            daemon=True,
            name="bubble-loader"
        ).start()

        debug_log("ElectronBackend initialized (bubbles loading in background)")

        # No default bubbles - bubbles are created via voice commands
        # and stored in the database

        # Initial Rowboat sync + Brain seeding (background, non-blocking)
        import threading
        def _sync_to_rowboat():
            try:
                import time
                time.sleep(2)
                from publishing import get_ideas_publisher
                publisher = get_ideas_publisher()
                publisher.sync_all()

                # Wire up BrainSeeder (if enabled)
                try:
                    from spaces.brain.brain_seeder import BrainSeeder
                    seeder = BrainSeeder(
                        mongo_client=getattr(publisher, '_client', None),
                        db_name=getattr(publisher, '_db_name', ''),
                        project_id=getattr(publisher, '_project_id', ''),
                    )
                    # Register callback for future publishes
                    if hasattr(publisher, 'on_source_updated'):
                        publisher.on_source_updated(seeder.on_source_ready)
                    # Startup seed
                    seeder.seed_all()
                except Exception as e:
                    debug_log(f"BrainSeeder init (non-critical): {e}")

                # Start periodic flush timers for buffered data
                def _periodic_flush():
                    tick = 0
                    while True:
                        time.sleep(30)
                        tick += 1
                        # Desktop buffer: every 30s
                        try:
                            if hasattr(publisher, 'flush_desktop_buffer'):
                                publisher.flush_desktop_buffer()
                        except Exception:
                            pass
                        # Agent metrics: every 5min (10 ticks of 30s)
                        if tick % 10 == 0:
                            try:
                                if hasattr(publisher, 'flush_agent_metrics'):
                                    publisher.flush_agent_metrics()
                            except Exception:
                                pass
                threading.Thread(
                    target=_periodic_flush, daemon=True, name="publisher-flush"
                ).start()

            except Exception as e:
                debug_log(f"Rowboat sync failed (non-critical): {e}")
        threading.Thread(target=_sync_to_rowboat, daemon=True, name="rowboat-sync").start()

        # Pre-load embedding model in background thread to avoid
        # timeout on first use of auto_link, explore, etc.
        import threading
        def _preload_embedding_model():
            try:
                from data.embedding_service import _get_model
                model = _get_model()  # Blocks until loaded (thread-safe)
                if model is not None:
                    debug_log(f"Embedding model pre-loaded: {type(model).__name__}")
                else:
                    debug_log("Embedding model failed to load (will use hash fallback)")
            except Exception as e:
                debug_log(f"Embedding model pre-load failed: {e}")
        threading.Thread(target=_preload_embedding_model, daemon=True, name="embedding-preload").start()


        # Roarboot autoconnect + self-healing loop
        # Checks Rowboat Docker health at startup, auto-starts if configured,
        # then monitors every 60s and restarts on failure.
        def _roarboot_autoconnect():
            import time
            try:
                from spaces.rowboat.config import get_config
                config = get_config()

                if not config.rowboat_enabled:
                    debug_log("Roarboot: disabled via ROWBOAT_ENABLED=false")
                    return

                debug_log(f"Roarboot: autoconnect starting (url={config.rowboat_url}, auto_start={config.auto_start_docker})")

                # Small delay to let Electron renderer initialize
                time.sleep(3)

                first_run = True
                while not _shutdown_event.is_set():
                    try:
                        from spaces.rowboat.tools.roarboot_client import get_roarboot_client
                        client = get_roarboot_client()
                        status = client.get_status()

                        if status.get("success"):
                            debug_log("Roarboot: healthy (connected)")
                            self.send_message({
                                "type": "roarboot_status",
                                "status": "connected",
                                "message": status.get("message", "Rowboat verbunden"),
                            })
                        else:
                            debug_log(f"Roarboot: unhealthy - {status.get('message')}")

                            # Auto-start Docker if configured
                            if config.auto_start_docker:
                                debug_log("Roarboot: auto-starting Docker...")
                                self.send_message({
                                    "type": "roarboot_status",
                                    "status": "starting",
                                    "message": "Rowboat Docker wird gestartet...",
                                })
                                try:
                                    from spaces.rowboat.tools.docker_tools import start_docker
                                    result = start_docker()
                                    if result.get("success"):
                                        debug_log("Roarboot: Docker auto-start successful")
                                        # Verify connection after Docker start
                                        time.sleep(5)
                                        verify = client.get_status()
                                        if verify.get("success"):
                                            self.send_message({
                                                "type": "roarboot_status",
                                                "status": "connected",
                                                "message": "Rowboat verbunden nach Docker-Start",
                                            })
                                        else:
                                            debug_log(f"Roarboot: Docker started but not yet reachable: {verify.get('message')}")
                                            self.send_message({
                                                "type": "roarboot_status",
                                                "status": "starting",
                                                "message": "Docker gestartet, warte auf Rowboat...",
                                            })
                                    else:
                                        debug_log(f"Roarboot: Docker auto-start failed: {result.get('message')}")
                                        self.send_message({
                                            "type": "roarboot_status",
                                            "status": "error",
                                            "message": result.get("message", "Docker start failed"),
                                        })
                                except Exception as e:
                                    debug_log(f"Roarboot: Docker auto-start error: {e}")
                                    self.send_message({
                                        "type": "roarboot_status",
                                        "status": "error",
                                        "message": f"Docker error: {e}",
                                    })
                            else:
                                self.send_message({
                                    "type": "roarboot_status",
                                    "status": "disconnected",
                                    "message": status.get("message", "Rowboat nicht erreichbar"),
                                })

                    except Exception as e:
                        debug_log(f"Roarboot: health check error: {e}")

                    # Wait before next check (shorter on first run for faster startup)
                    # Uses _shutdown_event.wait() so thread exits promptly on shutdown
                    _shutdown_event.wait(10 if first_run else 60)
                    first_run = False

            except ImportError as e:
                debug_log(f"Roarboot: module not available ({e}), skipping autoconnect")
            except Exception as e:
                debug_log(f"Roarboot: autoconnect init error: {e}")
        threading.Thread(target=_roarboot_autoconnect, daemon=True, name="roarboot-autoconnect").start()

        # Rowboat update checker — periodically polls GitHub for new releases
        try:
            from spaces.rowboat.workers.update_checker import RowboatUpdateChecker
            self._rowboat_update_checker = RowboatUpdateChecker(self.send_message)
            self._rowboat_update_checker.start()
            debug_log("Rowboat update checker started")
        except ImportError as e:
            debug_log(f"Rowboat update checker not available: {e}")
        except Exception as e:
            debug_log(f"Rowboat update checker init error: {e}")

        # Automation_ui auto-start (Vapi Voice Control + MCP + Clawdbot)
        # Starts the FastAPI backend at localhost:8007 if server.py exists
        self._automation_ui_proc = None
        def _autostart_automation_ui():
            import time
            print("[Automation_ui] Autostart thread: sleeping 2s...", file=sys.stderr, flush=True)
            time.sleep(2)
            try:
                print("[Automation_ui] Calling _start_automation_ui_backend()...", file=sys.stderr, flush=True)
                result = self._start_automation_ui_backend()
                print(f"[Automation_ui] _start_automation_ui_backend returned: {result}", file=sys.stderr, flush=True)
            except Exception as e:
                import traceback
                print(f"[Automation_ui] AUTO-START ERROR: {e}", file=sys.stderr, flush=True)
                print(traceback.format_exc(), file=sys.stderr, flush=True)
                debug_log(f"Automation_ui: auto-start error: {e}")
        threading.Thread(target=_autostart_automation_ui, daemon=True, name="automation-ui-autostart").start()

        # eyeTerm gaze/cursor controller (optional — needs camera + mediapipe)
        self._eyeterm_headless = None
        _eyeterm_env = os.environ.get("EYETERM_ENABLED", "false")
        # Log via debug_log (structured JSON) + plain stderr for double visibility
        debug_log(f"eyeTerm: EYETERM_ENABLED={_eyeterm_env!r}")
        print(f"[eyeTerm] EYETERM_ENABLED={_eyeterm_env!r}", file=sys.stderr, flush=True)
        if _eyeterm_env.lower() == "true":
            def _autostart_eyeterm():
                import time
                # Short delay to let Electron window settle — eyeTerm is
                # independent of Automation_ui and doesn't need to wait for it.
                print("[eyeTerm] Starting in 5s...", file=sys.stderr, flush=True)
                time.sleep(5)
                try:
                    print("[eyeTerm] Calling _start_eyeterm()...", file=sys.stderr, flush=True)
                    self._start_eyeterm()
                    print("[eyeTerm] _start_eyeterm() completed OK", file=sys.stderr, flush=True)
                except Exception as e:
                    import traceback
                    print(f"[eyeTerm] AUTO-START ERROR: {e}", file=sys.stderr, flush=True)
                    print(traceback.format_exc(), file=sys.stderr, flush=True)
            threading.Thread(target=_autostart_eyeterm, daemon=True, name="eyeterm-autostart").start()
            debug_log("eyeTerm: autostart thread launched")
        else:
            debug_log("eyeTerm: DISABLED (EYETERM_ENABLED != true)")
            print("[eyeTerm] DISABLED (EYETERM_ENABLED != true)", file=sys.stderr, flush=True)

        # SWE Design server lifecycle is now handled by Electron-side embed.js
        # (swe-design-manager.js → requirements_engineer/electron/embed.js)

    def _start_automation_ui_backend(self):
        """Start Automation_ui backend if not already running."""
        from spaces.desktop.automation_ui_client import get_automation_client
        client = get_automation_client()
        if client.is_available():
            debug_log("Automation_ui backend already running")
            self.send_message({"type": "automation_ui_status", "status": "running"})
            return True

        print("[Automation_ui] _start_automation_ui_backend called", file=sys.stderr, flush=True)
        debug_log("Starting Automation_ui backend...")
        try:
            server_path = Path(__file__).parent / "spaces" / "desktop" / "Automation_ui" / "backend" / "server.py"
            print(f"[Automation_ui] server_path={server_path}, exists={server_path.exists()}", file=sys.stderr, flush=True)
            if server_path.exists():
                # Build env: inherit current env + set SQLite DB + non-debug mode
                env = os.environ.copy()
                db_path = server_path.parent / "automation_ui.db"
                env["DATABASE_URL"] = f"sqlite:///{db_path}"
                env["DEBUG"] = "False"  # Avoid uvicorn reload mode in subprocess
                env["PYTHONIOENCODING"] = "utf-8"  # Emoji log messages on Windows
                # Ensure Redis URL is set (Automation_ui defaults to 6381 otherwise)
                if "REDIS_URL" not in env:
                    env["REDIS_URL"] = "redis://localhost:6379/0"
                self._automation_ui_proc = subprocess.Popen(
                    [sys.executable, str(server_path)],
                    cwd=str(server_path.parent.parent),
                    env=env,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                )
                debug_log(f"Automation_ui backend started (PID: {self._automation_ui_proc.pid})")
                self.send_message({"type": "automation_ui_status", "status": "starting"})

                # Drain stderr in background to prevent pipe buffer deadlock
                # (Windows pipe buffer is ~4KB — uvicorn fills it instantly)
                self._automation_ui_stderr_lines = []
                def _drain_stderr():
                    proc = self._automation_ui_proc
                    if not proc or not proc.stderr:
                        return
                    for line in iter(proc.stderr.readline, b''):
                        decoded = line.decode("utf-8", errors="replace").rstrip()
                        if decoded:
                            self._automation_ui_stderr_lines.append(decoded)
                            # Keep last 50 lines for debugging
                            if len(self._automation_ui_stderr_lines) > 50:
                                self._automation_ui_stderr_lines.pop(0)
                threading.Thread(target=_drain_stderr, daemon=True, name="automation-ui-stderr").start()

                # Wait for health check in background, then notify renderer
                def _wait_for_health():
                    import time
                    import httpx
                    for attempt in range(15):
                        time.sleep(2)
                        try:
                            r = httpx.get("http://localhost:8007/api/health/health", timeout=2)
                            if r.status_code == 200:
                                debug_log("Automation_ui backend is healthy")
                                self.send_message({"type": "automation_ui_status", "status": "running"})
                                return
                        except Exception:
                            pass
                        # Check if process died
                        if self._automation_ui_proc and self._automation_ui_proc.poll() is not None:
                            stderr_tail = "\n".join(self._automation_ui_stderr_lines[-5:])
                            debug_log(f"Automation_ui crashed (exit {self._automation_ui_proc.returncode}): {stderr_tail}")
                            self.send_message({"type": "automation_ui_status", "status": "error", "error": f"Process exited: {stderr_tail[:200]}"})
                            return
                    debug_log("Automation_ui health check timed out after 30s")
                    debug_log(f"Automation_ui stderr tail: {chr(10).join(self._automation_ui_stderr_lines[-5:])}")
                threading.Thread(target=_wait_for_health, daemon=True, name="automation-ui-health").start()
                return True
            else:
                debug_log(f"Automation_ui server.py not found at {server_path}")
                self.send_message({"type": "automation_ui_status", "status": "error", "error": "server.py not found"})
                return False
        except Exception as e:
            logger.error(f"Failed to start Automation_ui: {e}")
            self.send_message({"type": "automation_ui_status", "status": "error", "error": str(e)})
            return False


    def _start_eyeterm(self):
        """Start eyeTerm headless gaze/cursor controller."""
        try:
            debug_log("eyeTerm: importing EyeTermHeadless...")
            print("[eyeTerm] Importing EyeTermHeadless...", file=sys.stderr, flush=True)
            from spaces.desktop.eyeterm.headless import EyeTermHeadless
            debug_log("eyeTerm: import OK, creating instance")
            print("[eyeTerm] Import OK, creating instance...", file=sys.stderr, flush=True)

            def _on_voice_command(transcript, gaze_context):
                """Forward eyeTerm voice commands to the Moire Voice chat."""
                debug_log(f"eyeTerm voice command: {transcript[:80]}")
                self._clawport.handle_chat_text_input({"text": transcript})

            self._eyeterm_headless = EyeTermHeadless(
                on_voice_command=_on_voice_command,
                broadcast_fn=self.send_message,
            )
            print("[eyeTerm] Calling .start()...", file=sys.stderr, flush=True)
            self._eyeterm_headless.start()
            debug_log("eyeTerm: STARTED OK — MJPEG on port 8099")
            print("[eyeTerm] STARTED OK — MJPEG on port 8099", file=sys.stderr, flush=True)
            self.send_message({"type": "eyeterm_status", "status": "running"})
        except ImportError as e:
            print(f"[eyeTerm] IMPORT ERROR: {e}", file=sys.stderr, flush=True)
        except Exception as e:
            import traceback
            print(f"[eyeTerm] START ERROR: {e}", file=sys.stderr, flush=True)
            print(traceback.format_exc(), file=sys.stderr, flush=True)

    # ── Canvas methods moved to ipc/canvas_manager.py ──

    # ── Project VNC URL generation moved to ipc/project_manager.py ──

    # ── Voice methods moved to ipc/voice_manager.py ──

    # ========================================================================
    # COMMUNICATION
    # ========================================================================

    def send_message(self, message: dict):
        """Send JSON message to Electron via stdout."""
        try:
            print(json.dumps(message), flush=True)
        except Exception as e:
            logger.error(f"Failed to send message: {e}")

    def handle_message(self, message: dict):
        """Handle incoming message from Electron."""
        msg_type = message.get("type")
        debug_log(f"handle_message: {msg_type}")

        if msg_type == "get_bubbles":
            bubbles_data = self._canvas_mgr.get_all_bubbles()
            debug_log(f"Sending {len(bubbles_data)} bubbles")
            self.send_message({
                "type": "bubbles_sync",
                "bubbles": bubbles_data
            })

        elif msg_type == "bubble_selected":
            bubble_id = message.get("bubble_id")
            logger.info(f"Bubble selected: {bubble_id}")

        elif msg_type == "enter_bubble":
            bubble_id = message.get("bubble_id")
            self._canvas_mgr.enter_bubble(bubble_id)

        elif msg_type == "exit_bubble":
            self._canvas_mgr.exit_bubble()

        elif msg_type == "start_voice":
            task = asyncio.create_task(self._voice_mgr.start_voice())
            self._voice_start_task = task

        elif msg_type == "stop_voice":
            asyncio.create_task(self._voice_mgr.stop_voice())

        elif msg_type == "toggle_voice":
            if self.voice_active:
                asyncio.create_task(self._voice_mgr.stop_voice())
            else:
                task = asyncio.create_task(self._voice_mgr.start_voice())
                self._voice_start_task = task

        elif msg_type == "add_canvas_node":
            self._canvas_mgr.add_canvas_node(
                message.get("bubble_id"),
                message.get("node", {}).get("type"),
                message.get("node", {}).get("position"),
                message.get("node", {}).get("content")
            )

        elif msg_type == "update_canvas_node":
            self._canvas_mgr.update_canvas_node(
                message.get("bubble_id"),
                message.get("node_id"),
                message.get("updates", {})
            )

        elif msg_type == "delete_canvas_node":
            self._canvas_mgr.delete_canvas_node(
                message.get("bubble_id"),
                message.get("node_id")
            )
        
        elif msg_type == "start_project_preview":
            project_id = message.get("project_id")
            project_path = message.get("project_path")
            enable_vnc = message.get("enable_vnc", True)
            vnc_resolution = message.get("vnc_resolution", "1280x720")
            debug_log(f"Starting project preview: {project_id} at {project_path}")
            asyncio.create_task(self._project_mgr.handle_start_project_preview(
                project_id, project_path, enable_vnc, vnc_resolution
            ))

        elif msg_type == "stop_project_preview":
            project_id = message.get("project_id")
            debug_log(f"Stopping project preview: {project_id}")
            asyncio.create_task(self._project_mgr.handle_stop_project_preview(project_id))

        elif msg_type == "get_preview_status":
            project_id = message.get("project_id")
            status = self.active_previews.get(project_id, {"status": "not_running"})
            self.send_message({
                "type": "preview_status",
                "project_id": project_id,
                **status
            })
        
        # ====================================================================
        # PROJECTS SPACE - Code Generation IPC Handlers
        # ====================================================================
        
        elif msg_type == "get_generated_projects":
            asyncio.create_task(self._project_mgr.handle_get_generated_projects(message))

        elif msg_type == "get_generation_status":
            asyncio.create_task(self._project_mgr.handle_get_generation_status(message))

        elif msg_type == "start_code_generation":
            asyncio.create_task(self._project_mgr.handle_start_code_generation(message))

        elif msg_type == "cancel_code_generation":
            asyncio.create_task(self._project_mgr.handle_cancel_code_generation(message))

        elif msg_type == "enter_projects_space":
            asyncio.create_task(self._project_mgr.handle_enter_projects_space(message))
        
        # ====================================================================
        # NAVIGATION IPC Handlers (from voice commands via navigation_tools)
        # ====================================================================
        
        elif msg_type == "navigate_to_space":
            # Handle space navigation from Electron UI
            space = message.get("space")
            debug_log(f"Navigate to space: {space}")
            # Forward to Electron (echoes back for consistency)
            self.send_message({
                "type": "space_changed",
                "space": space,
                "source": "python"
            })
        
        elif msg_type == "navigate_space":
            # Handle space navigation from voice (navigation_tools)
            space = message.get("space")
            debug_log(f"Voice navigate to space: {space}")
            # Already sent by navigation_tools, just log
        
        elif msg_type == "select_item":
            # Handle item selection from voice
            direction = message.get("direction", 1)
            item_type = message.get("item_type", "bubble")
            debug_log(f"Select {item_type}: direction={direction}")
            # Forward to Electron
            self.send_message({
                "type": "select_item",
                "direction": direction,
                "item_type": item_type
            })
        
        elif msg_type == "select_by_name":
            # Handle selection by name from voice
            name = message.get("name")
            debug_log(f"Select by name: {name}")
            self.send_message({
                "type": "select_by_name",
                "name": name
            })
        
        elif msg_type == "select_by_index":
            # Handle selection by index from voice
            index = message.get("index")
            debug_log(f"Select by index: {index}")
            self.send_message({
                "type": "select_by_index",
                "index": index
            })
        
        elif msg_type == "enter_selection":
            # Handle enter current selection from voice
            debug_log("Enter current selection")
            self.send_message({
                "type": "enter_selection"
            })
        
        elif msg_type == "exit_view":
            # Handle exit view from voice
            debug_log("Exit current view")
            self.send_message({
                "type": "exit_view"
            })
        
        elif msg_type == "get_view_state":
            # Handle get view state request
            debug_log("Get view state requested")
            # Electron will respond with current state

        # ====================================================================
        # (Roarboot chat is now handled via embedded Rowboat Web UI iframe —
        #  no custom chat handlers needed. Status + URL sent via roarboot_status.)
        # ====================================================================
        # SHUTTLE IPC Handlers (requirement pipeline visualization)
        # ====================================================================

        elif msg_type == "shuttle_clicked":
            # Handle shuttle click from Electron
            shuttle_id = message.get("shuttle_id")
            bubble_name = message.get("bubble_name")
            debug_log(f"Shuttle clicked: {shuttle_id} from {bubble_name}")
            # Log the click, Alice transfer happens via shuttle_navigate

        elif msg_type == "shuttle_navigate":
            # Handle "Navigate with Alice" button click
            action = message.get("action")
            debug_log(f"Shuttle navigate: {action}")
            logger.info(f"Shuttle navigate action: {action} (agent transfers removed)")

        elif msg_type == "get_shuttles":
            shuttles_data = self._canvas_mgr.get_active_shuttles()
            debug_log(f"Sending {len(shuttles_data)} shuttles")
            self.send_message({
                "type": "shuttles_sync",
                "shuttles": shuttles_data
            })

        elif msg_type == "get_shuttle_requirements":
            shuttle_id = message.get("shuttle_id")
            debug_log(f"Getting requirements for shuttle: {shuttle_id}")
            asyncio.create_task(self._shuttle.handle_get_shuttle_requirements(shuttle_id))

        elif msg_type == "get_stage_shuttle_data":
            shuttle_id = message.get("shuttle_id")
            debug_log(f"Getting stage shuttle data: {shuttle_id}")
            asyncio.create_task(self._shuttle.handle_get_stage_shuttle_data(shuttle_id))

        # ========================================
        # SHUTTLE WIZARD (interactive steps)
        # ========================================

        elif msg_type == "wizard_get_state":
            shuttle_id = message.get("shuttle_id")
            debug_log(f"Wizard get state: {shuttle_id}")
            from spaces.shuttles.wizard_handler import get_wizard_handler
            handler = get_wizard_handler()
            result = handler.get_state(shuttle_id)
            self.send_message({"type": "wizard_state", "shuttle_id": shuttle_id, **result})

        elif msg_type == "wizard_init_from_bubble":
            shuttle_id = message.get("shuttle_id")
            bubble_id = message.get("bubble_id")
            debug_log(f"Wizard init from bubble: {shuttle_id} / {bubble_id}")
            from spaces.shuttles.wizard_handler import get_wizard_handler
            handler = get_wizard_handler()
            result = handler.init_from_bubble(shuttle_id, bubble_id)
            self.send_message({"type": "wizard_initialized", "shuttle_id": shuttle_id, **result})

        elif msg_type == "wizard_submit_step":
            shuttle_id = message.get("shuttle_id")
            step = message.get("step")
            data = message.get("data", {})
            debug_log(f"Wizard submit step: {shuttle_id} / {step}")
            from spaces.shuttles.wizard_handler import get_wizard_handler
            handler = get_wizard_handler()
            result = handler.submit_step(shuttle_id, step, data)
            self.send_message({"type": "wizard_step_saved", "shuttle_id": shuttle_id, **result})

        elif msg_type == "wizard_run_agent":
            shuttle_id = message.get("shuttle_id")
            team = message.get("team")
            input_data = message.get("input", {})
            debug_log(f"Wizard run agent: {shuttle_id} / {team}")
            async def _run_wizard_agent():
                from spaces.shuttles.wizard_handler import get_wizard_handler
                handler = get_wizard_handler()
                result = await handler.run_agent(shuttle_id, team, input_data)
                self.send_message({"type": "wizard_agent_result", "shuttle_id": shuttle_id, **result})
            asyncio.create_task(_run_wizard_agent())

        elif msg_type == "wizard_finalize":
            shuttle_id = message.get("shuttle_id")
            debug_log(f"Wizard finalize: {shuttle_id}")
            from spaces.shuttles.wizard_handler import get_wizard_handler
            handler = get_wizard_handler()
            result = handler.finalize(shuttle_id)
            self.send_message({"type": "wizard_finalized", "shuttle_id": shuttle_id, **result})

        elif msg_type == "wizard_approve_suggestion":
            suggestion_id = message.get("suggestion_id")
            debug_log(f"Wizard approve suggestion: {suggestion_id}")
            async def _approve():
                from spaces.shuttles.wizard_handler import get_wizard_handler
                handler = get_wizard_handler()
                result = await handler.approve_suggestion(suggestion_id)
                self.send_message({"type": "wizard_suggestion_resolved", **result})
            asyncio.create_task(_approve())

        elif msg_type == "wizard_reject_suggestion":
            suggestion_id = message.get("suggestion_id")
            reason = message.get("reason", "")
            debug_log(f"Wizard reject suggestion: {suggestion_id}")
            async def _reject():
                from spaces.shuttles.wizard_handler import get_wizard_handler
                handler = get_wizard_handler()
                result = await handler.reject_suggestion(suggestion_id, reason)
                self.send_message({"type": "wizard_suggestion_resolved", **result})
            asyncio.create_task(_reject())

        elif msg_type == "start_automation_ui":
            # Start Automation_ui backend on-demand (for Vapi Voice Control)
            self._start_automation_ui_backend()

        elif msg_type == "start_swe_design":
            # Server lifecycle now handled by Electron-side embed.js
            debug_log("start_swe_design: ignored (managed by embed.js)")

        elif msg_type == "create_project_from_shuttle":
            # Create a project from a validated shuttle
            shuttle_id = message.get("shuttle_id")
            bubble_name = message.get("bubble_name")
            debug_log(f"Creating project from shuttle: {shuttle_id}, bubble: {bubble_name}")

            try:
                from data import ShuttlesRepository, ProjectsRepository, ShuttleStatus
                import uuid

                shuttles_repo = ShuttlesRepository()
                projects_repo = ProjectsRepository()

                # Get shuttle data
                shuttle = shuttles_repo.get(shuttle_id)
                if not shuttle:
                    self.send_message({
                        "type": "project_created",
                        "success": False,
                        "error": f"Shuttle {shuttle_id} not found"
                    })
                    return

                # Create project from shuttle
                project_id = str(uuid.uuid4())
                project_name = shuttle.bubble_name or bubble_name or "Unnamed Project"

                # Get requirements if available
                requirements_json = shuttle.requirement_results if shuttle.requirement_results else None

                project = projects_repo.create(
                    name=project_name,
                    description=f"Project created from validated requirements (score: {shuttle.score:.2f})",
                    from_idea_id=shuttle.bubble_id,
                    metadata={
                        "source_shuttle_id": shuttle.shuttle_id,
                        "validation_score": shuttle.score,
                        "passed_count": shuttle.passed_count,
                        "failed_count": shuttle.failed_count,
                        "total_count": shuttle.total_count,
                        "current_stage": shuttle.current_stage
                    }
                )

                # Update project with requirements
                if requirements_json:
                    project.requirements_json = requirements_json
                    projects_repo.update(project)

                # Mark shuttle as arrived
                shuttles_repo.complete(shuttle.id, shuttle.score, ShuttleStatus.ARRIVED)

                debug_log(f"Project created: {project.id} from shuttle {shuttle.shuttle_id}")

                self.send_message({
                    "type": "project_created",
                    "success": True,
                    "project": {
                        "id": project.id,
                        "name": project.name,
                        "description": project.description,
                        "score": shuttle.score,
                        "from_shuttle": shuttle.shuttle_id
                    }
                })

            except Exception as e:
                logger.error(f"Failed to create project from shuttle: {e}")
                self.send_message({
                    "type": "project_created",
                    "success": False,
                    "error": str(e)
                })

        # ====================================================================
        # EXPLORATION IPC Handlers (AI-Scientist Tree Search)
        # ====================================================================

        elif msg_type == "exploration_start":
            # Start exploration from Electron UI
            bubble_id = message.get("bubble_id")
            depth = message.get("depth", 4)
            mode = message.get("mode", "auto")
            context = message.get("context")
            debug_log(f"Starting exploration: bubble={bubble_id}, mode={mode}, depth={depth}")
            asyncio.create_task(self._exploration.handle_exploration_start(bubble_id, depth, mode, context))

        elif msg_type == "exploration_stop":
            debug_log("Stopping exploration")
            asyncio.create_task(self._exploration.handle_exploration_stop())

        elif msg_type == "exploration_respond":
            question_id = message.get("question_id")
            response_type = message.get("response_type")
            selected_option = message.get("selected_option")
            custom_text = message.get("custom_text")
            debug_log(f"Exploration response: {response_type} for question {question_id}")
            asyncio.create_task(self._exploration.handle_exploration_respond(
                question_id, response_type, selected_option, custom_text
            ))

        elif msg_type == "exploration_direction":
            direction = message.get("direction")
            bubble_id = message.get("bubble_id")
            debug_log(f"Setting exploration direction: {direction}")
            asyncio.create_task(self._exploration.handle_exploration_direction(direction, bubble_id))

        elif msg_type == "exploration_status":
            asyncio.create_task(self._exploration.handle_exploration_status())

        # ====================================================================
        # UI TOOLBAR - Direct Tool Execution (user clicks tool in sidebar)
        # ====================================================================

        elif msg_type == "tool_action":
            event_type = message.get("event_type")
            payload = message.get("payload", {})
            debug_log(f"Tool action from UI toolbar: {event_type} with {payload}")
            asyncio.create_task(self._handle_tool_action(event_type, payload))

        # ====================================================================
        # CLAWPORT DASHBOARD - Schedule, Agents, Chat, Memory, N8N
        # ====================================================================

        elif msg_type == "get_scheduled_tasks":
            asyncio.create_task(self._clawport.handle_get_scheduled_tasks(message))

        elif msg_type == "update_task_status":
            asyncio.create_task(self._clawport.handle_update_task_status(message))

        elif msg_type == "get_agent_status":
            asyncio.create_task(self._clawport.handle_get_agent_status_sync())

        elif msg_type == "chat_text_input":
            asyncio.create_task(self._clawport.handle_chat_text_input(message))

        elif msg_type == "get_conversation_history":
            asyncio.create_task(self._clawport.handle_get_conversation_history(message))

        elif msg_type == "get_memory_overview":
            asyncio.create_task(self._clawport.handle_get_memory_overview())

        elif msg_type == "search_memory":
            asyncio.create_task(self._clawport.handle_search_memory(message))

        elif msg_type == "get_recent_memory":
            asyncio.create_task(self._clawport.handle_get_recent_memory(message))

        # ── Plugin Management ──
        elif msg_type == "get_plugins":
            asyncio.create_task(self._clawport.handle_get_plugins())

        elif msg_type == "accept_plugin":
            asyncio.create_task(self._clawport.handle_accept_plugin(message))

        elif msg_type == "reject_plugin":
            asyncio.create_task(self._clawport.handle_reject_plugin(message))

        elif msg_type == "toggle_plugin":
            asyncio.create_task(self._clawport.handle_toggle_plugin(message))

        elif msg_type == "n8n_status":
            asyncio.create_task(self._n8n.handle_n8n_status())

        elif msg_type == "n8n_list":
            asyncio.create_task(self._n8n.handle_n8n_list())

        elif msg_type == "n8n_generate":
            asyncio.create_task(self._n8n.handle_n8n_generate(message))

        elif msg_type == "n8n_activate":
            asyncio.create_task(self._n8n.handle_n8n_activate(message))

        elif msg_type == "n8n_deactivate":
            asyncio.create_task(self._n8n.handle_n8n_deactivate(message))

        elif msg_type == "n8n_delete":
            asyncio.create_task(self._n8n.handle_n8n_delete(message))

        # ── AgentFarm handlers ──
        elif msg_type == "agentfarm_create_team":
            asyncio.create_task(self._handle_agentfarm_create_team(message))

        elif msg_type == "agentfarm_run":
            asyncio.create_task(self._handle_agentfarm_run(message))

        elif msg_type == "agentfarm_status":
            asyncio.create_task(self._handle_agentfarm_status())

        elif msg_type == "agentfarm_list_teams":
            asyncio.create_task(self._handle_agentfarm_list_teams())

        elif msg_type == "agentfarm_stop_run":
            asyncio.create_task(self._handle_agentfarm_stop_run(message))

        elif msg_type == "agentfarm_run_results":
            asyncio.create_task(self._handle_agentfarm_run_results(message))

        # ── Video Production handlers ──
        elif msg_type == "video_status":
            asyncio.create_task(self._handle_video_tool("video_status", "video_status_result"))
        elif msg_type == "video_team_run":
            asyncio.create_task(self._handle_video_tool("team_run_step", "video_team_run_result", message))
        elif msg_type == "video_vision":
            asyncio.create_task(self._handle_video_tool("vision_generate", "video_vision_result", message))
        elif msg_type == "video_demo_analyze":
            asyncio.create_task(self._handle_video_tool("demo_analyze", "video_demo_analyze_result", message))
        elif msg_type == "video_demo_build":
            asyncio.create_task(self._handle_video_tool("demo_build", "video_demo_build_result", message))
        elif msg_type == "video_lipsync":
            asyncio.create_task(self._handle_video_tool("lipsync_run", "video_lipsync_result", message))
        elif msg_type == "video_lipsync_analyze":
            asyncio.create_task(self._handle_video_tool("lipsync_analyze", "video_lipsync_analyze_result"))
        elif msg_type == "video_voice_clone":
            asyncio.create_task(self._handle_video_tool("voice_clone", "video_voice_clone_result"))
        elif msg_type == "video_voice_tts":
            asyncio.create_task(self._handle_video_tool("voice_tts", "video_voice_tts_result", message))
        elif msg_type == "video_list":
            asyncio.create_task(self._handle_video_tool("scan_video_outputs", "video_list_result"))

        # ── Rowboat update checker ──
        elif msg_type == "check_rowboat_update":
            self._handle_check_rowboat_update()

        # ── eyeTerm handlers ──
        elif msg_type == "eyeterm_start":
            asyncio.create_task(self._eyeterm.handle_eyeterm_start(message))
        elif msg_type == "eyeterm_stop":
            asyncio.create_task(self._eyeterm.handle_eyeterm_stop())
        elif msg_type == "eyeterm_toggle_cursor":
            asyncio.create_task(self._eyeterm.handle_eyeterm_toggle_cursor())
        elif msg_type == "eyeterm_calibrate":
            asyncio.create_task(self._eyeterm.handle_eyeterm_calibrate())

        # ── Flowzen (Blaue Rose) handlers ──
        elif msg_type == "flowzen_status":
            try:
                from spaces.flowzen.tools.flowzen_tools import get_flowzen_status
                result = get_flowzen_status()
                self._send_to_electron({
                    "type": "flowzen_status_result",
                    **result.get("status", {}),
                })
            except Exception as e:
                logger.debug(f"flowzen_status failed: {e}")

        elif msg_type == "flowzen_recommend":
            asyncio.create_task(self._handle_flowzen_recommend())

        elif msg_type == "flowzen_diary_entries":
            try:
                from data.flowzen_repository import FlowzenRepository
                repo = FlowzenRepository()
                entries = repo.get_recent_diary_entries(limit=10)
                self._send_to_electron({
                    "type": "flowzen_diary_entries_result",
                    "entries": [e.to_dict() for e in entries],
                })
            except Exception as e:
                logger.debug(f"flowzen_diary_entries failed: {e}")
                self._send_to_electron({
                    "type": "flowzen_diary_entries_result",
                    "entries": [],
                })

    # ========================================================================
    # FLOWZEN RECOMMEND HANDLER
    # ========================================================================

    async def _handle_flowzen_recommend(self):
        """Handle flowzen_recommend IPC message — call recommend_task and send result."""
        try:
            from spaces.flowzen.tools.flowzen_tools import recommend_task
            result = recommend_task()
            self.send_message({
                "type": "flowzen_recommend_result",
                **result,
            })
        except Exception as e:
            logger.debug(f"flowzen_recommend failed: {e}")
            self.send_message({
                "type": "flowzen_recommend_result",
                "success": False,
                "recommendation": {"reasoning": f"Fehler: {e}", "category": "\u2014"},
            })

    # ========================================================================
    # ROWBOAT UPDATE CHECKER
    # ========================================================================

    def _handle_check_rowboat_update(self):
        """Handle manual Rowboat update check request from Electron."""
        if hasattr(self, '_rowboat_update_checker') and self._rowboat_update_checker:
            import threading
            threading.Thread(
                target=self._rowboat_update_checker.check_now,
                daemon=True,
                name="rowboat-update-manual",
            ).start()
            debug_log("Manual Rowboat update check triggered")
        else:
            debug_log("Rowboat update checker not available")
            self.send_message({
                "type": "rowboat_update_check_result",
                "up_to_date": False,
                "error": "Update checker not initialized",
            })

    # ========================================================================
    # UI TOOLBAR HANDLER
    # ========================================================================

    async def _handle_tool_action(self, event_type: str, payload: dict):
        """Execute a tool action triggered from the UI toolbar."""
        try:
            from swarm.orchestrator import get_orchestrator
            orchestrator = get_orchestrator()
            if not orchestrator:
                debug_log("No orchestrator available for tool action")
                return

            # Execute via orchestrator sync path (same as voice commands in FORCE_SYNC_MODE)
            result = await orchestrator._process_sync(
                event_type=event_type,
                payload=payload or {},
                response_hint="",
                user_id="ui_toolbar",
                session_id="ui"
            )

            if result and result.response_hint:
                debug_log(f"Tool action result: {result.response_hint[:100]}")
                self.send_message({
                    "type": "agent_response",
                    "text": result.response_hint
                })
        except Exception as e:
            logger.error(f"Tool action failed: {e}")
            self.send_message({
                "type": "agent_response",
                "text": f"Tool action failed: {str(e)}"
            })



    # ── AgentFarm Handlers ──────────────────────────────────────────

    async def _handle_agentfarm_create_team(self, message):
        try:
            from spaces.autogen.tools.agentfarm_tools import create_team
            result = create_team(
                template_id=message.get("template_id"),
                team_name=message.get("team_name"),
                team_config=message.get("team_config"),
            )
            self.send_message({"type": "agentfarm_create_team_result", **result})
        except Exception as e:
            self.send_message({"type": "agentfarm_create_team_result", "success": False, "message": str(e)})

    async def _handle_agentfarm_run(self, message):
        try:
            from spaces.autogen.tools.agentfarm_tools import run_team
            result = await run_team(
                team_id=message.get("team_id", ""),
                task=message.get("task", ""),
            )
            self.send_message({"type": "agentfarm_run_result", **result})
        except Exception as e:
            self.send_message({"type": "agentfarm_run_result", "success": False, "message": str(e)})

    async def _handle_agentfarm_status(self):
        try:
            from spaces.autogen.tools.agentfarm_tools import get_farm_status
            result = get_farm_status()
            self.send_message({"type": "agentfarm_status_result", **result})
        except Exception as e:
            self.send_message({"type": "agentfarm_status_result", "success": False, "message": str(e)})

    async def _handle_agentfarm_list_teams(self):
        try:
            from spaces.autogen.tools.agentfarm_tools import list_teams
            result = list_teams()
            self.send_message({"type": "agentfarm_list_teams_result", **result})
        except Exception as e:
            self.send_message({"type": "agentfarm_list_teams_result", "success": False, "message": str(e)})

    async def _handle_agentfarm_stop_run(self, message):
        try:
            from spaces.autogen.tools.agentfarm_tools import stop_run
            result = stop_run(run_id=message.get("run_id", ""))
            self.send_message({"type": "agentfarm_stop_run_result", **result})
        except Exception as e:
            self.send_message({"type": "agentfarm_stop_run_result", "success": False, "message": str(e)})

    async def _handle_agentfarm_run_results(self, message):
        try:
            from spaces.autogen.tools.agentfarm_tools import get_run_results
            result = get_run_results(run_id=message.get("run_id", ""))
            self.send_message({"type": "agentfarm_run_results_result", **result})
        except Exception as e:
            self.send_message({"type": "agentfarm_run_results_result", "success": False, "message": str(e)})

    # ========================================================================
    # VIDEO PRODUCTION IPC Handlers
    # ========================================================================

    async def _handle_video_tool(self, tool_name: str, response_type: str, message: dict = None):
        """Generic handler for video production tool calls."""
        try:
            import spaces.video.tools.video_tools as vt
            tool_fn = getattr(vt, tool_name, None)
            if not tool_fn:
                self.send_message({"type": response_type, "success": False, "message": f"Unknown tool: {tool_name}"})
                return
            # Extract params from message (exclude 'type')
            params = {k: v for k, v in (message or {}).items() if k != "type"} if message else {}
            result = tool_fn(**params)
            self.send_message({"type": response_type, **result})
        except Exception as e:
            debug_log(f"Video tool error ({tool_name}): {e}")
            self.send_message({"type": response_type, "success": False, "message": str(e)})







# ==============================================================================
# MAIN - Async Event Loop (Windows-kompatibel)
# ==============================================================================

def stdin_reader_thread(message_queue: 'asyncio.Queue', loop: asyncio.AbstractEventLoop):
    """
    Thread-basierter stdin Reader für Windows-Kompatibilität.
    Liest synchron von stdin und pusht Messages in die asyncio Queue.
    """
    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                debug_log("stdin closed, signaling exit")
                loop.call_soon_threadsafe(message_queue.put_nowait, None)
                break
                
            line_str = line.strip()
            if not line_str:
                continue
                
            try:
                message = json.loads(line_str)
                loop.call_soon_threadsafe(message_queue.put_nowait, message)
            except json.JSONDecodeError as e:
                debug_log(f"Invalid JSON: {e}")
                
        except Exception as e:
            debug_log(f"stdin reader error: {e}")
            break


async def main():
    """
    Haupt-Event-Loop mit Windows-kompatiblem stdin-Handling.
    Verwendet einen separaten Thread für stdin anstatt connect_read_pipe().
    """
    debug_log("main() starting...")
    
    # Initialize backend
    backend = ElectronBackend()
    debug_log("ElectronBackend created")
    
    # Send ready signal to Electron
    backend.send_message({"type": "python_ready"})
    debug_log("Sent python_ready signal")

    # Auto-start voice if configured (no need to click "Start Voice" button)
    if os.getenv("VOICE_AUTO_START", "false").lower() == "true":
        debug_log("VOICE_AUTO_START=true — starting voice automatically...")
        asyncio.create_task(backend._voice_mgr.start_voice())

    # Create message queue for thread-to-async communication
    message_queue = asyncio.Queue()
    loop = asyncio.get_event_loop()
    
    # Start stdin reader thread (works on Windows!)
    reader_thread = threading.Thread(
        target=stdin_reader_thread,
        args=(message_queue, loop),
        daemon=True
    )
    reader_thread.start()
    debug_log("stdin reader thread started")
    
    # Main message processing loop
    try:
        while True:
            try:
                message = await message_queue.get()

                if message is None:
                    debug_log("Received exit signal, shutting down")
                    break

                debug_log(f"Processing message: {message.get('type', 'unknown')}")
                backend.handle_message(message)

            except asyncio.CancelledError:
                debug_log("main() cancelled")
                break
            except Exception as e:
                debug_log(f"Error processing message: {e}")
                import traceback
                debug_log(traceback.format_exc())
    finally:
        # Coordinated graceful shutdown with 12s total budget
        debug_log("Performing graceful shutdown...")
        try:
            await asyncio.wait_for(backend._voice_mgr.cleanup(), timeout=12.0)
        except asyncio.TimeoutError:
            debug_log("cleanup() TIMED OUT (12s) — forcing exit")
        except Exception as e:
            debug_log(f"cleanup() error: {e}")

    debug_log("main() finished")


if __name__ == "__main__":
    debug_log("Starting electron_backend.py")
    
    # Windows-specific: Use ProactorEventLoop (default on Windows 3.8+)
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        debug_log("Interrupted by user")
    except Exception as e:
        debug_log(f"Fatal error: {e}")
        import traceback
        debug_log(traceback.format_exc())
        sys.exit(1)
