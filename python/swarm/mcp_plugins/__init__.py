"""
MCP Plugins Package
====================

Sakana-Style MCP (Model Context Protocol) Server Collection
für Integration in die Coding Engine.

Verfügbare Server:
- playwright: Browser Automation mit Console-Log Capture
- github: Git/GitHub Integration
- filesystem: File Operations
- docker: Container Management
- memory: Knowledge Management
- und weitere...

Usage:
    from mcp_plugins import PlaywrightAgent
    from mcp_plugins.servers.playwright import run as run_playwright
"""

import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

# Package root directory
PACKAGE_DIR = Path(__file__).parent
SERVERS_DIR = PACKAGE_DIR / "servers"

# Add servers/shared to path for imports
_shared_path = str(SERVERS_DIR / "shared")
if _shared_path not in sys.path:
    sys.path.insert(0, _shared_path)


# Lazy imports for heavy dependencies
if TYPE_CHECKING:
    from mcp_plugins.servers.playwright.agent import run as run_playwright
    from mcp_plugins.servers.playwright.preview_utils import PreviewManager
    from mcp_plugins.servers.github.agent import run as run_github


def get_server_path(server_name: str) -> Path:
    """Get the path to a specific MCP server."""
    server_path = SERVERS_DIR / server_name
    if not server_path.exists():
        raise ValueError(f"MCP Server '{server_name}' not found at {server_path}")
    return server_path


def list_available_servers() -> list[str]:
    """List all available MCP servers."""
    servers = []
    if SERVERS_DIR.exists():
        for item in SERVERS_DIR.iterdir():
            if item.is_dir() and (item / "agent.py").exists():
                servers.append(item.name)
    return sorted(servers)


def get_servers_config() -> dict:
    """Load the servers.json configuration."""
    import json
    config_path = SERVERS_DIR / "servers.json"
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"servers": []}


# Convenience exports
__all__ = [
    "PACKAGE_DIR",
    "SERVERS_DIR",
    "get_server_path",
    "list_available_servers",
    "get_servers_config",
]

# Version info
__version__ = "1.0.0"
__author__ = "Coding Engine Team"