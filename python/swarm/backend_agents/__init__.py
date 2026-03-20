"""
Backend Agents - Tool Executors for VibeMind Swarm

Backend agents listen to Redis streams and execute the actual tools.
Each agent is responsible for a specific domain.

Agent loading is now plugin-driven via PluginManager.
Legacy getter functions are kept for backward compatibility.

Architecture:
1. Rachel (voice) sends intent to Orchestrator
2. Orchestrator classifies and seeds event to Redis
3. Backend Agent receives event, executes tool
4. Backend Agent publishes status back to Redis
5. StatusListener receives status, triggers Rachel TTS
"""

import logging
from typing import Any, Optional

# BaseBackendAgent is always needed, so import it eagerly
from swarm.backend_agents.base_agent import BaseBackendAgent

logger = logging.getLogger(__name__)


def get_agent(plugin_id: str) -> Optional[Any]:
    """Get agent singleton by plugin ID via PluginManager (dynamic)."""
    try:
        from plugins.plugin_manager import get_plugin_manager
        pm = get_plugin_manager()
        manifest = pm.get_manifest(plugin_id)
        if manifest and pm.is_enabled(plugin_id):
            return pm.load_agent(manifest)
    except Exception as e:
        logger.debug(f"Plugin-based agent loading failed for '{plugin_id}': {e}")
    return None


# ── Backward-compatible getters (delegate to plugin system) ────

def get_bubbles_agent():
    """Get BubblesAgent singleton (lazy import)."""
    agent = get_agent("bubbles")
    if agent:
        return agent
    from spaces.ideas.agents.bubbles_agent import get_bubbles_agent as _get
    return _get()


def get_ideas_agent():
    """Get IdeasAgent singleton (lazy import)."""
    agent = get_agent("ideas")
    if agent:
        return agent
    from spaces.ideas.agents.ideas_agent import get_ideas_agent as _get
    return _get()


def get_desktop_agent():
    """Get DesktopAgent singleton (lazy import)."""
    agent = get_agent("desktop")
    if agent:
        return agent
    from spaces.desktop.agents.desktop_agent import get_desktop_agent as _get
    return _get()


def get_coding_agent():
    """Get CodingAgent singleton (lazy import)."""
    agent = get_agent("coding")
    if agent:
        return agent
    from spaces.coding.agents.coding_agent import get_coding_agent as _get
    return _get()


def get_roarboot_agent():
    """Get RoarbootAgent singleton (lazy import)."""
    agent = get_agent("rowboat")
    if agent:
        return agent
    from spaces.rowboat.agents.roarboot_agent import get_roarboot_agent as _get
    return _get()


def get_n8n_agent():
    """Get N8nAgent singleton (lazy import)."""
    agent = get_agent("n8n")
    if agent:
        return agent
    from spaces.n8n.agents.n8n_agent import get_n8n_agent as _get
    return _get()


def get_schedule_agent():
    """Get ScheduleBackendAgent singleton (lazy import)."""
    agent = get_agent("schedule")
    if agent:
        return agent
    from spaces.schedule.agents.schedule_agent import get_schedule_agent as _get
    return _get()


def get_minibook_agent():
    """Get MinibookBackendAgent singleton (lazy import)."""
    agent = get_agent("minibook")
    if agent:
        return agent
    from spaces.minibook.agents.minibook_agent import get_minibook_agent as _get
    return _get()


def get_zeroclaw_research_agent():
    """Get ZeroClawResearchAgent singleton (lazy import)."""
    agent = get_agent("research")
    if agent:
        return agent
    from spaces.research.agents.zeroclaw_research_agent import get_zeroclaw_research_agent as _get
    return _get()


def get_video_agent():
    """Get VideoBackendAgent singleton (lazy import)."""
    agent = get_agent("video")
    if agent:
        return agent
    from spaces.video.agents.video_agent import get_video_agent as _get
    return _get()


def get_agentfarm_agent():
    """Get AgentFarmAgent singleton (lazy import)."""
    agent = get_agent("agentfarm")
    if agent:
        return agent
    from spaces.autogen.agents.agentfarm_agent import get_agentfarm_agent as _get
    return _get()


def get_flowzen_agent():
    """Get FlowzenAgent singleton (lazy import)."""
    agent = get_agent("flowzen")
    if agent:
        return agent
    from spaces.flowzen.agents.flowzen_agent import get_flowzen_agent as _get
    return _get()


# For backward compatibility, also provide the classes via __getattr__
def __getattr__(name):
    """Lazy load agent classes to avoid circular imports."""
    if name == "BubblesAgent":
        from spaces.ideas.agents.bubbles_agent import BubblesAgent
        return BubblesAgent
    elif name == "IdeasAgent":
        from spaces.ideas.agents.ideas_agent import IdeasAgent
        return IdeasAgent
    elif name == "DesktopAgent":
        from spaces.desktop.agents.desktop_agent import DesktopAgent
        return DesktopAgent
    elif name == "CodingAgent":
        from spaces.coding.agents.coding_agent import CodingAgent
        return CodingAgent
    elif name == "RoarbootBackendAgent":
        from spaces.rowboat.agents.roarboot_agent import RoarbootBackendAgent
        return RoarbootBackendAgent
    elif name == "N8nBackendAgent":
        from spaces.n8n.agents.n8n_agent import N8nBackendAgent
        return N8nBackendAgent
    elif name == "ScheduleBackendAgent":
        from spaces.schedule.agents.schedule_agent import ScheduleBackendAgent
        return ScheduleBackendAgent
    elif name == "MinibookBackendAgent":
        from spaces.minibook.agents.minibook_agent import MinibookBackendAgent
        return MinibookBackendAgent
    elif name == "ZeroClawResearchAgent":
        from spaces.research.agents.zeroclaw_research_agent import ZeroClawResearchAgent
        return ZeroClawResearchAgent
    elif name == "VideoBackendAgent":
        from spaces.video.agents.video_agent import VideoBackendAgent
        return VideoBackendAgent
    elif name == "AgentFarmBackendAgent":
        from spaces.autogen.agents.agentfarm_agent import AgentFarmBackendAgent
        return AgentFarmBackendAgent
    elif name == "FlowzenAgent":
        from spaces.flowzen.agents.flowzen_agent import FlowzenAgent
        return FlowzenAgent
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "BaseBackendAgent",
    "get_agent",
    "BubblesAgent",
    "get_bubbles_agent",
    "IdeasAgent",
    "get_ideas_agent",
    "DesktopAgent",
    "get_desktop_agent",
    "CodingAgent",
    "get_coding_agent",
    "RoarbootBackendAgent",
    "get_roarboot_agent",
    "N8nBackendAgent",
    "get_n8n_agent",
    "ScheduleBackendAgent",
    "get_schedule_agent",
    "MinibookBackendAgent",
    "get_minibook_agent",
    "ZeroClawResearchAgent",
    "get_zeroclaw_research_agent",
    "VideoBackendAgent",
    "get_video_agent",
    "AgentFarmBackendAgent",
    "get_agentfarm_agent",
    "FlowzenAgent",
    "get_flowzen_agent",
]
