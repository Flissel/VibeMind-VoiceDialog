#!/usr/bin/env python3
"""
Deploy Client Tools to ElevenLabs Agents

Dieses Script:
1. Entfernt die alten transfer_to_agent System-Tools von allen Agenten
2. Deployed die neuen Client-Tool-Definitionen aus den Agent-Modulen

Der Unterschied zu System-Tools:
- System-Tools werden serverseitig von ElevenLabs ausgeführt (kein Callback)
- Client-Tools werden in Python ausgeführt (mit Callback!)

Nach diesem Script werden Transfers über Python gesteuert und
die App kann das UI entsprechend aktualisieren.
"""

import os
import sys
import json
import requests
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

# Füge parent directory zu path für imports
sys.path.insert(0, str(Path(__file__).parent))

from agents import get_registry

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
BASE_URL = "https://api.elevenlabs.io/v1/convai/agents"


def get_headers():
    """API Headers."""
    return {
        "xi-api-key": ELEVENLABS_API_KEY,
        "Content-Type": "application/json"
    }


def get_agent_config(agent_id: str) -> dict:
    """Hole aktuelle Agent-Konfiguration."""
    url = f"{BASE_URL}/{agent_id}"
    response = requests.get(url, headers=get_headers())
    
    if response.status_code == 200:
        return response.json()
    else:
        print(f"  Fehler beim Abrufen: {response.status_code}")
        return None


def remove_system_tools(agent_id: str) -> bool:
    """
    Entferne alle transfer_to_agent System-Tools von einem Agenten.
    """
    current = get_agent_config(agent_id)
    if not current:
        return False
    
    # Hole existierende Tools aus agent.prompt.tools
    prompt = current.get("conversation_config", {}).get("agent", {}).get("prompt", {})
    existing_tools = prompt.get("tools", [])
    
    # Filtere System-Tools raus
    filtered_tools = [
        t for t in existing_tools 
        if t.get("type") != "system" and t.get("name") != "transfer_to_agent"
    ]
    
    # Wenn keine Änderung nötig
    if len(filtered_tools) == len(existing_tools):
        return True
    
    # Update mit gefilterten Tools
    payload = {
        "conversation_config": {
            "agent": {
                "prompt": {
                    "tools": filtered_tools
                }
            }
        }
    }
    
    url = f"{BASE_URL}/{agent_id}"
    response = requests.patch(url, headers=get_headers(), json=payload)
    
    removed_count = len(existing_tools) - len(filtered_tools)
    if response.status_code == 200:
        print(f"  [OK] {removed_count} System-Tool(s) entfernt")
        return True
    else:
        print(f"  [FAIL] Fehler: {response.status_code}")
        return False


def deploy_client_tools(agent_id: str, tool_definitions: list) -> bool:
    """
    Deploy Client-Tool-Definitionen zu einem Agenten.
    
    Bei ElevenLabs werden Client-Tools als normale function tools registriert.
    Die Ausführung erfolgt dann im Python-Client via ClientTools.
    """
    current = get_agent_config(agent_id)
    if not current:
        return False
    
    # Hole existierende Tools
    prompt = current.get("conversation_config", {}).get("agent", {}).get("prompt", {})
    existing_tools = prompt.get("tools", [])
    
    # Sammle Namen der neuen Tools
    new_tool_names = [t["function"]["name"] for t in tool_definitions if "function" in t]
    
    # Filtere alte Versionen der gleichen Tools raus
    filtered_tools = [
        t for t in existing_tools
        if t.get("function", {}).get("name") not in new_tool_names
        and t.get("name") not in new_tool_names
    ]
    
    # Füge neue Tools hinzu
    updated_tools = filtered_tools + tool_definitions
    
    # Update
    payload = {
        "conversation_config": {
            "agent": {
                "prompt": {
                    "tools": updated_tools
                }
            }
        }
    }
    
    url = f"{BASE_URL}/{agent_id}"
    response = requests.patch(url, headers=get_headers(), json=payload)
    
    if response.status_code == 200:
        print(f"  [OK] {len(tool_definitions)} Client-Tool(s) deployed")
        return True
    else:
        print(f"  [FAIL] Fehler: {response.status_code} - {response.text[:100]}")
        return False


def deploy_all():
    """Hauptfunktion: Räume auf und deploye neue Tools."""
    print("=" * 60)
    print("Client-Tools Deployment")
    print("=" * 60)
    
    if not ELEVENLABS_API_KEY:
        print("FEHLER: ELEVENLABS_API_KEY nicht in .env")
        return False
    
    registry = get_registry()
    success_count = 0
    total = len(registry.get_all())
    
    for agent in registry.get_all():
        agent_id = registry.get_agent_id(agent.slug)
        
        print(f"\n{agent.name} ({agent.slug})")
        print("-" * 40)
        
        if not agent_id:
            print(f"  [!] Agent-ID fehlt - übersprungen")
            continue
        
        # 1. Entferne alte System-Tools
        print(f"  1. Entferne alte System-Tools...")
        if not remove_system_tools(agent_id):
            print(f"  [!] Konnte System-Tools nicht entfernen")
        
        # 2. Deploye neue Client-Tools
        print(f"  2. Deploye Client-Tools...")
        tool_definitions = registry.get_tool_definitions(agent.slug)
        
        if tool_definitions:
            if deploy_client_tools(agent_id, tool_definitions):
                success_count += 1
        else:
            print(f"  [!] Keine Tool-Definitionen gefunden")
    
    print("\n" + "=" * 60)
    print(f"Ergebnis: {success_count}/{total} Agenten erfolgreich aktualisiert")
    print("=" * 60)
    
    return success_count == total


def show_current_tools():
    """Zeige aktuelle Tool-Konfiguration aller Agenten."""
    print("=" * 60)
    print("Aktuelle Tool-Konfiguration")
    print("=" * 60)
    
    registry = get_registry()
    
    for agent in registry.get_all():
        agent_id = registry.get_agent_id(agent.slug)
        
        print(f"\n{agent.name}")
        print("-" * 40)
        
        if not agent_id:
            print("  Agent-ID fehlt")
            continue
        
        config = get_agent_config(agent_id)
        if not config:
            print("  Konnte Konfiguration nicht laden")
            continue
        
        prompt = config.get("conversation_config", {}).get("agent", {}).get("prompt", {})
        tools = prompt.get("tools", [])
        
        if not tools:
            print("  Keine Tools konfiguriert")
            continue
        
        for tool in tools:
            tool_type = tool.get("type", "function")
            name = tool.get("name") or tool.get("function", {}).get("name", "?")
            print(f"  - {name} ({tool_type})")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Deploy Client-Tools zu ElevenLabs")
    parser.add_argument("--show", action="store_true", help="Zeige aktuelle Tools")
    parser.add_argument("--deploy", action="store_true", help="Deploye neue Tools")
    
    args = parser.parse_args()
    
    if args.show:
        show_current_tools()
    elif args.deploy:
        deploy_all()
    else:
        # Default: Zeige Hilfe
        print("Verwendung:")
        print("  python deploy_client_tools.py --show    # Zeige aktuelle Tools")
        print("  python deploy_client_tools.py --deploy  # Deploye neue Client-Tools")