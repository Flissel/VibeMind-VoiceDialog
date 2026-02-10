"""
Clawed Voice - VibeMind to OpenClaw Bridge

This package provides integration between VibeMind voice agents
and OpenClaw's multi-channel messaging and AI capabilities.

Usage:
    from clawed_voice import get_bridge, execute_task_sync

    # Get status
    status = get_status_sync()

    # Execute a task
    result = execute_task_sync("messaging.whatsapp", {
        "recipient": "+1234567890",
        "content": "Hello from Rachel!"
    })

    # Get notifications
    notifications = get_notifications_sync()
"""

__version__ = "0.1.0"
__author__ = "VibeMind Team"

from .config import get_config, ClawedVoiceConfig
from .gateway_manager import (
    GatewayManager,
    GatewayState,
    get_gateway_manager,
    start_gateway,
    stop_gateway,
    ensure_gateway,
    cleanup_stale_locks,
)
from .client import (
    OpenClawClient,
    get_client,
    connect,
    disconnect,
)
from .notifications import (
    Notification,
    NotificationQueue,
    get_notification_queue,
)
from .bridge import (
    ClawedVoiceBridge,
    get_bridge,
    execute_task_sync,
    get_status_sync,
    get_notifications_sync,
)
from .archive import (
    ChatArchive,
    get_archive,
    archive_message,
)
from .html_debugger import (
    debug_html,
    debug_html_sync,
    quick_debug,
)

__all__ = [
    # Version
    "__version__",
    # Config
    "get_config",
    "ClawedVoiceConfig",
    # Gateway Manager
    "GatewayManager",
    "GatewayState",
    "get_gateway_manager",
    "start_gateway",
    "stop_gateway",
    "ensure_gateway",
    "cleanup_stale_locks",
    # Client
    "OpenClawClient",
    "get_client",
    "connect",
    "disconnect",
    # Notifications
    "Notification",
    "NotificationQueue",
    "get_notification_queue",
    # Bridge
    "ClawedVoiceBridge",
    "get_bridge",
    "execute_task_sync",
    "get_status_sync",
    "get_notifications_sync",
    # Archive
    "ChatArchive",
    "get_archive",
    "archive_message",
    # HTML Debugger
    "debug_html",
    "debug_html_sync",
    "quick_debug",
]
