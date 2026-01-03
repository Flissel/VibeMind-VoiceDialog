#!/usr/bin/env python3
"""
Deploy SuperMemory Tools to ElevenLabs

Deploys only the SuperMemory tools (search_memory, store_to_supermemory, etc.)
without touching other existing tools.
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
# SUPERMEMORY TOOL DEFINITIONS
# ============================================================================

SUPERMEMORY_TOOLS = [
    {
        "type": "client",
        "name": "search_memory",
        "description": "Search SuperMemory for relevant context. Use semantic search to find memories from past conversations. Use when user asks: Was weisst du noch ueber...?, Erinnere dich an..., Was haben wir ueber ... besprochen?, Suche nach Informationen ueber...",
        "expects_response": True,
        "response_timeout_secs": 15,
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "What to search for in memory"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum results to return (default: 5)"
                }
            },
            "required": ["query"]
        }
    },
    {
        "type": "client",
        "name": "store_to_supermemory",
        "description": "Store important information in SuperMemory for later recall. Use to remember facts, preferences, or context that should persist. Use when user says: Merke dir dass..., Speichere dass..., Erinnere dich dass ich..., Notiere fuer spaeter...",
        "expects_response": True,
        "response_timeout_secs": 10,
        "parameters": {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "The information to store"
                },
                "category": {
                    "type": "string",
                    "description": "Category: preference, fact, project, or note (default: note)"
                }
            },
            "required": ["content"]
        }
    },
    {
        "type": "client",
        "name": "recall_conversation",
        "description": "Recall conversation history from current session. Use when user asks: Was haben wir bisher besprochen?, Zusammenfassung unseres Gespraechs, Worueber haben wir geredet?",
        "expects_response": True,
        "response_timeout_secs": 10,
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "type": "client",
        "name": "clear_session_memory",
        "description": "Start a fresh session with new context. Use when user says: Vergiss diese Session, Starte neue Session, Reset Kontext.",
        "expects_response": True,
        "response_timeout_secs": 5,
        "parameters": {
            "type": "object",
            "properties": {}
        }
    }
]


# ============================================================================
# MAIN
# ============================================================================

def cleanup_supermemory_tools(api_key: str) -> int:
    """Remove existing SuperMemory tools to avoid duplicates."""
    print("\nCleaning up existing SuperMemory tools...")
    
    tools = list_tools(api_key)
    supermemory_names = [t["name"] for t in SUPERMEMORY_TOOLS]
    
    deleted = 0
    for tool in tools:
        config = tool.get("tool_config", {})
        name = config.get("name", "")
        if name in supermemory_names:
            tool_id = tool.get("id") or tool.get("tool_id")
            if tool_id:
                print(f"  Deleting existing: {name} ({tool_id})")
                if delete_tool(api_key, tool_id):
                    deleted += 1
    
    print(f"  Deleted {deleted} existing SuperMemory tools")
    return deleted


def main():
    """Main entry point."""
    load_env()

    try:
        api_key = get_api_key()
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)

    # Get Rachel/Multiverse agent ID
    agent_id = os.getenv("AGENT_MULTIVERSE") or os.getenv("AGENT_RACHEL")
    if not agent_id:
        print("Error: AGENT_MULTIVERSE or AGENT_RACHEL not set in .env")
        sys.exit(1)

    print("=" * 60)
    print("SuperMemory Tools Deployment")
    print("=" * 60)
    print(f"API Key: {api_key[:10]}...")
    print(f"Agent ID: {agent_id}")
    print()

    # Check if SUPERMEMORY_API_KEY is set
    supermemory_key = os.getenv("SUPERMEMORY_API_KEY")
    if not supermemory_key:
        print("WARNING: SUPERMEMORY_API_KEY not set in .env")
        print("SuperMemory tools will fail at runtime without this key!")
        print()
        response = input("Continue anyway? (y/N): ")
        if response.lower() != 'y':
            print("Aborted.")
            sys.exit(0)

    # Clean up existing tools
    cleanup_supermemory_tools(api_key)

    # Deploy new tools
    print("\nDeploying SuperMemory tools...")
    created_ids = []

    for tool_config in SUPERMEMORY_TOOLS:
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

    # Link tools to agent
    if created_ids:
        print(f"\nLinking {len(created_ids)} tools to Rachel agent...")
        try:
            update_agent_tools(api_key, agent_id, created_ids)
            print("  Linked successfully!")
        except Exception as e:
            print(f"  Error linking: {e}")

    # Summary
    print("\n" + "=" * 60)
    print("DEPLOYMENT COMPLETE")
    print("=" * 60)
    print(f"SuperMemory Tools: {len(created_ids)} created")
    print()
    print("Tools deployed:")
    for tool in SUPERMEMORY_TOOLS:
        print(f"  - {tool['name']}: {tool['description'][:60]}...")
    
    if created_ids:
        print("\nTool IDs:")
        for tid in created_ids:
            print(f"  - {tid}")

    print("\n" + "=" * 60)
    print("Voice Commands to test:")
    print("=" * 60)
    print("  - 'Merke dir dass ich gerne Python programmiere'")
    print("  - 'Was weisst du noch ueber mich?'")
    print("  - 'Was haben wir bisher besprochen?'")


if __name__ == "__main__":
    main()