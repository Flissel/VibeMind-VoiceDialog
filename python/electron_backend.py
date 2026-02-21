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
        print(f"[Python DEBUG] .env loaded: FORCE_SYNC_MODE={force_sync}, USE_VOICE_BRIDGE_V2={use_v2}", file=sys.stderr)
except ImportError:
    print("[Python DEBUG] dotenv not installed, using system env vars", file=sys.stderr)

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

def debug_log(msg: str):
    """Log debug message to stderr (visible in Electron terminal)."""
    if DEBUG:
        print(f"[Python DEBUG] {msg}", file=sys.stderr, flush=True)


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
# Suppress logging to stderr (would interfere with Electron)
logging.basicConfig(level=logging.WARNING, stream=sys.stderr)
logger = logging.getLogger(__name__)

# Try to import voice dialog components
try:
    from elevenlabs_voice_dialog import VoiceDialog
    HAS_VOICE = True
except ImportError:
    HAS_VOICE = False
    logger.warning("Voice dialog not available")

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

# Try to import full voice tools setup
try:
    from voice_dialog_main import setup_tools_manager
    from elevenlabs.client import ElevenLabs
    from elevenlabs.conversational_ai.conversation import Conversation
    from elevenlabs.conversational_ai.default_audio_interface import DefaultAudioInterface
    HAS_VOICE_TOOLS = True
except ImportError as e:
    HAS_VOICE_TOOLS = False
    logger.warning(f"Full voice tools not available: {e}")

# Try to import transfer handler
try:
    from tools.transfer_handler import init_transfer_handler, get_transfer_handler
    from tools.bubble_tools import get_pending_agent_switch
    HAS_TRANSFER_HANDLER = True
except ImportError as e:
    HAS_TRANSFER_HANDLER = False
    init_transfer_handler = None
    get_pending_agent_switch = None
    logger.warning(f"Transfer handler not available: {e}")

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
    from tools.coding_tools import set_electron_sender as set_coding_sender, set_coding_engine_runner
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

# Environment flag for VoiceBridgeV2 opt-in
USE_VOICE_BRIDGE_V2 = os.environ.get("USE_VOICE_BRIDGE_V2", "false").lower() == "true"


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
        self.voice_dialog: Optional[VoiceDialog] = None
        self.voice_active = False

        # Full voice tools support (for Electron IPC integration)
        self.voice_conversation = None  # ElevenLabs Conversation object
        self.tools_manager = None       # ClientToolsManager with all registered tools
        self.elevenlabs_client = None   # ElevenLabs API client
        self.audio_interface = None     # Audio interface for voice
        self.transfer_handler = None    # Agent transfer handler

        # VoiceBridgeV2 (new async architecture with NotificationQueue)
        self.voice_bridge = None  # VoiceBridgeV2 instance when USE_VOICE_BRIDGE_V2=true
        
        # Project Preview State (Coding Engine Integration)
        self.active_previews: Dict[str, Dict] = {}  # project_id -> preview_info
        self.coding_engine_path = os.environ.get(
            'CODING_ENGINE_PATH', 
            str(Path(__file__).parent.parent.parent / 'Coding_engine')
        )
        debug_log(f"Coding Engine path: {self.coding_engine_path}")
        
        # Coding Engine Runner for code generation
        self.coding_engine_runner = None
        if HAS_CODING_ENGINE:
            try:
                self.coding_engine_runner = CodingEngineRunner(
                    coding_engine_path=self.coding_engine_path,
                    on_status_update=self._on_generation_status_update,
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

        # Load bubbles from database
        self._load_bubbles_from_db()
        
        debug_log(f"ElectronBackend initialized with {len(self.bubbles)} bubbles")

        # No default bubbles - bubbles are created via voice commands
        # and stored in the database

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

        # Pre-warm voice components in background to speed up "Start Voice"
        # Only pre-warms synchronous operations (ElevenLabs client, audio interface)
        # VoiceBridgeV2 is async and created when voice starts
        def _prewarm_voice_components():
            try:
                api_key = os.getenv("ELEVENLABS_API_KEY")
                if not api_key:
                    debug_log("No ELEVENLABS_API_KEY - skipping voice pre-warm")
                    return

                # 1. Pre-create ElevenLabs client (slow network auth)
                if HAS_VOICE_TOOLS:
                    debug_log("Pre-warming ElevenLabs client...")
                    from elevenlabs.client import ElevenLabs
                    self.elevenlabs_client = ElevenLabs(api_key=api_key)
                    debug_log("ElevenLabs client pre-warmed")

                    # 2. Audio interface: skip pre-warm, just pre-import pyaudio
                    # DefaultAudioInterface.__init__ only does `import pyaudio`, so
                    # pre-warming it adds no benefit. Creating it fresh avoids potential
                    # cross-thread PortAudio issues on Windows.
                    try:
                        import pyaudio  # noqa: pre-import to cache module
                        debug_log("PyAudio module pre-imported")
                    except ImportError:
                        debug_log("PyAudio not installed")

                    # 3. Pre-initialize tools manager
                    debug_log("Pre-warming tools manager...")
                    self.tools_manager = setup_tools_manager()
                    debug_log("Tools manager pre-warmed")

            except Exception as e:
                debug_log(f"Voice pre-warm failed (will init on first use): {e}")
        threading.Thread(target=_prewarm_voice_components, daemon=True, name="voice-prewarm").start()

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
            print(f"[Python] Loaded {len(ideas)} bubbles from database", file=sys.stderr)

        except Exception as e:
            logger.warning(f"Failed to load bubbles from database: {e}")
            print(f"[Python] Failed to load bubbles: {e}", file=sys.stderr)

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
        """Start voice dialog session with full tool integration."""
        debug_log("start_voice() called")
        debug_log(f"HAS_VOICE_TOOLS: {HAS_VOICE_TOOLS}")
        debug_log(f"HAS_VOICE: {HAS_VOICE}")
        
        # Get agent ID from environment
        agent_id = os.getenv("AGENT_MULTIVERSE") or os.getenv("ELEVENLABS_AGENT_ID")
        if not agent_id:
            debug_log("ERROR: No agent ID configured")
            self.send_message({
                "type": "voice_error",
                "error": "No agent ID configured (AGENT_MULTIVERSE or ELEVENLABS_AGENT_ID)"
            })
            return
        
        await self.start_voice_with_agent(agent_id)
    
    async def start_voice_with_agent(self, agent_id: str):
        """Start voice dialog with a specific agent ID."""
        debug_log(f"start_voice_with_agent({agent_id})")

        # Option A: VoiceBridgeV2 (new async architecture with NotificationQueue)
        if USE_VOICE_BRIDGE_V2 and HAS_VOICE_BRIDGE_V2:
            debug_log("Using VoiceBridgeV2 mode (USE_VOICE_BRIDGE_V2=true)")
            await self._start_voice_bridge_v2(agent_id)
            return

        # Option B: Legacy - full voice tools setup (connects to Electron IPC)
        if HAS_VOICE_TOOLS:
            try:
                # Get API key
                api_key = os.getenv("ELEVENLABS_API_KEY")
                
                debug_log(f"API Key present: {bool(api_key)}")
                debug_log(f"Agent ID: {agent_id[:20] if agent_id else 'None'}...")
                
                if not api_key:
                    debug_log("ERROR: ELEVENLABS_API_KEY not set")
                    self.send_message({
                        "type": "voice_error",
                        "error": "ELEVENLABS_API_KEY not set"
                    })
                    return
                
                # Initialize tools manager (use pre-warmed if available)
                if not self.tools_manager:
                    debug_log("Initializing tools manager...")
                    self.tools_manager = setup_tools_manager()
                    debug_log(f"Tools manager initialized: {self.tools_manager}")
                else:
                    debug_log("Using pre-warmed tools manager")
                logger.info("Voice tools manager ready")

                # Create ElevenLabs client (use pre-warmed if available)
                if not self.elevenlabs_client:
                    debug_log("Creating ElevenLabs client...")
                    self.elevenlabs_client = ElevenLabs(api_key=api_key)
                    debug_log("ElevenLabs client created")
                else:
                    debug_log("Using pre-warmed ElevenLabs client")

                # Create audio interface (use pre-warmed if available)
                if not self.audio_interface:
                    debug_log("Creating audio interface...")
                    self.audio_interface = DefaultAudioInterface()
                    debug_log("Audio interface created")
                else:
                    debug_log("Using pre-warmed audio interface")
                
                # Create conversation with full tool support
                debug_log("Creating conversation...")
                self.voice_conversation = Conversation(
                    client=self.elevenlabs_client,
                    agent_id=agent_id,
                    requires_auth=False,
                    audio_interface=self.audio_interface,
                    client_tools=self.tools_manager.get_client_tools(),
                    callback_user_transcript=self._handle_user_transcript,
                    callback_agent_response=self._handle_agent_response,
                )
                debug_log("Conversation created")
                
                # Initialize transfer handler if available
                if HAS_TRANSFER_HANDLER and not self.transfer_handler:
                    debug_log("Initializing transfer handler...")
                    self.transfer_handler = init_transfer_handler(
                        get_pending_switch=get_pending_agent_switch,
                        end_session=self._end_voice_session_sync,
                        start_session=self._start_voice_session_sync,
                        send_to_electron=self.send_message
                    )
                    self.transfer_handler.start(agent_id)
                    debug_log("Transfer handler started")
                
                # Start conversation in a background thread (it blocks)
                def run_voice_session():
                    try:
                        debug_log("Voice session thread starting...")
                        self.voice_conversation.start_session()
                        debug_log("Voice session started, waiting for end...")
                        conversation_id = self.voice_conversation.wait_for_session_end()
                        debug_log(f"Voice session ended: {conversation_id}")
                        logger.info(f"Voice session ended: {conversation_id}")
                        self.voice_active = False
                        self.send_message({"type": "voice_stopped"})
                    except Exception as e:
                        debug_log(f"Voice session error: {e}")
                        logger.error(f"Voice session error: {e}")
                        self.voice_active = False
                        self.send_message({
                            "type": "voice_error",
                            "error": str(e)
                        })
                
                debug_log("Starting voice thread...")
                voice_thread = threading.Thread(target=run_voice_session, daemon=True)
                voice_thread.start()
                debug_log("Voice thread started")
                
                self.voice_active = True
                
                # Get agent name for UI
                agent_name = "Rachel"  # Default
                if self.transfer_handler:
                    agent_name = self.transfer_handler.get_agent_name(agent_id)
                    
                self.send_message({
                    "type": "voice_started",
                    "agent_id": agent_id,
                    "agent_name": agent_name
                })
                debug_log(f"Voice started with {agent_name}")
                logger.info(f"Voice session started with {agent_name}")
                
            except Exception as e:
                debug_log(f"Failed to start voice with tools: {e}")
                import traceback
                debug_log(traceback.format_exc())
                logger.error(f"Failed to start voice with tools: {e}")
                self.send_message({
                    "type": "voice_error",
                    "error": str(e)
                })
                return

        # Fallback to basic voice dialog (no tool integration)
        elif HAS_VOICE:
            try:
                self.voice_dialog = VoiceDialog(
                    agent_id=agent_id,
                    on_user_transcript=self._handle_user_transcript,
                    on_agent_response=self._handle_agent_response
                )
                await self.voice_dialog.start_conversation()
                self.voice_active = True
                self.send_message({"type": "voice_started"})
            except Exception as e:
                self.send_message({
                    "type": "voice_error",
                    "error": str(e)
                })
        else:
            self.send_message({
                "type": "voice_error",
                "error": "Voice dialog not available"
            })

    async def _start_voice_bridge_v2(self, agent_id: str):
        """
        Start voice with VoiceBridgeV2 architecture.

        This uses the new async architecture with:
        - Rachel as pure voice interface (only send_intent tool)
        - NotificationQueue for deferred feedback
        - Backend agents for async tool execution
        """
        try:
            import time as _time
            _t_total = _time.time()
            debug_log("Initializing VoiceBridgeV2...")

            # 1. Create VoiceBridge (6-step init: model client, queue, orchestrator, rachel, tts, agents)
            _t0 = _time.time()
            self.voice_bridge = await create_voice_bridge_v2(
                model_client=None,  # Auto-detect Cloud/Ollama
                event_manager=None  # Optional Redis
            )
            debug_log(f"VoiceBridgeV2 created ({_time.time() - _t0:.2f}s)")

            # 2. Get API key for ElevenLabs
            api_key = os.getenv("ELEVENLABS_API_KEY")
            if not api_key:
                debug_log("ERROR: ELEVENLABS_API_KEY not set")
                self.send_message({
                    "type": "voice_error",
                    "error": "ELEVENLABS_API_KEY not set"
                })
                return

            # 3. Create ElevenLabs client and audio interface (use pre-warmed if available)
            _t0 = _time.time()
            if not self.elevenlabs_client:
                debug_log("Creating ElevenLabs client...")
                self.elevenlabs_client = ElevenLabs(api_key=api_key)
            else:
                debug_log("Using pre-warmed ElevenLabs client")

            if not self.audio_interface:
                debug_log("Creating audio interface...")
                self.audio_interface = DefaultAudioInterface()
            else:
                debug_log("Using pre-warmed audio interface")
            debug_log(f"Client + audio ready ({_time.time() - _t0:.2f}s)")

            # 4. Create conversation with bridge tools
            _t0 = _time.time()
            bridge_tools = self._create_bridge_tools()
            debug_log(f"Bridge tools created ({_time.time() - _t0:.2f}s)")

            _t0 = _time.time()
            debug_log("Creating ElevenLabs Conversation object...")

            # run_in_executor doesn't work on Windows ProactorEventLoop.
            # Use a direct thread with call_soon_threadsafe instead.
            loop = asyncio.get_event_loop()
            conv_future = loop.create_future()

            def _create_conversation_thread():
                debug_log(f"[Conv] Thread started ({threading.current_thread().name})")
                try:
                    conv = Conversation(
                        client=self.elevenlabs_client,
                        agent_id=agent_id,
                        requires_auth=False,
                        audio_interface=self.audio_interface,
                        client_tools=bridge_tools,
                        callback_user_transcript=self._handle_user_transcript,
                        callback_agent_response=self._handle_agent_response,
                    )
                    debug_log("[Conv] Conversation() OK")
                    loop.call_soon_threadsafe(conv_future.set_result, conv)
                except Exception as e:
                    debug_log(f"[Conv] Conversation() FAILED: {e}")
                    loop.call_soon_threadsafe(conv_future.set_exception, e)

            t = threading.Thread(target=_create_conversation_thread, daemon=True, name="conv-init")
            t.start()
            debug_log("[Conv] Thread launched, awaiting result...")
            self.voice_conversation = await conv_future
            debug_log(f"Conversation object created ({_time.time() - _t0:.2f}s)")

            # 5. Start conversation thread (WebSocket connects in background)
            def run_voice_session():
                try:
                    _t_ws = _time.time()
                    debug_log("Connecting to ElevenLabs WebSocket...")
                    self.voice_conversation.start_session()
                    debug_log(f"WebSocket session started ({_time.time() - _t_ws:.2f}s), waiting for end...")
                    conversation_id = self.voice_conversation.wait_for_session_end()
                    debug_log(f"VoiceBridgeV2 session ended: {conversation_id}")
                    self.voice_active = False
                    self.send_message({"type": "voice_stopped"})
                except Exception as e:
                    debug_log(f"VoiceBridgeV2 session error: {e}")
                    self.voice_active = False
                    self.send_message({
                        "type": "voice_error",
                        "error": str(e)
                    })

            voice_thread = threading.Thread(target=run_voice_session, daemon=True)
            voice_thread.start()

            self.voice_active = True
            self.send_message({
                "type": "voice_started",
                "agent_id": agent_id,
                "agent_name": "Rachel",
                "mode": "voice_bridge_v2"
            })

            debug_log(f"VoiceBridgeV2 started successfully (total: {_time.time() - _t_total:.2f}s)")

        except Exception as e:
            debug_log(f"VoiceBridgeV2 start failed: {e}")
            import traceback
            debug_log(traceback.format_exc())
            self.send_message({
                "type": "voice_error",
                "error": str(e)
            })

    def _create_bridge_tools(self):
        """
        Create ClientTools with 5 domain-specific tools.

        Returns a ClientTools instance with domain tools:
        - send_bubbles_intent: Space/bubble navigation
        - send_ideas_intent: Idea management
        - send_desktop_intent: Desktop automation
        - send_coding_intent: Code generation
        - send_shuttles_intent: Requirements pipeline
        """
        from elevenlabs.conversational_ai.conversation import ClientTools

        backend = self  # Capture reference for closure
        client_tools = ClientTools()

        def _create_domain_handler(domain: str):
            """Factory to create domain-specific intent handlers."""
            def handler(params: dict) -> str:
                """
                Send domain-specific intent to the orchestrator.

                The domain_hint enables optimized routing to the correct
                backend agent (BubblesAgent, IdeasAgent, etc.).
                """
                import time as _time
                # Accept both 'command' and 'user_request' for backwards compat
                user_request = params.get("command") or params.get("user_request", "")

                # Debug logging
                debug_log(f"[VOICE INPUT] [{domain.upper()}] {user_request}")

                if not user_request:
                    domain_prompts = {
                        "bubbles": "Was moechtest du mit deinen Spaces machen?",
                        "ideas": "Was moechtest du mit deinen Ideen machen?",
                        "desktop": "Was soll ich auf dem Desktop machen?",
                        "coding": "Was soll ich programmieren?",
                        "shuttles": "Was moechtest du mit dem Shuttle machen?",
                    }
                    return domain_prompts.get(domain, "Ich habe dich nicht verstanden.")

                try:
                    # Get orchestrator and context store
                    from swarm.orchestrator import get_orchestrator
                    from swarm.orchestrator.system_context_store import get_system_context_store

                    orchestrator = get_orchestrator()
                    context_store = get_system_context_store()

                    # Process intent with domain hint for optimized routing
                    result = orchestrator.process_intent_sync(user_request, domain_hint=domain)

                    debug_log(f"send_{domain}_intent: {result.event_type} -> {result.response_hint[:200]}{'...' if len(result.response_hint) > 200 else ''}")

                    # Store result for context (Smart Rachel)
                    if not result.is_conversational and not result.error:
                        context_store.store(
                            event_type=result.event_type,
                            result=result.response_hint
                        )

                    # Notify Electron if task was queued
                    if not result.is_conversational:
                        backend.send_message({
                            "type": "task_queued",
                            "task_type": "backend_agent",
                            "domain": domain
                        })

                    if result.error:
                        return f"Es gab ein Problem: {result.error}"

                    # Enrich response with relevant context
                    response = result.response_hint
                    if not result.is_conversational:
                        relevant = context_store.get_relevant(user_request, limit=2)
                        context_texts = []
                        for entry in relevant:
                            if entry.result == result.response_hint:
                                continue
                            if _time.time() - entry.timestamp > 120:
                                continue
                            context_texts.append(entry.result)

                        if context_texts:
                            response = f"{result.response_hint} Ausserdem: {'. '.join(context_texts)}"

                    return response

                except Exception as e:
                    debug_log(f"send_{domain}_intent error: {e}")
                    import traceback
                    traceback.print_exc()
                    return f"Es gab ein Problem bei der Verarbeitung: {str(e)}"

            return handler

        # Register all 5 domain-specific tools
        domains = ["bubbles", "ideas", "desktop", "coding", "shuttles"]
        for domain in domains:
            tool_name = f"send_{domain}_intent"
            handler = _create_domain_handler(domain)
            client_tools.register(tool_name, handler, is_async=False)
            debug_log(f"Registered tool: {tool_name}")

        return client_tools

    def _end_voice_session_sync(self):
        """Synchronously end the current voice session (for transfer handler)."""
        if self.voice_conversation:
            try:
                self.voice_conversation.end_session()
                debug_log("Voice session ended by transfer handler")
            except Exception as e:
                debug_log(f"Error ending session: {e}")
            self.voice_conversation = None
        self.voice_active = False

    def _start_voice_session_sync(self, agent_id: str = None):
        """Synchronously start a new voice session (for transfer handler)."""
        import asyncio
        
        # Use provided agent_id or fall back to default
        if not agent_id:
            agent_id = os.getenv("AGENT_MULTIVERSE") or os.getenv("ELEVENLABS_AGENT_ID")
        
        if not agent_id:
            debug_log("ERROR: No agent ID for session start")
            return
        
        debug_log(f"_start_voice_session_sync called with agent_id: {agent_id[:20]}...")
        
        # Create new event loop if needed
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        # Start the voice session
        if loop.is_running():
            # Schedule in running loop
            asyncio.ensure_future(self.start_voice_with_agent(agent_id))
        else:
            # Run directly
            loop.run_until_complete(self.start_voice_with_agent(agent_id))

    async def stop_voice(self):
        """Stop voice dialog session."""
        # Stop transfer handler
        if self.transfer_handler:
            self.transfer_handler.stop()
            self.transfer_handler = None

        # Stop VoiceBridgeV2 if active
        if self.voice_bridge:
            try:
                await self.voice_bridge.shutdown()
                debug_log("VoiceBridgeV2 shutdown complete")
            except Exception as e:
                debug_log(f"Error shutting down VoiceBridgeV2: {e}")
            self.voice_bridge = None

        # Stop new conversation-based voice (with tools)
        if self.voice_conversation:
            try:
                self.voice_conversation.end_session()
            except Exception as e:
                logger.warning(f"Error ending voice session: {e}")
            self.voice_conversation = None

        # Stop legacy voice dialog
        if self.voice_dialog:
            await self.voice_dialog.end_conversation()
            self.voice_dialog = None

        self.voice_active = False
        self.send_message({"type": "voice_stopped"})

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
            asyncio.create_task(self.start_voice())

        elif msg_type == "stop_voice":
            asyncio.create_task(self.stop_voice())

        elif msg_type == "toggle_voice":
            if self.voice_active:
                asyncio.create_task(self.stop_voice())
            else:
                asyncio.create_task(self.start_voice())

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
            asyncio.create_task(self._start_project_preview(
                project_id, project_path, enable_vnc, vnc_resolution
            ))
        
        elif msg_type == "stop_project_preview":
            project_id = message.get("project_id")
            debug_log(f"Stopping project preview: {project_id}")
            asyncio.create_task(self._stop_project_preview(project_id))

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
            asyncio.create_task(self._handle_get_generated_projects(message))
        
        elif msg_type == "get_generation_status":
            asyncio.create_task(self._handle_get_generation_status(message))
        
        elif msg_type == "start_code_generation":
            asyncio.create_task(self._handle_start_code_generation(message))
        
        elif msg_type == "cancel_code_generation":
            asyncio.create_task(self._handle_cancel_code_generation(message))
        
        elif msg_type == "enter_projects_space":
            asyncio.create_task(self._handle_enter_projects_space(message))
        
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
            if action == "transfer_to_alice":
                try:
                    from tools.bubble_tools import transfer_to_alice
                    transfer_to_alice({
                        "context": "User clicked 'Navigate with Alice' on a requirement shuttle"
                    })
                except Exception as e:
                    logger.error(f"Failed to transfer to Alice: {e}")

        elif msg_type == "get_shuttles":
            # Return active shuttles for visualization restoration
            shuttles_data = self.get_active_shuttles()
            debug_log(f"Sending {len(shuttles_data)} shuttles")
            self.send_message({
                "type": "shuttles_sync",
                "shuttles": shuttles_data
            })

        elif msg_type == "get_shuttle_requirements":
            # Get requirements data for shuttle interior view
            shuttle_id = message.get("shuttle_id")
            debug_log(f"Getting requirements for shuttle: {shuttle_id}")
            asyncio.create_task(self._handle_get_shuttle_requirements(shuttle_id))

        elif msg_type == "get_stage_shuttle_data":
            # PHASE 13: Get stage-specific shuttle data
            shuttle_id = message.get("shuttle_id")
            debug_log(f"Getting stage shuttle data: {shuttle_id}")
            asyncio.create_task(self._handle_get_stage_shuttle_data(shuttle_id))

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
            asyncio.create_task(self._handle_exploration_start(bubble_id, depth, mode, context))

        elif msg_type == "exploration_stop":
            # Stop exploration
            debug_log("Stopping exploration")
            asyncio.create_task(self._handle_exploration_stop())

        elif msg_type == "exploration_respond":
            # Handle response to exploration question
            question_id = message.get("question_id")
            response_type = message.get("response_type")
            selected_option = message.get("selected_option")
            custom_text = message.get("custom_text")
            debug_log(f"Exploration response: {response_type} for question {question_id}")
            asyncio.create_task(self._handle_exploration_respond(
                question_id, response_type, selected_option, custom_text
            ))

        elif msg_type == "exploration_direction":
            # Set exploration direction (guided mode)
            direction = message.get("direction")
            bubble_id = message.get("bubble_id")
            debug_log(f"Setting exploration direction: {direction}")
            asyncio.create_task(self._handle_exploration_direction(direction, bubble_id))

        elif msg_type == "exploration_status":
            # Get exploration status
            asyncio.create_task(self._handle_exploration_status())

        # ====================================================================
        # UI TOOLBAR - Direct Tool Execution (user clicks tool in sidebar)
        # ====================================================================

        elif msg_type == "tool_action":
            event_type = message.get("event_type")
            payload = message.get("payload", {})
            debug_log(f"Tool action from UI toolbar: {event_type} with {payload}")
            asyncio.create_task(self._handle_tool_action(event_type, payload))

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
    # PROJECTS SPACE IPC Handlers
    # ========================================================================

    async def _handle_get_generated_projects(self, message: dict):
        """Get list of all projects - both code-generated and shuttle-created."""
        try:
            repo = ProjectsRepository()
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
            from swarm.tools.exploration_tools import start_exploration
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
            from swarm.tools.exploration_tools import stop_exploration
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
            from swarm.tools.exploration_tools import respond_to_exploration_question
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
            from swarm.tools.exploration_tools import set_exploration_direction
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
            from swarm.tools.exploration_tools import get_exploration_status
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
        # Graceful shutdown - prevent Windows asyncio errors
        debug_log("Performing graceful shutdown...")

        # Force reset EventBus to close Redis connections cleanly
        try:
            from swarm.event_bus import force_reset_event_bus
            force_reset_event_bus()
            debug_log("EventBus reset complete")
        except Exception as e:
            debug_log(f"EventBus reset error (ignored): {e}")

        # Cancel any pending asyncio tasks
        pending_tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        if pending_tasks:
            debug_log(f"Cancelling {len(pending_tasks)} pending tasks...")
            for task in pending_tasks:
                task.cancel()
            # Wait briefly for tasks to finish
            await asyncio.gather(*pending_tasks, return_exceptions=True)
            debug_log("All tasks cancelled")

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
