"""
Create ElevenLabs Multiverse Agent

This creates the top-level Multiverse agent that manages bubbles/spaces.
The Multiverse agent uses Rachel voice and has bubble_tools available.
"""

import os
import sys
import requests
from dotenv import load_dotenv

load_dotenv()

def create_multiverse_agent():
    """Create the Multiverse Rachel agent"""

    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        print("ERROR: ELEVENLABS_API_KEY not found in .env")
        return None

    url = "https://api.elevenlabs.io/v1/convai/agents/create"

    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json"
    }

    # Rachel voice - same voice for all agents in multiverse
    rachel_voice_id = "21m00Tcm4TlvDq8ikWAM"

    system_prompt = """You are Rachel, the Multiverse navigator.

You help users manage their idea spaces (bubbles). Each bubble is a separate area where they can develop ideas.

Your tools:
- list_bubbles: Show all spaces the user has created
- create_bubble: Create a new space for ideas
- get_bubble_stats: See how developed a space is (notes, connections)
- score_bubble: Evaluate and score a space based on its content
- promote_bubble: Turn a well-developed space into a project
- delete_bubble: Remove a space
- enter_bubble: Go into a space to work on ideas inside it

When the user wants to:
- "Show my spaces" → Use list_bubbles
- "Create a space for cooking" → Use create_bubble with title "Cooking"
- "Enter my cooking space" → Use enter_bubble with bubble_name "Cooking"
- "How good is this idea?" → Use score_bubble

Be conversational and helpful. Keep responses brief and action-oriented."""

    first_message = "Welcome to your multiverse! You have spaces where you can capture and develop ideas. What would you like to do?"

    payload = {
        "name": "Rachel - Multiverse",
        "conversation_config": {
            "tts": {
                "voice_id": rachel_voice_id,
                "model_id": "eleven_flash_v2"
            },
            "agent": {
                "prompt": {
                    "prompt": system_prompt
                },
                "first_message": first_message,
                "language": "en"
            }
        },
        "tags": ["multiverse", "vibemind"]
    }

    print("Creating Multiverse agent...")
    print(f"  Voice: Rachel ({rachel_voice_id})")
    print(f"  Name: Rachel - Multiverse")
    print()

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()

        result = response.json()
        agent_id = result.get("agent_id")

        if agent_id:
            print("SUCCESS! Multiverse agent created!")
            print()
            print("=" * 60)
            print("Add this line to your .env file:")
            print("=" * 60)
            print()
            print(f"AGENT_MULTIVERSE={agent_id}")
            print()
            return agent_id
        else:
            print("ERROR: No agent_id in response")
            print(f"Response: {result}")
            return None

    except requests.exceptions.RequestException as e:
        print(f"API Error: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response: {e.response.text}")
        return None


if __name__ == "__main__":
    agent_id = create_multiverse_agent()
    sys.exit(0 if agent_id else 1)
