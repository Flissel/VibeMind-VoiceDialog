"""
Ideas Agent - Backend agent for Idea/Note management

MIGRATED TO: spaces/ideas/agents/ideas_agent.py
This file re-exports for backward compatibility.
"""

# Re-export from new location
from spaces.ideas.agents.ideas_agent import IdeasAgent, get_ideas_agent

__all__ = ["IdeasAgent", "get_ideas_agent"]
