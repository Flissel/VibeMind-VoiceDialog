"""
Sub-Agents Package - AutoGen AssistantAgent factories for sub-agents.

Provides factory functions for creating:
- Shared sub-agents (Memory, Context) for all main agents
- Domain-specific sub-agents (Link Analyst, Structurer, etc.)
"""

from swarm.sub_agents.base_sub_agent import (
    create_memory_sub_agent,
    create_context_sub_agent,
)

__all__ = [
    "create_memory_sub_agent",
    "create_context_sub_agent",
]
