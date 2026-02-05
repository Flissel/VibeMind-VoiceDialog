"""
Backend Agents - Tool Executors for VibeMind Swarm

Backend agents listen to Redis streams and execute the actual tools.
Each agent is responsible for a specific domain:

- BubblesAgent: Space/Bubble management (13 tools)
- IdeasAgent: Ideas/Notes within bubbles (38 tools)
- DesktopAgent: Desktop automation (12 tools)
- CodingAgent: Code generation (8 tools)

Architecture:
1. Rachel (voice) sends intent to Orchestrator
2. Orchestrator classifies and seeds event to Redis
3. Backend Agent receives event, executes tool
4. Backend Agent publishes status back to Redis
5. StatusListener receives status, triggers Rachel TTS
"""

from swarm.backend_agents.base_agent import BaseBackendAgent
from swarm.backend_agents.bubbles_agent import BubblesAgent, get_bubbles_agent
from swarm.backend_agents.ideas_agent import IdeasAgent, get_ideas_agent
from swarm.backend_agents.desktop_agent import DesktopAgent, get_desktop_agent
from swarm.backend_agents.coding_agent import CodingAgent, get_coding_agent

__all__ = [
    "BaseBackendAgent",
    "BubblesAgent",
    "get_bubbles_agent",
    "IdeasAgent",
    "get_ideas_agent",
    "DesktopAgent",
    "get_desktop_agent",
    "CodingAgent",
    "get_coding_agent",
]
