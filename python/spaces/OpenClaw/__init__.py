"""
OpenClaw Desktop Space

AutoGen Society of Mind architecture with 3 agents:
- DesktopCoordinator: Routes tasks, no tools
- ClaudeCLIAgent: Planning + Vision verification via Claude CLI
- DesktopOperator: Executes desktop actions (direct + MCP)

Integration:
- Listens to Redis stream 'events:tasks:desktop'
- Uses adapted_desktop_tools + optional MCP workbench for execution
- Claude CLI for complex reasoning and Vision-based QA verification

Usage:
    from spaces.OpenClaw import run_desktop_swarm, get_openclaw_desktop_agent

    # Direct invocation (handles MCP lifecycle automatically)
    result = await run_desktop_swarm("Open Chrome and go to github.com")

    # Backend agent for Redis integration
    agent = get_openclaw_desktop_agent()
    await agent.start()  # Listen to Redis stream
"""

# Configuration
from .config import OpenClawConfig, get_config

# Backend Agent (Redis integration)
from .backend_agent import (
    OpenClawDesktopAgent,
    get_openclaw_desktop_agent,
    USE_AG2_DESKTOP_SWARM,
)

# AutoGen Swarm
from .agents import (
    create_desktop_swarm,
    get_desktop_swarm,
    reset_desktop_swarm,
    run_desktop_swarm,
    USE_MCP_DESKTOP,
)

# Tools
from .tools import (
    # Claude CLI Tools
    claude_reason,
    claude_analyze_screenshot,
    claude_plan_task,
    CLAUDE_CLI_TOOLS,
    # Desktop Worker Tools
    DESKTOP_WORKER_TOOLS,
    # Messaging Tools (ClawedVoice)
    send_whatsapp,
    send_telegram,
    web_search,
    web_fetch,
    get_pending_notifications,
    get_openclaw_status,
    MESSAGING_TOOLS,
)

__all__ = [
    # Config
    "OpenClawConfig",
    "get_config",
    # Backend Agent
    "OpenClawDesktopAgent",
    "get_openclaw_desktop_agent",
    "USE_AG2_DESKTOP_SWARM",
    # Swarm
    "create_desktop_swarm",
    "get_desktop_swarm",
    "reset_desktop_swarm",
    "run_desktop_swarm",
    "USE_MCP_DESKTOP",
    # Claude CLI Tools
    "claude_reason",
    "claude_analyze_screenshot",
    "claude_plan_task",
    "CLAUDE_CLI_TOOLS",
    # Desktop Worker Tools
    "DESKTOP_WORKER_TOOLS",
    # Messaging Tools (ClawedVoice)
    "send_whatsapp",
    "send_telegram",
    "web_search",
    "web_fetch",
    "get_pending_notifications",
    "get_openclaw_status",
    "MESSAGING_TOOLS",
]
