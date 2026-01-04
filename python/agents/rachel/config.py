"""
Rachel Agent Configuration

Rachel ist der Multiverse Navigator - der Entry-Point Agent.
Sie verwaltet Bubbles/Spaces und kann zu Alice weiterleiten.
"""

import os
from typing import List


# ElevenLabs Voice: Rachel
VOICE_ID = "21m00Tcm4TlvDq8ikWAM"

# Agent ID wird aus .env geladen (AGENT_MULTIVERSE oder RACHEL_AGENT_ID)
def get_agent_id() -> str:
    """Hole die Agent-ID aus der Umgebungsvariable."""
    agent_id = os.getenv("AGENT_MULTIVERSE") or os.getenv("RACHEL_AGENT_ID")
    if not agent_id:
        raise ValueError("AGENT_MULTIVERSE oder RACHEL_AGENT_ID nicht in .env gesetzt")
    return agent_id


# Agenten-Eigenschaften
AGENT_CONFIG = {
    "name": "Rachel",
    "slug": "rachel",
    "voice_id": VOICE_ID,
    "role": "Multiverse Navigator - Verwaltet Bubbles/Spaces und Ideen",
    
    # Rachel kann zu Alice weiterleiten (Hub)
    "can_transfer_to": ["alice"],
    
    # Rachel ist der Entry-Agent
    "is_entry_agent": True,
    
    # Geteilte Tool-Module (aus python/tools/)
    "shared_tools": [
        "bubble_tools",  # enter_bubble, exit_bubble, list_bubbles, etc.
        "idea_tools",    # create_idea, list_ideas, etc.
    ],
    
    # Agent-spezifische Tools
    "agent_tools": [
        "transfer_to_alice",
    ],
}