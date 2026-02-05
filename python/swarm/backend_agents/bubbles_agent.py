"""
Bubbles Agent - Backend agent for Space/Bubble management

MIGRATED TO: spaces/ideas/agents/bubbles_agent.py
This file re-exports for backward compatibility.
"""

# Re-export from new location
from spaces.ideas.agents.bubbles_agent import BubblesAgent, get_bubbles_agent

__all__ = ["BubblesAgent", "get_bubbles_agent"]
