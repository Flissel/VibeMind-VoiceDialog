"""
OpenClaw Desktop Space Configuration

Configuration for the AutoGen Society of Mind Desktop Space.
"""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class OpenClawConfig:
    """Configuration for OpenClaw Desktop Space."""

    # Claude CLI
    claude_cli_path: str = "claude"
    claude_cli_timeout: float = 60.0
    claude_cli_no_markdown: bool = True

    # MoireTracker
    moire_tracker_path: str = r"C:\Users\User\Desktop\Moire_tracker_v1\MoireTracker_v2\python"
    moire_server_url: str = "ws://localhost:8766"

    # OpenClaw Gateway
    openclaw_enabled: bool = True
    openclaw_gateway_url: str = "ws://127.0.0.1:18789"
    openclaw_gateway_token: Optional[str] = None
    openclaw_idle_timeout: int = 300

    # AutoGen Swarm
    use_ag2_desktop_swarm: bool = True
    max_swarm_messages: int = 30

    # MCP Integration
    use_mcp_desktop: bool = False
    mcp_servers_json: str = ""  # Auto-detected from swarm/mcp_plugins/servers/servers.json

    # Redis Stream (integrates with existing 4-stream architecture)
    redis_stream_desktop: str = "events:tasks:desktop"

    @classmethod
    def from_env(cls) -> "OpenClawConfig":
        """Load configuration from environment variables."""
        return cls(
            # Claude CLI
            claude_cli_path=os.getenv("CLAUDE_CLI_PATH", "claude"),
            claude_cli_timeout=float(os.getenv("CLAUDE_CLI_TIMEOUT", "60")),
            claude_cli_no_markdown=os.getenv("CLAUDE_CLI_NO_MARKDOWN", "true").lower() in ("true", "1"),

            # MoireTracker
            moire_tracker_path=os.getenv(
                "MOIRE_TRACKER_PATH",
                r"C:\Users\User\Desktop\Moire_tracker_v1\MoireTracker_v2\python"
            ),
            moire_server_url=os.getenv("MOIRE_SERVER_URL", "ws://localhost:8766"),

            # OpenClaw Gateway
            openclaw_enabled=os.getenv("OPENCLAW_ENABLED", "true").lower() in ("true", "1"),
            openclaw_gateway_url=os.getenv("OPENCLAW_GATEWAY_URL", "ws://127.0.0.1:18789"),
            openclaw_gateway_token=os.getenv("OPENCLAW_GATEWAY_TOKEN"),
            openclaw_idle_timeout=int(os.getenv("OPENCLAW_IDLE_TIMEOUT", "300")),

            # AutoGen Swarm
            use_ag2_desktop_swarm=os.getenv("USE_AG2_DESKTOP_SWARM", "true").lower() in ("true", "1"),
            max_swarm_messages=int(os.getenv("MAX_DESKTOP_SWARM_MESSAGES", "30")),

            # MCP Integration
            use_mcp_desktop=os.getenv("USE_MCP_DESKTOP", "false").lower() in ("true", "1"),
            mcp_servers_json=os.getenv("MCP_SERVERS_JSON", ""),

            # Redis Stream
            redis_stream_desktop=os.getenv("REDIS_STREAM_DESKTOP", "events:tasks:desktop"),
        )


# Singleton config instance
_config: Optional[OpenClawConfig] = None


def get_config() -> OpenClawConfig:
    """Get OpenClaw configuration singleton."""
    global _config
    if _config is None:
        _config = OpenClawConfig.from_env()
    return _config


__all__ = ["OpenClawConfig", "get_config"]
