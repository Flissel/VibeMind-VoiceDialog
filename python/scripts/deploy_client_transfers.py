#!/usr/bin/env python3
"""
Deploy Client Transfer Tools to ElevenLabs Agents

These are CLIENT tools (not system transfer_to_agent) that notify Python
before an agent transfer happens. This solves the problem:

Problem:  ElevenLabs transfer_to_agent is a System Tool executed server-side
          → Python gets no callback → UI doesn't know about agent switch

Solution: Deploy Client Transfer Tools that:
          1. Python receives the tool call
          2. Python broadcasts to Electron UI
          3. TransferHandler coordinates the session switch
          4. Then the System transfer happens (if still needed)

Transfer Configuration (Hub-and-Spoke):
    Rachel (Bubbles)  ←→  Alice (Hub)  ←→  Adam (Desktop)
           ↓                   ↓               
       Multiverse         Antoni (Coding)    
           ↓                   
         Alice                 
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


def get_agent_ids() -> Dict[str, str]:
    """Get all agent IDs from environment."""
    agents = {
        "Rachel": os.getenv("AGENT_CONVERSATIONAL_MEMORY") or os.getenv("AGENT_RACHEL"),
        "Alice": os.getenv("AGENT_PROJECT_MANAGER") or os.getenv("AGENT_ALICE"),
        "Adam": os.getenv("AGENT_DESKTOP_WORKER") or os.getenv("AGENT_ADAM"),
        "Antoni": os.getenv("AGENT_PROJECT_WRITER") or os.getenv("AGENT_ANTONI"),
        "Multiverse": os.getenv("AGENT_MULTIVERSE"),
    }
    
    # Validate all agents are configured
    missing = [name for name, id in agents.items() if not id]
    if missing:
        raise ValueError(f"Missing agent IDs in .env: {', '.join(missing)}")
    
    return agents


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
        print(f"    Error creating tool: {response.status_code}")
        print(f"    {response.text}")
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
        print(f"    Error updating agent: {response.status_code}")
        print(f"    {response.text}")
        response.raise_for_status()

    return response.json()


# ============================================================================
# CLIENT TRANSFER TOOLS DEFINITIONS
# ============================================================================

def get_transfer_tools_for_agent(agent_name: str, agents: Dict[str, str]) -> List[Dict[str, Any]]:
    """
    Get the transfer tools configuration for a specific agent.
    
    Each agent gets tools to transfer to their allowed targets.
    The tools call Python which then broadcasts to Electron UI.
    """
    
    tools = []
    
    # Define which agents each agent can transfer to
    transfer_targets = {
        "Rachel": ["Alice", "Multiverse"],
        "Alice": ["Adam", "Antoni", "Rachel"],
        "Adam": ["Alice"],
        "Antoni": ["Alice"],
        "Multiverse": ["Rachel", "Alice"],
    }
    
    targets = transfer_targets.get(agent_name, [])
    
    for target in targets:
        target_lower = target.lower()
        
        # Target-specific descriptions
        descriptions = {
            "Alice": "Transfer to Alice, the project coordinator. She manages tasks and can delegate to specialists.",
            "Adam": "Transfer to Adam for desktop operations, file management, and system tasks.",
            "Antoni": "Transfer to Antoni for coding, writing, and document creation.",
            "Rachel": "Transfer to Rachel for creative brainstorming and idea exploration.",
            "Multiverse": "Transfer to Multiverse Navigator for space navigation and bubble exploration.",
        }
        
        tool_config = {
            "type": "client",
            "name": f"transfer_to_{target_lower}",
            "description": f"""{descriptions.get(target, f'Transfer conversation to {target}.')}

Use when user says:
- Connect me to {target}
- Talk to {target}
- I need {target}
- Transfer to {target}
- Get {target}
- Let me speak with {target}""",
            "expects_response": True,
            "response_timeout_secs": 10,
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "description": "Brief reason for the transfer (optional)"
                    }
                }
            }
        }
        
        tools.append(tool_config)
    
    return tools


# ============================================================================
# DEPLOYMENT FUNCTIONS
# ============================================================================

def cleanup_existing_transfer_tools(api_key: str, tool_names: List[str]):
    """Remove existing client transfer tools before deploying new ones."""
    print("\nCleaning up existing client transfer tools...")
    
    tools = list_tools(api_key)
    
    deleted = 0
    for tool in tools:
        config = tool.get("tool_config", {})
        name = config.get("name", "")
        tool_type = config.get("type", "")
        
        # Only delete CLIENT transfer tools (not system transfer_to_agent)
        if tool_type == "client" and name in tool_names:
            tool_id = tool.get("id")
            if tool_id:
                print(f"  Deleting: {name} ({tool_id})")
                if delete_tool(api_key, tool_id):
                    deleted += 1
                    
    if deleted:
        print(f"  Removed {deleted} existing client transfer tools")
    else:
        print("  No existing client transfer tools found")


def deploy_tools_to_agent(api_key: str, agent_name: str, agent_id: str, 
                          tools: List[Dict[str, Any]]) -> List[str]:
    """Deploy tools to a specific agent."""
    print(f"\n  {agent_name} ({agent_id[:20]}...)")
    print("  " + "-" * 40)
    
    created_ids = []
    
    for tool_config in tools:
        tool_name = tool_config["name"]
        print(f"    Creating: {tool_name}...", end=" ")
        
        try:
            result = create_tool(api_key, tool_config)
            tool_id = result.get("id") or result.get("tool_id")
            
            if tool_id:
                created_ids.append(tool_id)
                print(f"✅ {tool_id}")
            else:
                print("⚠️ No ID returned")
        except Exception as e:
            print(f"❌ {e}")
    
    if created_ids:
        print(f"    Linking {len(created_ids)} tools to agent...", end=" ")
        try:
            update_agent_tools(api_key, agent_id, created_ids)
            print("✅")
        except Exception as e:
            print(f"❌ {e}")
    
    return created_ids


def list_agent_tools(api_key: str, agent_id: str, agent_name: str):
    """List tools currently linked to agent."""
    print(f"\n  {agent_name} tools:")
    
    agent = get_agent(api_key, agent_id)
    tool_ids = agent.get("conversation_config", {}).get("agent", {}).get("prompt", {}).get("tool_ids", [])
    
    all_tools = list_tools(api_key)
    tools_by_id = {t.get("id"): t for t in all_tools}
    
    for tool_id in tool_ids:
        tool = tools_by_id.get(tool_id)
        if tool:
            config = tool.get("tool_config", {})
            name = config.get("name", "Unknown")
            tool_type = config.get("type", "?")
            print(f"    [{tool_type}] {name}")


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Main entry point."""
    load_env()
    
    print("=" * 60)
    print("VibeMind Client Transfer Tools Deployment")
    print("=" * 60)
    
    try:
        api_key = get_api_key()
        agents = get_agent_ids()
    except ValueError as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
    
    print(f"\nAPI Key: {api_key[:15]}...")
    print("\nAgents configured:")
    for name, agent_id in agents.items():
        print(f"  {name}: {agent_id[:25]}...")
    
    # Collect all transfer tool names for cleanup
    all_tool_names = set()
    for agent_name in agents.keys():
        tools = get_transfer_tools_for_agent(agent_name, agents)
        for tool in tools:
            all_tool_names.add(tool["name"])
    
    # Clean up existing client transfer tools
    cleanup_existing_transfer_tools(api_key, list(all_tool_names))
    
    # Deploy transfer tools to each agent
    print("\n" + "=" * 60)
    print("Deploying Client Transfer Tools")
    print("=" * 60)
    
    total_created = 0
    deployment_summary = {}
    
    for agent_name, agent_id in agents.items():
        tools = get_transfer_tools_for_agent(agent_name, agents)
        
        if tools:
            created_ids = deploy_tools_to_agent(api_key, agent_name, agent_id, tools)
            deployment_summary[agent_name] = created_ids
            total_created += len(created_ids)
        else:
            print(f"\n  {agent_name}: No transfer tools needed")
            deployment_summary[agent_name] = []
    
    # Summary
    print("\n" + "=" * 60)
    print("DEPLOYMENT COMPLETE")
    print("=" * 60)
    print(f"\nTotal tools created: {total_created}")
    
    print("\nTransfer capabilities:")
    for agent_name, tool_ids in deployment_summary.items():
        targets = [tid.replace("transfer_to_", "") for tid in 
                   [t["name"] for t in get_transfer_tools_for_agent(agent_name, agents)]]
        if targets:
            print(f"  {agent_name} → {', '.join(targets)}")
        else:
            print(f"  {agent_name} → (no transfers)")
    
    # Show final state
    print("\n" + "=" * 60)
    print("Current Agent Tools")
    print("=" * 60)
    for agent_name, agent_id in agents.items():
        list_agent_tools(api_key, agent_id, agent_name)
    
    print("\n✅ Client Transfer Tools deployed!")
    print("\nPython will now receive callbacks before agent transfers.")
    print("The UI will update automatically when agents switch.")


if __name__ == "__main__":
    main()