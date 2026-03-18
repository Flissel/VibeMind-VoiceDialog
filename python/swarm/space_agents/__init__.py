"""
SpaceAgents — Per-space LLM tool-calling agents.

Each Space gets its own agent with domain-specific tools.
The agent uses native function calling (gpt-4o-mini via OpenRouter)
to intelligently orchestrate multiple tools for complex requests.
"""

from .models import SpaceAgentContext, SpaceAgentResult, SpaceToolCall, SpaceToolResult
from .base_space_agent import BaseSpaceAgent
from .ideas_agent import IdeasSpaceAgent, get_ideas_space_agent, reset_ideas_space_agent

__all__ = [
    "SpaceAgentContext",
    "SpaceAgentResult",
    "SpaceToolCall",
    "SpaceToolResult",
    "BaseSpaceAgent",
    "IdeasSpaceAgent",
    "get_ideas_space_agent",
    "reset_ideas_space_agent",
]
