"""
Space Logger - Per-space colored logging for VibeMind.

Adds colored [TAG] prefixes to log output based on which space generated the message.
Auto-detects space from module path (__name__), no changes needed in existing code.

Usage:
    # Call once at startup (e.g., in electron_backend.py)
    from swarm.logging.space_logger import setup_space_logging
    setup_space_logging()

    # All existing logging.getLogger(__name__) calls automatically get colored output.

Environment Variables:
    SPACE_LOG_LEVEL  - Log level for space output (default: INFO)
    SPACE_LOG_FILES  - "true" to enable per-space log files in logs/spaces/
    NO_COLOR         - Set to any value to disable ANSI colors
"""

import json
import os
import sys
import logging
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Optional, Dict


# =============================================================================
# ANSI Color Codes
# =============================================================================

class SpaceColors:
    """ANSI escape codes for each space domain."""
    BUBBLES = "\033[96m"       # Bright Cyan
    IDEAS = "\033[92m"         # Bright Green
    CODING = "\033[93m"        # Bright Yellow
    DESKTOP = "\033[95m"       # Bright Magenta
    ROWBOAT = "\033[94m"       # Blue
    RESEARCH = "\033[91m"      # Red
    MINIBOOK = "\033[97m"      # White Bold
    SCHEDULE = "\033[36m"      # Cyan
    VOICE = "\033[33m"         # Dark Yellow
    ORCHESTRATOR = "\033[35m"  # Dark Magenta
    BRAIN = "\033[32m"         # Dark Green
    AGENTFARM = "\033[38;5;208m"  # Orange (distinct from all other spaces)
    N8N = "\033[38;5;99m"      # Purple
    DEFAULT = "\033[2m"        # Dim
    RESET = "\033[0m"

    # Level colors (applied to the level name)
    LEVEL_DEBUG = "\033[2m"    # Dim
    LEVEL_INFO = ""            # Default
    LEVEL_WARNING = "\033[93m" # Yellow
    LEVEL_ERROR = "\033[91m"   # Red
    LEVEL_CRITICAL = "\033[91;1m"  # Bold Red


# =============================================================================
# Space Detection
# =============================================================================

# Module path fragment -> space name (longest match wins)
MODULE_TO_SPACE: Dict[str, str] = {
    "spaces.ideas.agents.bubbles": "bubbles",
    "spaces.ideas": "ideas",
    "spaces.coding": "coding",
    "spaces.desktop": "desktop",
    "eyeterm": "desktop",
    "spaces.rowboat": "rowboat",
    "spaces.research": "research",
    "spaces.minibook": "minibook",
    "spaces.schedule": "schedule",
    "spaces.autogen": "agentfarm",
    "spaces.n8n": "n8n",
    "voice": "voice",
    "swarm.orchestrator": "orchestrator",
    "brain": "brain",
    # AutoGen library loggers → agentfarm/n8n
    "autogen_agentchat": "agentfarm",
    "autogen_core": "agentfarm",
    "autogen_ext": "agentfarm",
    # n8n Society agents
    "n8n.society": "n8n",
    "society": "n8n",
    # Publishing → rowboat
    "publishing": "rowboat",
    # IPC handlers → associated spaces
    "ipc.canvas_manager": "ideas",
    "ipc.eyeterm_handlers": "desktop",
    "ipc.project_manager": "coding",
    "ipc.n8n_handlers": "n8n",
    "ipc.exploration_handlers": "ideas",
    "ipc.shuttle_handlers": "ideas",
    "ipc.voice_manager": "voice",
}

# Sorted by key length descending for longest-prefix matching
_SORTED_PATTERNS = sorted(MODULE_TO_SPACE.items(), key=lambda x: len(x[0]), reverse=True)

SPACE_TO_COLOR: Dict[str, str] = {
    "bubbles": SpaceColors.BUBBLES,
    "ideas": SpaceColors.IDEAS,
    "coding": SpaceColors.CODING,
    "desktop": SpaceColors.DESKTOP,
    "rowboat": SpaceColors.ROWBOAT,
    "research": SpaceColors.RESEARCH,
    "minibook": SpaceColors.MINIBOOK,
    "schedule": SpaceColors.SCHEDULE,
    "voice": SpaceColors.VOICE,
    "orchestrator": SpaceColors.ORCHESTRATOR,
    "brain": SpaceColors.BRAIN,
    "agentfarm": SpaceColors.AGENTFARM,
    "n8n": SpaceColors.N8N,
}

SPACE_TO_TAG: Dict[str, str] = {
    "bubbles": "[BUBBLES]",
    "ideas": "[IDEAS]",
    "coding": "[CODING]",
    "desktop": "[DESKTOP]",
    "rowboat": "[ROWBOAT]",
    "research": "[RESEARCH]",
    "minibook": "[MINIBOOK]",
    "schedule": "[SCHEDULE]",
    "voice": "[VOICE]",
    "orchestrator": "[ORCH]",
    "brain": "[BRAIN]",
    "agentfarm": "[AGENTFARM]",
    "n8n": "[N8N]",
}

# Pad all tags to same width for aligned output
_MAX_TAG_LEN = max(len(t) for t in SPACE_TO_TAG.values())
SPACE_TO_TAG_PADDED: Dict[str, str] = {
    k: v.ljust(_MAX_TAG_LEN) for k, v in SPACE_TO_TAG.items()
}
_DEFAULT_TAG_PADDED = "[SYSTEM]".ljust(_MAX_TAG_LEN)


@lru_cache(maxsize=256)
def _detect_space(logger_name: str) -> str:
    """
    Detect space from a logger name (typically __name__).

    Uses longest-prefix matching against MODULE_TO_SPACE.
    Results are cached for O(1) repeat lookups.
    """
    for pattern, space in _SORTED_PATTERNS:
        if pattern in logger_name:
            return space
    return "system"


# =============================================================================
# Formatter
# =============================================================================

# Short level names for compact output
_LEVEL_SHORT = {
    "DEBUG": "DEBUG",
    "INFO": "INFO ",
    "WARNING": "WARN ",
    "ERROR": "ERROR",
    "CRITICAL": "CRIT ",
}

_LEVEL_COLOR = {
    "DEBUG": SpaceColors.LEVEL_DEBUG,
    "INFO": SpaceColors.LEVEL_INFO,
    "WARNING": SpaceColors.LEVEL_WARNING,
    "ERROR": SpaceColors.LEVEL_ERROR,
    "CRITICAL": SpaceColors.LEVEL_CRITICAL,
}


class SpaceColorFormatter(logging.Formatter):
    """
    Logging formatter that prepends colored [SPACE] tags.

    Auto-detects space from record.name (module __name__).
    Also supports explicit tagging via record.space extra attribute.
    """

    def __init__(self, use_color: bool = True):
        super().__init__()
        self.use_color = use_color

    def format(self, record: logging.LogRecord) -> str:
        # Detect space: explicit extra > auto-detect from module name
        space = getattr(record, "space", None) or _detect_space(record.name)

        tag = SPACE_TO_TAG_PADDED.get(space, _DEFAULT_TAG_PADDED)
        color = SPACE_TO_COLOR.get(space, SpaceColors.DEFAULT)
        level_name = _LEVEL_SHORT.get(record.levelname, record.levelname)
        level_color = _LEVEL_COLOR.get(record.levelname, "")
        timestamp = datetime.fromtimestamp(record.created).strftime("%H:%M:%S")

        message = record.getMessage()

        if self.use_color:
            try:
                return (
                    f"{color}{tag}{SpaceColors.RESET} "
                    f"{level_color}{level_name}{SpaceColors.RESET} "
                    f"[{timestamp}] {message}"
                )
            except UnicodeEncodeError:
                safe_msg = message.encode("ascii", "replace").decode("ascii")
                return f"{tag} {level_name} [{timestamp}] {safe_msg}"
        else:
            return f"{tag} {level_name} [{timestamp}] {message}"


class SpaceJsonFormatter(logging.Formatter):
    """JSON log lines for Electron DevTools consumption.

    Emits one JSON object per log line on stderr. Electron's main.js parses
    these and renders them with CSS-styled console.log(%c...) calls.

    Automatically selected when stderr is piped (i.e., spawned by Electron).
    """

    def format(self, record: logging.LogRecord) -> str:
        space = getattr(record, "space", None) or _detect_space(record.name)
        ts = datetime.fromtimestamp(record.created).strftime("%H:%M:%S.%f")[:-3]
        msg = record.getMessage()
        if record.exc_info and not record.exc_text:
            record.exc_text = self.formatException(record.exc_info)
        if record.exc_text:
            msg = msg + "\n" + record.exc_text
        return json.dumps(
            {"log": True, "s": space, "l": record.levelname, "t": ts, "m": msg, "n": record.name},
            ensure_ascii=False,
        )


# =============================================================================
# Per-Space File Handlers (optional)
# =============================================================================

class SpaceFileFilter(logging.Filter):
    """Filter that only passes records matching a specific space."""

    def __init__(self, space: str):
        super().__init__()
        self.space = space

    def filter(self, record: logging.LogRecord) -> bool:
        detected = getattr(record, "space", None) or _detect_space(record.name)
        return detected == self.space


def _setup_space_file_handlers(log_dir: str, level: str):
    """Create per-space file handlers under log_dir."""
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    today = datetime.now().strftime("%Y-%m-%d")
    file_formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s")
    log_level = getattr(logging, level.upper(), logging.INFO)

    all_spaces = list(SPACE_TO_TAG.keys()) + ["system"]
    root = logging.getLogger()

    for space in all_spaces:
        handler = logging.FileHandler(
            log_path / f"{space}_{today}.log",
            encoding="utf-8",
        )
        handler.setLevel(log_level)
        handler.setFormatter(file_formatter)
        handler.addFilter(SpaceFileFilter(space))
        root.addHandler(handler)


# =============================================================================
# Windows ANSI Support
# =============================================================================

def _enable_windows_ansi():
    """Enable VT100 ANSI escape codes on Windows 10+."""
    if os.name != "nt":
        return
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        # STD_ERROR_HANDLE = -12
        handle = kernel32.GetStdHandle(-12)
        # ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
        mode = ctypes.c_ulong()
        kernel32.GetConsoleMode(handle, ctypes.byref(mode))
        kernel32.SetConsoleMode(handle, mode.value | 0x0004)
    except Exception:
        pass  # Older Windows or no console — ANSI won't work, but no crash


# =============================================================================
# Setup Function (call once at startup)
# =============================================================================

_initialized = False


def setup_space_logging(
    level: Optional[str] = None,
    enable_files: Optional[bool] = None,
    log_dir: Optional[str] = None,
):
    """
    Install space-colored logging on the root logger.

    Call once at startup. Idempotent — multiple calls are safe.

    Args:
        level: Log level override (default: from SPACE_LOG_LEVEL env or "INFO")
        enable_files: Enable per-space files (default: from SPACE_LOG_FILES env)
        log_dir: Directory for space files (default: from SPACE_LOG_DIR env)
    """
    global _initialized
    if _initialized:
        return
    _initialized = True

    # Read config from env
    level = level or os.getenv("SPACE_LOG_LEVEL", "INFO")
    if enable_files is None:
        enable_files = os.getenv("SPACE_LOG_FILES", "false").lower() == "true"
    log_dir = log_dir or os.getenv("SPACE_LOG_DIR", os.path.join(
        os.path.dirname(__file__), "..", "..", "logs", "spaces"
    ))

    # Enable Windows ANSI
    _enable_windows_ansi()

    # Determine output mode: JSON when piped (Electron), ANSI colors in terminal
    is_piped = not sys.stderr.isatty()
    force_json = os.getenv("SPACE_LOG_JSON", "").lower() == "true"

    handler = logging.StreamHandler(sys.stderr)
    log_level = getattr(logging, level.upper(), logging.INFO)
    handler.setLevel(log_level)

    if is_piped or force_json:
        handler.setFormatter(SpaceJsonFormatter())
    else:
        use_color = not os.getenv("NO_COLOR")
        handler.setFormatter(SpaceColorFormatter(use_color=use_color))

    root = logging.getLogger()
    # Remove any pre-existing handlers (e.g. from basicConfig) to prevent duplication
    root.handlers.clear()
    root.addHandler(handler)

    # Ensure root level allows messages through to our handler
    if root.level == logging.NOTSET or root.level > log_level:
        root.setLevel(log_level)

    # Optional per-space file handlers
    if enable_files:
        _setup_space_file_handlers(log_dir, level)

    # Log that space logging is active (to stderr via our new handler)
    mode = "json" if (is_piped or force_json) else ("color" if not os.getenv("NO_COLOR") else "plain")
    logging.getLogger("swarm.logging.space_logger").info(
        f"Space logging initialized (level={level}, files={enable_files}, mode={mode})"
    )


__all__ = [
    "SpaceColors",
    "SpaceColorFormatter",
    "SpaceJsonFormatter",
    "setup_space_logging",
    "SPACE_TO_COLOR",
    "SPACE_TO_TAG",
]
