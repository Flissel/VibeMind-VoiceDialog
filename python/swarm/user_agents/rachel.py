"""
Rachel - Voice Interface for VibeMind

MIGRATED TO: spaces/ideas/agents/rachel_agent.py
This file re-exports for backward compatibility.
"""

# Re-export from new location
from spaces.ideas.agents.rachel_agent import RachelAgent, create_rachel_agent, RACHEL_VOICE_PROMPT

__all__ = ["RachelAgent", "create_rachel_agent", "RACHEL_VOICE_PROMPT"]
