"""
Rachel Agent Tools

Definiert die Tools die Rachel zur Verfügung hat:
- Shared Tools aus python/tools/ (bubble_tools, idea_tools)
- Agent-spezifisches Transfer-Tool zu Alice
"""

import os
import sys
from pathlib import Path
from typing import Dict, Any, List, Callable

# Füge parent directory zu path für imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tools.bubble_tools import (
    list_bubbles,
    create_bubble,
    enter_bubble,
    exit_bubble,
    get_bubble_stats,
    score_bubble,
    promote_bubble,
    delete_bubble,
    _signal_agent_switch,
)


def transfer_to_alice(params: Dict[str, Any]) -> str:
    """
    Übergib die Konversation an Alice (Projekt-Koordinator).
    
    Voice triggers: "zu Alice", "Projekt starten", "ich brauche Hilfe bei einem Projekt"
    
    Args (via params):
        reason: Optional - Grund für den Transfer
    
    Returns:
        str: Bestätigungsnachricht (löst Agent-Switch im Python-Backend aus)
    """
    reason = params.get("reason", "")
    
    alice_agent_id = os.getenv("ALICE_AGENT_ID") or os.getenv("AGENT_PROJECT_MANAGER")
    
    if not alice_agent_id:
        return "Ich kann Alice nicht erreichen. Bitte ALICE_AGENT_ID in .env setzen."
    
    # Signal Agent-Switch
    _signal_agent_switch(alice_agent_id, None, "Alice")
    
    if reason:
        return f"Ich verbinde dich mit Alice für: {reason}"
    return "Ich verbinde dich mit Alice..."


# =============================================================================
# TOOL DEFINITIONS für ElevenLabs
# =============================================================================

def get_tool_definitions() -> List[Dict[str, Any]]:
    """
    Gibt die Tool-Definitionen für ElevenLabs zurück.
    
    Diese werden bei der Agent-Erstellung/Update an ElevenLabs gesendet.
    """
    return [
        {
            "type": "function",
            "function": {
                "name": "list_bubbles",
                "description": "Zeige alle Spaces/Bubbles im Multiverse",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "create_bubble",
                "description": "Erstelle einen neuen Space/Bubble",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "title": {
                            "type": "string",
                            "description": "Name des neuen Spaces"
                        },
                        "description": {
                            "type": "string",
                            "description": "Optionale Beschreibung"
                        }
                    },
                    "required": ["title"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "enter_bubble",
                "description": "Betrete einen Space und starte dort einen Dialog",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "bubble_name": {
                            "type": "string",
                            "description": "Name des Spaces der betreten werden soll"
                        }
                    },
                    "required": ["bubble_name"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "get_bubble_stats",
                "description": "Zeige Statistiken zu einem Space",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "bubble_name": {
                            "type": "string",
                            "description": "Name des Spaces (optional - nutzt aktuellen wenn leer)"
                        }
                    },
                    "required": []
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "score_bubble",
                "description": "Bewerte einen Space nach Entwicklungsstand",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "bubble_name": {
                            "type": "string",
                            "description": "Name des Spaces (optional)"
                        }
                    },
                    "required": []
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "promote_bubble",
                "description": "Befördere einen Space zum Projekt",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "bubble_name": {
                            "type": "string",
                            "description": "Name des Spaces (optional)"
                        }
                    },
                    "required": []
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "delete_bubble",
                "description": "Lösche einen Space",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "bubble_name": {
                            "type": "string",
                            "description": "Name des Spaces der gelöscht werden soll"
                        }
                    },
                    "required": ["bubble_name"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "transfer_to_alice",
                "description": "Übergib an Alice für Projektkoordination",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "reason": {
                            "type": "string",
                            "description": "Grund für den Transfer (optional)"
                        }
                    },
                    "required": []
                }
            }
        },
    ]


def get_tools() -> Dict[str, Callable]:
    """
    Gibt alle Tool-Funktionen für die Client-Tools-Registrierung zurück.
    """
    return {
        "list_bubbles": list_bubbles,
        "create_bubble": create_bubble,
        "enter_bubble": enter_bubble,
        "exit_bubble": exit_bubble,
        "get_bubble_stats": get_bubble_stats,
        "score_bubble": score_bubble,
        "promote_bubble": promote_bubble,
        "delete_bubble": delete_bubble,
        "transfer_to_alice": transfer_to_alice,
    }


def register_tools(client_tools) -> None:
    """
    Registriere alle Rachel-Tools beim ClientTools-Manager.
    
    Args:
        client_tools: ElevenLabs ClientTools Instanz
    """
    for tool_name, tool_func in get_tools().items():
        client_tools.register(tool_name, tool_func)
        print(f"  [Rachel] Registered: {tool_name}")