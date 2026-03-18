"""
Tool Definitions for VibeMind Orchestrator

All available tools as OpenAI-compatible JSON schemas for native tool calling.
These definitions are used by the ToolOrchestrator to enable Sonnet to
select and call the appropriate tools based on user intent.
"""

import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

# =============================================================================
# BUBBLE/SPACE TOOLS
# =============================================================================

BUBBLE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "bubble_list",
            "description": "Liste alle Spaces/Bubbles im Multiverse auf. Zeigt alle verfuegbaren Workspaces.",
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
            "name": "bubble_create",
            "description": "Erstelle einen neuen Space/Bubble als Workspace fuer Ideen.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Name des neuen Spaces (z.B. 'Projekt Alpha', 'Rezepte')"
                    }
                },
                "required": ["title"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "bubble_enter",
            "description": "Betrete einen Space um darin zu arbeiten. Wechselt in den angegebenen Workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "bubble_name": {
                        "type": "string",
                        "description": "Name des Spaces den du betreten moechtest"
                    }
                },
                "required": ["bubble_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "bubble_exit",
            "description": "Verlasse den aktuellen Space und kehre zur Multiverse-Uebersicht zurueck.",
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
            "name": "bubble_delete",
            "description": "Loesche einen Space und alle enthaltenen Ideen/Notizen.",
            "parameters": {
                "type": "object",
                "properties": {
                    "bubble_name": {
                        "type": "string",
                        "description": "Name des zu loeschenden Spaces"
                    }
                },
                "required": ["bubble_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "bubble_stats",
            "description": "Zeige Statistiken ueber einen Space (Anzahl Ideen, Score, etc.).",
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
            "name": "bubble_score",
            "description": "Berechne den Score eines Spaces basierend auf Inhalt und Aktivitaet.",
            "parameters": {
                "type": "object",
                "properties": {
                    "bubble_name": {
                        "type": "string",
                        "description": "Name des Spaces (optional, sonst aktueller Space)"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "bubble_promote",
            "description": "Befördere einen Space zu einem Projekt (fuer Code-Generierung).",
            "parameters": {
                "type": "object",
                "properties": {
                    "bubble_name": {
                        "type": "string",
                        "description": "Name des Spaces der zum Projekt werden soll"
                    }
                },
                "required": ["bubble_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "bubble_current",
            "description": "Zeige den aktuellen Standort (welcher Space oder Multiverse).",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
]

# =============================================================================
# IDEA/NOTE TOOLS
# =============================================================================

IDEA_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "idea_list",
            "description": "Liste alle Ideen/Notizen im aktuellen Space auf.",
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
            "name": "idea_create",
            "description": "Erstelle eine neue Idee/Notiz im aktuellen Space.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Titel der Idee"
                    },
                    "content": {
                        "type": "string",
                        "description": "Inhalt/Beschreibung der Idee"
                    }
                },
                "required": ["title", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "idea_find",
            "description": "Suche nach Ideen/Notizen anhand eines Suchbegriffs.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Suchbegriff"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "idea_update",
            "description": "Aktualisiere eine bestehende Idee (Titel oder Inhalt aendern).",
            "parameters": {
                "type": "object",
                "properties": {
                    "idea_name": {
                        "type": "string",
                        "description": "Name der zu aktualisierenden Idee"
                    },
                    "new_title": {
                        "type": "string",
                        "description": "Neuer Titel (optional)"
                    },
                    "new_content": {
                        "type": "string",
                        "description": "Neuer Inhalt (optional)"
                    }
                },
                "required": ["idea_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "idea_delete",
            "description": "Loesche eine Idee/Notiz.",
            "parameters": {
                "type": "object",
                "properties": {
                    "idea_name": {
                        "type": "string",
                        "description": "Name der zu loeschenden Idee"
                    }
                },
                "required": ["idea_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "idea_connect",
            "description": "Verbinde zwei Ideen miteinander (erstelle eine Kante/Verbindung).",
            "parameters": {
                "type": "object",
                "properties": {
                    "idea1": {
                        "type": "string",
                        "description": "Name der ersten Idee"
                    },
                    "idea2": {
                        "type": "string",
                        "description": "Name der zweiten Idee"
                    }
                },
                "required": ["idea1", "idea2"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "idea_add_image",
            "description": "Fuege ein Bild zu einer Idee hinzu.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "URL des Bildes"
                    },
                    "title": {
                        "type": "string",
                        "description": "Titel/Beschreibung des Bildes"
                    }
                },
                "required": ["url"]
            }
        }
    },
]

# =============================================================================
# DESKTOP AUTOMATION TOOLS
# =============================================================================

DESKTOP_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "desktop_task",
            "description": "Fuehre eine komplexe Desktop-Aufgabe aus (z.B. App oeffnen, Dateien verwalten).",
            "parameters": {
                "type": "object",
                "properties": {
                    "goal": {
                        "type": "string",
                        "description": "Beschreibung der Aufgabe (z.B. 'Oeffne Chrome und geh zu Google')"
                    }
                },
                "required": ["goal"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "desktop_open_app",
            "description": "Oeffne eine Anwendung auf dem Desktop.",
            "parameters": {
                "type": "object",
                "properties": {
                    "app_name": {
                        "type": "string",
                        "description": "Name der zu oeffnenden App (z.B. 'Chrome', 'Notepad', 'VS Code')"
                    }
                },
                "required": ["app_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "desktop_click",
            "description": "Klicke auf ein Element auf dem Bildschirm.",
            "parameters": {
                "type": "object",
                "properties": {
                    "element_description": {
                        "type": "string",
                        "description": "Beschreibung des zu klickenden Elements"
                    }
                },
                "required": ["element_description"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "desktop_type",
            "description": "Tippe Text ein.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Der einzugebende Text"
                    }
                },
                "required": ["text"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "desktop_press_key",
            "description": "Druecke eine Taste oder Tastenkombination.",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {
                        "type": "string",
                        "description": "Taste (z.B. 'Enter', 'Escape', 'Ctrl+C')"
                    }
                },
                "required": ["key"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "desktop_screenshot",
            "description": "Mache einen Screenshot des Bildschirms.",
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
            "name": "desktop_scroll",
            "description": "Scrolle auf dem Bildschirm.",
            "parameters": {
                "type": "object",
                "properties": {
                    "direction": {
                        "type": "string",
                        "enum": ["up", "down"],
                        "description": "Scroll-Richtung"
                    },
                    "amount": {
                        "type": "integer",
                        "description": "Scroll-Menge (Standard: 3)"
                    }
                },
                "required": []
            }
        }
    },
]

# =============================================================================
# CODE GENERATION TOOLS
# =============================================================================

CODE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "code_generate",
            "description": "Generiere ein neues Code-Projekt basierend auf einer Beschreibung.",
            "parameters": {
                "type": "object",
                "properties": {
                    "description": {
                        "type": "string",
                        "description": "Beschreibung des zu erstellenden Projekts"
                    },
                    "tech_stack": {
                        "type": "string",
                        "description": "Technologie-Stack (z.B. 'React', 'Python Flask', 'Node.js')"
                    }
                },
                "required": ["description"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "code_status",
            "description": "Pruefe den Status einer laufenden Code-Generierung.",
            "parameters": {
                "type": "object",
                "properties": {
                    "job_id": {
                        "type": "string",
                        "description": "Job-ID der Generierung (optional, nimmt letzte)"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "code_preview_start",
            "description": "Starte die Live-Preview eines generierten Projekts.",
            "parameters": {
                "type": "object",
                "properties": {
                    "job_id": {
                        "type": "string",
                        "description": "Job-ID des Projekts (optional)"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "code_preview_stop",
            "description": "Stoppe die Live-Preview.",
            "parameters": {
                "type": "object",
                "properties": {
                    "job_id": {
                        "type": "string",
                        "description": "Job-ID des Projekts (optional)"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "code_list",
            "description": "Liste alle generierten Projekte auf.",
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
            "name": "code_cancel",
            "description": "Breche eine laufende Code-Generierung ab.",
            "parameters": {
                "type": "object",
                "properties": {
                    "job_id": {
                        "type": "string",
                        "description": "Job-ID der abzubrechenden Generierung"
                    }
                },
                "required": ["job_id"]
            }
        }
    },
]

# =============================================================================
# CONVERSATION TOOLS (handled by Rachel directly)
# =============================================================================

CONVERSATION_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "conversation_clarify",
            "description": "Bitte um Klaerung wenn die Anfrage unklar ist.",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "Die Klaerungsfrage an den User"
                    }
                },
                "required": ["question"]
            }
        }
    },
]

# =============================================================================
# COMBINED TOOL LIST
# =============================================================================

def get_all_tools() -> List[Dict[str, Any]]:
    """Get all available tools as OpenAI-compatible definitions."""
    return (
        BUBBLE_TOOLS +
        IDEA_TOOLS +
        DESKTOP_TOOLS +
        CODE_TOOLS +
        CONVERSATION_TOOLS
    )


def get_tool_count() -> int:
    """Get total number of available tools."""
    return len(get_all_tools())


# Tool name to event_type mapping (for backwards compatibility)
TOOL_TO_EVENT_TYPE = {
    # Bubble tools
    "bubble_list": "bubble.list",
    "bubble_create": "bubble.create",
    "bubble_enter": "bubble.enter",
    "bubble_exit": "bubble.exit",
    "bubble_delete": "bubble.delete",
    "bubble_stats": "bubble.stats",
    "bubble_score": "bubble.score",
    "bubble_promote": "bubble.promote",
    "bubble_current": "bubble.current",
    # Idea tools
    "idea_list": "idea.list",
    "idea_create": "idea.create",
    "idea_find": "idea.find",
    "idea_update": "idea.update",
    "idea_delete": "idea.delete",
    "idea_connect": "idea.connect",
    "idea_add_image": "idea.add_image",
    # Desktop tools
    "desktop_task": "desktop.task",
    "desktop_open_app": "desktop.open_app",
    "desktop_click": "desktop.click",
    "desktop_type": "desktop.type",
    "desktop_press_key": "desktop.press_key",
    "desktop_screenshot": "desktop.screenshot",
    "desktop_scroll": "desktop.scroll",
    # Code tools
    "code_generate": "code.generate",
    "code_status": "code.status",
    "code_preview_start": "code.preview.start",
    "code_preview_stop": "code.preview.stop",
    "code_list": "code.list",
    "code_cancel": "code.cancel",
    # Conversation
    "conversation_clarify": "conversation.clarify",
}


__all__ = [
    "BUBBLE_TOOLS",
    "IDEA_TOOLS",
    "DESKTOP_TOOLS",
    "CODE_TOOLS",
    "CONVERSATION_TOOLS",
    "get_all_tools",
    "get_tool_count",
    "TOOL_TO_EVENT_TYPE",
]
