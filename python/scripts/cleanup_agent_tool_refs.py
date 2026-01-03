#!/usr/bin/env python3
"""
Cleanup Agent Tool References

Fixes the issue where agents have multiple tool_ids for the same tool name.
This happens because deploy_tools.py creates NEW tools each run and ADDS them
instead of REPLACING existing ones.

Solution:
1. Get all tools, group by name, identify newest
2. For each agent, replace all tool_ids with only the newest for each name
"""

import os
import sys
import json
import requests
from pathlib import Path
from typing import Dict, Any, List, Set
from collections import defaultdict


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
    key = os.getenv('ELEVENLABS_API_KEY')
    if not key:
        raise ValueError("ELEVENLABS_API_KEY not set")
    return key


def list_all_tools(api_key: str) -> List[Dict]:
    """Get all tools from ElevenLabs."""
    url = f"{API_BASE}/tools"
    headers = {"xi-api-key": api_key}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json().get("tools", [])


def get_agent(api_key: str, agent_id: str) -> Dict:
    """Get agent configuration."""
    url = f"{API_BASE}/agents/{agent_id}"
    headers = {"xi-api-key": api_key}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    return response.json()


def update_agent_tool_ids(api_key: str, agent_id: str, tool_ids: List[str]) -> Dict:
    """Update agent with specific tool_ids (REPLACE, not add)."""
    url = f"{API_BASE}/agents/{agent_id}"
    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json"
    }
    
    payload = {
        "conversation_config": {
            "agent": {
                "prompt": {
                    "tool_ids": tool_ids  # REPLACE completely
                }
            }
        }
    }
    
    response = requests.patch(url, headers=headers, json=payload)
    if response.status_code != 200:
        print(f"    Error: {response.status_code} - {response.text[:200]}")
    response.raise_for_status()
    return response.json()


def get_tool_dependent_agents(api_key: str, tool_id: str) -> List[Dict]:
    """Get list of agents that depend on a specific tool."""
    url = f"{API_BASE}/tools/{tool_id}/dependent_agents"
    headers = {"xi-api-key": api_key}
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        return []
    return response.json().get("agents", [])


def main():
    load_env()
    api_key = get_api_key()
    
    print("=" * 70)
    print("CLEANUP AGENT TOOL REFERENCES")
    print("=" * 70)
    
    # Step 1: Get all tools and group by name
    print("\n1. Getting all tools...")
    all_tools = list_all_tools(api_key)
    print(f"   Found {len(all_tools)} total tools")
    
    # Group tools by name
    tools_by_name: Dict[str, List[Dict]] = defaultdict(list)
    for tool in all_tools:
        config = tool.get("tool_config", {})
        name = config.get("name", "unknown")
        tools_by_name[name].append(tool)
    
    # Find newest tool for each name (by ID - newest are usually at end)
    newest_tools: Dict[str, str] = {}  # name -> tool_id
    all_valid_tool_ids: Set[str] = set()
    
    print("\n2. Identifying newest tool for each name:")
    for name, tool_list in sorted(tools_by_name.items()):
        if len(tool_list) > 1:
            # Sort by created timestamp or ID
            tool_list.sort(key=lambda t: t.get("id", ""))
            newest = tool_list[-1]  # Last one is newest
            oldest_ids = [t.get("id") for t in tool_list[:-1]]
            print(f"   {name}: {len(tool_list)} versions")
            print(f"      KEEP: {newest.get('id')}")
            print(f"      OLD:  {oldest_ids}")
        else:
            newest = tool_list[0]
            print(f"   {name}: 1 version (OK)")
        
        tool_id = newest.get("id")
        if tool_id:
            newest_tools[name] = tool_id
            all_valid_tool_ids.add(tool_id)
    
    print(f"\n   Valid tool IDs: {len(all_valid_tool_ids)}")
    
    # Step 2: Get all agents from .env
    print("\n3. Getting agent configurations...")
    agent_ids = {}
    for key in ["AGENT_RACHEL", "AGENT_ALICE", "AGENT_ADAM", "AGENT_ANTONI", "AGENT_MULTIVERSE"]:
        agent_id = os.getenv(key)
        if agent_id:
            agent_ids[key.replace("AGENT_", "").title()] = agent_id
    
    print(f"   Found {len(agent_ids)} agents: {list(agent_ids.keys())}")
    
    # Step 3: For each agent, fix tool references
    print("\n4. Fixing agent tool references:")
    
    for agent_name, agent_id in agent_ids.items():
        print(f"\n   {agent_name} ({agent_id[:20]}...):")
        
        try:
            agent = get_agent(api_key, agent_id)
            current_tool_ids = []
            
            try:
                current_tool_ids = agent.get("conversation_config", {}).get("agent", {}).get("prompt", {}).get("tool_ids", [])
            except (KeyError, TypeError):
                pass
            
            print(f"      Current tools: {len(current_tool_ids)}")
            
            # Filter to only keep valid (newest) tool IDs
            valid_ids = [tid for tid in current_tool_ids if tid in all_valid_tool_ids]
            removed_ids = [tid for tid in current_tool_ids if tid not in all_valid_tool_ids]
            
            if removed_ids:
                print(f"      Removing {len(removed_ids)} old/duplicate IDs:")
                for rid in removed_ids[:5]:  # Show first 5
                    print(f"         - {rid}")
                if len(removed_ids) > 5:
                    print(f"         ... and {len(removed_ids) - 5} more")
                
                # Update agent with only valid tool IDs
                update_agent_tool_ids(api_key, agent_id, valid_ids)
                print(f"      Updated: now has {len(valid_ids)} tools")
            else:
                print(f"      OK - all {len(valid_ids)} tool IDs are valid")
                
        except Exception as e:
            print(f"      Error: {e}")
    
    # Step 4: Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Total tools: {len(all_tools)}")
    print(f"Unique tool names: {len(newest_tools)}")
    print(f"Valid tool IDs kept: {len(all_valid_tool_ids)}")
    print(f"Agents processed: {len(agent_ids)}")
    
    # List final tool mapping
    print("\nFinal tool mapping (name -> id):")
    for name, tid in sorted(newest_tools.items()):
        print(f"   {name}: {tid[:30]}...")


if __name__ == "__main__":
    main()