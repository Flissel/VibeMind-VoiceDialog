#!/usr/bin/env python3
"""
Deploy Transfer-Tools to ElevenLabs Agents

Creates client tools for agent transfers and links them to the appropriate agents.
Transfer-Tools execute in Python and signal the backend to switch agents.
"""

import os
import sys
import json
import requests
from pathlib import Path
from typing import Dict, Any, List


# ============================================================================
# CONFIGURATION
# ============================================================================

API_BASE = "https://api.elevenlabs.io/v1/convai"


def load_env():
    """Load environment variables from .env file."""
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


def get_api_key() -> str:
    """Get ElevenLabs API key from environment."""
    key = os.getenv('ELEVENLABS_API_KEY')
    if not key:
        raise ValueError("ELEVENLABS_API_KEY not set in .env")
    return key


def get_agent_id(name: str) -> str:
    """Get agent ID from environment."""
    env_var = f"AGENT_{name.upper()}"
    agent_id = os.getenv(env_var)
    if not agent_id:
        raise ValueError(f"{env_var} not set in .env")
    return agent_id


# ============================================================================
# API FUNCTIONS
# ============================================================================

def create_tool(api_key: str, tool_config: Dict[str, Any]) -> Dict[str, Any]:
    """Create a tool via the ElevenLabs API."""
    url = f"{API_BASE}/tools"
    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json"
    }
    payload = {"tool_config": tool_config}
    response = requests.post(url, headers=headers, json=payload)

    if response.status_code != 200:
        print(f"Error creating tool: {response.status_code}")
        print(response.text)
        response.raise_for_status()

    return response.json()


def list_tools(api_key: str) -> List[Dict[str, Any]]:
    """List all tools."""
    url = f"{API_BASE}/tools"
    headers = {"xi-api-key": api_key}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json().get("tools", [])


def delete_tool(api_key: str, tool_id: str) -> bool:
    """Delete a tool."""
    url = f"{API_BASE}/tools/{tool_id}"
    headers = {"xi-api-key": api_key}
    response = requests.delete(url, headers=headers)
    return response.status_code == 200


def get_agent(api_key: str, agent_id: str) -> Dict[str, Any]:
    """Get agent configuration."""
    url = f"{API_BASE}/agents/{agent_id}"
    headers = {"xi-api-key": api_key}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()


def update_agent_tools(api_key: str, agent_id: str, tool_ids: List[str]) -> Dict[str, Any]:
    """Update agent to link tools."""
    url = f"{API_BASE}/agents/{agent_id}"
    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json"
    }

    # Get current agent config to preserve existing tool_ids
    current = get_agent(api_key, agent_id)
    current_tool_ids = []
    try:
        current_tool_ids = current.get("conversation_config", {}).get("agent", {}).get("prompt", {}).get("tool_ids", [])
    except (KeyError, TypeError):
        pass

    # Merge new tools with existing (avoid duplicates)
    all_tool_ids = list(set(current_tool_ids + tool_ids))

    payload = {
        "conversation_config": {
            "agent": {
                "prompt": {
                    "tool_ids": all_tool_ids
                }
            }
        }
    }

    response = requests.patch(url, headers=headers, json=payload)
    if response.status_code != 200:
        print(f"Error updating agent: {response.status_code}")
        print(response.text)
        response.raise_for_status()

    return response.json()


# ============================================================================
# TRANSFER TOOL DEFINITIONS
# ============================================================================

# Tools for Rachel (Multiverse Navigator) 
RACHEL_TRANSFER_TOOLS = [
    {
        "type": "client",
        "name": "transfer_to_alice",
        "description": "Transfer the conversation to Alice, the coordinator. Use when user needs help with work tasks, coding, or desktop operations. Say 'Ich verbinde dich mit Alice' before calling.",
        "expects_response": False,  # Async - don't wait for response
        "response_timeout_secs": 5,
        "parameters": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Why transferring to Alice"
                }
            }
        }
    }
]

# Tools for Alice (Coordinator Hub)
ALICE_TRANSFER_TOOLS = [
    {
        "type": "client",
        "name": "transfer_to_adam",
        "description": "Transfer to Adam for desktop operations, file management, system tasks. Say 'Ich verbinde dich mit Adam' before calling.",
        "expects_response": False,  # Async - don't wait for response
        "response_timeout_secs": 5,
        "parameters": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Why transferring to Adam"
                }
            }
        }
    },
    {
        "type": "client",
        "name": "transfer_to_antoni",
        "description": "Transfer to Antoni for coding, programming, writing tasks. Say 'Ich verbinde dich mit Antoni' before calling.",
        "expects_response": False,  # Async - don't wait for response
        "response_timeout_secs": 5,
        "parameters": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Why transferring to Antoni"
                }
            }
        }
    },
    {
        "type": "client",
        "name": "transfer_to_rachel",
        "description": "Transfer to Rachel for creative brainstorming, idea exploration, or multiverse navigation. Say 'Ich verbinde dich mit Rachel' before calling.",
        "expects_response": False,  # Async - don't wait for response
        "response_timeout_secs": 5,
        "parameters": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Why transferring to Rachel"
                }
            }
        }
    }
]

# Tools for Adam (Desktop Worker)
ADAM_TRANSFER_TOOLS = [
    {
        "type": "client",
        "name": "transfer_to_alice",
        "description": "Transfer back to Alice when desktop task is complete or user needs different help. Say 'Ich verbinde dich zurueck mit Alice' before calling.",
        "expects_response": False,  # Async - don't wait for response
        "response_timeout_secs": 5,
        "parameters": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Why transferring to Alice"
                }
            }
        }
    }
]

# Tools for Antoni (Coding Worker)
ANTONI_TRANSFER_TOOLS = [
    {
        "type": "client",
        "name": "transfer_to_alice",
        "description": "Transfer back to Alice when coding task is complete or user needs different help. Say 'Ich verbinde dich zurueck mit Alice' before calling.",
        "expects_response": False,  # Async - don't wait for response
        "response_timeout_secs": 5,
        "parameters": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Why transferring to Alice"
                }
            }
        }
    }
]


# ============================================================================
# DEPLOYMENT FUNCTIONS
# ============================================================================

def cleanup_transfer_tools(api_key: str):
    """Remove existing transfer tools to avoid duplicates."""
    print("\nCleaning up existing transfer tools...")
    
    tools = list_tools(api_key)
    transfer_names = ["transfer_to_alice", "transfer_to_adam", "transfer_to_antoni", "transfer_to_rachel"]
    
    deleted = 0
    for tool in tools:
        config = tool.get("tool_config", {})
        name = config.get("name", "")
        if name in transfer_names:
            tool_id = tool.get("id") or tool.get("tool_id")
            if tool_id:
                print(f"  Deleting: {name} ({tool_id})")
                delete_tool(api_key, tool_id)
                deleted += 1
    
    print(f"  Deleted {deleted} existing transfer tools")
    return deleted


def deploy_tools_to_agent(api_key: str, tools: List[Dict], agent_name: str) -> List[str]:
    """Deploy tools and link them to an agent."""
    agent_id = get_agent_id(agent_name)
    
    print(f"\nDeploying to {agent_name} ({agent_id})...")
    
    created_ids = []
    for tool_config in tools:
        tool_name = tool_config["name"]
        print(f"  Creating: {tool_name}...")
        
        try:
            result = create_tool(api_key, tool_config)
            tool_id = result.get("id") or result.get("tool_id")
            
            if tool_id:
                created_ids.append(tool_id)
                print(f"    -> {tool_id}")
            else:
                print(f"    Warning: No tool ID returned")
        except Exception as e:
            print(f"    Error: {e}")
    
    if created_ids:
        print(f"  Linking {len(created_ids)} tools to agent...")
        try:
            update_agent_tools(api_key, agent_id, created_ids)
            print(f"    Linked!")
        except Exception as e:
            print(f"    Error linking: {e}")
    
    return created_ids


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Main entry point."""
    load_env()
    
    try:
        api_key = get_api_key()
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)
    
    print("=" * 60)
    print("Transfer-Tools Deployment")
    print("=" * 60)
    print(f"API Key: {api_key[:10]}...")
    
    # Check required agent IDs
    agents = ["RACHEL", "ALICE", "ADAM", "ANTONI"]
    print("\nAgent IDs:")
    for name in agents:
        try:
            agent_id = get_agent_id(name)
            print(f"  {name}: {agent_id}")
        except ValueError:
            print(f"  {name}: NOT SET!")
            print(f"\nError: AGENT_{name} must be set in .env")
            sys.exit(1)
    
    # Cleanup existing transfer tools
    cleanup_transfer_tools(api_key)
    
    # Deploy to each agent
    all_ids = []
    
    rachel_ids = deploy_tools_to_agent(api_key, RACHEL_TRANSFER_TOOLS, "RACHEL")
    all_ids.extend(rachel_ids)
    
    alice_ids = deploy_tools_to_agent(api_key, ALICE_TRANSFER_TOOLS, "ALICE")
    all_ids.extend(alice_ids)
    
    adam_ids = deploy_tools_to_agent(api_key, ADAM_TRANSFER_TOOLS, "ADAM")
    all_ids.extend(adam_ids)
    
    antoni_ids = deploy_tools_to_agent(api_key, ANTONI_TRANSFER_TOOLS, "ANTONI")
    all_ids.extend(antoni_ids)
    
    # Summary
    print("\n" + "=" * 60)
    print("DEPLOYMENT COMPLETE")
    print("=" * 60)
    print(f"Rachel: {len(rachel_ids)} tools (transfer_to_alice)")
    print(f"Alice:  {len(alice_ids)} tools (transfer_to_adam, transfer_to_antoni, transfer_to_rachel)")
    print(f"Adam:   {len(adam_ids)} tools (transfer_to_alice)")
    print(f"Antoni: {len(antoni_ids)} tools (transfer_to_alice)")
    print(f"Total:  {len(all_ids)} tools deployed")
    
    if all_ids:
        print("\nTool IDs:")
        for tid in all_ids:
            print(f"  - {tid}")


if __name__ == "__main__":
    main()