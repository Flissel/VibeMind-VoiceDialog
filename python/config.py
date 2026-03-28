"""
Voice Dialog Configuration
Simple configuration management for OpenAI Realtime voice dialog
"""

import os
import logging
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

from llm_config import get_model

logger = logging.getLogger(__name__)


@dataclass
class LoggingConfig:
    """Logging configuration"""
    level: str = "INFO"
    file: Optional[str] = "voice_dialog.log"
    max_bytes: int = 10 * 1024 * 1024  # 10MB
    backup_count: int = 5
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


@dataclass
class AudioConfig:
    """Audio interface configuration"""
    amplitude_threshold: float = 0.03  # Minimum RMS amplitude (0.0-1.0)
    min_speech_duration: float = 0.3   # Minimum speech duration (seconds)
    use_threshold_filtering: bool = True  # Enable/disable threshold filtering


@dataclass
class VoiceConfig:
    """Voice dialog configuration"""
    openai_api_key: Optional[str]

    # OpenAI Realtime settings
    openai_realtime_model: str = get_model("voice")
    openai_realtime_voice: str = "alloy"

    logging: LoggingConfig = None
    audio: AudioConfig = None
    version: str = "3.0.0"


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
        # OpenAI API key (required for voice)
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

        # Audio configuration
        audio_threshold = float(os.getenv('AUDIO_THRESHOLD', '0.03'))
        min_speech_duration = float(os.getenv('MIN_SPEECH_DURATION', '0.3'))
        use_threshold_filtering = os.getenv('USE_THRESHOLD_FILTERING', 'true').lower() in ('true', '1', 'yes')

        audio_config = AudioConfig(
            amplitude_threshold=audio_threshold,
            min_speech_duration=min_speech_duration,
            use_threshold_filtering=use_threshold_filtering
        )

        # OpenAI Realtime settings
        openai_realtime_model = get_model("voice")
        openai_realtime_voice = os.getenv('OPENAI_REALTIME_VOICE', 'alloy')

        return VoiceConfig(
            openai_api_key=openai_key,
            openai_realtime_model=openai_realtime_model,
            openai_realtime_voice=openai_realtime_voice,
            logging=log_config,
            audio=audio_config
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

        if not config.openai_api_key:
            errors.append("OPENAI_API_KEY is required for voice")

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
    logger.debug("get_config called")
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
