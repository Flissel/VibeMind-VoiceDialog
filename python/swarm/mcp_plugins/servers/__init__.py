"""
MCP Servers Package
===================

Enthält alle MCP Server Implementationen.

Verfügbare Server:
- playwright: Browser Automation, Console-Log Capture
- github: Git/GitHub Operations
- filesystem: File System Operations
- docker: Container Management
- memory: Knowledge/Memory Management
- redis: Redis Database Operations
- context7: Library Documentation
- desktop: Desktop Automation
- time: Timezone Operations
- und weitere...
"""

import os
from pathlib import Path

# Server directory
SERVERS_DIR = Path(__file__).parent


def get_server_agent(server_name: str):
    """
    Dynamically import and return a server's agent module.
    
    Args:
        server_name: Name of the server (e.g., 'playwright', 'github')
        
    Returns:
        The agent module for the specified server
    """
    import importlib
    module_path = f"mcp_plugins.servers.{server_name}.agent"
    return importlib.import_module(module_path)


def get_server_prompt(server_name: str, prompt_type: str = "system") -> str:
    """
    Load a prompt file for a server.
    
    Args:
        server_name: Name of the server
        prompt_type: Type of prompt ('system', 'task', 'operator', 'validator')
        
    Returns:
        The prompt content as string
    """
    prompt_file = SERVERS_DIR / server_name / f"{prompt_type}_prompt.txt"
    if prompt_file.exists():
        return prompt_file.read_text(encoding="utf-8")
    return ""


__all__ = [
    "SERVERS_DIR",
    "get_server_agent",
    "get_server_prompt",
]