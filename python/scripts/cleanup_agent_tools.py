#!/usr/bin/env python3
"""
Bereinigt die Tool-Verknüpfungen bei Agenten.
Behält nur die neuesten (kbj) Versionen der Tools.
"""
import os
import requests
from collections import defaultdict
from deploy_tools import load_env, get_api_key, list_tools

API_BASE = "https://api.elevenlabs.io/v1/convai"

# Agent IDs aus .env
AGENTS = {
    "rachel": "AGENT_RACHEL",
    "alice": "AGENT_ALICE", 
    "adam": "AGENT_ADAM",
    "antoni": "AGENT_ANTONI",
    "multiverse": "AGENT_MULTIVERSE"
}

OUTPUT_FILE = "cleanup_agent_output.txt"
output = []

def log(msg):
    print(msg, flush=True)
    output.append(msg)


def get_agent(api_key: str, agent_id: str) -> dict:
    """Holt Agent-Konfiguration"""
    url = f"{API_BASE}/agents/{agent_id}"
    headers = {"xi-api-key": api_key}
    resp = requests.get(url, headers=headers)
    if resp.status_code != 200:
        log(f"Error getting agent {agent_id}: {resp.status_code}")
        return {}
    return resp.json()


def update_agent_tool_ids(api_key: str, agent_id: str, tool_ids: list) -> bool:
    """Ersetzt die Tool-IDs eines Agenten komplett"""
    url = f"{API_BASE}/agents/{agent_id}"
    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json"
    }
    
    payload = {
        "conversation_config": {
            "agent": {
                "prompt": {
                    "tool_ids": tool_ids
                }
            }
        }
    }
    
    resp = requests.patch(url, headers=headers, json=payload)
    if resp.status_code != 200:
        log(f"  Error updating agent: {resp.status_code} - {resp.text[:100]}")
        return False
    return True


def main():
    load_env()
    api_key = get_api_key()
    
    log("="*60)
    log("Agent Tool Cleanup")
    log("="*60)
    
    # Hole alle Tools und gruppiere nach Name
    all_tools = list_tools(api_key)
    log(f"\nTotal tools in account: {len(all_tools)}")
    
    # Group tools by name und finde die "kbj" (neueste) Version
    tools_by_name = defaultdict(list)
    for tool in all_tools:
        config = tool.get("tool_config", {})
        name = config.get("name", "unknown")
        tools_by_name[name].append(tool)
    
    # Erstelle Mapping: Tool-Name -> Beste Tool-ID (kbj bevorzugt)
    best_tool_ids = {}
    for name, tool_list in tools_by_name.items():
        # Prefer "kbj" tools (newest)
        kbj_tools = [t for t in tool_list if "kbj" in t.get("id", "")]
        if kbj_tools:
            best_tool_ids[name] = kbj_tools[0]["id"]
        elif tool_list:
            best_tool_ids[name] = tool_list[0]["id"]
    
    log(f"\nBest tool IDs (one per name):")
    for name, tid in sorted(best_tool_ids.items()):
        log(f"  {name}: {tid[:30]}...")
    
    # Für jeden Agenten: Hole aktuelle Tool-IDs und ersetze mit den besten
    for agent_name, agent_env_var in AGENTS.items():
        agent_id = os.environ.get(agent_env_var)
        if not agent_id:
            log(f"\n{agent_name}: Skipping (no env var {agent_env_var})")
            continue
        
        log(f"\n{'='*40}")
        log(f"Processing {agent_name} ({agent_id})")
        log(f"{'='*40}")
        
        # Get current agent config
        agent_data = get_agent(api_key, agent_id)
        if not agent_data:
            continue
        
        # Get current tool_ids
        try:
            current_tool_ids = agent_data.get("conversation_config", {}).get("agent", {}).get("prompt", {}).get("tool_ids", [])
        except:
            current_tool_ids = []
        
        log(f"  Current tools: {len(current_tool_ids)}")
        
        # Finde tool names für current IDs
        tool_id_to_name = {}
        for tool in all_tools:
            tool_id_to_name[tool.get("id")] = tool.get("tool_config", {}).get("name", "unknown")
        
        # Erstelle neue Tool-ID Liste (nur beste Version pro Name)
        seen_names = set()
        new_tool_ids = []
        
        for old_id in current_tool_ids:
            name = tool_id_to_name.get(old_id, "unknown")
            if name not in seen_names:
                seen_names.add(name)
                # Use the best (kbj) version instead of old version
                best_id = best_tool_ids.get(name, old_id)
                new_tool_ids.append(best_id)
        
        # Check what changed
        removed = set(current_tool_ids) - set(new_tool_ids)
        added = set(new_tool_ids) - set(current_tool_ids)
        
        log(f"  New tools: {len(new_tool_ids)}")
        if removed:
            log(f"  Removing: {len(removed)} duplicate tool references")
        if added:
            log(f"  Upgrading to: {len(added)} newer tool versions")
        
        # Update agent
        if new_tool_ids != current_tool_ids:
            log(f"  Updating agent...")
            if update_agent_tool_ids(api_key, agent_id, new_tool_ids):
                log(f"  ✓ Updated successfully")
            else:
                log(f"  ✗ Update failed")
        else:
            log(f"  No changes needed")
    
    log(f"\n{'='*60}")
    log(f"CLEANUP COMPLETE")
    log(f"{'='*60}")
    
    # Save output
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(output))
    log(f"\nOutput saved to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()