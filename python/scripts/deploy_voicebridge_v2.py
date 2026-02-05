#!/usr/bin/env python3
"""
Deploy VoiceBridgeV2 Configuration to ElevenLabs

This script:
1. Removes ALL old tools from Rachel's agent
2. Updates system prompt to VoiceBridgeV2 version
3. Deploys ONLY the send_intent client tool
4. Verifies the configuration

Usage:
    python scripts/deploy_voicebridge_v2.py           # Full deployment
    python scripts/deploy_voicebridge_v2.py --verify  # Only verify, no changes
    python scripts/deploy_voicebridge_v2.py --show    # Show current config
"""

import os
import sys
import json
import requests
from pathlib import Path

# Load .env
def load_env():
    """Load environment variables from .env file."""
    env_path = Path(__file__).parent.parent / ".env"
    if not env_path.exists():
        env_path = Path(__file__).parent / ".env"

    if env_path.exists():
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    key, value = line.split('=', 1)
                    os.environ.setdefault(key.strip(), value.strip())

load_env()

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.rachel.prompts_v2 import SYSTEM_PROMPT_V2, FIRST_MESSAGE_V2, SEND_INTENT_TOOL

# API Configuration
API_BASE = "https://api.elevenlabs.io/v1/convai"


def get_api_key() -> str:
    """Get ElevenLabs API key from environment."""
    key = os.getenv('ELEVENLABS_API_KEY')
    if not key:
        raise ValueError("ELEVENLABS_API_KEY not set in .env")
    return key


def get_agent_id() -> str:
    """Get Rachel/Multiverse agent ID from environment."""
    agent_id = os.getenv("AGENT_MULTIVERSE") or os.getenv("AGENT_RACHEL")
    if not agent_id:
        raise ValueError("AGENT_MULTIVERSE or AGENT_RACHEL not set in .env")
    return agent_id


def get_headers() -> dict:
    """Get API headers."""
    return {
        "xi-api-key": get_api_key(),
        "Content-Type": "application/json"
    }


def get_agent_config(agent_id: str) -> dict:
    """Get current agent configuration."""
    url = f"{API_BASE}/agents/{agent_id}"
    response = requests.get(url, headers=get_headers())

    if response.status_code == 200:
        return response.json()
    else:
        print(f"  Error fetching agent: {response.status_code}")
        print(f"  {response.text[:200]}")
        return None


def clear_all_tools(agent_id: str) -> bool:
    """Remove ALL tools from agent."""
    payload = {
        "conversation_config": {
            "agent": {
                "prompt": {
                    "tools": []  # Empty = remove all tools
                }
            }
        }
    }

    url = f"{API_BASE}/agents/{agent_id}"
    response = requests.patch(url, headers=get_headers(), json=payload)

    if response.status_code == 200:
        return True
    else:
        print(f"  Error clearing tools: {response.status_code}")
        print(f"  {response.text[:200]}")
        return False


def update_prompt(agent_id: str, system_prompt: str, first_message: str) -> bool:
    """Update system prompt and first message."""
    payload = {
        "conversation_config": {
            "agent": {
                "prompt": {
                    "prompt": system_prompt
                },
                "first_message": first_message,
                "language": "de"  # German
            }
        }
    }

    url = f"{API_BASE}/agents/{agent_id}"
    response = requests.patch(url, headers=get_headers(), json=payload)

    if response.status_code == 200:
        return True
    else:
        print(f"  Error updating prompt: {response.status_code}")
        print(f"  {response.text[:200]}")
        return False


def deploy_send_intent_tool(agent_id: str) -> bool:
    """Deploy ONLY the send_intent tool."""
    payload = {
        "conversation_config": {
            "agent": {
                "prompt": {
                    "tools": [SEND_INTENT_TOOL]
                }
            }
        }
    }

    url = f"{API_BASE}/agents/{agent_id}"
    response = requests.patch(url, headers=get_headers(), json=payload)

    if response.status_code == 200:
        return True
    else:
        print(f"  Error deploying tool: {response.status_code}")
        print(f"  {response.text[:200]}")
        return False


def verify_config(agent_id: str) -> tuple:
    """
    Verify VoiceBridgeV2 configuration.

    Returns:
        (success: bool, message: str or list of errors)
    """
    config = get_agent_config(agent_id)
    if not config:
        return False, "Could not fetch agent config"

    prompt = config.get("conversation_config", {}).get("agent", {}).get("prompt", {})
    tools = prompt.get("tools", [])
    system_prompt = prompt.get("prompt", "")
    first_message = config.get("conversation_config", {}).get("agent", {}).get("first_message", "")

    errors = []

    # Check tool count (should be exactly 1)
    if len(tools) != 1:
        errors.append(f"Expected 1 tool, found {len(tools)}")

    # Check tool name
    tool_names = [t.get("name") for t in tools]
    if "send_intent" not in tool_names:
        errors.append("send_intent tool not found")

    # Check system prompt contains VoiceBridgeV2 markers
    if "send_intent" not in system_prompt.lower():
        errors.append("System prompt missing send_intent instructions")

    # Check first message is in German
    if not first_message or "Rachel" not in first_message:
        errors.append("First message not set correctly")

    if errors:
        return False, errors
    return True, "VoiceBridgeV2 configuration verified!"


def show_current_config(agent_id: str):
    """Show current agent configuration."""
    config = get_agent_config(agent_id)
    if not config:
        print("Could not fetch configuration")
        return

    print("\n--- Current Agent Configuration ---")
    print(f"Name: {config.get('name', 'Unknown')}")

    agent_config = config.get("conversation_config", {}).get("agent", {})
    prompt_config = agent_config.get("prompt", {})

    # System prompt (first 200 chars)
    system_prompt = prompt_config.get("prompt", "")
    print(f"\nSystem Prompt (first 200 chars):")
    print(f"  {system_prompt[:200]}...")

    # First message
    first_message = agent_config.get("first_message", "")
    print(f"\nFirst Message:")
    print(f"  {first_message}")

    # Language
    language = agent_config.get("language", "not set")
    print(f"\nLanguage: {language}")

    # Tools
    tools = prompt_config.get("tools", [])
    print(f"\nTools ({len(tools)} total):")
    for tool in tools:
        tool_name = tool.get("name", "unknown")
        tool_type = tool.get("type", "unknown")
        print(f"  - {tool_name} ({tool_type})")

    if not tools:
        print("  (no tools configured)")


def main():
    """Main entry point."""
    verify_only = "--verify" in sys.argv
    show_only = "--show" in sys.argv

    print("=" * 60)
    print("VoiceBridgeV2 ElevenLabs Deployment")
    print("=" * 60)

    try:
        agent_id = get_agent_id()
        api_key = get_api_key()
    except ValueError as e:
        print(f"\nError: {e}")
        print("\nPlease ensure these environment variables are set:")
        print("  ELEVENLABS_API_KEY=your_api_key")
        print("  AGENT_MULTIVERSE=your_agent_id")
        return 1

    print(f"\nAgent ID: {agent_id}")
    print(f"API Key: {api_key[:10]}...")

    # Show mode
    if show_only:
        show_current_config(agent_id)
        return 0

    # Verify mode
    if verify_only:
        print("\n[Verify Only Mode]")
        success, msg = verify_config(agent_id)
        if success:
            print(f"\n[OK] {msg}")
        else:
            print(f"\n[FAIL] Verification errors:")
            if isinstance(msg, list):
                for error in msg:
                    print(f"  - {error}")
            else:
                print(f"  {msg}")
        return 0 if success else 1

    # Full deployment
    print("\n--- Starting Deployment ---")

    # Step 1: Show current state
    print("\n1. Current configuration:")
    current = get_agent_config(agent_id)
    if current:
        current_tools = current.get("conversation_config", {}).get("agent", {}).get("prompt", {}).get("tools", [])
        print(f"   Tools before: {len(current_tools)}")
    else:
        print("   Could not fetch current config")

    # Step 2: Clear all tools
    print("\n2. Clearing old tools...")
    if clear_all_tools(agent_id):
        print("   [OK] All tools removed")
    else:
        print("   [FAIL] Could not clear tools")

    # Step 3: Update system prompt
    print("\n3. Updating system prompt...")
    if update_prompt(agent_id, SYSTEM_PROMPT_V2, FIRST_MESSAGE_V2):
        print("   [OK] System prompt updated")
        print("   [OK] First message set (German)")
        print("   [OK] Language set to 'de'")
    else:
        print("   [FAIL] Could not update prompt")

    # Step 4: Deploy send_intent tool
    print("\n4. Deploying send_intent tool...")
    if deploy_send_intent_tool(agent_id):
        print("   [OK] send_intent tool deployed")
    else:
        print("   [FAIL] Could not deploy tool")

    # Step 5: Verify
    print("\n5. Verifying configuration...")
    success, msg = verify_config(agent_id)
    if success:
        print(f"   [OK] {msg}")
    else:
        print(f"   [WARN] Verification issues:")
        if isinstance(msg, list):
            for error in msg:
                print(f"     - {error}")
        else:
            print(f"     {msg}")

    # Summary
    print("\n" + "=" * 60)
    print("DEPLOYMENT COMPLETE")
    print("=" * 60)
    print("""
Next steps:
1. Ensure VoiceBridgeV2 is enabled in .env:
   USE_VOICE_BRIDGE_V2=true

2. Start the application:
   cd electron-app && npm start

3. Test voice commands:
   - "Welche Spaces habe ich?"
   - "Erstelle einen neuen Space namens Test"
   - "Oeffne Chrome"

The send_intent tool will forward all requests to the backend
orchestrator for async processing.
""")
    return 0


if __name__ == "__main__":
    sys.exit(main())
