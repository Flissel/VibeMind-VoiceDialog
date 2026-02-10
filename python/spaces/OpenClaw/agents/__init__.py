"""
OpenClaw Desktop Space Agents

AutoGen Society of Mind agents for desktop automation (3 agents):
- Desktop Coordinator: Routes tasks between agents
- Claude CLI Agent: Planning + Vision verification via Claude CLI
- Desktop Operator: Executes desktop actions (direct + MCP)
"""

from .desktop_swarm import (
    create_desktop_swarm,
    get_desktop_swarm,
    reset_desktop_swarm,
    run_desktop_swarm,
    USE_MCP_DESKTOP,
)

__all__ = [
    "create_desktop_swarm",
    "get_desktop_swarm",
    "reset_desktop_swarm",
    "run_desktop_swarm",
    "USE_MCP_DESKTOP",
]
