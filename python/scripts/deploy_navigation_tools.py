#!/usr/bin/env python3
"""
Deploy Navigation Tools to ElevenLabs Multiverse Agent

Creates voice navigation tools for controlling the VibeMind UI:
- navigate_to_space: Move camera to Ideas/Projects/Desktop space
- select_item: Select next/previous bubble or project
- select_by_name: Select item by name
- enter_selection: Enter the selected item
- exit_view: Exit current view

These tools enable hands-free navigation of the multiverse.
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
        with open(env_path, 'r') as f:
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


def get_multiverse_agent_id() -> str:
    """Get the Multiverse (Rachel) agent ID from environment."""
    agent_id = os.getenv("AGENT_MULTIVERSE") or os.getenv("AGENT_RACHEL")
    if not agent_id:
        raise ValueError("AGENT_MULTIVERSE or AGENT_RACHEL not set in .env")
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
# NAVIGATION TOOLS DEFINITIONS
# ============================================================================

NAVIGATION_TOOLS = [
    {
        "type": "client",
        "name": "navigate_to_space",
        "description": """Navigate to a specific space in the multiverse with animated camera movement.
Use when user says:
- Go to Ideas Space / Show Ideas / Bubbles
- Go to Projects Space / Show Projects / DNA
- Go to Desktop Space / Show Desktop / Adam's Space
- Navigate to [space name]
- Take me to [space name]""",
        "expects_response": True,
        "response_timeout_secs": 5,
        "parameters": {
            "type": "object",
            "properties": {
                "space": {
                    "type": "string",
                    "description": "Target space: 'ideas' (bubbles/Rachel), 'projects' (DNA helix/Sofia), or 'desktop' (light planet/Adam)"
                }
            },
            "required": ["space"]
        }
    },
    {
        "type": "client",
        "name": "select_item",
        "description": """Select the next or previous item (bubble/project) in current space.
Use when user says:
- Next bubble / Next project
- Previous bubble / Previous one
- Select next / Select previous
- Go to next / Go forward
- Go back / Go to previous""",
        "expects_response": True,
        "response_timeout_secs": 5,
        "parameters": {
            "type": "object",
            "properties": {
                "direction": {
                    "type": "string",
                    "description": "'next' or 'previous' (default: next)"
                },
                "space_type": {
                    "type": "string",
                    "description": "Item type: 'bubble' or 'project' (auto-detected from current space)"
                }
            }
        }
    },
    {
        "type": "client",
        "name": "select_by_name",
        "description": """Select a bubble or project by its name.
Use when user says:
- Select [name] bubble
- Go to [name] project
- Focus on [name]
- Find [name]
- Show me [name]""",
        "expects_response": True,
        "response_timeout_secs": 5,
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Name or partial name of the item to select"
                },
                "index": {
                    "type": "integer",
                    "description": "Alternative: select by number (1-based)"
                }
            }
        }
    },
    {
        "type": "client",
        "name": "enter_selection",
        "description": """Enter the currently selected bubble or project with zoom animation.
Use when user says:
- Enter / Enter this
- Go inside / Open this
- Let's go in / Dive in
- Open / Show details""",
        "expects_response": True,
        "response_timeout_secs": 5,
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "type": "client",
        "name": "exit_view",
        "description": """Exit the current bubble/project view and return to space overview.
Use when user says:
- Go back / Back
- Exit / Leave
- Return / Return to overview
- Close this / Back out""",
        "expects_response": True,
        "response_timeout_secs": 5,
        "parameters": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "type": "client",
        "name": "get_current_view",
        "description": """Get information about where you currently are in the multiverse.
Use when user says:
- Where am I?
- What space is this?
- What's selected?
- Current location""",
        "expects_response": True,
        "response_timeout_secs": 5,
        "parameters": {
            "type": "object",
            "properties": {}
        }
    }
]


# ============================================================================
# DEPLOYMENT FUNCTIONS
# ============================================================================

def deploy_tools(api_key: str, tools: List[Dict], agent_id: str, tool_set_name: str) -> List[str]:
    """Deploy a set of tools and link them to an agent."""
    print(f"\n{'='*60}")
    print(f"Deploying {tool_set_name} to agent {agent_id}")
    print('='*60)

    created_ids = []

    for tool_config in tools:
        tool_name = tool_config["name"]
        print(f"\n  Creating tool: {tool_name}...")

        try:
            result = create_tool(api_key, tool_config)
            tool_id = result.get("id") or result.get("tool_id")

            if tool_id:
                created_ids.append(tool_id)
                print(f"    ✅ Created: {tool_id}")
            else:
                print(f"    ⚠️ Warning: No tool ID in response")
        except Exception as e:
            print(f"    ❌ Error: {e}")

    if created_ids:
        print(f"\n  Linking {len(created_ids)} tools to agent...")
        try:
            update_agent_tools(api_key, agent_id, created_ids)
            print(f"    ✅ Linked successfully!")
        except Exception as e:
            print(f"    ❌ Error linking tools: {e}")

    return created_ids


def cleanup_existing_navigation_tools(api_key: str):
    """Remove any existing navigation tools before deploying new ones."""
    print("\nChecking for existing navigation tools...")
    
    tools = list_tools(api_key)
    nav_tool_names = [t["name"] for t in NAVIGATION_TOOLS]
    
    deleted = 0
    for tool in tools:
        config = tool.get("tool_config", {})
        name = config.get("name")
        if name in nav_tool_names:
            tool_id = tool.get("id")
            if tool_id:
                print(f"  Deleting existing: {name} ({tool_id})")
                if delete_tool(api_key, tool_id):
                    deleted += 1
                    
    if deleted:
        print(f"  Removed {deleted} existing navigation tools")
    else:
        print("  No existing navigation tools found")


def list_agent_tools(api_key: str, agent_id: str):
    """List tools currently linked to agent."""
    print(f"\nCurrent tools for agent {agent_id}:")
    print("-" * 40)
    
    agent = get_agent(api_key, agent_id)
    tool_ids = agent.get("conversation_config", {}).get("agent", {}).get("prompt", {}).get("tool_ids", [])
    
    all_tools = list_tools(api_key)
    tools_by_id = {t.get("id"): t for t in all_tools}
    
    for tool_id in tool_ids:
        tool = tools_by_id.get(tool_id)
        if tool:
            name = tool.get("tool_config", {}).get("name", "Unknown")
            print(f"  - {name}: {tool_id}")
        else:
            print(f"  - (unknown): {tool_id}")


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Main entry point."""
    load_env()

    try:
        api_key = get_api_key()
        agent_id = get_multiverse_agent_id()
    except ValueError as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

    print("=" * 60)
    print("VibeMind Navigation Tools Deployment")
    print("=" * 60)
    print(f"API Key: {api_key[:10]}...")
    print(f"Target Agent: Multiverse (Rachel)")
    print(f"Agent ID: {agent_id}")

    # List current agent tools
    list_agent_tools(api_key, agent_id)

    # Clean up any existing navigation tools
    cleanup_existing_navigation_tools(api_key)

    # Deploy navigation tools
    nav_ids = deploy_tools(api_key, NAVIGATION_TOOLS, agent_id, "Navigation Tools")

    # Summary
    print("\n" + "=" * 60)
    print("DEPLOYMENT COMPLETE")
    print("=" * 60)
    print(f"Navigation Tools: {len(nav_ids)} created and linked")
    
    if nav_ids:
        print("\nCreated Tool IDs:")
        for tool_name, tool_id in zip([t["name"] for t in NAVIGATION_TOOLS], nav_ids):
            print(f"  - {tool_name}: {tool_id}")
    
    # Show updated agent tools
    list_agent_tools(api_key, agent_id)
    
    print("\n✅ Voice navigation is now enabled!")
    print("Try saying: 'Go to the Projects Space' or 'Select the next bubble'")


if __name__ == "__main__":
    main()