"""
Alice Agent Tools

Alice delegiert Aufgaben an Spezialisten:
- Adam für Desktop-Arbeit
- Antoni für Coding/Schreiben
- Rachel für Rückkehr zum Multiverse
"""

import os
import sys
from pathlib import Path
from typing import Dict, Any, List, Callable

# Füge parent directory zu path für imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tools.bubble_tools import _signal_agent_switch


def transfer_to_adam(params: Dict[str, Any]) -> str:
    """
    Übergib die Aufgabe an Adam (Desktop Worker).
    
    Voice triggers: "Desktop", "öffne App", "klick auf", "System-Aufgabe"
    
    Args (via params):
        task: Die Aufgabe für Adam
    
    Returns:
        str: Bestätigungsnachricht
    """
    task = params.get("task", "")
    
    adam_agent_id = os.getenv("ADAM_AGENT_ID") or os.getenv("AGENT_DESKTOP_WORKER")
    
    if not adam_agent_id:
        return "Adam ist nicht verfügbar. Bitte ADAM_AGENT_ID in .env setzen."
    
    _signal_agent_switch(adam_agent_id, None, "Adam")
    
    if task:
        return f"Ich übergebe an Adam für: {task}"
    return "Adam übernimmt. Er kümmert sich um Desktop-Aufgaben."


def transfer_to_antoni(params: Dict[str, Any]) -> str:
    """
    Übergib die Aufgabe an Antoni (Coding/Writing).
    
    Voice triggers: "Code schreiben", "Dokumentation", "schreib", "erstelle Datei"
    
    Args (via params):
        task: Die Aufgabe für Antoni
    
    Returns:
        str: Bestätigungsnachricht
    """
    task = params.get("task", "")
    
    antoni_agent_id = os.getenv("ANTONI_AGENT_ID") or os.getenv("AGENT_PROJECT_WRITER")
    
    if not antoni_agent_id:
        return "Antoni ist nicht verfügbar. Bitte ANTONI_AGENT_ID in .env setzen."
    
    _signal_agent_switch(antoni_agent_id, None, "Antoni")
    
    if task:
        return f"Antoni übernimmt das: {task}"
    return "Antoni ist dran. Er kümmert sich ums Schreiben."


def transfer_to_rachel(params: Dict[str, Any]) -> str:
    """
    Zurück zu Rachel (Multiverse Navigator).
    
    Voice triggers: "zurück", "Multiverse", "andere Idee", "Rachel"
    
    Returns:
        str: Bestätigungsnachricht
    """
    rachel_agent_id = os.getenv("RACHEL_AGENT_ID") or os.getenv("AGENT_MULTIVERSE")
    
    if not rachel_agent_id:
        return "Rachel ist nicht erreichbar. Bitte RACHEL_AGENT_ID in .env setzen."
    
    _signal_agent_switch(rachel_agent_id, None, "Rachel")
    
    return "Du gehst zurück zu Rachel ins Multiverse."


def list_projects(params: Dict[str, Any]) -> str:
    """
    Liste alle aktiven Projekte.
    
    Returns:
        str: Liste der Projekte
    """
    # TODO: Implementiere Projekt-Listing aus der Datenbank
    return "Projekt-Listing wird noch implementiert..."


def get_project_status(params: Dict[str, Any]) -> str:
    """
    Status eines Projekts abfragen.
    
    Args (via params):
        project_name: Name des Projekts
    
    Returns:
        str: Projekt-Status
    """
    project_name = params.get("project_name", "")
    if not project_name:
        return "Welches Projekt meinst du?"
    
    # TODO: Implementiere Status-Abfrage
    return f"Status für '{project_name}' wird noch implementiert..."


# =============================================================================
# TOOL DEFINITIONS für ElevenLabs
# =============================================================================

def get_tool_definitions() -> List[Dict[str, Any]]:
    """Tool-Definitionen für ElevenLabs."""
    return [
        {
            "type": "function",
            "function": {
                "name": "transfer_to_adam",
                "description": "Delegiere Desktop/System-Aufgaben an Adam",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "task": {
                            "type": "string",
                            "description": "Beschreibung der Aufgabe für Adam"
                        }
                    },
                    "required": []
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "transfer_to_antoni",
                "description": "Delegiere Coding/Schreib-Aufgaben an Antoni",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "task": {
                            "type": "string",
                            "description": "Beschreibung der Aufgabe für Antoni"
                        }
                    },
                    "required": []
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "transfer_to_rachel",
                "description": "Zurück zu Rachel ins Multiverse",
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
                "name": "list_projects",
                "description": "Zeige alle aktiven Projekte",
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
                "name": "get_project_status",
                "description": "Status eines Projekts abfragen",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "project_name": {
                            "type": "string",
                            "description": "Name des Projekts"
                        }
                    },
                    "required": ["project_name"]
                }
            }
        },
    ]


def get_tools() -> Dict[str, Callable]:
    """Alle Tool-Funktionen für Client-Tools-Registrierung."""
    return {
        "transfer_to_adam": transfer_to_adam,
        "transfer_to_antoni": transfer_to_antoni,
        "transfer_to_rachel": transfer_to_rachel,
        "list_projects": list_projects,
        "get_project_status": get_project_status,
    }


def register_tools(client_tools) -> None:
    """Registriere alle Alice-Tools beim ClientTools-Manager."""
    for tool_name, tool_func in get_tools().items():
        client_tools.register(tool_name, tool_func)
        print(f"  [Alice] Registered: {tool_name}")