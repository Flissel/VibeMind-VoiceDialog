"""
Swarm Executive Package

High-level coordination layer for the VibeMind agent swarm.

Components:
- IntentBatcher: Collects rapid-fire voice intents into batched action plans
- ConversationMemory: Long-term conversation history across sessions

The executive layer sits above the orchestrator and handles:
1. Intent batching (multiple rapid intents -> single action plan)
2. Dependency resolution between related intents
3. Long-term context memory beyond the 10-minute window
"""

from .intent_batcher import IntentBatcher, Intent, ActionPlan
from .conversation_memory import ConversationMemory, Interaction

__all__ = [
    "IntentBatcher",
    "Intent",
    "ActionPlan",
    "ConversationMemory",
    "Interaction",
]
