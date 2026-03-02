"""
Minibook Space Configuration

Configuration for the Minibook inter-space collaboration layer.
Minibook runs locally and VibeMind communicates via its REST API.
"""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class MinibookConfig:
    """Configuration for Minibook Space (inter-space collaboration)."""

    # Minibook API
    minibook_url: str = "http://localhost:3480"
    minibook_frontend_url: str = "http://localhost:3481"

    # Collaboration project (auto-created on startup)
    collaboration_project_name: str = "VibeMind Collaboration"

    # Feature flags
    minibook_enabled: bool = False
    auto_register_spaces: bool = True

    # Polling
    poll_interval_seconds: float = 2.0
    collaboration_timeout_seconds: float = 120.0

    # Redis Stream
    redis_stream_minibook: str = "events:tasks:minibook"

    @classmethod
    def from_env(cls) -> "MinibookConfig":
        """Load configuration from environment variables."""
        return cls(
            minibook_url=os.getenv("MINIBOOK_URL", "http://localhost:3480"),
            minibook_frontend_url=os.getenv("MINIBOOK_FRONTEND_URL", "http://localhost:3481"),
            minibook_enabled=os.getenv("MINIBOOK_ENABLED", "false").lower() in ("true", "1"),
            auto_register_spaces=os.getenv("MINIBOOK_AUTO_REGISTER", "true").lower() in ("true", "1"),
            poll_interval_seconds=float(os.getenv("MINIBOOK_POLL_INTERVAL", "2.0")),
            collaboration_timeout_seconds=float(os.getenv("MINIBOOK_COLLABORATION_TIMEOUT", "120.0")),
        )


# Singleton config instance
_config: Optional[MinibookConfig] = None


def get_config() -> MinibookConfig:
    """Get Minibook configuration singleton."""
    global _config
    if _config is None:
        _config = MinibookConfig.from_env()
    return _config


__all__ = ["MinibookConfig", "get_config"]
