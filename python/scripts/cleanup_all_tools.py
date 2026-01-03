#!/usr/bin/env python3
"""
Cleanup alle redundanten ElevenLabs Tools.
Behaelt nur die neueste Version jedes Tool-Namens.
SUPER AGGRESSIV: Ruft ALLE Agenten ab und entfernt Tool-Referenzen.
"""
import os
import sys
import requests
from pathlib import Path
from collections import defaultdict

def load_env():
    env_path = Path(__file__).parent.parent / ".env"
    if not env_path.exists():
        env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ.setdefault(key.strip(), value.strip())

def get_all_agents(headers):
    """Ruft ALLE Agenten ab ueber die API."""
    url = "https://api.elevenlabs.io/v1/convai/agents"
    resp = requests.get(url, headers=headers)
    if resp.status_code != 200:
        print("Fehler beim Abrufen der Agenten: %d" % resp.status_code)
        return []
    return resp.json().get("agents", [])

def main():
    load_env()
    
    api_key = os.getenv('ELEVENLABS_API_KEY')
    if not api_key:
        print("ERROR: ELEVENLABS_API_KEY not set")
        return
    
    headers = {'xi-api-key': api_key}
    
    print("=" * 70)
    print("Tool Cleanup - SUPER AGGRESSIV")
    print("=" * 70)
    
    # Alle Tools abrufen
    tools_resp = requests.get('https://api.elevenlabs.io/v1/convai/tools', headers=headers)
    tools = tools_resp.json().get('tools', [])
    
    print("Aktuelle Tools: %d" % len(tools))
    
    # Alle Agenten abrufen
    all_agents = get_all_agents(headers)
    print("Agenten gefunden: %d" % len(all_agents))
    
    # Nach Name gruppieren
    by_name = defaultdict(list)
    for tool in tools:
        config = tool.get("tool_config", {})
        name = config.get("name", "unknown")
        tool_id = tool.get("id", "")
        by_name[name].append({"id": tool_id, "name": name})
    
    # Bestimme welche Tools zu behalten und welche zu loeschen
    to_keep = {}  # name -> tool_id
    to_delete = []  # list of {"id": ..., "name": ...}
    
    for name, tool_list in sorted(by_name.items()):
        # Sortiere nach ID (neuere IDs sind laenger/spaeter)
        tool_list.sort(key=lambda t: t["id"], reverse=True)
        
        # Behalte das erste (neueste)
        to_keep[name] = tool_list[0]["id"]
        
        # Loesche den Rest
        if len(tool_list) > 1:
            for t in tool_list[1:]:
                to_delete.append(t)
    
    print("Unique Tool Namen: %d" % len(to_keep))
    print("Zu loeschende Tools: %d" % len(to_delete))
    
    if not to_delete:
        print("Keine Duplikate gefunden!")
        return
    
    # Erstelle Set der zu loeschenden IDs
    delete_ids = set(t["id"] for t in to_delete)
    
    # PHASE 1: Entferne Referenzen von ALLEN Agenten
    print("")
    print("[1/2] Entferne Tool-Referenzen von ALLEN %d Agenten..." % len(all_agents))
    
    for agent_info in all_agents:
        agent_id = agent_info.get("agent_id") or agent_info.get("id")
        agent_name = agent_info.get("name", "Unknown")
        
        if not agent_id:
            continue
        
        # Get full agent config
        agent_resp = requests.get('https://api.elevenlabs.io/v1/convai/agents/%s' % agent_id, headers=headers)
        if agent_resp.status_code != 200:
            continue
        
        agent = agent_resp.json()
        prompt = agent.get("conversation_config", {}).get("agent", {}).get("prompt", {})
        current_tool_ids = prompt.get("tool_ids", [])
        
        # Behalte nur die neuesten (nicht zu loeschenden) Tools
        new_tool_ids = [tid for tid in current_tool_ids if tid not in delete_ids]
        
        removed_count = len(current_tool_ids) - len(new_tool_ids)
        
        if removed_count > 0:
            payload = {
                "conversation_config": {
                    "agent": {
                        "prompt": {
                            "tool_ids": new_tool_ids
                        }
                    }
                }
            }
            
            update_resp = requests.patch(
                'https://api.elevenlabs.io/v1/convai/agents/%s' % agent_id,
                headers={**headers, 'Content-Type': 'application/json'},
                json=payload
            )
            
            if update_resp.status_code == 200:
                print("  %s: %d Referenzen entfernt" % (agent_name[:30], removed_count))
            else:
                print("  %s: Update FEHLER" % agent_name[:30])
    
    # Pause
    import time
    time.sleep(2)
    
    # PHASE 2: Tools loeschen
    print("")
    print("[2/2] Loesche redundante Tools...")
    
    deleted = 0
    failed = 0
    
    for tool in to_delete:
        tool_id = tool["id"]
        tool_name = tool["name"]
        
        delete_resp = requests.delete(
            'https://api.elevenlabs.io/v1/convai/tools/%s' % tool_id,
            headers=headers
        )
        
        # 200 und 204 sind beide Erfolgs-Codes
        if delete_resp.status_code in [200, 204]:
            deleted += 1
            print("  [OK] %s" % tool_name)
        else:
            failed += 1
            print("  [X] %s - %d" % (tool_name, delete_resp.status_code))
    
    print("")
    print("=" * 70)
    print("ERGEBNIS")
    print("=" * 70)
    print("  Geloescht: %d" % deleted)
    print("  Fehlgeschlagen: %d" % failed)
    print("  Verbleibende Tools: ca. %d" % (len(tools) - deleted))
    print("=" * 70)

if __name__ == "__main__":
    main()