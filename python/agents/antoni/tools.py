"""
Antoni Agent Tools

Antoni schreibt Code und Dokumentation.
"""

import os
import sys
from pathlib import Path
from typing import Dict, Any, List, Callable

# Füge parent directory zu path für imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tools.bubble_tools import _signal_agent_switch


def transfer_to_alice(params: Dict[str, Any]) -> str:
    """
    Zurück zu Alice (Coordinator).
    
    Returns:
        str: Bestätigungsnachricht
    """
    alice_agent_id = os.getenv("ALICE_AGENT_ID") or os.getenv("AGENT_PROJECT_MANAGER")
    
    if not alice_agent_id:
        return "Alice ist nicht erreichbar."
    
    _signal_agent_switch(alice_agent_id, None, "Alice")
    
    return "Schreibarbeit erledigt. Zurück zu Alice."


def write_code(params: Dict[str, Any]) -> str:
    """
    Schreibe Code-Snippet.
    
    Args (via params):
        language: Programmiersprache
        description: Was der Code tun soll
        code: Der geschriebene Code (falls bereits generiert)
    
    Returns:
        str: Bestätigung mit Code-Snippet
    """
    language = params.get("language", "python").strip()
    description = params.get("description", "").strip()
    code = params.get("code", "").strip()
    
    if not description and not code:
        return "Was soll ich programmieren?"
    
    # Hier würde normalerweise Code-Generierung stattfinden
    # Für jetzt: Bestätigung
    if code:
        return f"Code in {language} erstellt:\n```{language}\n{code}\n```"
    
    return f"Ich schreibe {language}-Code für: {description}. Einen Moment..."


def create_file(params: Dict[str, Any]) -> str:
    """
    Erstelle eine neue Datei.
    
    Args (via params):
        filename: Name der Datei
        content: Inhalt der Datei
    
    Returns:
        str: Bestätigung
    """
    filename = params.get("filename", "").strip()
    content = params.get("content", "")
    
    if not filename:
        return "Wie soll die Datei heißen?"
    
    try:
        # Sicherheitscheck: Kein Pfad-Traversal
        if ".." in filename or filename.startswith("/"):
            return "Ungültiger Dateiname."
        
        # Workspace-relativer Pfad
        workspace = os.getenv("WORKSPACE_PATH", ".")
        filepath = os.path.join(workspace, filename)
        
        # Verzeichnis erstellen falls nötig
        os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        
        return f"Datei '{filename}' erstellt mit {len(content)} Zeichen."
    except Exception as e:
        return f"Fehler beim Erstellen: {str(e)}"


def update_file(params: Dict[str, Any]) -> str:
    """
    Aktualisiere existierende Datei.
    
    Args (via params):
        filename: Name der Datei
        content: Neuer Inhalt
        mode: "replace" oder "append"
    
    Returns:
        str: Bestätigung
    """
    filename = params.get("filename", "").strip()
    content = params.get("content", "")
    mode = params.get("mode", "replace").strip()
    
    if not filename:
        return "Welche Datei soll ich aktualisieren?"
    
    try:
        workspace = os.getenv("WORKSPACE_PATH", ".")
        filepath = os.path.join(workspace, filename)
        
        if not os.path.exists(filepath):
            return f"Datei '{filename}' existiert nicht."
        
        write_mode = "a" if mode == "append" else "w"
        with open(filepath, write_mode, encoding="utf-8") as f:
            f.write(content)
        
        action = "erweitert" if mode == "append" else "aktualisiert"
        return f"Datei '{filename}' {action}."
    except Exception as e:
        return f"Fehler beim Aktualisieren: {str(e)}"


def generate_readme(params: Dict[str, Any]) -> str:
    """
    Generiere README für ein Projekt.
    
    Args (via params):
        project_name: Name des Projekts
        description: Kurzbeschreibung
    
    Returns:
        str: Bestätigung
    """
    project_name = params.get("project_name", "Projekt").strip()
    description = params.get("description", "").strip()
    
    readme_content = f"""# {project_name}

{description if description else 'Beschreibung folgt.'}

## Installation

```bash
# Installation instructions here
```

## Usage

```bash
# Usage examples here
```

## License

MIT
"""
    
    try:
        workspace = os.getenv("WORKSPACE_PATH", ".")
        filepath = os.path.join(workspace, "README.md")
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(readme_content)
        
        return f"README.md für '{project_name}' erstellt."
    except Exception as e:
        return f"Fehler: {str(e)}"


# =============================================================================
# TOOL DEFINITIONS für ElevenLabs
# =============================================================================

def get_tool_definitions() -> List[Dict[str, Any]]:
    """Tool-Definitionen für ElevenLabs."""
    return [
        {
            "type": "function",
            "function": {
                "name": "write_code",
                "description": "Schreibe Code in einer Programmiersprache",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "language": {
                            "type": "string",
                            "description": "Programmiersprache (python, javascript, etc.)"
                        },
                        "description": {
                            "type": "string",
                            "description": "Was der Code tun soll"
                        }
                    },
                    "required": ["description"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "create_file",
                "description": "Erstelle eine neue Datei",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "filename": {
                            "type": "string",
                            "description": "Name der Datei inkl. Erweiterung"
                        },
                        "content": {
                            "type": "string",
                            "description": "Inhalt der Datei"
                        }
                    },
                    "required": ["filename"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "update_file",
                "description": "Aktualisiere eine existierende Datei",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "filename": {
                            "type": "string",
                            "description": "Name der Datei"
                        },
                        "content": {
                            "type": "string",
                            "description": "Neuer oder zusätzlicher Inhalt"
                        },
                        "mode": {
                            "type": "string",
                            "enum": ["replace", "append"],
                            "description": "Ersetzen oder anhängen"
                        }
                    },
                    "required": ["filename", "content"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "generate_readme",
                "description": "Generiere README.md für ein Projekt",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "project_name": {
                            "type": "string",
                            "description": "Name des Projekts"
                        },
                        "description": {
                            "type": "string",
                            "description": "Kurzbeschreibung des Projekts"
                        }
                    },
                    "required": ["project_name"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "transfer_to_alice",
                "description": "Zurück zu Alice wenn fertig",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        },
    ]


def get_tools() -> Dict[str, Callable]:
    """Alle Tool-Funktionen für Client-Tools-Registrierung."""
    return {
        "write_code": write_code,
        "create_file": create_file,
        "update_file": update_file,
        "generate_readme": generate_readme,
        "transfer_to_alice": transfer_to_alice,
    }


def register_tools(client_tools) -> None:
    """Registriere alle Antoni-Tools beim ClientTools-Manager."""
    for tool_name, tool_func in get_tools().items():
        client_tools.register(tool_name, tool_func)
        print(f"  [Antoni] Registered: {tool_name}")