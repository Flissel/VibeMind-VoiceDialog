"""
Update Rachel Agent for VoiceBridgeV2

This script updates the ElevenLabs agent configuration with the new
VoiceBridgeV2 system prompt where Rachel is a pure voice interface.

Usage:
    python update_rachel_agent.py
"""

import os
import sys
import json
import requests
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Import VoiceBridgeV2 prompts and domain tools
sys.path.insert(0, os.path.dirname(__file__))
from agents.rachel.prompts_v2 import (
    SYSTEM_PROMPT_V2,
    FIRST_MESSAGE_V2,
    SEND_INTENT_TOOL,
    DOMAIN_TOOLS,
    get_all_tool_definitions,
)

# ElevenLabs API configuration
ELEVENLABS_API_URL = "https://api.elevenlabs.io/v1"
VOICE_ID = "21m00Tcm4TlvDq8ikWAM"  # Rachel voice


def get_agent_id() -> str:
    """Get Rachel's agent ID from environment."""
    agent_id = os.getenv("AGENT_MULTIVERSE") or os.getenv("RACHEL_AGENT_ID")
    if not agent_id:
        raise ValueError("AGENT_MULTIVERSE or RACHEL_AGENT_ID not set in .env")
    return agent_id


def get_api_key() -> str:
    """Get ElevenLabs API key from environment."""
    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        raise ValueError("ELEVENLABS_API_KEY not set in .env")
    return api_key


def get_current_agent_config(agent_id: str, api_key: str) -> dict:
    """Fetch current agent configuration from ElevenLabs."""
    url = f"{ELEVENLABS_API_URL}/convai/agents/{agent_id}"
    headers = {"xi-api-key": api_key}

    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        return response.json()
    else:
        print(f"Failed to get agent config: {response.status_code}")
        print(response.text)
        return None


def update_agent_config(agent_id: str, api_key: str, include_tools: bool = True) -> bool:
    """Update the ElevenLabs agent with VoiceBridgeV2 configuration including tools."""
    url = f"{ELEVENLABS_API_URL}/convai/agents/{agent_id}"
    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json",
    }

    # Build prompt config with tools
    prompt_config = {
        "prompt": SYSTEM_PROMPT_V2,
    }

    # Include all 5 domain tools in the prompt
    if include_tools:
        prompt_config["tools"] = get_all_tool_definitions()
        print(f"   Including {len(prompt_config['tools'])} domain tools in prompt")

    # Build update payload
    payload = {
        "conversation_config": {
            "agent": {
                "prompt": prompt_config,
                "first_message": FIRST_MESSAGE_V2,
                "language": "de"  # German
            },
            "tts": {
                "voice_id": VOICE_ID,
                "model_id": "eleven_turbo_v2_5"
            }
        },
        "name": "Rachel (VoiceBridgeV2)",
        "tags": ["vibemind", "voice-bridge-v2", "rachel", "domain-tools"]
    }

    print(f"   Sending PATCH to {url}")
    response = requests.patch(url, headers=headers, json=payload)

    if response.status_code == 200:
        print("Agent updated successfully!")
        return True
    else:
        print(f"Failed to update agent: {response.status_code}")
        print(response.text)
        return False


def add_send_intent_tool(agent_id: str, api_key: str) -> bool:
    """Add the send_intent tool to the agent (legacy, kept for backwards compat)."""
    url = f"{ELEVENLABS_API_URL}/convai/agents/{agent_id}/tools"
    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json",
    }

    response = requests.post(url, headers=headers, json=SEND_INTENT_TOOL)

    if response.status_code in [200, 201]:
        print("send_intent tool added successfully!")
        return True
    elif response.status_code == 409:
        print("send_intent tool already exists")
        return True
    else:
        print(f"Note: Could not add tool via API: {response.status_code}")
        print("You may need to add the tool manually in the ElevenLabs dashboard")
        return False


def add_domain_tools(agent_id: str, api_key: str) -> bool:
    """Add all 5 domain-specific tools to the agent."""
    url = f"{ELEVENLABS_API_URL}/convai/agents/{agent_id}/tools"
    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json",
    }

    all_success = True
    tools = get_all_tool_definitions()

    for tool in tools:
        tool_name = tool.get("name", "unknown")
        response = requests.post(url, headers=headers, json=tool)

        if response.status_code in [200, 201]:
            print(f"  + {tool_name} added successfully!")
        elif response.status_code == 409:
            print(f"  ~ {tool_name} already exists")
        else:
            print(f"  - {tool_name} failed: {response.status_code}")
            all_success = False

    return all_success


def main():
    print("=" * 60)
    print("VibeMind - Update Rachel Agent for VoiceBridgeV2")
    print("=" * 60)

    try:
        agent_id = get_agent_id()
        api_key = get_api_key()
    except ValueError as e:
        print(f"\nError: {e}")
        print("\nPlease ensure these environment variables are set:")
        print("  ELEVENLABS_API_KEY=your_api_key")
        print("  AGENT_MULTIVERSE=your_agent_id (or RACHEL_AGENT_ID)")
        return 1

    print(f"\nAgent ID: {agent_id}")
    print(f"API Key: {api_key[:10]}...")

    # Get current config
    print("\n1. Fetching current agent configuration...")
    current_config = get_current_agent_config(agent_id, api_key)

    if current_config:
        print(f"   Current name: {current_config.get('name', 'Unknown')}")

    # Update agent
    print("\n2. Updating agent with VoiceBridgeV2 configuration...")
    success = update_agent_config(agent_id, api_key)

    if not success:
        print("\nFailed to update agent via API.")
        print("\nManual update instructions:")
        print("=" * 60)
        print("1. Go to: https://elevenlabs.io/app/conversational-ai")
        print("2. Select your Rachel agent")
        print("3. Go to 'Agent' tab")
        print("4. Replace the System Prompt with:")
        print("-" * 40)
        print(SYSTEM_PROMPT_V2[:500] + "...")
        print("-" * 40)
        print("5. Set First Message to:")
        print(f"   {FIRST_MESSAGE_V2}")
        print("6. Go to 'Tools' tab")
        print("7. Add a new tool called 'send_intent' with:")
        print(json.dumps(SEND_INTENT_TOOL["function"], indent=2))
        print("8. Save the agent")
        return 1

    # Tools are now included in the agent update above
    print("\n3. Tools deployed with agent config:")
    for tool in get_all_tool_definitions():
        print(f"   + {tool['name']}")

    print("\n" + "=" * 60)
    print("SUCCESS! Rachel agent updated for VoiceBridgeV2")
    print("=" * 60)
    print("""
Next steps:
1. Verify in ElevenLabs dashboard that the agent has:
   - System prompt updated (mentions 5 domain tools)
   - First message in German
   - 5 domain tools configured:
     * send_bubbles_intent (space/bubble navigation)
     * send_ideas_intent (idea management)
     * send_desktop_intent (desktop automation)
     * send_coding_intent (code generation)
     * send_shuttles_intent (requirements pipeline)

2. Enable VoiceBridgeV2 in .env:
   USE_VOICE_BRIDGE_V2=true

3. Restart Electron app:
   cd electron-app && npm start

4. Test with: "Erstelle einen Testspace" (should use send_bubbles_intent)
""")

    return 0


if __name__ == "__main__":
    sys.exit(main())
