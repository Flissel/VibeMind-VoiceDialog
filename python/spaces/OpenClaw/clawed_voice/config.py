"""
Configuration management for clawed_voice.

Loads settings from environment variables and .env file.
"""

import os
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

# Try to load dotenv
try:
    from dotenv import load_dotenv
    _HAS_DOTENV = True
except ImportError:
    _HAS_DOTENV = False

logger = logging.getLogger(__name__)


@dataclass
class ClawedVoiceConfig:
    """Configuration for clawed_voice bridge."""

    # OpenClaw Gateway
    openclaw_path: str = ""
    gateway_port: int = 18789
    gateway_host: str = "127.0.0.1"
    gateway_token: Optional[str] = None
    gateway_url: str = field(init=False)
    idle_timeout_seconds: int = 300

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Logging
    log_level: str = "INFO"
    log_file: Optional[str] = None

    # VibeMind
    vibemind_path: Optional[str] = None

    # Default recipient for agent responses
    openclaw_default_recipient: str = "+491749708452"

    def __post_init__(self):
        """Compute derived values."""
        self.gateway_url = f"ws://{self.gateway_host}:{self.gateway_port}"

    @classmethod
    def from_env(cls) -> "ClawedVoiceConfig":
        """Create config from environment variables."""
        return cls(
            openclaw_path=os.getenv("OPENCLAW_PATH", _find_openclaw()),
            gateway_port=int(os.getenv("OPENCLAW_GATEWAY_PORT", "18789")),
            gateway_host=os.getenv("OPENCLAW_GATEWAY_HOST", "127.0.0.1"),
            gateway_token=os.getenv("OPENCLAW_GATEWAY_TOKEN") or None,
            idle_timeout_seconds=int(os.getenv("OPENCLAW_IDLE_TIMEOUT_SECONDS", "300")),
            redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            log_file=os.getenv("LOG_FILE"),
            vibemind_path=os.getenv("VIBEMIND_PATH"),
            openclaw_default_recipient=os.getenv("OPENCLAW_DEFAULT_RECIPIENT", "+491749708452"),
        )


def _find_openclaw() -> str:
    """Try to find openclaw executable."""
    # Common locations
    candidates = [
        # Windows npm global
        Path(os.environ.get("APPDATA", "")) / "npm" / "openclaw.cmd",
        Path(os.environ.get("APPDATA", "")) / "npm" / "openclaw",
        # Unix-like
        Path.home() / ".npm-global" / "bin" / "openclaw",
        Path("/usr/local/bin/openclaw"),
        Path("/usr/bin/openclaw"),
        # pnpm
        Path.home() / ".local" / "share" / "pnpm" / "openclaw",
    ]

    for path in candidates:
        if path.exists():
            return str(path)

    # Try PATH
    import shutil
    found = shutil.which("openclaw")
    if found:
        return found

    # Default fallback
    return "openclaw"


def _find_env_file() -> Optional[Path]:
    """Find .env file, searching upward from current directory."""
    current = Path.cwd()

    # Check current directory and project root
    candidates = [
        current / ".env",
        Path(__file__).parent.parent / ".env",
    ]

    for path in candidates:
        if path.exists():
            return path

    return None


# Singleton config
_config: Optional[ClawedVoiceConfig] = None


def get_config() -> ClawedVoiceConfig:
    """Get or create configuration singleton."""
    global _config

    if _config is None:
        # Load .env file if available
        if _HAS_DOTENV:
            env_file = _find_env_file()
            if env_file:
                load_dotenv(env_file)
                logger.debug(f"Loaded environment from {env_file}")

        _config = ClawedVoiceConfig.from_env()

        # Setup logging
        _setup_logging(_config)

        logger.info(f"Configuration loaded: gateway={_config.gateway_url}")

    return _config


def _setup_logging(config: ClawedVoiceConfig):
    """Configure logging based on config."""
    level = getattr(logging, config.log_level.upper(), logging.INFO)

    # Basic format
    fmt = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"

    handlers = [logging.StreamHandler()]

    if config.log_file:
        log_path = Path(config.log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_path))

    logging.basicConfig(
        level=level,
        format=fmt,
        handlers=handlers,
    )

    # Try colored logs
    try:
        import coloredlogs
        coloredlogs.install(level=level, fmt=fmt)
    except ImportError:
        pass


def reload_config() -> ClawedVoiceConfig:
    """Force reload configuration."""
    global _config
    _config = None
    return get_config()


__all__ = ["ClawedVoiceConfig", "get_config", "reload_config"]
