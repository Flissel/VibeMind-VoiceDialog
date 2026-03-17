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
                    on_status_update=self._on_generation_status_update,
                    on_issue_detected=self._on_issue_detected,
                    on_quality_update=self._on_quality_summary_update,
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

        # Connect bubble position getter for tools that need to store positions
        if HAS_WORKSPACE_TOOLS and set_bubble_position_getter:
            set_bubble_position_getter(self._get_bubble_position_by_db_id)
            debug_log("Bubble position getter connected")
            
        # Connect navigation tools to our IPC
        if HAS_NAVIGATION_TOOLS and set_navigation_sender:
            set_navigation_sender(self.send_message)
            debug_log("Navigation tools connected to Electron IPC")
            logger.info("Navigation tools connected to Electron IPC")

        # ── IPC Handler Modules ──
        from ipc.n8n_handlers import N8nHandlers
        from ipc.clawport_handlers import ClawPortHandlers
        from ipc.exploration_handlers import ExplorationHandlers
        from ipc.eyeterm_handlers import EyeTermHandlers
        from ipc.project_manager import ProjectManager
        from ipc.shuttle_handlers import ShuttleHandlers
        self._n8n = N8nHandlers(self)
        self._clawport = ClawPortHandlers(self)
        self._exploration = ExplorationHandlers(self)
        self._eyeterm = EyeTermHandlers(self)
        self._project_mgr = ProjectManager(self)
        self._shuttle = ShuttleHandlers(self)
        debug_log("IPC handler modules loaded")

        # Load bubbles from database in background (sends node_added IPC per bubble)
        import threading
        threading.Thread(
            target=self._load_bubbles_from_db,
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
                self._handle_chat_text_input({"text": transcript})

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

    def _check_collision(self, new_pos: Dict[str, float], min_distance: float = 1.2) -> bool:
        """Check if a position collides with existing bubbles."""
        for bubble in self.bubbles.values():
            dx = new_pos["x"] - bubble.position["x"]
            dy = new_pos["y"] - bubble.position["y"]
            dz = new_pos["z"] - bubble.position["z"]
            distance = (dx*dx + dy*dy + dz*dz) ** 0.5

            # Check against bubble radius + minimum spacing
            bubble_radius = bubble.radius
            if distance < (bubble_radius + min_distance):
                return True
        return False

    def _find_free_position(self, angle: float, base_radius: float, max_attempts: int = 20) -> Dict[str, float]:
        """Find a collision-free position using spiral pattern with collision avoidance."""
        import math
        import random

        for attempt in range(max_attempts):
            # Increase radius slightly for each attempt
            radius_pos = base_radius + (attempt * 0.4)
            # Add some randomness to angle to avoid patterns
            adjusted_angle = angle + (attempt * 0.3) + (random.random() - 0.5) * 0.5

            x = math.cos(adjusted_angle) * radius_pos
            z = math.sin(adjusted_angle) * radius_pos
            y = (attempt % 4 - 1.5) * 0.6  # More varied heights

            new_pos = {"x": x, "y": y, "z": z}

            if not self._check_collision(new_pos):
                return new_pos

        # If no free position found, use a fallback with larger spacing
        fallback_angle = angle + random.random() * math.pi * 2
        fallback_radius = base_radius + max_attempts * 0.5
        return {
            "x": math.cos(fallback_angle) * fallback_radius,
            "y": (random.random() - 0.5) * 2.0,
            "z": math.sin(fallback_angle) * fallback_radius
        }

    def _load_bubbles_from_db(self):
        """Load bubbles from IdeasRepository into in-memory state."""
        global _bubble_id_map

        if not self.ideas_repo:
            return

        try:
            import math
            ideas = self.ideas_repo.list(limit=50, order_by="created_at DESC")

            # Color palette for bubbles
            colors = [0x66aaff, 0xff66aa, 0x66ffaa, 0xffcc66, 0xcc66ff,
                      0xff9966, 0x66ffcc, 0x9966ff, 0xff6666, 0x66ff66]

            for i, idea in enumerate(ideas):
                # Check for stored position in metadata (persists across restarts)
                stored_pos = None
                if idea.metadata and isinstance(idea.metadata, dict):
                    stored_pos = idea.metadata.get("position")

                if stored_pos and all(k in stored_pos for k in ["x", "y", "z"]):
                    # Use stored position but check if it still works
                    x, y, z = stored_pos["x"], stored_pos["y"], stored_pos["z"]
                    test_pos = {"x": x, "y": y, "z": z}

                    if not self._check_collision(test_pos):
                        debug_log(f"Using stored position for '{idea.title}': ({x}, {y}, {z})")
                    else:
                        # Stored position collides, find a new one
                        debug_log(f"Stored position collides for '{idea.title}', finding new position")
                        base_angle = i * 0.8
                        base_radius = 1.5 + (i * 0.3)
                        new_pos = self._find_free_position(base_angle, base_radius)
                        x, y, z = new_pos["x"], new_pos["y"], new_pos["z"]

                        # Update stored position
                        new_metadata = idea.metadata.copy() if idea.metadata else {}
                        new_metadata["position"] = {"x": x, "y": y, "z": z}
                        try:
                            idea.metadata = new_metadata
                            self.ideas_repo.update(idea)
                            debug_log(f"Updated position for '{idea.title}': ({x}, {y}, {z})")
                        except Exception as e:
                            debug_log(f"Failed to update position for '{idea.title}': {e}")
                else:
                    # Generate new position with collision avoidance
                    base_angle = i * 0.8
                    base_radius = 1.5 + (i * 0.3)
                    new_pos = self._find_free_position(base_angle, base_radius)
                    x, y, z = new_pos["x"], new_pos["y"], new_pos["z"]

                    # Save generated position to metadata for persistence
                    new_metadata = idea.metadata.copy() if idea.metadata else {}
                    new_metadata["position"] = {"x": x, "y": y, "z": z}
                    try:
                        # Update the idea object's metadata and save
                        idea.metadata = new_metadata
                        self.ideas_repo.update(idea)
                        debug_log(f"Saved position for '{idea.title}': ({x}, {y}, {z})")
                    except Exception as e:
                        debug_log(f"Failed to save position for '{idea.title}': {e}")

                bubble = Bubble(
                    id=self.next_bubble_id,
                    title=idea.title,
                    position={"x": x, "y": y, "z": z},
                    color=colors[i % len(colors)],
                    radius=0.6 + (idea.score / 200),  # Bigger bubbles for higher scores
                    db_id=idea.id  # Store the database UUID
                )

                # Store mappings (both instance and module-level)
                self.bubbles[bubble.id] = bubble
                self.bubble_id_map[idea.id] = bubble.id
                _bubble_id_map[idea.id] = bubble.id  # Sync module-level
                self.next_bubble_id += 1

            logger.info(f"Loaded {len(ideas)} bubbles from database")

        except Exception as e:
            logger.warning(f"Failed to load bubbles from database: {e}")

    def _generate_vnc_url(self, project_id: str, vnc_port: int) -> str:
        """
        Generate VNC URL based on configuration.
        
        Modes:
        1. Proxy Mode (VNC_BASE_URL set): https://preview.domain.com/vnc/{project_id}
        2. Direct Mode (VNC_HOST set): http://{host}:{port}/vnc.html
        3. Default: http://localhost:{port}/vnc.html
        """
        if self.vnc_use_proxy and self.vnc_base_url:
            # Cloud Production: Use reverse proxy URL
            # URL format: {base_url}/{project_id}
            # Example: https://preview.vibemind.io/vnc/proj-abc123
            base = self.vnc_base_url.rstrip('/')
            return f"{base}/{project_id}"
        else:
            # Direct connection mode
            return f"http://{self.vnc_host}:{vnc_port}/vnc.html"

    def add_bubble(self, title: str, position: Dict = None,
                   color: int = 0x4488ff, radius: float = 0.7) -> Bubble:
        """Add a new bubble."""
        bubble = Bubble(
            id=self.next_bubble_id,
            title=title,
            position=position or {"x": 0, "y": 0, "z": 0},
            color=color,
            radius=radius
        )
        self.bubbles[bubble.id] = bubble
        self.next_bubble_id += 1
        return bubble

    def remove_bubble(self, bubble_id: int) -> bool:
        """Remove a bubble by ID."""
        if bubble_id in self.bubbles:
            del self.bubbles[bubble_id]
            return True
        return False

    def get_all_bubbles(self) -> List[dict]:
        """Get all bubbles as dictionaries with numbered titles."""
        bubbles_list = []
        for i, bubble in enumerate(self.bubbles.values(), 1):
            bubble_dict = bubble.to_dict()
            # Add numbered title for navigation (e.g., "1. Universe A")
            bubble_dict["numbered_title"] = f"{i}. {bubble.title}"
            bubbles_list.append(bubble_dict)
        return bubbles_list

    def get_all_bubbles_with_embeddings(self) -> List[dict]:
        """Get all bubbles with their embeddings for exploration.

        Returns list of dicts with id, title, description, embedding.
        """
        if not self.ideas_repo:
            return []

        try:
            import json
            ideas = self.ideas_repo.list(limit=100)
            bubbles = []

            for idea in ideas:
                # Only top-level ideas (bubbles) - no parent_id
                if idea.parent_id:
                    continue

                bubble = {
                    "id": idea.id,
                    "title": idea.title,
                    "description": idea.description or "",
                }

                # Parse embedding if available
                if idea.embedding_vector:
                    try:
                        bubble["embedding"] = json.loads(idea.embedding_vector)
                    except (json.JSONDecodeError, TypeError):
                        bubble["embedding"] = None
                else:
                    bubble["embedding"] = None

                bubbles.append(bubble)

            debug_log(f"get_all_bubbles_with_embeddings: Found {len(bubbles)} bubbles")
            return bubbles

        except Exception as e:
            debug_log(f"Failed to get bubbles with embeddings: {e}")
            logger.warning(f"Failed to get bubbles with embeddings: {e}")
            return []

    @property
    def current_bubble(self) -> Optional[dict]:
        """Get the current bubble as a dict (for exploration tools)."""
        if self.current_bubble_id is None:
            return None

        bubble = self.bubbles.get(self.current_bubble_id)
        if not bubble:
            return None

        return {
            "id": bubble.db_id,
            "title": bubble.title,
            "local_id": self.current_bubble_id,
        }

    def _get_bubble_position_by_db_id(self, bubble_db_id: str) -> Optional[dict]:
        """Get bubble position by database ID. Used by tools to store positions."""
        for bubble in self.bubbles.values():
            if bubble.db_id == bubble_db_id:
                return bubble.position
        return None

    def get_active_shuttles(self) -> List[dict]:
        """Get active shuttles for visualization restoration."""
        if not self.shuttles_repo:
            return []

        try:
            shuttles = self.shuttles_repo.list_active(limit=50)
            result = []
            for s in shuttles:
                shuttle_dict = s.to_dict()
                # ALWAYS use bubble's CURRENT position (from self.bubbles)
                # This ensures shuttle and bubble positions are in sync
                bubble_pos = None
                for bubble in self.bubbles.values():
                    if bubble.db_id == s.bubble_id:
                        bubble_pos = bubble.position
                        break
                shuttle_dict["start_position"] = bubble_pos
                result.append(shuttle_dict)
            return result
        except Exception as e:
            debug_log(f"Failed to get active shuttles: {e}")
            logger.warning(f"Failed to get active shuttles: {e}")
            return []

    def enter_bubble(self, bubble_id: int):
        """Enter a bubble to view its canvas."""
        global _current_bubble_id

        if bubble_id not in self.bubbles:
            return

        self.current_bubble_id = bubble_id
        _current_bubble_id = bubble_id  # Sync module-level state

        # Find the database UUID for this bubble
        db_bubble_id = None
        for db_id, local_id in self.bubble_id_map.items():
            if local_id == bubble_id:
                db_bubble_id = db_id
                break

        logger.info(f"Entering bubble {bubble_id} (db_id: {db_bubble_id})")

        # CRITICAL: Sync _current_bubble_db_id in bubble_tools for list_ideas to work
        if HAS_BUBBLE_TOOLS and bubble_tools_module and db_bubble_id:
            bubble_tools_module._current_bubble_db_id = db_bubble_id
            logger.info(f"Synced _current_bubble_db_id to '{db_bubble_id}'")

        # Load nodes from database if available
        bubble_nodes = []
        if self.canvas_repo and db_bubble_id:
            try:
                db_nodes = self.canvas_repo.list_nodes(limit=1000)
                # Filter nodes by linked_idea_id (the DB UUID of the bubble)
                for db_node in db_nodes:
                    if db_node.linked_idea_id == db_bubble_id:
                        # Map DB UUID to local int ID
                        if db_node.id not in self.db_id_map:
                            local_id = self.next_node_id
                            self.next_node_id += 1
                            self.db_id_map[db_node.id] = local_id
                            self.node_id_map[local_id] = db_node.id
                        else:
                            local_id = self.db_id_map[db_node.id]

                        node = {
                            "id": local_id,
                            "type": db_node.node_type or "note",
                            "position": {"x": db_node.x or 100, "y": db_node.y or 100},
                            "content": {
                                "title": db_node.title or "",
                                "text": db_node.content or "",
                            },
                            "connections": []
                        }
                        bubble_nodes.append(node)

                logger.info(f"Loaded {len(bubble_nodes)} nodes for bubble {db_bubble_id}")
            except Exception as e:
                logger.warning(f"Failed to load nodes from database: {e}")

        # Update in-memory content
        self.bubbles[bubble_id].content = bubble_nodes

        # Also load edges if available
        edges = []
        if self.canvas_repo:
            try:
                db_edges = self.canvas_repo.list_edges(limit=1000)
                for db_edge in db_edges:
                    from_local = self.db_id_map.get(db_edge.from_node_id)
                    to_local = self.db_id_map.get(db_edge.to_node_id)
                    if from_local and to_local:
                        edges.append({
                            "from_node_id": from_local,
                            "to_node_id": to_local
                        })
            except Exception as e:
                logger.warning(f"Failed to load edges from database: {e}")

        self.send_message({
            "type": "entered_bubble",
            "bubble_id": bubble_id,
            "bubble_title": self.bubbles[bubble_id].title,
            "content": self.bubbles[bubble_id].content,
            "edges": edges
        })

    def exit_bubble(self):
        """Exit current bubble back to multiverse view."""
        global _current_bubble_id

        self.current_bubble_id = None
        _current_bubble_id = None  # Sync module-level state
        
        # CRITICAL: Clear _current_bubble_db_id in bubble_tools
        if HAS_BUBBLE_TOOLS and bubble_tools_module:
            bubble_tools_module._current_bubble_db_id = None
            logger.info("Cleared _current_bubble_db_id (exited bubble)")

        self.send_message({"type": "exited_bubble"})

    # ========================================================================
    # CANVAS OPERATIONS
    # ========================================================================

    def add_canvas_node(self, bubble_id: int, node_type: str,
                        position: Dict, content: Dict) -> Optional[int]:
        """Add a node to a bubble's canvas."""
        if bubble_id not in self.bubbles:
            return None

        local_id = self.next_node_id
        self.next_node_id += 1

        node = {
            "id": local_id,
            "type": node_type,
            "position": position or {"x": 100, "y": 100},
            "content": content or {},
            "connections": []
        }
        self.bubbles[bubble_id].content.append(node)

        # Save to database
        if self.canvas_repo:
            try:
                # Store extra content fields in metadata
                content_extra = {k: v for k, v in (content or {}).items()
                               if k not in ("title", "text")}
                metadata = {
                    "bubble_id": bubble_id,
                    "content_extra": content_extra if content_extra else None
                }

                db_node = self.canvas_repo.create_node(
                    node_type=node_type or "note",
                    title=(content or {}).get("title", ""),
                    content=(content or {}).get("text", ""),
                    x=(position or {}).get("x", 100),
                    y=(position or {}).get("y", 100),
                    metadata=metadata
                )

                # Store ID mapping
                self.node_id_map[local_id] = db_node.id
                self.db_id_map[db_node.id] = local_id
                logger.info(f"Saved node to DB: {db_node.id} -> local {local_id}")
            except Exception as e:
                logger.warning(f"Failed to save node to database: {e}")

        self.send_message({
            "type": "node_added",
            "bubble_id": bubble_id,
            "node": node
        })

        return local_id

    def update_canvas_node(self, bubble_id: int, node_id: int, updates: Dict):
        """Update a canvas node."""
        if bubble_id not in self.bubbles:
            return

        for node in self.bubbles[bubble_id].content:
            if node["id"] == node_id:
                node.update(updates)

                # Update in database
                if self.canvas_repo and node_id in self.node_id_map:
                    try:
                        db_id = self.node_id_map[node_id]
                        db_node = self.canvas_repo.get_node(db_id)
                        if db_node:
                            # Update position
                            if "position" in updates:
                                db_node.x = updates["position"].get("x", db_node.x)
                                db_node.y = updates["position"].get("y", db_node.y)
                            # Update content
                            if "content" in updates:
                                if "title" in updates["content"]:
                                    db_node.title = updates["content"]["title"]
                                if "text" in updates["content"]:
                                    db_node.content = updates["content"]["text"]
                                # Store extra content in metadata
                                content_extra = {k: v for k, v in updates["content"].items()
                                               if k not in ("title", "text")}
                                if content_extra:
                                    metadata = db_node.metadata or {}
                                    metadata["content_extra"] = content_extra
                                    db_node.metadata = metadata
                            self.canvas_repo.update_node(db_node)
                            logger.info(f"Updated node in DB: {db_id}")
                    except Exception as e:
                        logger.warning(f"Failed to update node in database: {e}")

                self.send_message({
                    "type": "node_updated",
                    "bubble_id": bubble_id,
                    "node_id": node_id,
                    "updates": updates
                })
                break

    def delete_canvas_node(self, bubble_id: int, node_id: int):
        """Delete a canvas node."""
        if bubble_id not in self.bubbles:
            return

        bubble = self.bubbles[bubble_id]
        bubble.content = [n for n in bubble.content if n["id"] != node_id]

        # Delete from database
        if self.canvas_repo and node_id in self.node_id_map:
            try:
                db_id = self.node_id_map[node_id]
                self.canvas_repo.delete_node(db_id)
                # Clean up mappings
                del self.node_id_map[node_id]
                del self.db_id_map[db_id]
                logger.info(f"Deleted node from DB: {db_id}")
            except Exception as e:
                logger.warning(f"Failed to delete node from database: {e}")

        self.send_message({
            "type": "node_deleted",
            "bubble_id": bubble_id,
            "node_id": node_id
        })

    # ========================================================================
    # VOICE DIALOG
    # ========================================================================

    async def start_voice(self):
        """Start voice dialog session with OpenAI Realtime API."""
        self._main_loop = asyncio.get_running_loop()
        debug_log(f"start_voice() called (active={self.voice_active}, stopping={self._voice_stopping}, "
                  f"session={self.openai_realtime_session is not None}, bridge={self.voice_bridge is not None})")
        debug_log(f"HAS_OPENAI_REALTIME: {HAS_OPENAI_REALTIME}")

        # Cancel any still-running start_voice task to prevent concurrent connect() calls
        # IMPORTANT: Skip if old_task is the current task (self-reference from
        # message handler storing the task before the body runs).
        current_task = asyncio.current_task()
        old_task = self._voice_start_task
        if old_task and old_task is not current_task and not old_task.done():
            debug_log("Cancelling previous start_voice task before new start")
            self._start_cancelled = True
            old_task.cancel()
            try:
                await asyncio.wait_for(asyncio.shield(old_task), timeout=5.0)
            except (asyncio.CancelledError, asyncio.TimeoutError, Exception):
                debug_log("Previous start_voice cancel timed out — proceeding anyway")
            self._start_cancelled = False
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
        session = None  # Track for cleanup on CancelledError
        try:
            import time as _time
            _t_total = _time.time()
            debug_log("Initializing OpenAI Realtime voice session...")

            # Reset cancellation flag for this start attempt
            self._start_cancelled = False

            # 0. Clean up any previous session DIRECTLY (not via stop_voice,
            #    which may return immediately if _voice_stopping is True from
            #    a concurrent stop call).
            old_session = self.openai_realtime_session
            old_bridge = self.voice_bridge
            if old_session or old_bridge:
                debug_log("Cleaning up previous session before restart...")
                if old_session:
                    self.openai_realtime_session = None
                    try:
                        await asyncio.wait_for(old_session.disconnect(), timeout=5.0)
                    except (asyncio.TimeoutError, Exception) as e:
                        debug_log(f"Old session disconnect: {e}")
                if old_bridge:
                    self.voice_bridge = None
                    try:
                        await old_bridge.shutdown()
                    except Exception as e:
                        debug_log(f"Old bridge shutdown: {e}")
                self.voice_active = False
                debug_log("Previous session cleaned up")
                self._start_cancelled = False  # Reset after cleanup

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
            if self._start_cancelled:
                debug_log("Voice start cancelled during connect — aborting")
                await session.disconnect()
                return

            # 5. Start audio + greeting IMMEDIATELY after WebSocket connects.
            #    Rachel speaks right away while VoiceBridge initializes.
            self.openai_realtime_session = session
            _t0 = _time.time()
            await session.start()
            debug_log(f"Audio capture + greeting started ({_time.time() - _t0:.2f}s)")

            # Check again after start()
            if self._start_cancelled:
                debug_log("Voice start cancelled during audio init — aborting")
                await session.disconnect()
                self.openai_realtime_session = None
                return

            self.voice_active = True
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
        import time as _time
        try:
            _t0 = _time.time()
            debug_log("Background: Initializing VoiceBridgeV2...")
            bridge = await asyncio.wait_for(
                create_voice_bridge_v2(model_client=None, event_manager=None),
                timeout=30.0
            )
            # Check if voice was stopped during init
            if self.voice_active:
                self.voice_bridge = bridge
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
                return self.openai_realtime_session

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
                return self.openai_realtime_session

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

            self._schedule_worker = worker
            debug_log(
                f"Background: Schedule Space ready — {worker.job_count} active jobs "
                f"({_time.time() - _t0:.2f}s)"
            )

        except Exception as e:
            debug_log(f"Background: Schedule init failed: {e} — scheduling disabled")
            import traceback
            debug_log(traceback.format_exc())

    async def _init_messaging_bridge_background(self):
        """Initialize Messaging Bridge (Voice ↔ WhatsApp/Telegram) in background."""
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
                return self.openai_realtime_session

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
            if self._main_loop and not self._main_loop.is_closed():
                asyncio.run_coroutine_threadsafe(
                    self._deliver_dispatch_result(result),
                    self._main_loop,
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
        session = self.openai_realtime_session
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
            self.voice_active = False

    def _handle_realtime_error(self, error_msg: str):
        """Handle OpenAI Realtime errors."""
        debug_log(f"OpenAI Realtime error: {error_msg}")
        self.send_message({
            "type": "voice_error",
            "error": error_msg
        })

    async def stop_voice(self):
        """Stop voice dialog session (with re-entrance guard)."""
        debug_log(f"stop_voice() called (active={self.voice_active}, stopping={self._voice_stopping})")
        # Signal any pending start_voice to abort
        self._start_cancelled = True

        # Cancel running start_voice task (kills connect() mid-flight)
        # Timeout ensures stop_voice never hangs if connect() is stuck on dead WebSocket
        start_task = self._voice_start_task
        if start_task and not start_task.done():
            debug_log("stop_voice: cancelling running start_voice task")
            start_task.cancel()
            try:
                await asyncio.wait_for(asyncio.shield(start_task), timeout=5.0)
            except (asyncio.CancelledError, asyncio.TimeoutError, Exception):
                debug_log("stop_voice: start_task cancel timed out — proceeding anyway")
        self._voice_start_task = None

        if getattr(self, '_voice_stopping', False):
            debug_log("stop_voice: already stopping — returning early")
            return
        self._voice_stopping = True
        try:
            await self._stop_voice_impl()
        finally:
            self._voice_stopping = False
            debug_log("stop_voice() complete")

    async def _stop_voice_impl(self):
        """Internal stop implementation.

        IMPORTANT: Capture local references to session/bridge before async
        disconnect.  A concurrent start_voice() may replace
        self.openai_realtime_session while we are awaiting disconnect().
        Only clear the instance vars if they still point to the objects
        we stopped — otherwise a new session was started and we must not
        clobber it.
        """
        # Capture references BEFORE any await
        session_to_stop = self.openai_realtime_session
        bridge_to_stop = self.voice_bridge

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
            if self.openai_realtime_session is session_to_stop:
                self.openai_realtime_session = None

        # Stop VoiceBridgeV2 if active
        if bridge_to_stop:
            try:
                await bridge_to_stop.shutdown()
                debug_log("VoiceBridgeV2 shutdown complete")
            except Exception as e:
                debug_log(f"Error shutting down VoiceBridgeV2: {e}")
            if self.voice_bridge is bridge_to_stop:
                self.voice_bridge = None

        # Only send voice_stopped if no new session was started during shutdown
        if self.openai_realtime_session is None:
            self.voice_active = False
            self.send_message({"type": "voice_stopped"})
        else:
            debug_log("stop_voice_impl: new session active — skipping voice_stopped")

    async def cleanup(self):
        """Coordinated shutdown of all services. Budget: 12s total."""
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
        if hasattr(self, '_automation_ui_proc') and self._automation_ui_proc:
            try:
                self._automation_ui_proc.terminate()
                self._automation_ui_proc.wait(timeout=3)
                debug_log("cleanup: automation_ui stopped")
            except subprocess.TimeoutExpired:
                try:
                    self._automation_ui_proc.kill()
                    debug_log("cleanup: automation_ui force-killed")
                except Exception:
                    pass
            except Exception as e:
                debug_log(f"cleanup: automation_ui stop error: {e}")

        # 2b. Stop eyeTerm (camera + MJPEG stream on port 8099)
        for attr in ('_eyeterm_headless', '_eyeterm_app'):
            et = getattr(self, attr, None)
            if et:
                try:
                    et.stop()
                    debug_log(f"cleanup: {attr} stopped")
                except Exception as e:
                    debug_log(f"cleanup: {attr} stop error: {e}")
                setattr(self, attr, None)

        # 3. Stop Rowboat update checker
        if hasattr(self, '_rowboat_update_checker'):
            try:
                self._rowboat_update_checker.stop()
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
            for bubble in self.bubbles.values():
                if bubble.title.lower() in text_lower:
                    self.send_message({
                        "type": "navigate_to_bubble",
                        "bubble_id": bubble.id
                    })
                    break

        elif "exit" in text_lower or "back" in text_lower or "leave" in text_lower:
            if self.current_bubble_id:
                self.send_message({"type": "exit_bubble"})

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
            bubbles_data = self.get_all_bubbles()
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
            self.enter_bubble(bubble_id)

        elif msg_type == "exit_bubble":
            self.exit_bubble()

        elif msg_type == "start_voice":
            task = asyncio.create_task(self.start_voice())
            self._voice_start_task = task

        elif msg_type == "stop_voice":
            asyncio.create_task(self.stop_voice())

        elif msg_type == "toggle_voice":
            if self.voice_active:
                asyncio.create_task(self.stop_voice())
            else:
                task = asyncio.create_task(self.start_voice())
                self._voice_start_task = task

        elif msg_type == "add_canvas_node":
            self.add_canvas_node(
                message.get("bubble_id"),
                message.get("node", {}).get("type"),
                message.get("node", {}).get("position"),
                message.get("node", {}).get("content")
            )

        elif msg_type == "update_canvas_node":
            self.update_canvas_node(
                message.get("bubble_id"),
                message.get("node_id"),
                message.get("updates", {})
            )

        elif msg_type == "delete_canvas_node":
            self.delete_canvas_node(
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
            # Return active shuttles for visualization restoration
            shuttles_data = self.get_active_shuttles()
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

    # ========================================================================
    # CLAWPORT DASHBOARD IPC Handlers
    # ========================================================================

    async def _handle_get_scheduled_tasks(self, message: dict):
        """Get scheduled tasks for ClawPort Schedule tab."""
        try:
            from data import ScheduledTasksRepository
            repo = ScheduledTasksRepository()
            status = message.get("status")
            limit = int(message.get("limit", 50))
            tasks = repo.list(status=status, limit=limit)
            tasks_data = []
            for t in tasks:
                tasks_data.append({
                    "id": t.id,
                    "title": t.title,
                    "description": t.description or "",
                    "action_text": t.action_text or "",
                    "trigger_type": t.trigger_type,
                    "trigger_config": t.trigger_config or "",
                    "execution_mode": t.execution_mode or "",
                    "timezone": t.timezone or "Europe/Berlin",
                    "status": t.status,
                    "next_run_at": t.next_run_at.isoformat() if t.next_run_at else None,
                    "last_run_at": t.last_run_at.isoformat() if t.last_run_at else None,
                    "run_count": t.run_count or 0,
                    "max_runs": t.max_runs,
                    "last_result": t.last_result,
                    "last_error": t.last_error,
                    "created_at": t.created_at.isoformat() if t.created_at else None,
                    "updated_at": t.updated_at.isoformat() if t.updated_at else None,
                    "metadata": t.metadata if isinstance(t.metadata, dict) else {},
                })
            self.send_message({
                "type": "scheduled_tasks_list",
                "tasks": tasks_data,
                "total": len(tasks_data),
            })
        except Exception as e:
            debug_log(f"Error getting scheduled tasks: {e}")
            self.send_message({
                "type": "scheduled_tasks_list",
                "tasks": [],
                "total": 0,
                "error": str(e),
            })

    async def _handle_update_task_status(self, message: dict):
        """Update a scheduled task's status (pause/resume/cancel)."""
        try:
            from data import ScheduledTasksRepository
            repo = ScheduledTasksRepository()
            task_id = message.get("task_id")
            new_status = message.get("new_status")
            if not task_id or not new_status:
                self.send_message({
                    "type": "task_status_updated",
                    "success": False,
                    "task_id": task_id,
                    "new_status": new_status,
                    "error": "task_id and new_status required",
                })
                return
            repo.update_status(task_id, new_status)
            self.send_message({
                "type": "task_status_updated",
                "success": True,
                "task_id": task_id,
                "new_status": new_status,
            })
        except Exception as e:
            debug_log(f"Error updating task status: {e}")
            self.send_message({
                "type": "task_status_updated",
                "success": False,
                "task_id": message.get("task_id"),
                "new_status": message.get("new_status"),
                "error": str(e),
            })

    async def _handle_get_agent_status_sync(self):
        """Get status of all backend agents for ClawPort Agents tab."""
        try:
            from swarm.listeners.status_listener import get_status_listener
            listener = get_status_listener()
            agents_data = []
            for name, info in listener.get_all_status().items():
                agents_data.append({
                    "name": name,
                    "status": info.get("status", "idle"),
                    "last_event_type": info.get("last_event_type"),
                    "last_event_at": info.get("last_event_at"),
                    "last_result": info.get("last_result"),
                    "error": info.get("error"),
                })
            self.send_message({
                "type": "agent_status_list",
                "agents": agents_data,
            })
        except Exception as e:
            debug_log(f"Error getting agent status: {e}")
            self.send_message({
                "type": "agent_status_list",
                "agents": [],
                "error": str(e),
            })

    async def _handle_chat_text_input(self, message: dict):
        """Handle text chat input from ClawPort Chat tab."""
        text = message.get("text", "").strip()
        if not text:
            self.send_message({
                "type": "chat_response",
                "success": False,
                "message": "Empty input",
            })
            return
        try:
            from swarm.orchestrator import get_orchestrator
            orchestrator = get_orchestrator()
            if not orchestrator:
                self.send_message({
                    "type": "chat_response",
                    "success": False,
                    "message": "Orchestrator not available",
                })
                return
            result = await orchestrator.process_intent(text)
            self.send_message({
                "type": "chat_response",
                "success": True,
                "message": result.response_hint if result else "OK",
                "event_type": result.event_type if result else None,
            })
        except Exception as e:
            debug_log(f"Chat input error: {e}")
            self.send_message({
                "type": "chat_response",
                "success": False,
                "message": str(e),
            })

    async def _handle_get_conversation_history(self, message: dict):
        """Get conversation history for ClawPort Chat tab."""
        try:
            limit = int(message.get("limit", 50))
            from tools.conversation_tools import get_conversation_history
            history = get_conversation_history(limit=limit)
            self.send_message({
                "type": "conversation_history",
                "messages": history if isinstance(history, list) else [],
            })
        except Exception as e:
            debug_log(f"Error getting conversation history: {e}")
            self.send_message({
                "type": "conversation_history",
                "messages": [],
            })

    async def _handle_get_memory_overview(self):
        """Get memory services overview for ClawPort Memory tab."""
        try:
            from tools.memory_tools import get_memory_overview
            overview = get_memory_overview()
            self.send_message({
                "type": "memory_overview",
                "data": overview if isinstance(overview, dict) else {
                    "task_memory": {"available": False},
                    "conversation_memory": {"available": False},
                    "user_profiles": {"available": False},
                },
            })
        except Exception as e:
            debug_log(f"Error getting memory overview: {e}")
            self.send_message({
                "type": "memory_overview",
                "data": {
                    "task_memory": {"available": False, "error": str(e)},
                    "conversation_memory": {"available": False},
                    "user_profiles": {"available": False},
                },
            })

    async def _handle_search_memory(self, message: dict):
        """Search memory for ClawPort Memory tab."""
        try:
            query = message.get("query", "")
            category = message.get("category", "task_memory")
            limit = int(message.get("limit", 10))
            from tools.memory_tools import search_memory
            results = search_memory(query=query, category=category, limit=limit)
            self.send_message({
                "type": "memory_search_results",
                "category": category,
                "results": results if isinstance(results, list) else [],
            })
        except Exception as e:
            debug_log(f"Error searching memory: {e}")
            self.send_message({
                "type": "memory_search_results",
                "category": message.get("category", "task_memory"),
                "results": [],
            })

    async def _handle_get_recent_memory(self, message: dict):
        """Get recent memory entries for ClawPort Memory tab."""
        try:
            category = message.get("category", "task_memory")
            limit = int(message.get("limit", 10))
            from tools.memory_tools import get_recent_memory
            results = get_recent_memory(category=category, limit=limit)
            self.send_message({
                "type": "recent_memory",
                "category": category,
                "results": results if isinstance(results, list) else [],
            })
        except Exception as e:
            debug_log(f"Error getting recent memory: {e}")
            self.send_message({
                "type": "recent_memory",
                "category": message.get("category", "task_memory"),
                "results": [],
            })

    # ── N8N Workflow Builder ──────────────────────────────────────────────

    async def _handle_n8n_status(self):
        """Check n8n instance status."""
        try:
            from spaces.n8n.tools.n8n_workflow_tools import get_n8n_status
            result = get_n8n_status()
            self.send_message({
                "type": "n8n_status_result",
                **result,
            })
        except Exception as e:
            debug_log(f"n8n status error: {e}")
            self.send_message({
                "type": "n8n_status_result",
                "success": False,
                "message": str(e),
                "online": False,
            })

    async def _handle_n8n_list(self):
        """List all n8n workflows."""
        try:
            from spaces.n8n.tools.n8n_workflow_tools import list_workflows
            result = list_workflows()
            self.send_message({
                "type": "n8n_list_result",
                **result,
            })
        except Exception as e:
            debug_log(f"n8n list error: {e}")
            self.send_message({
                "type": "n8n_list_result",
                "success": False,
                "message": str(e),
                "workflows": [],
            })

    async def _handle_n8n_generate(self, message: dict):
        """Generate an n8n workflow from natural language description."""
        description = message.get("description", "").strip()
        if not description:
            self.send_message({
                "type": "n8n_generate_result",
                "success": False,
                "message": "No description provided.",
            })
            return
        try:
            from spaces.n8n.tools.n8n_workflow_tools import generate_workflow
            result = generate_workflow(description=description)
            self.send_message({
                "type": "n8n_generate_result",
                **result,
            })
        except Exception as e:
            debug_log(f"n8n generate error: {e}")
            self.send_message({
                "type": "n8n_generate_result",
                "success": False,
                "message": str(e),
            })

    async def _handle_n8n_activate(self, message: dict):
        """Activate an n8n workflow."""
        workflow_id = message.get("workflow_id")
        if not workflow_id:
            self.send_message({
                "type": "n8n_activate_result",
                "success": False,
                "message": "workflow_id required",
            })
            return
        try:
            from spaces.n8n.tools.n8n_workflow_tools import activate_workflow
            result = activate_workflow(workflow_id=workflow_id)
            self.send_message({
                "type": "n8n_activate_result",
                **result,
            })
        except Exception as e:
            debug_log(f"n8n activate error: {e}")
            self.send_message({
                "type": "n8n_activate_result",
                "success": False,
                "message": str(e),
            })

    async def _handle_n8n_deactivate(self, message: dict):
        """Deactivate an n8n workflow."""
        workflow_id = message.get("workflow_id")
        if not workflow_id:
            self.send_message({
                "type": "n8n_deactivate_result",
                "success": False,
                "message": "workflow_id required",
            })
            return
        try:
            from spaces.n8n.tools.n8n_workflow_tools import deactivate_workflow
            result = deactivate_workflow(workflow_id=workflow_id)
            self.send_message({
                "type": "n8n_deactivate_result",
                **result,
            })
        except Exception as e:
            debug_log(f"n8n deactivate error: {e}")
            self.send_message({
                "type": "n8n_deactivate_result",
                "success": False,
                "message": str(e),
            })

    async def _handle_n8n_delete(self, message: dict):
        """Delete an n8n workflow."""
        workflow_id = message.get("workflow_id")
        if not workflow_id:
            self.send_message({
                "type": "n8n_delete_result",
                "success": False,
                "message": "workflow_id required",
            })
            return
        try:
            from spaces.n8n.tools.n8n_workflow_tools import delete_workflow
            result = delete_workflow(workflow_id=workflow_id)
            self.send_message({
                "type": "n8n_delete_result",
                **result,
            })
        except Exception as e:
            debug_log(f"n8n delete error: {e}")
            self.send_message({
                "type": "n8n_delete_result",
                "success": False,
                "message": str(e),
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

    # ========================================================================
    # EYETERM IPC Handlers
    # ========================================================================

    async def _handle_eyeterm_start(self, message: dict):
        """Start eyeTerm in a background thread."""
        if hasattr(self, '_eyeterm_app') and self._eyeterm_app:
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

            self._eyeterm_app = EyeTermApp(config)

            # Wire command router to IntentOrchestrator for complex tasks
            self._wire_eyeterm_orchestrator()

            thread = threading.Thread(
                target=self._eyeterm_app.run,
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
        if not hasattr(self, '_eyeterm_app') or not self._eyeterm_app:
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

        self._eyeterm_app._command_router._on_agent_team = _agent_team_callback

    async def _handle_eyeterm_stop(self):
        """Stop eyeTerm."""
        if hasattr(self, '_eyeterm_app') and self._eyeterm_app:
            self._eyeterm_app._running = False
            self._eyeterm_app = None
            self.send_message({"type": "eyeterm_status", "status": "stopped"})
        else:
            self.send_message({"type": "eyeterm_status", "status": "not_running"})

    async def _handle_eyeterm_toggle_cursor(self):
        """Toggle eyeTerm cursor control."""
        if hasattr(self, '_eyeterm_app') and self._eyeterm_app:
            driver = self._eyeterm_app._cursor_driver
            if driver:
                state = driver.toggle()
                self.send_message({
                    "type": "eyeterm_cursor_status",
                    "success": True,
                    "enabled": state,
                })
                return
        self.send_message({"type": "eyeterm_cursor_status", "success": False, "message": "eyeTerm not running"})

    async def _handle_eyeterm_calibrate(self):
        """Trigger eyeTerm calibration (non-blocking for headless mode)."""
        # Headless instance (primary)
        if hasattr(self, '_eyeterm') and self._eyeterm:
            success = self._eyeterm.calibrate()
            self.send_message({
                "type": "eyeterm_calibrate_result",
                "success": success,
                "message": "Kalibrierung gestartet" if success else "eyeTerm nicht bereit",
            })
            return
        # App instance (legacy)
        if hasattr(self, '_eyeterm_app') and self._eyeterm_app:
            self._eyeterm_app._run_calibration()
            self.send_message({"type": "eyeterm_calibrate_result", "success": True})
            return
        self.send_message({"type": "eyeterm_calibrate_result", "success": False, "message": "eyeTerm not running"})

    # ========================================================================
    # PROJECTS SPACE IPC Handlers
    # ========================================================================

    async def _handle_get_generated_projects(self, message: dict):
        """Get list of all projects - both code-generated and shuttle-created."""
        try:
            repo = ProjectsRepository()

            # --- Discover projects from filesystem (idempotent) ---
            if self.coding_engine_path:
                try:
                    from spaces.coding.engine.project_discovery import ProjectDiscoveryService
                    discovery = ProjectDiscoveryService(self.coding_engine_path)
                    discovered = discovery.discover_projects()
                    synced_count = 0
                    for d in discovered:
                        result = repo.sync_from_discovery(d)
                        if result:
                            synced_count += 1
                    if synced_count > 0:
                        debug_log(f"Synced {synced_count} discovered projects to DB")
                except Exception as e:
                    debug_log(f"Project discovery failed: {e}")
            # --- End discovery ---

            status_filter = message.get("status_filter")
            limit = int(message.get("limit", 20))

            if status_filter:
                projects = repo.list_by_generation_status(status_filter, limit=limit)
            else:
                # Get ALL projects - both code-generated (with job_id) and
                # shuttle-created (with from_idea_id or status=shuttling/active)
                all_projects = repo.list(limit=limit * 2)
                # Include projects that have either:
                # - job_id (code generation)
                # - from_idea_id (shuttle-created)
                # - status is shuttling or active
                projects = [p for p in all_projects if (
                    p.job_id or
                    p.from_idea_id or
                    p.status in ('shuttling', 'active', 'generating', 'completed')
                )][:limit]
            
            # Convert to dicts for JSON
            projects_data = []

            # Get shuttles repo to find linked shuttles
            shuttles_repo = self.shuttles_repo

            for p in projects:
                # Find linked shuttle if project came from a bubble
                linked_shuttle = None
                if p.id and shuttles_repo:
                    shuttle = shuttles_repo.get_by_project_id(p.id)
                    if shuttle:
                        linked_shuttle = shuttle.shuttle_id

                # Enrichment metadata from discovery (stored in metadata JSON)
                proj_meta = p.metadata if isinstance(p.metadata, dict) else {}

                projects_data.append({
                    "id": p.id,
                    "name": p.name,
                    "description": p.description,
                    "status": p.status,  # shuttling, active, generating, completed
                    "from_idea_id": p.from_idea_id,  # Source bubble
                    "linked_shuttle": linked_shuttle,  # Shuttle that created this project
                    "job_id": p.job_id,
                    "generation_status": p.generation_status,
                    "convergence_progress": p.convergence_progress,
                    "tech_stack": p.tech_stack,
                    "vnc_port": p.vnc_port,
                    "preview_url": p.preview_url,
                    "project_path": p.project_path,
                    "error_message": p.error_message,
                    "created_at": p.created_at.isoformat() if p.created_at else None,
                    # Enrichment fields from discovery
                    "total_issues": proj_meta.get("total_issues", 0),
                    "issue_counts": proj_meta.get("issue_counts", {}),
                    "quality_score": proj_meta.get("quality_score", 0),
                    "total_artifacts": proj_meta.get("total_artifacts", 0),
                    "total_cost_usd": proj_meta.get("total_cost_usd", 0),
                    "total_duration_ms": proj_meta.get("total_duration_ms", 0),
                    "stages_completed": proj_meta.get("stages_completed", 0),
                    "total_stages": proj_meta.get("total_stages", 0),
                    "task_count": proj_meta.get("task_count", 0),
                    "diagram_count": proj_meta.get("diagram_count", 0),
                    "user_story_count": proj_meta.get("user_story_count", 0),
                })
            
            self.send_message({
                "type": "generated_projects_list",
                "projects": projects_data
            })
            
        except Exception as e:
            debug_log(f"Error getting generated projects: {e}")
            self.send_message({
                "type": "generated_projects_list",
                "projects": [],
                "error": str(e)
            })

    async def _handle_get_generation_status(self, message: dict):
        """Get status of a specific generation job."""
        job_id = message.get("job_id")
        project_id = message.get("project_id")
        
        if not job_id and not project_id:
            self.send_message({
                "type": "generation_status",
                "error": "job_id or project_id required"
            })
            return
        
        try:
            repo = ProjectsRepository()
            project = None
            
            if job_id:
                project = repo.get_by_job_id(job_id)
            elif project_id:
                project = repo.get(project_id)
            
            if not project:
                self.send_message({
                    "type": "generation_status",
                    "error": "Project not found"
                })
                return
            
            # Get live status from runner if available
            live_status = None
            if self.coding_engine_runner and project.job_id:
                live_status = self.coding_engine_runner.get_job_status(project.job_id)
            
            self.send_message({
                "type": "generation_status",
                "job_id": project.job_id,
                "project_id": project.id,
                "name": project.name,
                "status": live_status.get("status") if live_status else project.generation_status,
                "progress": live_status.get("progress") if live_status else project.convergence_progress,
                "phase": live_status.get("phase") if live_status else "",
                "phase_error": live_status.get("phase_error") if live_status else project.phase_error,
            })
            
        except Exception as e:
            debug_log(f"Error getting generation status: {e}")
            self.send_message({
                "type": "generation_status",
                "error": str(e)
            })

    async def _handle_start_code_generation(self, message: dict):
        """Start a new code generation job (triggered from UI)."""
        if not HAS_CODING_ENGINE or not self.coding_engine_runner:
            self.send_message({
                "type": "generation_started",
                "success": False,
                "error": "Coding engine not available"
            })
            return
        
        try:
            title = message.get("title", "").strip()
            description = message.get("description", "")
            tech_stack = message.get("tech_stack", "react")
            requirements = message.get("requirements", [])
            
            if not title:
                self.send_message({
                    "type": "generation_started",
                    "success": False,
                    "error": "Project title required"
                })
                return
            
            result = await self.coding_engine_runner.run_generate_code(title, description, tech_stack, requirements)
            
            self.send_message({
                "type": "generation_started",
                "success": True,
                "message": result,
            })
            
        except Exception as e:
            debug_log(f"Error starting code generation: {e}")
            self.send_message({
                "type": "generation_started",
                "success": False,
                "error": str(e)
            })

    async def _handle_cancel_code_generation(self, message: dict):
        """Cancel a running code generation job."""
        job_id = message.get("job_id")
        
        if not job_id:
            self.send_message({
                "type": "generation_cancelled",
                "success": False,
                "error": "job_id required"
            })
            return
        
        if not self.coding_engine_runner:
            self.send_message({
                "type": "generation_cancelled",
                "success": False,
                "error": "Coding engine not available"
            })
            return
        
        try:
            success = self.coding_engine_runner.cancel_job(job_id)
            
            self.send_message({
                "type": "generation_cancelled",
                "success": success,
                "job_id": job_id,
            })
            
        except Exception as e:
            debug_log(f"Error cancelling generation: {e}")
            self.send_message({
                "type": "generation_cancelled",
                "success": False,
                "error": str(e)
            })

    async def _handle_enter_projects_space(self, message: dict):
        """Enter the Projects Space view."""
        debug_log("Entering Projects Space")

        # Get all generated projects
        await self._handle_get_generated_projects({"limit": 50})

        self.send_message({
            "type": "entered_projects_space",
        })

    async def _handle_get_shuttle_requirements(self, shuttle_id: str):
        """Get requirements data for a shuttle's interior view."""
        if not shuttle_id:
            self.send_message({
                "type": "shuttle-requirements-loaded",
                "error": "shuttle_id required"
            })
            return

        try:
            # Get shuttle from database
            if not self.shuttles_repo:
                self.send_message({
                    "type": "shuttle-requirements-loaded",
                    "shuttle_id": shuttle_id,
                    "requirements": [],
                    "error": "Database not available"
                })
                return

            shuttle = self.shuttles_repo.get_by_shuttle_id(shuttle_id)
            if not shuttle:
                self.send_message({
                    "type": "shuttle-requirements-loaded",
                    "shuttle_id": shuttle_id,
                    "requirements": [],
                    "error": f"Shuttle {shuttle_id} not found"
                })
                return

            # Get requirements from shuttle.requirement_results
            requirements = []
            if shuttle.requirement_results:
                # requirement_results is stored as JSON string or dict
                results = shuttle.requirement_results
                if isinstance(results, str):
                    results = json.loads(results)

                # Extract requirements with scores
                if isinstance(results, dict):
                    # Format: {"validation": {"results": [...]}} or {"results": [...]}
                    validation_data = results.get("validation", results)
                    if isinstance(validation_data, dict):
                        req_list = validation_data.get("results", [])
                    else:
                        req_list = validation_data if isinstance(validation_data, list) else []

                    for req in req_list:
                        requirements.append({
                            "id": req.get("id", req.get("requirement_id", "REQ-???")),
                            "text": req.get("text", req.get("original_text", "")),
                            "score": req.get("score", req.get("overall_score", 0)),
                            "status": "passed" if req.get("score", 0) >= 0.7 else "failed",
                            "criteria": req.get("criteria", {})
                        })
                elif isinstance(results, list):
                    # Direct list of requirements
                    for req in results:
                        requirements.append({
                            "id": req.get("id", "REQ-???"),
                            "text": req.get("text", ""),
                            "score": req.get("score", 0),
                            "status": "passed" if req.get("score", 0) >= 0.7 else "failed"
                        })

            # If no requirements in shuttle, try to extract from bubble's whitepaper
            if not requirements and shuttle.bubble_id:
                requirements = await self._extract_requirements_from_bubble(shuttle.bubble_id)

            self.send_message({
                "type": "shuttle-requirements-loaded",
                "shuttle_id": shuttle_id,
                "requirements": requirements,
                "total": shuttle.total_count or len(requirements),
                "passed": shuttle.passed_count or sum(1 for r in requirements if r.get("status") == "passed"),
                "failed": shuttle.failed_count or sum(1 for r in requirements if r.get("status") == "failed"),
                "score": shuttle.score or 0,
                "current_stage": shuttle.current_stage or "mining"
            })

        except Exception as e:
            debug_log(f"Error getting shuttle requirements: {e}")
            import traceback
            debug_log(traceback.format_exc())
            self.send_message({
                "type": "shuttle-requirements-loaded",
                "shuttle_id": shuttle_id,
                "requirements": [],
                "error": str(e)
            })

    async def _extract_requirements_from_bubble(self, bubble_id: str) -> list:
        """Extract requirements from a bubble's whitepaper/feature nodes."""
        requirements = []

        try:
            if not self.canvas_repo:
                return requirements

            # Get all nodes for this bubble
            nodes = self.canvas_repo.list_nodes(limit=1000)
            bubble_nodes = [n for n in nodes if n.linked_idea_id == bubble_id]

            req_id = 1
            for node in bubble_nodes:
                # Extract from feature/note/whitepaper nodes
                if node.node_type in ("feature", "note", "whitepaper"):
                    content = node.content or node.title or ""
                    if content:
                        requirements.append({
                            "id": f"REQ-{req_id:03d}",
                            "text": content[:500],  # Truncate long content
                            "score": 0,  # Not yet evaluated
                            "status": "pending",
                            "source": node.node_type
                        })
                        req_id += 1

        except Exception as e:
            debug_log(f"Error extracting requirements from bubble: {e}")

        return requirements

    async def _handle_get_stage_shuttle_data(self, shuttle_id: str):
        """
        PHASE 13: Get stage-specific shuttle data.

        For stage shuttles, the data is stored in stage_data (JSON).
        This handler returns that data for the shuttle interior view.
        """
        if not shuttle_id:
            self.send_message({
                "type": "stage_shuttle_data",
                "error": "shuttle_id required"
            })
            return

        try:
            if not self.shuttles_repo:
                self.send_message({
                    "type": "stage_shuttle_data",
                    "shuttle_id": shuttle_id,
                    "error": "Database not available"
                })
                return

            # Get shuttle by visual shuttle_id
            shuttle = self.shuttles_repo.get_by_shuttle_id(shuttle_id)
            if not shuttle:
                self.send_message({
                    "type": "stage_shuttle_data",
                    "shuttle_id": shuttle_id,
                    "error": f"Shuttle {shuttle_id} not found"
                })
                return

            # Get stage_data (stored as JSON or dict)
            stage_data = shuttle.stage_data
            if isinstance(stage_data, str):
                stage_data = json.loads(stage_data)

            # Return the stage-specific data
            self.send_message({
                "type": "stage_shuttle_data",
                "shuttle_id": shuttle_id,
                "bubble_id": shuttle.bubble_id,
                "bubble_name": shuttle.bubble_name,
                "stage_type": shuttle.stage_type,
                "stage_data": stage_data or {},
                "score": shuttle.score or 0,
                "passed": shuttle.passed_count or 0,
                "failed": shuttle.failed_count or 0,
                "total": shuttle.total_count or 0,
                "status": shuttle.status
            })

            debug_log(f"Sent stage shuttle data for {shuttle_id} ({shuttle.stage_type})")

        except Exception as e:
            debug_log(f"Error getting stage shuttle data: {e}")
            import traceback
            debug_log(traceback.format_exc())
            self.send_message({
                "type": "stage_shuttle_data",
                "shuttle_id": shuttle_id,
                "error": str(e)
            })

    # ========================================================================
    # EXPLORATION IPC Handler Methods (AI-Scientist Tree Search)
    # ========================================================================

    async def _handle_exploration_start(self, bubble_id, depth, mode, context):
        """Handle exploration start from Electron."""
        try:
            from spaces.ideas.tools.exploration_tools import start_exploration
            result = await start_exploration(
                bubble_id=bubble_id,
                depth=depth,
                mode=mode,
                context=context,
            )
            self.send_message({
                "type": "exploration_started",
                **result
            })
        except Exception as e:
            logger.error(f"Exploration start error: {e}")
            self.send_message({
                "type": "exploration_error",
                "error": str(e)
            })

    async def _handle_exploration_stop(self):
        """Handle exploration stop."""
        try:
            from spaces.ideas.tools.exploration_tools import stop_exploration
            result = await stop_exploration()
            self.send_message({
                "type": "exploration_stopped",
                **result
            })
        except Exception as e:
            logger.error(f"Exploration stop error: {e}")
            self.send_message({
                "type": "exploration_error",
                "error": str(e)
            })

    async def _handle_exploration_respond(self, question_id, response_type, selected_option, custom_text):
        """Handle response to exploration question."""
        try:
            from spaces.ideas.tools.exploration_tools import respond_to_exploration_question
            result = await respond_to_exploration_question(
                question_id=question_id,
                response_type=response_type,
                selected_option=selected_option,
                custom_text=custom_text,
            )
            debug_log(f"Exploration response processed: {result}")
            # The exploration will continue automatically after response
        except Exception as e:
            logger.error(f"Exploration respond error: {e}")
            self.send_message({
                "type": "exploration_error",
                "error": str(e)
            })

    async def _handle_exploration_direction(self, direction, bubble_id):
        """Handle exploration direction setting."""
        try:
            from spaces.ideas.tools.exploration_tools import set_exploration_direction
            result = await set_exploration_direction(
                direction=direction,
                bubble_id=bubble_id,
            )
            self.send_message({
                "type": "exploration_direction_set",
                **result
            })
        except Exception as e:
            logger.error(f"Exploration direction error: {e}")
            self.send_message({
                "type": "exploration_error",
                "error": str(e)
            })

    async def _handle_exploration_status(self):
        """Get current exploration status."""
        try:
            from spaces.ideas.tools.exploration_tools import get_exploration_status
            result = await get_exploration_status()
            self.send_message({
                "type": "exploration_status",
                **result
            })
        except Exception as e:
            logger.error(f"Exploration status error: {e}")
            self.send_message({
                "type": "exploration_error",
                "error": str(e)
            })

    # ========================================================================
    # PROJECT PREVIEW (Coding Engine Integration)
    # ========================================================================

    async def _start_project_preview(self, project_id: str, project_path: str,
                                     enable_vnc: bool = True, vnc_resolution: str = "1280x720"):
        """Start a live preview for a project."""
        try:
            debug_log(f"Starting preview for {project_id}")
            
            # Check if already running
            if project_id in self.active_previews:
                existing = self.active_previews[project_id]
                if existing.get("status") == "running":
                    self.send_message({
                        "type": "project_preview_ready",
                        "projectId": project_id,
                        "vncUrl": existing.get("vnc_url"),
                        "status": "already_running"
                    })
                    return
            
            # Mark as starting
            self.active_previews[project_id] = {
                "status": "starting",
                "project_path": project_path
            }
            
            # Find available port
            import socket
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('', 0))
                vnc_port = s.getsockname()[1]
            
            # Build Docker command
            docker_cmd = [
                "docker", "run", "-d",
                "--name", f"preview-{project_id[:8]}",
                "-p", f"{vnc_port}:6080",
                "-v", f"{project_path}:/app",
                "-e", f"DISPLAY_RESOLUTION={vnc_resolution}",
                "sandbox-vnc:latest",
            ]
            
            process = subprocess.Popen(
                docker_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout, stderr = process.communicate(timeout=30)
            
            if process.returncode == 0:
                container_id = stdout.decode().strip()
                vnc_url = self._generate_vnc_url(project_id, vnc_port)
                
                self.active_previews[project_id] = {
                    "status": "running",
                    "vnc_url": vnc_url,
                    "vnc_port": vnc_port,
                    "container_id": container_id,
                    "project_path": project_path
                }
                
                await asyncio.sleep(3)
                
                self.send_message({
                    "type": "project_preview_ready",
                    "projectId": project_id,
                    "vncUrl": vnc_url
                })
            else:
                error = stderr.decode() or "Docker command failed"
                self.active_previews[project_id] = {"status": "error", "error": error}
                self.send_message({
                    "type": "project_preview_error",
                    "projectId": project_id,
                    "error": error
                })
                
        except Exception as e:
            debug_log(f"Error starting preview: {e}")
            self.active_previews[project_id] = {"status": "error", "error": str(e)}
            self.send_message({
                "type": "project_preview_error",
                "projectId": project_id,
                "error": str(e)
            })
    
    async def _stop_project_preview(self, project_id: str):
        """Stop a running project preview."""
        try:
            if project_id not in self.active_previews:
                return
                
            preview = self.active_previews[project_id]
            container_id = preview.get("container_id")
            
            if container_id:
                subprocess.run(["docker", "stop", container_id], capture_output=True, timeout=10)
                subprocess.run(["docker", "rm", container_id], capture_output=True, timeout=10)
                
            preview_name = f"preview-{project_id[:8]}"
            subprocess.run(["docker", "stop", preview_name], capture_output=True, timeout=10)
            subprocess.run(["docker", "rm", preview_name], capture_output=True, timeout=10)
            
            del self.active_previews[project_id]
            
            self.send_message({
                "type": "project_preview_stopped",
                "projectId": project_id
            })
            
        except Exception as e:
            debug_log(f"Error stopping preview: {e}")
            self.send_message({
                "type": "project_preview_error",
                "projectId": project_id,
                "error": f"Failed to stop: {str(e)}"
            })
    
    def _on_generation_status_update(self, job_id: str, status: str, progress: float, 
                                      phase: str = "", error: str = None):
        """Callback from CodingEngineRunner when generation status changes."""
        debug_log(f"Generation status update: job={job_id}, status={status}, progress={progress}")
        
        self.send_message({
            "type": "generation_status_update",
            "job_id": job_id,
            "status": status,
            "progress": progress,
            "phase": phase,
            "error": error
        })
        
        if status in ("completed", "failed"):
            self.send_message({
                "type": "generation_finished",
                "job_id": job_id,
                "success": status == "completed",
                "error": error
            })

    def _on_issue_detected(self, job_id: str, issue: dict):
        """Callback when a quality issue is detected during generation."""
        debug_log(f"Issue detected in job {job_id}: {issue.get('id', '?')} [{issue.get('severity', '?')}]")
        self.send_message({
            "type": "project_issue_detected",
            "job_id": job_id,
            "issue": {
                "id": issue.get("id", ""),
                "category": issue.get("category", ""),
                "severity": issue.get("severity", "medium"),
                "title": issue.get("title", ""),
                "description": issue.get("description", ""),
                "affected_artifacts": issue.get("affected_artifacts", []),
                "suggestion": issue.get("suggestion", ""),
                "auto_fixable": issue.get("auto_fixable", False),
            }
        })

    def _on_quality_summary_update(self, job_id: str, summary: dict):
        """Callback when quality summary is updated during generation."""
        debug_log(f"Quality summary update for job {job_id}: {summary.get('total_issues', 0)} issues")
        self.send_message({
            "type": "project_quality_update",
            "job_id": job_id,
            "summary": {
                "total_issues": summary.get("total_issues", 0),
                "by_severity": summary.get("by_severity", {}),
                "by_category": summary.get("by_category", {}),
                "auto_fixed": summary.get("auto_fixed", 0),
            }
        })


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
        asyncio.create_task(backend.start_voice())

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
            await asyncio.wait_for(backend.cleanup(), timeout=12.0)
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
