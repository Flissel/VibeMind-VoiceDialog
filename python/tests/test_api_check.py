#!/usr/bin/env python3
"""Quick API connectivity check."""
import os
import sys
import requests
from pathlib import Path

# Load .env
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

api_key = os.getenv('ELEVENLABS_API_KEY')
print(f"API Key: {api_key[:15]}...")

# Test GET agents
print("\n1. Testing GET /v1/convai/agents...")
try:
    r = requests.get(
        'https://api.elevenlabs.io/v1/convai/agents',
        headers={'xi-api-key': api_key},
        timeout=30
    )
    print(f"   Status: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        agents = data.get('agents', [])
        print(f"   Found {len(agents)} agents")
        for a in agents[:5]:
            print(f"   - {a.get('name', 'Unknown')}: {a.get('agent_id', '?')}")
except Exception as e:
    print(f"   Error: {e}")

# Test GET tools
print("\n2. Testing GET /v1/convai/tools...")
try:
    r = requests.get(
        'https://api.elevenlabs.io/v1/convai/tools',
        headers={'xi-api-key': api_key},
        timeout=30
    )
    print(f"   Status: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        tools = data.get('tools', [])
        print(f"   Found {len(tools)} tools")
        for t in tools[:5]:
            cfg = t.get('tool_config', {})
            print(f"   - {cfg.get('name', 'Unknown')} ({cfg.get('type', '?')})")
except Exception as e:
    print(f"   Error: {e}")

# Test simulate conversation (minimal)
agent_id = os.getenv('AGENT_RACHEL')
if agent_id:
    print(f"\n3. Testing simulate-conversation for Rachel...")
    print(f"   Agent ID: {agent_id}")
    try:
        r = requests.post(
            f'https://api.elevenlabs.io/v1/convai/agents/{agent_id}/simulate-conversation',
            headers={'xi-api-key': api_key, 'Content-Type': 'application/json'},
            json={
                "simulation_specification": {
                    "simulated_user_config": {
                        "first_message": "Hallo"
                    },
                    "new_turns_limit": 2
                }
            },
            timeout=120  # 2 minute timeout for simulation
        )
        print(f"   Status: {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            conv = data.get('simulated_conversation', [])
            print(f"   Conversation turns: {len(conv)}")
            for turn in conv[:3]:
                msg = turn.get('message', '')[:50]
                print(f"   - [{turn.get('role', '?')}] {msg}...")
        else:
            print(f"   Response: {r.text[:200]}")
    except requests.exceptions.Timeout:
        print("   Timeout after 120 seconds - simulation takes too long")
    except Exception as e:
        print(f"   Error: {e}")

print("\nDone.")