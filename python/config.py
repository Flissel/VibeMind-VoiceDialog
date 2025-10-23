"""
Production Configuration Management
Handles environment variables, validation, and default settings
"""

import os
import logging
from pathlib import Path
from typing import Optional
from dataclasses import dataclass


@dataclass
class MoireTrackerConfig:
    """MoireTracker service configuration"""
    path: Path
    timeout_ms: int = 10000
    max_reconnect_attempts: int = 3
    health_check_interval: int = 30
    ipc_auth_enabled: bool = True  # Enable IPC authentication by default
    auto_start: bool = False  # Auto-start MoireTracker on launch (default: manual)


@dataclass
class LoggingConfig:
    """Logging configuration"""
    level: str = "INFO"
    file: Optional[str] = "voice_dialog.log"
    max_bytes: int = 10 * 1024 * 1024  # 10MB
    backup_count: int = 5
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


@dataclass
class AppConfig:
    """Main application configuration"""
    openai_api_key: Optional[str]
    elevenlabs_api_key: Optional[str]
    moire_tracker: MoireTrackerConfig
    logging: LoggingConfig
    version: str = "1.0.0"


class ConfigurationError(Exception):
    """Configuration validation error"""
    pass


class ConfigManager:
    """
    Manages application configuration from environment variables
    with validation and defaults
    """

    def __init__(self, env_file: Optional[str] = None):
        """
        Initialize configuration manager

        Args:
            env_file: Path to .env file (defaults to .env in project root)
        """
        self.env_file = env_file or self._find_env_file()
        self._load_env_file()

    def _find_env_file(self) -> Optional[str]:
        """Find .env file in project directory"""
        # Start from current file's directory and go up
        current = Path(__file__).parent
        for _ in range(3):  # Check up to 3 levels up
            env_path = current / ".env"
            if env_path.exists():
                return str(env_path)
            current = current.parent
        return None

    def _load_env_file(self):
        """Load environment variables from .env file"""
        if not self.env_file or not Path(self.env_file).exists():
            logging.warning(f"No .env file found at {self.env_file}")
            return

        try:
            with open(self.env_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    if '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip()
                        if value and key not in os.environ:
                            os.environ[key] = value
        except Exception as e:
            logging.error(f"Failed to load .env file: {e}")

    def get_config(self) -> AppConfig:
        """
        Get validated application configuration

        Returns:
            AppConfig instance

        Raises:
            ConfigurationError: If required config is missing or invalid
        """
        # OpenAI API key (optional in demo mode)
        openai_key = os.getenv('OPENAI_API_KEY')
        if openai_key and openai_key.strip() in ['', 'your_openai_api_key_here']:
            openai_key = None

        # ElevenLabs API key (optional)
        elevenlabs_key = os.getenv('ELEVENLABS_API_KEY')
        if elevenlabs_key and elevenlabs_key.strip() in ['', 'your_elevenlabs_key_here']:
            elevenlabs_key = None

        # MoireTracker configuration
        moire_path = os.getenv('MOIRE_TRACKER_PATH',
                               r'C:\Users\User\Desktop\Moire\build\Release')
        moire_path = Path(moire_path)

        if not moire_path.exists():
            logging.warning(f"MoireTracker path does not exist: {moire_path}")

        moire_timeout = int(os.getenv('MOIRE_TRACKER_TIMEOUT', '10000'))

        # IPC authentication (enabled by default)
        ipc_auth_enabled = os.getenv('IPC_AUTH_ENABLED', 'true').lower() in ['true', '1', 'yes']

        # Auto-start MoireTracker (disabled by default for robustness)
        auto_start = os.getenv('AUTO_START_MOIRE', 'false').lower() in ['true', '1', 'yes']

        moire_config = MoireTrackerConfig(
            path=moire_path,
            timeout_ms=moire_timeout,
            max_reconnect_attempts=int(os.getenv('MOIRE_MAX_RECONNECT', '3')),
            health_check_interval=int(os.getenv('MOIRE_HEALTH_CHECK_INTERVAL', '30')),
            ipc_auth_enabled=ipc_auth_enabled,
            auto_start=auto_start
        )

        # Logging configuration
        log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
        if log_level not in ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']:
            log_level = 'INFO'

        log_config = LoggingConfig(
            level=log_level,
            file=os.getenv('LOG_FILE', 'voice_dialog.log'),
            max_bytes=int(os.getenv('LOG_MAX_BYTES', str(10 * 1024 * 1024))),
            backup_count=int(os.getenv('LOG_BACKUP_COUNT', '5'))
        )

        return AppConfig(
            openai_api_key=openai_key,
            elevenlabs_api_key=elevenlabs_key,
            moire_tracker=moire_config,
            logging=log_config
        )

    def validate_config(self, config: AppConfig, strict: bool = False) -> bool:
        """
        Validate configuration

        Args:
            config: Configuration to validate
            strict: If True, raise exceptions on errors

        Returns:
            True if valid

        Raises:
            ConfigurationError: If strict=True and validation fails
        """
        errors = []

        # Check MoireTracker path
        exe_path = config.moire_tracker.path / "MoireTracker.exe"
        if not exe_path.exists():
            errors.append(f"MoireTracker.exe not found at {exe_path}")

        # Check API keys in production mode
        if strict and not config.openai_api_key:
            errors.append("OPENAI_API_KEY is required for production")

        if errors:
            error_msg = "Configuration validation failed:\n" + "\n".join(f"  - {e}" for e in errors)
            if strict:
                raise ConfigurationError(error_msg)
            else:
                logging.warning(error_msg)
                return False

        return True


# Global configuration instance
_config_manager = None


def get_config() -> AppConfig:
    """
    Get global configuration instance

    Returns:
        AppConfig instance
    """
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager.get_config()


def validate_config(strict: bool = False) -> bool:
    """
    Validate global configuration

    Args:
        strict: If True, raise exceptions on errors

    Returns:
        True if valid
    """
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    config = _config_manager.get_config()
    return _config_manager.validate_config(config, strict=strict)
