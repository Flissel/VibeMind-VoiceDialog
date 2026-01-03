#!/usr/bin/env python3
"""
Deploy Desktop Automation Tools zu ElevenLabs

Deployed alle 11 neuen Client Tools für Adam (Desktop Agent):
- 5 Task Tools
- 2 Quick Action Tools
- 2 Memory Tools
- 2 Claude Skills
"""

import os
import sys
import requests
import json
from pathlib import Path
from dotenv import load_dotenv

# Load .env from parent directory
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
AGENT_ADAM = os.getenv("AGENT_ADAM")

BASE_URL = "https://api.elevenlabs.io/v1"

# Output log
log_file = Path(__file__).parent / "deploy_desktop_tools.log"
log_lines = []

def log(msg):
    print(msg)
    log_lines.append(msg)

def save_log():
    log_file.write_text("\n".join(log_lines), encoding='utf-8')


# =====================================================================
# TOOL DEFINITIONS
# =====================================================================

TASK_TOOLS = [
    {
        "type": "client",
        "name": "create_task_node",
        "description": "Erstellt einen neuen Desktop-Task der im To-Do Widget erscheint. Benutze dies um Tasks zu tracken die du ausführst.",
        "parameters": {
            "type": "object",
            "properties": {
                "goal": {
                    "type": "string",
                    "description": "Beschreibung des Tasks (z.B. 'Öffne Chrome und navigiere zu Google')"
                },
                "agent": {
                    "type": "string",
                    "description": "Name des ausführenden Agents",
                    "default": "Adam"
                }
            },
            "required": ["goal"]
        }
    },
    {
        "type": "client",
        "name": "update_task_status",
        "description": "Aktualisiert den Status eines Tasks. Status kann sein: pending, running, completed, failed, cancelled",
        "parameters": {
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "string",
                    "description": "ID des Tasks"
                },
                "status": {
                    "type": "string",
                    "enum": ["pending", "running", "completed", "failed", "cancelled"],
                    "description": "Neuer Status"
                },
                "progress": {
                    "type": "number",
                    "description": "Fortschritt 0.0 bis 1.0"
                },
                "error": {
                    "type": "string",
                    "description": "Fehlermeldung wenn failed"
                }
            },
            "required": ["task_id", "status"]
        }
    },
    {
        "type": "client",
        "name": "get_task_list",
        "description": "Holt alle Tasks für die Widget-Anzeige. Optional nach Status filtern.",
        "parameters": {
            "type": "object",
            "properties": {
                "status_filter": {
                    "type": "string",
                    "enum": ["pending", "running", "completed", "failed", "cancelled"],
                    "description": "Nur Tasks mit diesem Status anzeigen"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximale Anzahl",
                    "default": 20
                }
            },
            "required": []
        }
    },
    {
        "type": "client",
        "name": "mark_task_complete",
        "description": "Markiert einen Task als erledigt. Wie eine Checkbox im To-Do Widget.",
        "parameters": {
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "string",
                    "description": "ID des Tasks"
                },
                "success": {
                    "type": "boolean",
                    "description": "True für erfolgreich, False für fehlgeschlagen",
                    "default": True
                },
                "result_message": {
                    "type": "string",
                    "description": "Beschreibung des Ergebnisses"
                }
            },
            "required": ["task_id"]
        }
    },
    {
        "type": "client",
        "name": "watch_task_progress", 
        "description": "Überwacht einen Task bis zum Abschluss und sendet Progress-Updates.",
        "parameters": {
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "string",
                    "description": "ID des Tasks"
                },
                "timeout": {
                    "type": "number",
                    "description": "Maximale Wartezeit in Sekunden",
                    "default": 120
                }
            },
            "required": ["task_id"]
        }
    }
]

QUICKACTION_TOOLS = [
    {
        "type": "client",
        "name": "open_app",
        "description": "Öffnet eine Anwendung schnell. Unterstützt Chrome, Word, Excel, VSCode, Notepad, Terminal und viele mehr. Bei Browsern kann eine URL mitgegeben werden.",
        "parameters": {
            "type": "object",
            "properties": {
                "app_name": {
                    "type": "string",
                    "description": "Name der App: chrome, word, excel, vscode, notepad, terminal, spotify, slack, discord, etc."
                },
                "url": {
                    "type": "string",
                    "description": "Optional: URL für Browser (z.B. 'google.com')"
                }
            },
            "required": ["app_name"]
        }
    },
    {
        "type": "client",
        "name": "use_app",
        "description": "Führt eine Aktion in einer laufenden App aus. Aktionen: navigate (Browser), type (Text eingeben), click (Element klicken), save (Speichern), close (Schließen).",
        "parameters": {
            "type": "object",
            "properties": {
                "app_name": {
                    "type": "string",
                    "description": "Name der App"
                },
                "action": {
                    "type": "string",
                    "enum": ["navigate", "type", "click", "save", "close"],
                    "description": "Aktion: navigate, type, click, save, close"
                },
                "parameters": {
                    "type": "object",
                    "description": "Action-Parameter: url (für navigate), text (für type), element (für click), filename (für save)"
                }
            },
            "required": ["app_name", "action"]
        }
    }
]

MEMORY_TOOLS = [
    {
        "type": "client",
        "name": "store_command_history",
        "description": "Speichert einen ausgeführten Desktop-Befehl für spätere Vorschläge.",
        "parameters": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "Der ausgeführte Befehl (z.B. 'Öffne Chrome')"
                },
                "app_context": {
                    "type": "string",
                    "description": "App-Kontext: desktop, chrome, word, excel, etc.",
                    "default": "desktop"
                },
                "success": {
                    "type": "boolean",
                    "description": "War der Befehl erfolgreich?",
                    "default": True
                },
                "tags": {
                    "type": "string",
                    "description": "Komma-separierte Tags für Kategorisierung"
                }
            },
            "required": ["command"]
        }
    },
    {
        "type": "client",
        "name": "get_frequent_commands",
        "description": "Ruft häufig verwendete Befehle ab. Nützlich um dem Nutzer Vorschläge zu machen.",
        "parameters": {
            "type": "object",
            "properties": {
                "app_context": {
                    "type": "string",
                    "description": "Filter für bestimmte App (optional)"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximale Anzahl",
                    "default": 10
                },
                "include_recent": {
                    "type": "boolean",
                    "description": "Die letzten 5 Befehle einschließen?",
                    "default": True
                }
            },
            "required": []
        }
    }
]

CLAUDE_SKILLS_TOOLS = [
    {
        "type": "client",
        "name": "execute_complex_automation",
        "description": "Führt komplexe Multi-Step Desktop Tasks aus. Nutzt KI-Reasoning um das Ziel in Einzelschritte aufzuteilen und diese auszuführen. Ideal für komplexe Aufgaben wie 'Erstelle ein Word-Dokument mit einer Tabelle'.",
        "parameters": {
            "type": "object",
            "properties": {
                "goal": {
                    "type": "string",
                    "description": "Das Ziel der Automation (z.B. 'Erstelle ein Word-Dokument mit einer Tabelle')"
                },
                "context": {
                    "type": "string",
                    "description": "Zusätzlicher Kontext (z.B. 'Word ist bereits geöffnet')"
                },
                "constraints": {
                    "type": "string",
                    "description": "Komma-separierte Einschränkungen"
                }
            },
            "required": ["goal"]
        }
    },
    {
        "type": "client",
        "name": "generate_automation_script",
        "description": "Generiert ein Automation-Script (PyAutoGUI, AHK, PowerShell) basierend auf einer Beschreibung. Das Script kann gespeichert und später wiederverwendet werden.",
        "parameters": {
            "type": "object",
            "properties": {
                "description": {
                    "type": "string",
                    "description": "Beschreibung was das Script tun soll"
                },
                "output_format": {
                    "type": "string",
                    "enum": ["pyautogui", "ahk", "powershell"],
                    "description": "Format: pyautogui (Python), ahk (AutoHotkey), powershell",
                    "default": "pyautogui"
                },
                "include_comments": {
                    "type": "boolean",
                    "description": "Kommentare hinzufügen?",
                    "default": True
                },
                "safety_checks": {
                    "type": "boolean",
                    "description": "Sicherheitschecks einfügen?",
                    "default": True
                }
            },
            "required": ["description"]
        }
    }
]


# =====================================================================
# API FUNCTIONS
# =====================================================================

def update_agent_tools(agent_id: str, tools: list) -> dict:
    """Aktualisiert die Tools eines Agenten."""
    headers = {
        "xi-api-key": ELEVENLABS_API_KEY,
        "Content-Type": "application/json"
    }
    
    # Zuerst bestehende Konfiguration holen
    current = get_agent_config(agent_id)
    existing_tools = current.get("conversation_config", {}).get("agent", {}).get("prompt", {}).get("tools", [])
    
    # Bestehende Tools behalten die nicht ersetzt werden
    new_tool_names = {t["name"] for t in tools}
    filtered_existing = [t for t in existing_tools if t.get("name") not in new_tool_names]
    
    # Neue Tools hinzufügen
    all_tools = filtered_existing + tools
    
    log(f"Existing tools: {len(existing_tools)}")
    log(f"Keeping: {len(filtered_existing)}, Adding: {len(tools)}")
    log(f"Total: {len(all_tools)}")
    
    # Update senden - korrekter Pfad!
    payload = {
        "conversation_config": {
            "agent": {
                "prompt": {
                    "tools": all_tools
                }
            }
        }
    }
    
    log(f"Sending payload with {len(all_tools)} tools...")
    
    response = requests.patch(
        f"{BASE_URL}/convai/agents/{agent_id}",
        headers=headers,
        json=payload
    )
    
    log(f"DEBUG - Response status: {response.status_code}")
    
    if response.status_code != 200:
        raise Exception(f"Failed to update agent: {response.status_code} - {response.text}")
    return response.json()


def get_agent_config(agent_id: str) -> dict:
    """Holt die aktuelle Agent-Konfiguration."""
    headers = {"xi-api-key": ELEVENLABS_API_KEY}
    
    response = requests.get(
        f"{BASE_URL}/convai/agents/{agent_id}",
        headers=headers
    )
    
    if response.status_code != 200:
        raise Exception(f"Failed to get agent: {response.status_code} - {response.text}")
    return response.json()


def deploy_tools_to_adam():
    """Deployed alle Tools zu Adam."""
    if not ELEVENLABS_API_KEY:
        log("ERROR: ELEVENLABS_API_KEY nicht gesetzt")
        return False
    
    if not AGENT_ADAM:
        log("ERROR: AGENT_ADAM nicht gesetzt")
        return False
    
    log(f"{'='*60}")
    log("Deploying Desktop Automation Tools to Adam")
    log(f"{'='*60}")
    log(f"Agent ID: {AGENT_ADAM}")
    
    # Alle Tools kombinieren
    all_tools = (
        TASK_TOOLS + 
        QUICKACTION_TOOLS + 
        MEMORY_TOOLS + 
        CLAUDE_SKILLS_TOOLS
    )
    
    log(f"\nDeploying {len(all_tools)} NEW tools:")
    for tool in all_tools:
        log(f"   - {tool['name']}")
    
    try:
        result = update_agent_tools(AGENT_ADAM, all_tools)
        log("\nAPI call successful!")
        
        # Verifizieren
        updated = get_agent_config(AGENT_ADAM)
        deployed_tools = updated.get("conversation_config", {}).get("agent", {}).get("prompt", {}).get("tools", [])
        
        log(f"\nVerified - Total Tools: {len(deployed_tools)}")
        
        # Zeige nur die neuen Tools
        new_tool_names = {t["name"] for t in all_tools}
        for t in deployed_tools:
            name = t.get('name')
            if name in new_tool_names:
                log(f"   NEW: {name}")
        
        return True
        
    except Exception as e:
        log(f"\nDeployment failed: {e}")
        import traceback
        log(traceback.format_exc())
        return False


def main():
    """Hauptfunktion."""
    success = deploy_tools_to_adam()
    save_log()
    return success


if __name__ == "__main__":
    result = main()
    sys.exit(0 if result else 1)