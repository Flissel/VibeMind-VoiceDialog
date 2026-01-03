#!/usr/bin/env python3
"""
Test: Rachel Startup Rule
=========================
Tests if Rachel automatically calls list_bubbles at conversation start.

Uses the ElevenLabs simulate-conversation API with a "Hi" message 
to see if Rachel calls list_bubbles as her first action.
"""

import os
import sys
import json
import time
import requests
from pathlib import Path


# Load .env
def load_env():
    env_path = Path(__file__).parent.parent / ".env"
    if not env_path.exists():
        env_path = Path(__file__).parent / ".env"

    if env_path.exists():
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    key, value = line.split('=', 1)
                    os.environ.setdefault(key.strip(), value.strip())


load_env()

API_BASE = "https://api.elevenlabs.io/v1/convai"


def get_api_key():
    key = os.getenv('ELEVENLABS_API_KEY')
    if not key:
        raise ValueError("ELEVENLABS_API_KEY not set")
    return key


def get_rachel_agent_id():
    agent_id = os.getenv("AGENT_MULTIVERSE") or os.getenv("AGENT_RACHEL")
    if not agent_id:
        raise ValueError("AGENT_MULTIVERSE or AGENT_RACHEL not set")
    return agent_id


def simulate_conversation(api_key: str, agent_id: str, first_message: str):
    """Run a simulation and return the response."""
    url = f"{API_BASE}/agents/{agent_id}/simulate-conversation"
    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json"
    }
    
    # Mock all tools so they return results
    tool_mocks = {
        "list_bubbles": {"result_value": '{"bubbles": [{"title": "Test Space", "score": 75}, {"title": "Ideas", "score": 50}]}'},
        "create_bubble": {"result_value": '{"success": true}'},
        "enter_bubble": {"result_value": '{"success": true}'},
        "list_ideas": {"result_value": '{"ideas": []}'},
        "create_idea": {"result_value": '{"success": true}'}
    }
    
    payload = {
        "simulation_specification": {
            "simulated_user_config": {
                "first_message": first_message,
                "language": "de"
            },
            "new_turns_limit": 3,
            "tool_mock_config": tool_mocks
        }
    }
    
    print(f"Sending simulation request...")
    print(f"First message: \"{first_message}\"")
    print()
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=120)
        
        if response.status_code != 200:
            print(f"Error: {response.status_code}")
            print(response.text)
            return None
        
        return response.json()
    
    except Exception as e:
        print(f"Request error: {e}")
        return None


def extract_tool_calls(response):
    """Extract tool names from simulation response."""
    tool_names = []
    
    conversation = response.get("simulated_conversation", [])
    for turn in conversation:
        tool_calls = turn.get("tool_calls", [])
        for call in tool_calls:
            tool_name = call.get("tool_name")
            if tool_name:
                tool_names.append(tool_name)
    
    return tool_names


def print_conversation(response):
    """Print the simulated conversation."""
    conversation = response.get("simulated_conversation", [])
    
    print("=" * 60)
    print("CONVERSATION")
    print("=" * 60)
    
    for turn in conversation:
        role = turn.get("role", "?")
        message = turn.get("message", "")
        tool_calls = turn.get("tool_calls", [])
        
        print(f"\n[{role.upper()}]")
        if message:
            print(f"  {message[:200]}{'...' if len(message) > 200 else ''}")
        
        if tool_calls:
            for call in tool_calls:
                print(f"  → TOOL: {call.get('tool_name')}")
                params = call.get("tool_parameters", {})
                if params:
                    print(f"    Params: {json.dumps(params)}")


def main():
    print("=" * 60)
    print("TEST: Rachel Startup Rule")
    print("=" * 60)
    print()
    print("Testing if Rachel calls list_bubbles at conversation start")
    print()
    
    api_key = get_api_key()
    agent_id = get_rachel_agent_id()
    
    print(f"Agent ID: {agent_id}")
    print(f"API Key: {api_key[:10]}...")
    print()
    
    # Test with a simple greeting - Rachel should call list_bubbles first
    print("-" * 60)
    print("Test 1: Simple greeting 'Hi'")
    print("-" * 60)
    
    response = simulate_conversation(api_key, agent_id, "Hi")
    
    if not response:
        print("Test failed - no response")
        sys.exit(1)
    
    tool_calls = extract_tool_calls(response)
    print_conversation(response)
    
    print()
    print("=" * 60)
    print("RESULT")
    print("=" * 60)
    print(f"Tool calls: {tool_calls}")
    
    if "list_bubbles" in tool_calls:
        first_call = tool_calls[0] if tool_calls else None
        if first_call == "list_bubbles":
            print("\n✅ SUCCESS: list_bubbles was called FIRST!")
        else:
            print(f"\n⚠️ PARTIAL: list_bubbles called, but not first (first was: {first_call})")
    else:
        print("\n❌ FAIL: list_bubbles was NOT called")
        print("   Maybe the agent needs more prompting to trigger the startup rule?")
    
    print()
    print("-" * 60)
    print("Test 2: Empty prompt (just starting)")
    print("-" * 60)
    
    response2 = simulate_conversation(api_key, agent_id, "")
    
    if response2:
        tool_calls2 = extract_tool_calls(response2)
        print_conversation(response2)
        print(f"\nTool calls: {tool_calls2}")
        
        if "list_bubbles" in tool_calls2:
            print("✅ list_bubbles called on empty prompt!")


if __name__ == "__main__":
    main()