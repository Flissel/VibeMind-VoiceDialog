#!/usr/bin/env python3
"""
Quick API Test - Testet ElevenLabs API-Verbindung
"""

import os
import sys
import json
import requests
from pathlib import Path


def load_env():
    """Load environment variables from .env file."""
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    key, value = line.split('=', 1)
                    os.environ.setdefault(key.strip(), value.strip())


def main():
    load_env()
    
    api_key = os.getenv('ELEVENLABS_API_KEY')
    agent_id = os.getenv('AGENT_RACHEL')
    
    print("=" * 60)
    print("ElevenLabs API Quick Test")
    print("=" * 60)
    print(f"API Key: {api_key[:10]}...")
    print(f"Agent Rachel: {agent_id}")
    
    # Test 1: List Tools
    print("\n1. Testing: GET /v1/convai/tools")
    try:
        response = requests.get(
            "https://api.elevenlabs.io/v1/convai/tools",
            headers={"xi-api-key": api_key},
            timeout=30
        )
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            tools = response.json().get("tools", [])
            print(f"   Tools found: {len(tools)}")
            for t in tools[:5]:
                config = t.get("tool_config", {})
                name = config.get("name", "?")
                tool_type = config.get("type", "?")
                print(f"     - {name} ({tool_type})")
        else:
            print(f"   Error: {response.text[:200]}")
    except Exception as e:
        print(f"   Error: {e}")
    
    # Test 2: Get Agent Info
    print(f"\n2. Testing: GET /v1/convai/agents/{agent_id}")
    try:
        response = requests.get(
            f"https://api.elevenlabs.io/v1/convai/agents/{agent_id}",
            headers={"xi-api-key": api_key},
            timeout=30
        )
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            name = data.get("name", "?")
            config = data.get("conversation_config", {})
            agent = config.get("agent", {})
            prompt = agent.get("prompt", {})
            tools = prompt.get("tools", [])
            tool_ids = prompt.get("tool_ids", [])
            print(f"   Agent name: {name}")
            print(f"   Inline tools: {len(tools)}")
            print(f"   Tool IDs: {len(tool_ids)}")
            for tid in tool_ids[:5]:
                print(f"     - {tid}")
        else:
            print(f"   Error: {response.text[:200]}")
    except Exception as e:
        print(f"   Error: {e}")
    
    # Test 3: Simple Simulate (with short timeout)
    print(f"\n3. Testing: POST /v1/convai/agents/{agent_id}/simulate-conversation")
    print("   (This may take 30-120 seconds...)")
    try:
        response = requests.post(
            f"https://api.elevenlabs.io/v1/convai/agents/{agent_id}/simulate-conversation",
            headers={
                "xi-api-key": api_key,
                "Content-Type": "application/json"
            },
            json={
                "simulation_specification": {
                    "simulated_user_config": {
                        "first_message": "Hallo",
                        "language": "de"
                    },
                    "new_turns_limit": 2
                }
            },
            timeout=120
        )
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            conv = data.get("simulated_conversation", [])
            print(f"   Conversation turns: {len(conv)}")
            for turn in conv[:2]:
                role = turn.get("role", "?")
                msg = turn.get("message", "")[:100]
                print(f"   [{role}] {msg}")
        else:
            print(f"   Error: {response.text[:300]}")
    except requests.exceptions.Timeout:
        print("   TIMEOUT - API took too long to respond")
    except Exception as e:
        print(f"   Error: {e}")
    
    print("\nDone!")


if __name__ == "__main__":
    main()