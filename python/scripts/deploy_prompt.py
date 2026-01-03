#!/usr/bin/env python3
"""
Deploy Rachel System-Prompt to ElevenLabs

Updates the Multiverse/Rachel agent's system prompt via PATCH API.

Usage:
    python deploy_prompt.py          # Interactive mode with confirmation
    python deploy_prompt.py --force  # Auto-deploy without confirmation
"""

import os
import sys
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

# Import the prompt
from agents.rachel.prompts import SYSTEM_PROMPT, FIRST_MESSAGE

# Configuration
API_BASE = "https://api.elevenlabs.io/v1/convai"


def get_api_key() -> str:
    """Get ElevenLabs API key."""
    key = os.getenv('ELEVENLABS_API_KEY')
    if not key:
        raise ValueError("ELEVENLABS_API_KEY not set")
    return key


def get_agent_id() -> str:
    """Get Rachel/Multiverse agent ID."""
    agent_id = os.getenv("AGENT_MULTIVERSE") or os.getenv("AGENT_RACHEL")
    if not agent_id:
        raise ValueError("AGENT_MULTIVERSE or AGENT_RACHEL not set in .env")
    return agent_id


def get_current_agent(api_key: str, agent_id: str) -> dict:
    """Get current agent configuration."""
    url = f"{API_BASE}/agents/{agent_id}"
    headers = {"xi-api-key": api_key}
    
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()


def update_agent_prompt(api_key: str, agent_id: str, system_prompt: str, first_message: str) -> dict:
    """
    Update agent's system prompt and first message via PATCH.
    
    PATCH /v1/convai/agents/{agent_id}
    """
    url = f"{API_BASE}/agents/{agent_id}"
    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json"
    }
    
    payload = {
        "conversation_config": {
            "agent": {
                "prompt": {
                    "prompt": system_prompt
                },
                "first_message": first_message
            }
        }
    }
    
    response = requests.patch(url, headers=headers, json=payload)
    
    if response.status_code != 200:
        print(f"Error: {response.status_code}")
        print(response.text)
        response.raise_for_status()
    
    return response.json()


def main():
    """Deploy the prompt to ElevenLabs."""
    force_mode = "--force" in sys.argv or "-f" in sys.argv
    
    print("=" * 60)
    print("Deploy Rachel System-Prompt to ElevenLabs")
    print("=" * 60)
    
    try:
        api_key = get_api_key()
        agent_id = get_agent_id()
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)
    
    print(f"\nAgent ID: {agent_id}")
    print(f"API Key: {api_key[:10]}...")
    
    # Show current prompt (abbreviated)
    print("\n--- Current Agent Config ---")
    current = get_current_agent(api_key, agent_id)
    current_prompt = current.get("conversation_config", {}).get("agent", {}).get("prompt", {}).get("prompt", "")
    current_first = current.get("conversation_config", {}).get("agent", {}).get("first_message", "")
    
    print(f"Current prompt (first 100 chars): {current_prompt[:100]}...")
    print(f"Current first_message: {current_first}")
    
    # Show new prompt
    print("\n--- New Prompt ---")
    print(f"New prompt (first 200 chars): {SYSTEM_PROMPT[:200]}...")
    print(f"New first_message: {FIRST_MESSAGE}")
    
    # Confirm (skip if force mode)
    if not force_mode:
        print("\n" + "-" * 40)
        confirm = input("Deploy this prompt? (y/n): ").strip().lower()
        
        if confirm != 'y':
            print("Aborted.")
            sys.exit(0)
    else:
        print("\n[Force mode - auto-deploying]")
    
    # Deploy
    print("\nDeploying...")
    result = update_agent_prompt(api_key, agent_id, SYSTEM_PROMPT, FIRST_MESSAGE)
    
    print("\n" + "=" * 60)
    print("SUCCESS! Prompt deployed.")
    print("=" * 60)
    
    # Verify
    print("\nVerifying...")
    updated = get_current_agent(api_key, agent_id)
    new_prompt = updated.get("conversation_config", {}).get("agent", {}).get("prompt", {}).get("prompt", "")
    
    if "STARTUP-REGEL" in new_prompt:
        print("✓ STARTUP-REGEL found in deployed prompt!")
    else:
        print("⚠ Warning: STARTUP-REGEL not found in prompt")
    
    print(f"\nUpdated prompt starts with: {new_prompt[:150]}...")


if __name__ == "__main__":
    main()