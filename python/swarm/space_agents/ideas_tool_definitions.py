"""
Ideas Space Tool Definitions — JSON schemas for all Ideas/Bubbles tools.

~40 tools covering: Bubble management, Idea/Note management,
Summary/Docs generation, Format conversion, and Exploration.
"""

from typing import List, Dict, Any


# =============================================================================
# BUBBLE MANAGEMENT TOOLS (13)
# =============================================================================

BUBBLE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "bubble_list",
            "description": "Liste alle Spaces/Bubbles im Multiverse auf. Zeigt Namen, Score und Anzahl Ideen.",
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
            "name": "bubble_find",
            "description": "Suche einen Space/Bubble per Name (fuzzy Suche). Betritt den Space automatisch.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Suchbegriff fuer den Space-Namen"
                    },
                    "auto_enter": {
                        "type": "boolean",
                        "description": "Automatisch betreten wenn gefunden (default: true)"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "bubble_create",
            "description": "Erstelle einen neuen Space/Bubble. Gibt ID und Titel zurueck.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Name des neuen Spaces"
                    },
                    "description": {
                        "type": "string",
                        "description": "Optionale Beschreibung des Spaces"
                    }
                },
                "required": ["title"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "bubble_update",
            "description": "Aktualisiere Titel oder Beschreibung eines Spaces.",
            "parameters": {
                "type": "object",
                "properties": {
                    "bubble_name": {
                        "type": "string",
                        "description": "Aktueller Name des Spaces"
                    },
                    "title": {
                        "type": "string",
                        "description": "Neuer Titel"
                    },
                    "description": {
                        "type": "string",
                        "description": "Neue Beschreibung"
                    }
                },
                "required": ["bubble_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "bubble_delete",
            "description": "Loesche einen Space und alle enthaltenen Ideen.",
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
            "name": "bubble_delete_all_except",
            "description": "Loesche ALLE Spaces ausser den angegebenen.",
            "parameters": {
                "type": "object",
                "properties": {
                    "keep": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Liste der Space-Namen die behalten werden sollen"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "bubble_enter",
            "description": "Betrete einen Space um darin zu arbeiten. Wechselt den Kontext.",
            "parameters": {
                "type": "object",
                "properties": {
                    "bubble_name": {
                        "type": "string",
                        "description": "Name des Spaces"
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
            "description": "Verlasse den aktuellen Space. Zurueck zur Multiverse-Uebersicht.",
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
            "name": "bubble_stats",
            "description": "Zeige Statistiken des aktuellen Spaces (Anzahl Ideen, Verbindungen, Score).",
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
            "description": "Berechne Score eines Spaces basierend auf Inhalt und Aktivitaet.",
            "parameters": {
                "type": "object",
                "properties": {
                    "bubble_name": {
                        "type": "string",
                        "description": "Space-Name (optional, sonst aktueller Space)"
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
            "description": "Befoerdere einen Space zu einem Coding-Projekt (fuer Code-Generierung).",
            "parameters": {
                "type": "object",
                "properties": {
                    "bubble_name": {
                        "type": "string",
                        "description": "Name des Spaces"
                    }
                },
                "required": ["bubble_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "bubble_evaluate",
            "description": "Evaluiere die Entwicklung/Reife eines Spaces ueber Zeit.",
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
            "name": "bubble_current",
            "description": "Zeige aktuellen Standort: welcher Space oder Multiverse.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
]


# =============================================================================
# IDEA/NOTE MANAGEMENT TOOLS (18)
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
            "name": "idea_count",
            "description": "Zaehle die Ideen im aktuellen Space.",
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
                        "description": "Inhalt/Beschreibung (optional)"
                    },
                    "type": {
                        "type": "string",
                        "enum": ["note", "idea", "link", "image"],
                        "description": "Node-Typ (default: note)"
                    }
                },
                "required": ["title"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "idea_find",
            "description": "Suche nach Ideen per Name oder Inhalt (fuzzy).",
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
            "description": "Aktualisiere eine Idee (Titel, Inhalt, oder generiere neuen Inhalt).",
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
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["literal", "generate"],
                        "description": "literal=direkt, generate=LLM generiert Inhalt"
                    },
                    "topic": {
                        "type": "string",
                        "description": "Thema fuer generierte Inhalte (bei mode=generate)"
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
            "description": "Verbinde zwei Ideen miteinander (erstelle eine Kante).",
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
            "name": "idea_disconnect",
            "description": "Entferne die Verbindung zwischen zwei Ideen.",
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
            "name": "idea_connect_multi",
            "description": "Verbinde mehrere Ideen auf einmal.",
            "parameters": {
                "type": "object",
                "properties": {
                    "connections": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "from": {"type": "string"},
                                "to": {"type": "string"}
                            }
                        },
                        "description": "Liste von {from, to} Verbindungen"
                    }
                },
                "required": ["connections"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "idea_link_to_root",
            "description": "Verlinke eine Idee auf Root/Multiverse-Ebene.",
            "parameters": {
                "type": "object",
                "properties": {
                    "idea_name": {
                        "type": "string",
                        "description": "Name der Idee"
                    }
                },
                "required": ["idea_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "idea_add_image",
            "description": "Fuege ein Bild als Idee/Node hinzu.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "URL des Bildes"
                    },
                    "title": {
                        "type": "string",
                        "description": "Titel/Beschreibung"
                    }
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "idea_expand",
            "description": "Erweitere kurze Ideen mit LLM-generiertem Inhalt.",
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
            "name": "idea_move",
            "description": "Verschiebe eine Idee an eine neue Position.",
            "parameters": {
                "type": "object",
                "properties": {
                    "idea_name": {
                        "type": "string",
                        "description": "Name der Idee"
                    },
                    "x": {
                        "type": "number",
                        "description": "Neue X-Position"
                    },
                    "y": {
                        "type": "number",
                        "description": "Neue Y-Position"
                    }
                },
                "required": ["idea_name", "x", "y"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "idea_classify",
            "description": "Klassifiziere/kategorisiere eine Idee per LLM.",
            "parameters": {
                "type": "object",
                "properties": {
                    "idea_name": {
                        "type": "string",
                        "description": "Name der zu klassifizierenden Idee"
                    }
                },
                "required": ["idea_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "idea_explain",
            "description": "Generiere eine Erklaerung/Analyse einer Idee per LLM.",
            "parameters": {
                "type": "object",
                "properties": {
                    "idea_name": {
                        "type": "string",
                        "description": "Name der Idee"
                    }
                },
                "required": ["idea_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "idea_auto_link",
            "description": "Automatisch semantische Verbindungen zwischen Ideen erkennen und erstellen.",
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
            "name": "idea_analyze_links",
            "description": "Analysiere Ideen und schlage sinnvolle Verbindungen vor.",
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
            "name": "idea_format_table",
            "description": "Formatiere eine Idee als Tabelle.",
            "parameters": {
                "type": "object",
                "properties": {
                    "idea_name": {
                        "type": "string",
                        "description": "Name der Idee"
                    }
                },
                "required": ["idea_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "idea_create_batch",
            "description": "Erstelle MEHRERE Ideen auf einmal zu einem Thema. "
                           "Generiert automatisch Titel und Beschreibungen per LLM. "
                           "Nutze dieses Tool wenn der User mehrere Ideen gleichzeitig will (z.B. 'Erstelle 15 Ideen ueber X').",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "Thema/Bereich fuer die Ideen"
                    },
                    "count": {
                        "type": "integer",
                        "description": "Anzahl der zu erstellenden Ideen (max 20)"
                    }
                },
                "required": ["topic", "count"]
            }
        }
    },
]


# =============================================================================
# SUMMARY & DOCUMENTATION TOOLS (6)
# =============================================================================

SUMMARY_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "idea_summarize",
            "description": "Generiere eine KI-Zusammenfassung einer Idee oder des gesamten Spaces.",
            "parameters": {
                "type": "object",
                "properties": {
                    "bubble_name": {
                        "type": "string",
                        "description": "Space-Name (optional, sonst aktueller Space)"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "idea_whitepaper",
            "description": "Generiere ein umfassendes Whitepaper aus dem Space-Inhalt.",
            "parameters": {
                "type": "object",
                "properties": {
                    "bubble_name": {
                        "type": "string",
                        "description": "Space-Name (optional)"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "idea_project_structure",
            "description": "Generiere eine Projektstruktur aus den Anforderungen im Space.",
            "parameters": {
                "type": "object",
                "properties": {
                    "bubble_name": {
                        "type": "string",
                        "description": "Space-Name (optional)"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "idea_feature_docs",
            "description": "Generiere Feature-Dokumentation aus Space-Inhalten.",
            "parameters": {
                "type": "object",
                "properties": {
                    "bubble_name": {
                        "type": "string",
                        "description": "Space-Name (optional)"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "summary_list",
            "description": "Liste alle generierten Zusammenfassungen auf.",
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
            "name": "summary_get",
            "description": "Hole eine bestimmte Zusammenfassung.",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary_id": {
                        "type": "string",
                        "description": "ID der Zusammenfassung"
                    }
                },
                "required": ["summary_id"]
            }
        }
    },
]


# =============================================================================
# FORMAT CONVERSION TOOLS (2) — parametric, covers all 11 formats
# =============================================================================

FORMAT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "idea_format",
            "description": "Formatiere/konvertiere eine Idee in ein strukturiertes Format. "
                           "Verfuegbare Formate: table, action_list, pros_cons, hierarchy, "
                           "specs, kanban, mindmap, swot, user_story, flowchart, note.",
            "parameters": {
                "type": "object",
                "properties": {
                    "idea_name": {
                        "type": "string",
                        "description": "Name der Idee die formatiert werden soll"
                    },
                    "format_type": {
                        "type": "string",
                        "enum": [
                            "table", "action_list", "pros_cons", "hierarchy",
                            "specs", "kanban", "mindmap", "swot",
                            "user_story", "flowchart", "note"
                        ],
                        "description": "Zielformat"
                    }
                },
                "required": ["idea_name", "format_type"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "idea_list_formats",
            "description": "Zeige alle verfuegbaren Format-Typen.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
]


# =============================================================================
# EXPLORATION TOOLS (7)
# =============================================================================

EXPLORATION_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "exploration_start",
            "description": "Starte eine KI-Exploration der Ideen-Verbindungen im aktuellen Space.",
            "parameters": {
                "type": "object",
                "properties": {
                    "depth": {
                        "type": "integer",
                        "description": "Tiefe der Exploration (default: 4)"
                    },
                    "context": {
                        "type": "string",
                        "description": "Kontext/Richtung fuer die Exploration"
                    },
                    "mode": {
                        "type": "string",
                        "enum": ["auto", "interactive", "guided"],
                        "description": "auto=autonom, interactive=fragt bei jeder Verbindung, guided=User steuert"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "exploration_stop",
            "description": "Stoppe eine laufende Exploration.",
            "parameters": {
                "type": "object",
                "properties": {
                    "session_id": {
                        "type": "string",
                        "description": "Session-ID der Exploration"
                    }
                },
                "required": ["session_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "exploration_status",
            "description": "Zeige Status einer laufenden Exploration.",
            "parameters": {
                "type": "object",
                "properties": {
                    "session_id": {
                        "type": "string",
                        "description": "Session-ID"
                    }
                },
                "required": ["session_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "exploration_accept",
            "description": "Akzeptiere eine vorgeschlagene Verbindung.",
            "parameters": {
                "type": "object",
                "properties": {
                    "session_id": {"type": "string"},
                    "connection_id": {"type": "string"}
                },
                "required": ["session_id", "connection_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "exploration_reject",
            "description": "Lehne eine vorgeschlagene Verbindung ab.",
            "parameters": {
                "type": "object",
                "properties": {
                    "session_id": {"type": "string"},
                    "connection_id": {"type": "string"}
                },
                "required": ["session_id", "connection_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "exploration_deeper",
            "description": "Explore tiefer von einem bestimmten Node aus.",
            "parameters": {
                "type": "object",
                "properties": {
                    "session_id": {"type": "string"},
                    "node_id": {"type": "string"},
                    "depth": {"type": "integer"}
                },
                "required": ["session_id", "node_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "exploration_visualize",
            "description": "Visualisiere Explorations-Ergebnisse.",
            "parameters": {
                "type": "object",
                "properties": {
                    "session_id": {"type": "string"}
                },
                "required": ["session_id"]
            }
        }
    },
]


# =============================================================================
# COMBINED
# =============================================================================

def get_ideas_tools() -> List[Dict[str, Any]]:
    """Get all Ideas/Bubbles space tools as OpenAI-compatible definitions."""
    return (
        BUBBLE_TOOLS +
        IDEA_TOOLS +
        SUMMARY_TOOLS +
        FORMAT_TOOLS +
        EXPLORATION_TOOLS
    )


def get_ideas_tool_count() -> int:
    """Get total number of Ideas space tools."""
    return len(get_ideas_tools())


# Tool name → event_type mapping (for logging/tracking)
TOOL_TO_EVENT_TYPE = {
    # Bubble
    "bubble_list": "bubble.list",
    "bubble_find": "bubble.find",
    "bubble_create": "bubble.create",
    "bubble_update": "bubble.update",
    "bubble_delete": "bubble.delete",
    "bubble_delete_all_except": "bubble.delete_all_except",
    "bubble_enter": "bubble.enter",
    "bubble_exit": "bubble.exit",
    "bubble_stats": "bubble.stats",
    "bubble_score": "bubble.score",
    "bubble_promote": "bubble.promote",
    "bubble_evaluate": "bubble.evaluate",
    "bubble_current": "bubble.current",
    # Idea
    "idea_list": "idea.list",
    "idea_count": "idea.count",
    "idea_create": "idea.create",
    "idea_find": "idea.find",
    "idea_update": "idea.update",
    "idea_delete": "idea.delete",
    "idea_connect": "idea.connect",
    "idea_disconnect": "idea.disconnect",
    "idea_connect_multi": "idea.connect_multi",
    "idea_link_to_root": "idea.link_to_root",
    "idea_add_image": "idea.add_image",
    "idea_expand": "idea.expand",
    "idea_move": "idea.move",
    "idea_classify": "idea.classify",
    "idea_explain": "idea.explain",
    "idea_auto_link": "idea.auto_link",
    "idea_analyze_links": "idea.analyze_links",
    "idea_format_table": "idea.format_table",
    "idea_create_batch": "idea.create_batch",
    # Summary
    "idea_summarize": "idea.summarize",
    "idea_whitepaper": "idea.whitepaper",
    "idea_project_structure": "idea.project_structure",
    "idea_feature_docs": "idea.feature_docs",
    "summary_list": "summary.list",
    "summary_get": "summary.get",
    # Format
    "idea_format": "idea.convert_format",
    "idea_list_formats": "idea.list_formats",
    # Exploration
    "exploration_start": "exploration.start",
    "exploration_stop": "exploration.stop",
    "exploration_status": "exploration.status",
    "exploration_accept": "exploration.accept",
    "exploration_reject": "exploration.reject",
    "exploration_deeper": "exploration.deeper",
    "exploration_visualize": "exploration.visualize",
}
