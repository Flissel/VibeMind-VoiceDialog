"""
OpenClaw Desktop Space Tools

Tools for the AutoGen Society of Mind desktop automation:
- Claude CLI Tools: Invoke Claude CLI for reasoning
- Desktop CLI Tools: Execute desktop actions
- Messaging Tools: WhatsApp, Telegram, Web via ClawedVoice
"""

from .claude_cli_tools import (
    claude_reason,
    claude_analyze_screenshot,
    claude_plan_task,
    CLAUDE_CLI_TOOLS,
)

from .desktop_cli_tools import (
    DESKTOP_WORKER_TOOLS,
)

from .messaging_tools import (
    send_whatsapp,
    send_telegram,
    web_search,
    web_fetch,
    get_pending_notifications,
    get_openclaw_status,
    MESSAGING_TOOLS,
)

__all__ = [
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
