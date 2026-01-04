"""
Antoni Agent Configuration

Antoni ist der Coding/Writing Worker.
"""

import os


# ElevenLabs Voice: Antoni
VOICE_ID = "ErXwobaYiN019PkySvjV"

def get_agent_id() -> str:
    """Hole die Agent-ID aus der Umgebungsvariable."""
    agent_id = os.getenv("ANTONI_AGENT_ID") or os.getenv("AGENT_PROJECT_WRITER")
    if not agent_id:
        raise ValueError("ANTONI_AGENT_ID oder AGENT_PROJECT_WRITER nicht in .env gesetzt")
    return agent_id


AGENT_CONFIG = {
    "name": "Antoni",
    "slug": "antoni",
    "voice_id": VOICE_ID,
    "role": "Coding & Writing Worker - Schreibt Code und Dokumentation",
    
    # Antoni berichtet zurück an Alice
    "can_transfer_to": ["alice"],
    
    "is_entry_agent": False,
    
    # Antoni hat seinen eigenen festen Space (wird automatisch erstellt)
    "has_fixed_space": True,
    "space_name": "Antoni Workshop",
    
    # Geteilte Tool-Module (Ideen-Tools für Notizen)
    "shared_tools": [
        "idea_tools",  # Kann Notizen/Ideen erstellen
    ],
    
    # Agent-spezifische Tools
    "agent_tools": [
        "transfer_to_alice",
        "write_code",
        "create_file",
        "update_file",
        "generate_readme",
    ],
}