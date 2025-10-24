"""
Voice Dialog Configuration
Simple configuration management for ElevenLabs voice dialog
"""

import os
import logging
from pathlib import Path
from typing import Optional
from dataclasses import dataclass


@dataclass
class LoggingConfig:
    """Logging configuration"""
    level: str = "INFO"
    file: Optional[str] = "voice_dialog.log"
    max_bytes: int = 10 * 1024 * 1024  # 10MB
    backup_count: int = 5
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


@dataclass
class VoiceConfig:
    """Voice dialog configuration"""
    elevenlabs_api_key: Optional[str]
    elevenlabs_agent_id: Optional[str]
    openai_api_key: Optional[str]  # Optional fallback
    logging: LoggingConfig
    version: str = "2.0.0"


class ConfigurationError(Exception):
    """Configuration validation error"""
    pass


class ConfigManager:
    """
    Manages voice dialog configuration from environment variables
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

    def get_config(self) -> VoiceConfig:
        """
        Get validated voice dialog configuration

        Returns:
            VoiceConfig instance

        Raises:
            ConfigurationError: If required config is missing
        """
        # ElevenLabs API key (required)
        elevenlabs_key = os.getenv('ELEVENLABS_API_KEY')
        if not elevenlabs_key or elevenlabs_key.strip() in ['', 'your_elevenlabs_key_here']:
            elevenlabs_key = None

        # ElevenLabs Agent ID (required)
        agent_id = os.getenv('ELEVENLABS_AGENT_ID')
        if not agent_id or agent_id.strip() in ['', 'your_agent_id_here']:
            agent_id = None

        # OpenAI API key (optional)
        openai_key = os.getenv('OPENAI_API_KEY')
        if openai_key and openai_key.strip() in ['', 'your_openai_key_here']:
            openai_key = None

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

        return VoiceConfig(
            elevenlabs_api_key=elevenlabs_key,
            elevenlabs_agent_id=agent_id,
            openai_api_key=openai_key,
            logging=log_config
        )

    def validate_config(self, config: VoiceConfig, strict: bool = False) -> bool:
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

        # Check required ElevenLabs credentials
        if not config.elevenlabs_api_key:
            errors.append("ELEVENLABS_API_KEY is required")

        if not config.elevenlabs_agent_id:
            errors.append("ELEVENLABS_AGENT_ID is required")

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


def get_config() -> VoiceConfig:
    """
    Get global configuration instance

    Returns:
        VoiceConfig instance
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
