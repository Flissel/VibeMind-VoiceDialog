"""
Alice Agent Configuration

Alice ist der Coordinator Hub - sie delegiert Aufgaben an Spezialisten.
"""

import os


# ElevenLabs Voice: Alice
VOICE_ID = "Xb7hH8MSUJpSbSDYk0k2"

def get_agent_id() -> str:
    """Hole die Agent-ID aus der Umgebungsvariable."""
    agent_id = os.getenv("ALICE_AGENT_ID") or os.getenv("AGENT_PROJECT_MANAGER")
    if not agent_id:
        raise ValueError("ALICE_AGENT_ID oder AGENT_PROJECT_MANAGER nicht in .env gesetzt")
    return agent_id


AGENT_CONFIG = {
    "name": "Alice",
    "slug": "alice",
    "voice_id": VOICE_ID,
    "role": "Coordinator Hub - Delegiert Aufgaben an Adam, Antoni oder zurück zu Rachel",
    
    # Alice kann zu allen anderen weiterleiten
    "can_transfer_to": ["adam", "antoni", "rachel"],
    
    # Alice ist nicht der Entry-Agent
    "is_entry_agent": False,
    
    # Alice hat ihren eigenen festen Space
    "has_fixed_space": True,
    "space_name": "Alice Workspace",
    
    # Geteilte Tool-Module
    "shared_tools": [],
    
    # Agent-spezifische Tools
    "agent_tools": [
        "transfer_to_adam",
        "transfer_to_antoni",
        "transfer_to_rachel",
        "list_projects",
        "get_project_status",
    ],
}