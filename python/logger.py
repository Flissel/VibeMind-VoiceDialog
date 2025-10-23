"""
Production Logging Infrastructure
Provides structured logging with rotation, levels, and proper formatting
"""

import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Optional
from config import LoggingConfig, get_config


class ProductionLogger:
    """
    Production-grade logging setup with file rotation and console output
    """

    _initialized = False
    _loggers = {}

    @classmethod
    def setup(cls, config: Optional[LoggingConfig] = None):
        """
        Setup logging infrastructure (call once at application start)

        Args:
            config: Logging configuration (uses default if None)
        """
        if cls._initialized:
            return

        if config is None:
            app_config = get_config()
            config = app_config.logging

        # Create logs directory if needed
        if config.file:
            log_path = Path(config.file)
            log_path.parent.mkdir(parents=True, exist_ok=True)

        # Setup root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, config.level))

        # Remove existing handlers
        root_logger.handlers.clear()

        # Console handler (colored output)
        # CRITICAL: Use stderr for console output to avoid conflicts with stdout-based IPC
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setLevel(getattr(logging, config.level))
        console_formatter = ColoredFormatter(
            fmt=config.format,
            use_color=True
        )
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)

        # File handler with rotation (if file logging enabled)
        if config.file:
            file_handler = logging.handlers.RotatingFileHandler(
                config.file,
                maxBytes=config.max_bytes,
                backupCount=config.backup_count,
                encoding='utf-8'
            )
            file_handler.setLevel(logging.DEBUG)  # Log everything to file
            file_formatter = logging.Formatter(
                fmt=config.format,
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            file_handler.setFormatter(file_formatter)
            root_logger.addHandler(file_handler)

        cls._initialized = True

        # Log startup
        root_logger.info("="*60)
        root_logger.info("Voice Dialog Logging Initialized")
        root_logger.info(f"Log Level: {config.level}")
        if config.file:
            root_logger.info(f"Log File: {config.file}")
        root_logger.info("="*60)

    @classmethod
    def get_logger(cls, name: str) -> logging.Logger:
        """
        Get a logger instance for a module

        Args:
            name: Logger name (usually __name__)

        Returns:
            Logger instance
        """
        if not cls._initialized:
            cls.setup()

        if name not in cls._loggers:
            cls._loggers[name] = logging.getLogger(name)

        return cls._loggers[name]


class ColoredFormatter(logging.Formatter):
    """
    Formatter that adds color to console output based on log level
    """

    # ANSI color codes
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
    }
    RESET = '\033[0m'

    def __init__(self, fmt: str, use_color: bool = True):
        super().__init__(fmt)
        self.use_color = use_color and sys.stdout.isatty()

    def format(self, record):
        if self.use_color and record.levelname in self.COLORS:
            # Color the level name
            record.levelname = (
                f"{self.COLORS[record.levelname]}"
                f"{record.levelname:8s}"
                f"{self.RESET}"
            )
        else:
            record.levelname = f"{record.levelname:8s}"

        return super().format(record)


class StructuredLogger:
    """
    Wrapper for structured logging with context
    """

    def __init__(self, name: str):
        """
        Initialize structured logger

        Args:
            name: Logger name
        """
        self.logger = ProductionLogger.get_logger(name)
        self.context = {}

    def set_context(self, **kwargs):
        """Set context variables for all log messages"""
        self.context.update(kwargs)

    def clear_context(self):
        """Clear all context variables"""
        self.context.clear()

    def _format_message(self, msg: str) -> str:
        """Format message with context"""
        if self.context:
            context_str = " | ".join(f"{k}={v}" for k, v in self.context.items())
            return f"{msg} | {context_str}"
        return msg

    def debug(self, msg: str, **kwargs):
        """Log debug message"""
        self.logger.debug(self._format_message(msg), **kwargs)

    def info(self, msg: str, **kwargs):
        """Log info message"""
        self.logger.info(self._format_message(msg), **kwargs)

    def warning(self, msg: str, **kwargs):
        """Log warning message"""
        self.logger.warning(self._format_message(msg), **kwargs)

    def error(self, msg: str, exc_info=False, **kwargs):
        """Log error message"""
        self.logger.error(self._format_message(msg), exc_info=exc_info, **kwargs)

    def critical(self, msg: str, exc_info=False, **kwargs):
        """Log critical message"""
        self.logger.critical(self._format_message(msg), exc_info=exc_info, **kwargs)

    def exception(self, msg: str, **kwargs):
        """Log exception with traceback"""
        self.logger.exception(self._format_message(msg), **kwargs)


# Convenience function
def get_logger(name: str) -> StructuredLogger:
    """
    Get a structured logger instance

    Args:
        name: Logger name (usually __name__)

    Returns:
        StructuredLogger instance
    """
    return StructuredLogger(name)


# Setup logging on module import
ProductionLogger.setup()
