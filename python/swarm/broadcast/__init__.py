"""
Broadcast Package - Fan-Out Intent Dispatch Architecture

Replaces Backend Agents with a broadcast pattern where every classified
intent is sent to ALL domain agents simultaneously. The responsible agent
executes; non-responsible agents create user profiling data.

Architecture:
    BroadcastDispatcher (fan-out engine)
    ├── IdeasBroadcastAgent (idea.* + bubble.*)
    ├── CodingBroadcastAgent (code.*)
    └── DesktopBroadcastAgent (desktop.*)

Each agent has:
    ├── MemorySubAgent (user profiling → Supermemory)
    ├── ContextSubAgent (transcript summary for AI restart)
    └── Domain-specific sub-agents
"""

from swarm.broadcast.dispatcher import (
    BroadcastDispatcher,
    IntentPayload,
    BroadcastResult,
)
from swarm.broadcast.base_broadcast_agent import (
    BaseBroadcastAgent,
    ResponsibilityEvaluation,
)

__all__ = [
    "BroadcastDispatcher",
    "IntentPayload",
    "BroadcastResult",
    "BaseBroadcastAgent",
    "ResponsibilityEvaluation",
]
