"""
Adam Agent Configuration

Adam is the Desktop Worker - seeds tasks to the Claude worker for execution.
"""

import os


# ElevenLabs Voice: Adam
VOICE_ID = "pNInz6obpgDQGcFmaJgB"

def get_agent_id() -> str:
    """Get agent ID from environment variable."""
    agent_id = os.getenv("ADAM_AGENT_ID") or os.getenv("AGENT_DESKTOP_WORKER")
    if not agent_id:
        raise ValueError("ADAM_AGENT_ID or AGENT_DESKTOP_WORKER not set in .env")
    return agent_id


AGENT_CONFIG = {
    "name": "Adam",
    "slug": "adam",
    "voice_id": VOICE_ID,
    "role": "Desktop Worker - Seeds tasks to Claude worker for execution",

    # Adam reports back to Alice
    "can_transfer_to": ["alice"],

    "is_entry_agent": False,

    # Adam has his own fixed space (created automatically)
    "has_fixed_space": True,
    "space_name": "Adam Desktop",

    # Shared tool modules
    "shared_tools": [],

    # Adam has two tools: seed_task and get_worker_report
    "agent_tools": [
        "seed_task",
        "get_worker_report",
    ],
}
