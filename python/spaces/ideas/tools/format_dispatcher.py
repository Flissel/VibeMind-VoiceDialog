"""
Format Dispatcher - Central hub for format conversion.

Manages format agents that can convert ideas between any format type:
note <-> table <-> action_list <-> pros_cons <-> hierarchy <-> specs

Each format agent knows how to:
1. Parse content from other formats
2. Generate content in its target format
3. Validate the output
"""

import json
import logging
import sys
from datetime import datetime
from typing import Dict, Any, Optional, Tuple

from data.format_schemas import (
    FORMAT_SCHEMAS,
    DEFAULT_FORMAT,
    get_format_schema,
    validate_format_type,
    get_available_format_types
)
from data.repository import CanvasRepository, IdeasRepository
from data.models import CanvasNode

logger = logging.getLogger(__name__)

# =============================================================================
# FORMAT AGENT BASE
# =============================================================================

def _get_llm_client():
    """Get OpenRouter LLM client."""
    from openai import OpenAI
    import os

    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY not set")

    return OpenAI(
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1"
    )


def _call_format_agent(prompt: str, target_format: str) -> Dict[str, Any]:
    """Call LLM to convert content to target format."""
    try:
        client = _get_llm_client()

        response = client.chat.completions.create(
            model="anthropic/claude-sonnet-4.5",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=3000,
        )

        content = response.choices[0].message.content.strip()

        # Extract JSON from response
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        elif not content.startswith("{") and "{" in content:
            first_brace = content.find("{")
            content = content[first_brace:]

        result = json.loads(content)

        # Ensure type field is correct
        type_mapping = {
            "simple_table": "table",
            "pros_cons_table": "pros_cons_table",
        }
        expected_type = type_mapping.get(target_format, target_format)
        if "type" not in result:
            result["type"] = expected_type

        return result

    except Exception as e:
        logger.error(f"Format agent call failed: {e}")
        raise


def _extract_content_text(content_json: Optional[Dict], plain_content: str = "") -> str:
    """Extract plain text from any format for conversion."""
    if not content_json:
        return plain_content

    content_type = content_json.get("type", "note")
    parts = []

    # Add title if present
    if content_json.get("title"):
        parts.append(f"Titel: {content_json['title']}")

    if content_type == "note":
        parts.append(content_json.get("text", ""))

    elif content_type == "table":
        headers = content_json.get("headers", [])
        rows = content_json.get("rows", [])
        if headers:
            parts.append("Spalten: " + ", ".join(headers))
        for row in rows:
            parts.append(" | ".join(str(cell) for cell in row))

    elif content_type == "action_list":
        for item in content_json.get("items", []):
            task = item.get("task", "")
            status = item.get("status", "pending")
            priority = item.get("priority", "medium")
            parts.append(f"- [{status}] {task} (Prioritaet: {priority})")

    elif content_type == "pros_cons_table":
        parts.append("Vorteile:")
        for pro in content_json.get("pros", []):
            parts.append(f"+ {pro.get('point', '')}")
        parts.append("Nachteile:")
        for con in content_json.get("cons", []):
            parts.append(f"- {con.get('point', '')}")

    elif content_type == "hierarchy":
        for level in content_json.get("levels", []):
            level_num = level.get("level", 1)
            for item in level.get("items", []):
                indent = "  " * (level_num - 1)
                parts.append(f"{indent}- {item.get('name', '')}")

    elif content_type == "technical_specs":
        for spec in content_json.get("specifications", []):
            cat = spec.get("category", "")
            req = spec.get("requirement", "")
            parts.append(f"[{cat}] {req}")

    elif content_type == "comparison_table":
        options = content_json.get("options", [])
        criteria = content_json.get("criteria", [])
        for opt in options:
            parts.append(f"Option: {opt.get('name', '')}")

    return "\n".join(parts) if parts else plain_content


# =============================================================================
# FORMAT-SPECIFIC AGENTS
# =============================================================================

def format_as_note(source_content: Dict[str, Any], title: str = "") -> Dict[str, Any]:
    """Convert any format to a well-written plain note using LLM."""
    text = _extract_content_text(source_content)
    original_title = source_content.get("title", title)

    prompt = f"""Konvertiere diesen strukturierten Inhalt in eine gut lesbare Textnotiz:

TITEL: {original_title}
INHALT:
{text}

Formatiere als JSON:
{{
  "type": "note",
  "title": "Notiz-Titel",
  "text": "Gut formulierter Fliesstext, der alle Informationen natuerlich zusammenfasst."
}}

WICHTIG:
- Fliesstext, keine Aufzaehlungen
- Alle Informationen erhalten
- Natuerlich formuliert, gut lesbar
"""

    try:
        result = _call_format_agent(prompt, "note")
        result["metadata"] = {
            "source": "converted",
            "original_format": source_content.get("type", "unknown"),
            "created_at": datetime.now().isoformat(),
            "formatted_by": "NoteAgent"
        }
        return result
    except Exception:
        # Fallback: pure logic extraction if LLM fails
        return {
            "type": "note",
            "title": original_title,
            "text": text,
            "metadata": {
                "source": "converted",
                "original_format": source_content.get("type", "unknown"),
                "created_at": datetime.now().isoformat(),
                "formatted_by": "NoteAgent (fallback)"
            }
        }


def format_as_table(source_content: Dict[str, Any], title: str = "", columns: str = "") -> Dict[str, Any]:
    """Convert any format to table."""
    text = _extract_content_text(source_content)
    original_title = source_content.get("title", title)

    column_hint = f"\nGewuenschte Spalten: {columns}" if columns else ""

    prompt = f"""Konvertiere diesen Inhalt in eine Tabelle:

TITEL: {original_title}
INHALT:
{text}
{column_hint}

Formatiere als JSON:
{{
  "type": "table",
  "title": "Tabellentitel",
  "headers": ["Spalte1", "Spalte2", "Spalte3"],
  "rows": [
    ["Wert1", "Wert2", "Wert3"]
  ]
}}

WICHTIG:
- Extrahiere strukturierte Informationen
- Jede Zeile muss genau so viele Werte haben wie Headers
- Verwende "" fuer leere Felder
"""

    result = _call_format_agent(prompt, "table")
    result["metadata"] = {
        "source_idea": original_title,
        "original_format": source_content.get("type", "unknown"),
        "created_at": datetime.now().isoformat(),
        "formatted_by": "TableAgent"
    }
    return result


def format_as_action_list(source_content: Dict[str, Any], title: str = "") -> Dict[str, Any]:
    """Convert any format to action list."""
    text = _extract_content_text(source_content)
    original_title = source_content.get("title", title)

    prompt = f"""Konvertiere diesen Inhalt in eine Aufgabenliste:

TITEL: {original_title}
INHALT:
{text}

Formatiere als JSON:
{{
  "type": "action_list",
  "title": "Aufgabenliste",
  "items": [
    {{
      "task": "Konkrete Aufgabe",
      "status": "pending",
      "priority": "medium",
      "assignee": "Rachel"
    }}
  ]
}}

WICHTIG:
- Extrahiere alle actionable Aufgaben
- Status: pending, in_progress, completed
- Priority: low, medium, high, critical
"""

    result = _call_format_agent(prompt, "action_list")
    result["metadata"] = {
        "original_format": source_content.get("type", "unknown"),
        "created_at": datetime.now().isoformat(),
        "formatted_by": "ActionAgent"
    }
    return result


def format_as_pros_cons(source_content: Dict[str, Any], title: str = "") -> Dict[str, Any]:
    """Convert any format to pros/cons table."""
    text = _extract_content_text(source_content)
    original_title = source_content.get("title", title)

    prompt = f"""Analysiere diesen Inhalt und erstelle eine Pro-Contra-Liste:

TITEL: {original_title}
INHALT:
{text}

Formatiere als JSON:
{{
  "type": "pros_cons_table",
  "title": "Pro-Contra Analyse",
  "topic": "Was analysiert wird",
  "pros": [
    {{
      "point": "Vorteil",
      "weight": 3,
      "evidence": "Begruendung"
    }}
  ],
  "cons": [
    {{
      "point": "Nachteil",
      "weight": 2,
      "evidence": "Begruendung",
      "mitigation": "Loesungsansatz"
    }}
  ],
  "summary": {{
    "overall_rating": 7,
    "recommendation": "Empfehlung"
  }}
}}
"""

    result = _call_format_agent(prompt, "pros_cons_table")
    result["metadata"] = {
        "original_format": source_content.get("type", "unknown"),
        "created_at": datetime.now().isoformat(),
        "formatted_by": "ProsConsAgent"
    }
    return result


def format_as_hierarchy(source_content: Dict[str, Any], title: str = "") -> Dict[str, Any]:
    """Convert any format to hierarchy/outline."""
    text = _extract_content_text(source_content)
    original_title = source_content.get("title", title)

    prompt = f"""Strukturiere diesen Inhalt als hierarchische Gliederung:

TITEL: {original_title}
INHALT:
{text}

Formatiere als JSON:
{{
  "type": "hierarchy",
  "title": "Gliederung",
  "root_concept": "Hauptthema",
  "levels": [
    {{
      "level": 1,
      "name": "Hauptpunkte",
      "items": [
        {{
          "name": "Punkt 1",
          "description": "Beschreibung",
          "children": ["Unterpunkt 1.1", "Unterpunkt 1.2"]
        }}
      ]
    }},
    {{
      "level": 2,
      "name": "Unterpunkte",
      "items": [
        {{
          "name": "Unterpunkt 1.1",
          "description": "Detail",
          "parent": "Punkt 1"
        }}
      ]
    }}
  ]
}}

WICHTIG:
- Erstelle eine logische Hierarchie
- Mindestens 2 Ebenen
- Verknuepfe Parent-Child-Beziehungen
"""

    result = _call_format_agent(prompt, "hierarchy")
    result["metadata"] = {
        "original_format": source_content.get("type", "unknown"),
        "created_at": datetime.now().isoformat(),
        "formatted_by": "HierarchyAgent"
    }
    return result


def format_as_specs(source_content: Dict[str, Any], title: str = "") -> Dict[str, Any]:
    """Convert any format to technical specifications."""
    text = _extract_content_text(source_content)
    original_title = source_content.get("title", title)

    prompt = f"""Extrahiere technische Spezifikationen aus diesem Inhalt:

TITEL: {original_title}
INHALT:
{text}

Formatiere als JSON:
{{
  "type": "technical_specs",
  "title": "Technische Spezifikation",
  "component": "Betroffene Komponente",
  "specifications": [
    {{
      "category": "Performance|Security|Scalability|Usability",
      "requirement": "Konkrete Anforderung",
      "priority": "must_have|should_have|nice_to_have",
      "acceptance_criteria": "Wie wird es getestet?"
    }}
  ],
  "implementation_notes": "Hinweise zur Implementierung"
}}

WICHTIG:
- Extrahiere alle technischen Anforderungen
- Kategorisiere nach Bereich
- Definiere klare Akzeptanzkriterien
"""

    result = _call_format_agent(prompt, "technical_specs")
    result["metadata"] = {
        "original_format": source_content.get("type", "unknown"),
        "created_at": datetime.now().isoformat(),
        "formatted_by": "SpecsAgent"
    }
    return result


def format_as_kanban(source_content: Dict[str, Any], title: str = "") -> Dict[str, Any]:
    """Convert any format to a Kanban board with columns and cards."""
    text = _extract_content_text(source_content)
    original_title = source_content.get("title", title)

    prompt = f"""Strukturiere diesen Inhalt als Kanban-Board:

TITEL: {original_title}
INHALT:
{text}

Formatiere als JSON:
{{
  "type": "kanban",
  "title": "Kanban Board",
  "columns": [
    {{
      "name": "Backlog",
      "color": "#94a3b8",
      "cards": [
        {{
          "title": "Aufgabe/Idee",
          "description": "Kurze Beschreibung",
          "priority": "medium",
          "labels": ["label1"]
        }}
      ]
    }},
    {{
      "name": "In Progress",
      "color": "#3b82f6",
      "cards": []
    }},
    {{
      "name": "Done",
      "color": "#22c55e",
      "cards": []
    }}
  ]
}}

WICHTIG:
- Verteile Inhalte sinnvoll auf Spalten (Backlog, In Progress, Review, Done)
- Jede Card braucht title + description
- Priority: low, medium, high, critical
- Labels fuer Kategorisierung
"""

    result = _call_format_agent(prompt, "kanban")
    result["metadata"] = {
        "original_format": source_content.get("type", "unknown"),
        "created_at": datetime.now().isoformat(),
        "formatted_by": "KanbanAgent"
    }
    return result


def format_as_mindmap(source_content: Dict[str, Any], title: str = "") -> Dict[str, Any]:
    """Convert any format to a mind map with central concept and branches."""
    text = _extract_content_text(source_content)
    original_title = source_content.get("title", title)

    prompt = f"""Strukturiere diesen Inhalt als Mind Map:

TITEL: {original_title}
INHALT:
{text}

Formatiere als JSON:
{{
  "type": "mindmap",
  "title": "Mind Map",
  "center": {{
    "label": "Zentrales Konzept",
    "description": "Kurze Beschreibung"
  }},
  "branches": [
    {{
      "label": "Hauptzweig 1",
      "color": "#3b82f6",
      "children": [
        {{
          "label": "Unterpunkt",
          "description": "Detail",
          "children": []
        }}
      ]
    }}
  ]
}}

WICHTIG:
- Ein zentrales Konzept in der Mitte
- 3-6 Hauptzweige (branches)
- Jeder Zweig kann Unterpunkte (children) haben
- Maximal 3 Ebenen tief
- Verschiedene Farben fuer Hauptzweige
"""

    result = _call_format_agent(prompt, "mindmap")
    result["metadata"] = {
        "original_format": source_content.get("type", "unknown"),
        "created_at": datetime.now().isoformat(),
        "formatted_by": "MindmapAgent"
    }
    return result


def format_as_swot(source_content: Dict[str, Any], title: str = "") -> Dict[str, Any]:
    """Convert any format to a SWOT analysis."""
    text = _extract_content_text(source_content)
    original_title = source_content.get("title", title)

    prompt = f"""Erstelle eine SWOT-Analyse aus diesem Inhalt:

TITEL: {original_title}
INHALT:
{text}

Formatiere als JSON:
{{
  "type": "swot",
  "title": "SWOT Analyse",
  "subject": "Was analysiert wird",
  "strengths": [
    {{
      "point": "Staerke",
      "impact": "high",
      "evidence": "Begruendung"
    }}
  ],
  "weaknesses": [
    {{
      "point": "Schwaeche",
      "impact": "medium",
      "mitigation": "Gegenmaassnahme"
    }}
  ],
  "opportunities": [
    {{
      "point": "Chance",
      "likelihood": "high",
      "action": "Naechster Schritt"
    }}
  ],
  "threats": [
    {{
      "point": "Risiko",
      "likelihood": "medium",
      "contingency": "Absicherung"
    }}
  ],
  "summary": {{
    "strategic_position": "Gesamtbewertung",
    "key_actions": ["Aktion 1", "Aktion 2"]
  }}
}}

WICHTIG:
- Mindestens 2 Punkte pro Quadrant
- Impact/Likelihood: low, medium, high
- Konkrete Actions und Mitigations
"""

    result = _call_format_agent(prompt, "swot")
    result["metadata"] = {
        "original_format": source_content.get("type", "unknown"),
        "created_at": datetime.now().isoformat(),
        "formatted_by": "SwotAgent"
    }
    return result


def format_as_user_story(source_content: Dict[str, Any], title: str = "") -> Dict[str, Any]:
    """Convert any format to user stories."""
    text = _extract_content_text(source_content)
    original_title = source_content.get("title", title)

    prompt = f"""Extrahiere User Stories aus diesem Inhalt:

TITEL: {original_title}
INHALT:
{text}

Formatiere als JSON:
{{
  "type": "user_story",
  "title": "User Stories",
  "epic": "Uebergeordnetes Thema",
  "stories": [
    {{
      "id": "US-001",
      "role": "Als [Rolle/Persona]",
      "want": "moechte ich [Funktionalitaet]",
      "benefit": "damit [Nutzen/Wert]",
      "acceptance_criteria": [
        "Gegeben [Kontext], wenn [Aktion], dann [Ergebnis]"
      ],
      "priority": "must_have",
      "story_points": 3
    }}
  ],
  "personas": [
    {{
      "name": "Persona-Name",
      "role": "Rolle",
      "goals": ["Ziel 1"]
    }}
  ]
}}

WICHTIG:
- Verwende das Format "Als [Rolle] moechte ich [X], damit [Y]"
- Mindestens 1 Acceptance Criterion pro Story
- Priority: must_have, should_have, could_have, wont_have
- Story Points: 1, 2, 3, 5, 8, 13
"""

    result = _call_format_agent(prompt, "user_story")
    result["metadata"] = {
        "original_format": source_content.get("type", "unknown"),
        "created_at": datetime.now().isoformat(),
        "formatted_by": "UserStoryAgent"
    }
    return result


def format_as_flowchart(source_content: Dict[str, Any], title: str = "") -> Dict[str, Any]:
    """Convert any format to a flowchart with steps and decisions."""
    text = _extract_content_text(source_content)
    original_title = source_content.get("title", title)

    prompt = f"""Strukturiere diesen Inhalt als Flowchart/Prozessdiagramm:

TITEL: {original_title}
INHALT:
{text}

Formatiere als JSON:
{{
  "type": "flowchart",
  "title": "Prozess-Flowchart",
  "description": "Was dieser Prozess beschreibt",
  "nodes": [
    {{
      "id": "start",
      "type": "start",
      "label": "Start"
    }},
    {{
      "id": "step1",
      "type": "process",
      "label": "Schritt 1",
      "description": "Was passiert hier"
    }},
    {{
      "id": "decision1",
      "type": "decision",
      "label": "Entscheidung?",
      "condition": "Was wird geprueft"
    }},
    {{
      "id": "end",
      "type": "end",
      "label": "Ende"
    }}
  ],
  "edges": [
    {{
      "from": "start",
      "to": "step1",
      "label": ""
    }},
    {{
      "from": "step1",
      "to": "decision1",
      "label": ""
    }},
    {{
      "from": "decision1",
      "to": "end",
      "label": "Ja"
    }}
  ]
}}

WICHTIG:
- Node types: start, end, process, decision, subprocess
- Jede Decision hat mindestens 2 ausgehende Edges (Ja/Nein oder Optionen)
- Linearer Flow von Start zu End
- Edges haben optionale Labels
- IDs muessen eindeutig sein
"""

    result = _call_format_agent(prompt, "flowchart")
    result["metadata"] = {
        "original_format": source_content.get("type", "unknown"),
        "created_at": datetime.now().isoformat(),
        "formatted_by": "FlowchartAgent"
    }
    return result


# =============================================================================
# FORMAT DISPATCHER
# =============================================================================

FORMAT_AGENTS = {
    "note": format_as_note,
    "table": format_as_table,
    "simple_table": format_as_table,
    "action_list": format_as_action_list,
    "pros_cons": format_as_pros_cons,
    "pros_cons_table": format_as_pros_cons,
    "hierarchy": format_as_hierarchy,
    "specs": format_as_specs,
    "technical_specs": format_as_specs,
    # Figma-inspired formats
    "kanban": format_as_kanban,
    "mindmap": format_as_mindmap,
    "mind_map": format_as_mindmap,
    "swot": format_as_swot,
    "user_story": format_as_user_story,
    "user_stories": format_as_user_story,
    "flowchart": format_as_flowchart,
    "flow": format_as_flowchart,
}


def convert_format(params: Dict[str, Any]) -> str:
    """
    Convert an idea from one format to another.

    Voice triggers:
    - "Formatiere als Tabelle"
    - "Mach eine Aufgabenliste daraus"
    - "Erstelle Pro-Contra-Liste"
    - "Strukturiere als Gliederung"
    - "Wandle in Spezifikation um"
    - "Zurueck zur Notiz"

    Args (via params):
        idea_name: Name of the idea to convert
        target_format: Target format type
        columns: Optional column names for table format

    Returns:
        str: Success/error message
    """
    idea_name = (params.get("idea_name") or params.get("name") or "").strip()
    target_format = (params.get("target_format") or params.get("format") or "").strip().lower()
    columns = params.get("columns", "")

    if not target_format:
        return "Bitte gib ein Zielformat an (table, action_list, pros_cons, hierarchy, specs, note)."

    # Normalize format names
    format_aliases = {
        "tabelle": "table",
        "aufgabenliste": "action_list",
        "tasks": "action_list",
        "todos": "action_list",
        "pro-contra": "pros_cons",
        "vorteile-nachteile": "pros_cons",
        "gliederung": "hierarchy",
        "outline": "hierarchy",
        "spezifikation": "specs",
        "notiz": "note",
        "text": "note",
        # Figma-inspired aliases
        "board": "kanban",
        "kanban-board": "kanban",
        "brett": "kanban",
        "mindmap": "mindmap",
        "mind-map": "mindmap",
        "gedankenkarte": "mindmap",
        "swot-analyse": "swot",
        "analyse": "swot",
        "user-story": "user_story",
        "stories": "user_story",
        "anforderungen": "user_story",
        "flowchart": "flowchart",
        "prozess": "flowchart",
        "ablauf": "flowchart",
        "diagramm": "flowchart",
    }
    target_format = format_aliases.get(target_format, target_format)

    if target_format not in FORMAT_AGENTS:
        available = ", ".join(FORMAT_AGENTS.keys())
        return f"Unbekanntes Format '{target_format}'. Verfuegbar: {available}"

    try:
        # Find the idea
        ideas_repo = IdeasRepository()
        canvas_repo = CanvasRepository()

        # Get current bubble
        from tools.bubble_tools import get_current_bubble_db_id
        bubble_id = get_current_bubble_db_id()

        if not bubble_id:
            return "Bitte betrete zuerst einen Space."

        # Find the node
        all_nodes = canvas_repo.list_nodes(limit=500)
        nodes_in_bubble = [n for n in all_nodes if n.linked_idea_id == bubble_id]

        target_node = None
        if idea_name:
            # Find by name
            idea_lower = idea_name.lower()
            for node in nodes_in_bubble:
                if node.title and idea_lower in node.title.lower():
                    target_node = node
                    break
        else:
            # Use first node with content
            for node in nodes_in_bubble:
                if node.content or node.content_json:
                    target_node = node
                    break

        if not target_node:
            return f"Keine Idee '{idea_name}' im aktuellen Space gefunden." if idea_name else "Keine Ideen im aktuellen Space."

        # Get source content
        source_content = target_node.content_json or {"type": "note", "text": target_node.content or ""}

        # Call the appropriate format agent
        agent = FORMAT_AGENTS[target_format]

        if target_format in ["table", "simple_table"]:
            new_content = agent(source_content, target_node.title or "", columns)
        else:
            new_content = agent(source_content, target_node.title or "")

        # Validate the generated content
        from tools.structured_formatting_tools import validate_format_schema
        is_valid, error_msg = validate_format_schema(new_content, target_format)
        if not is_valid:
            logger.warning(f"Format validation failed for {target_format}: {error_msg}")
            # Try fallback: convert to note format
            try:
                fallback_agent = FORMAT_AGENTS["note"]
                new_content = fallback_agent(source_content, target_node.title or "")
                logger.info(f"Used fallback note format for {target_format}")
            except Exception as fallback_error:
                logger.error(f"Fallback also failed: {fallback_error}")
                return f"Fehler bei der Formatierung: {error_msg}"

        # Update the node
        target_node.content_json = new_content
        target_node.format_schema = get_format_schema(target_format)
        target_node.last_formatted = datetime.now()

        # Save to database
        canvas_repo.update_node(target_node)

        # Send to Electron
        _send_format_update_to_electron(target_node.id, bubble_id, new_content, target_format)

        format_names = {
            "note": "Notiz",
            "table": "Tabelle",
            "action_list": "Aufgabenliste",
            "pros_cons": "Pro-Contra-Liste",
            "hierarchy": "Gliederung",
            "specs": "Spezifikation",
        }
        format_display = format_names.get(target_format, target_format)

        return f"Idee '{target_node.title}' als {format_display} formatiert."

    except Exception as e:
        logger.error(f"Format conversion failed: {e}")
        return f"Fehler bei der Formatierung: {str(e)}"


def _send_format_update_to_electron(node_id: str, bubble_id: str, content: Dict, format_type: str):
    """Send format update to Electron via stdout."""
    message = {
        "type": "node_structured_update",
        "node_id": node_id,
        "bubble_id": bubble_id,
        "content": content,
        "format_type": format_type,
        "timestamp": datetime.now().isoformat()
    }

    try:
        print(json.dumps(message), flush=True)
        logger.info(f"[FormatDispatcher] Sent update for node {node_id} ({format_type})")
    except Exception as e:
        logger.error(f"Failed to send format update: {e}")


def get_idea_format(params: Dict[str, Any]) -> str:
    """
    Get the current format of an idea.

    Args (via params):
        idea_name: Name of the idea

    Returns:
        str: Current format type
    """
    idea_name = (params.get("idea_name") or params.get("name") or "").strip()

    try:
        from tools.bubble_tools import get_current_bubble_db_id
        bubble_id = get_current_bubble_db_id()

        if not bubble_id:
            return "Bitte betrete zuerst einen Space."

        canvas_repo = CanvasRepository()
        all_nodes = canvas_repo.list_nodes(limit=500)
        nodes_in_bubble = [n for n in all_nodes if n.linked_idea_id == bubble_id]

        if idea_name:
            idea_lower = idea_name.lower()
            for node in nodes_in_bubble:
                if node.title and idea_lower in node.title.lower():
                    current_format = "note"
                    if node.content_json:
                        current_format = node.content_json.get("type", "note")
                    return f"Idee '{node.title}' ist als {current_format} formatiert."

        # List all formats in bubble
        formats = []
        for node in nodes_in_bubble[:10]:
            fmt = "note"
            if node.content_json:
                fmt = node.content_json.get("type", "note")
            formats.append(f"- {node.title}: {fmt}")

        return "Formate der Ideen:\n" + "\n".join(formats)

    except Exception as e:
        logger.error(f"Failed to get format: {e}")
        return f"Fehler: {str(e)}"


def list_available_formats(params: Dict[str, Any] = None) -> str:
    """
    List all available format types.

    Returns:
        str: List of formats with descriptions
    """
    formats = [
        ("note", "Einfache Textnotiz (Standard)"),
        ("table", "Tabelle mit Spalten und Zeilen"),
        ("action_list", "Aufgabenliste mit Status und Prioritaet"),
        ("pros_cons", "Pro-Contra-Analyse"),
        ("hierarchy", "Hierarchische Gliederung/Outline"),
        ("specs", "Technische Spezifikationen"),
        ("kanban", "Kanban-Board mit Spalten und Cards"),
        ("mindmap", "Mind Map mit zentralem Konzept und Zweigen"),
        ("swot", "SWOT-Analyse (Staerken, Schwaechen, Chancen, Risiken)"),
        ("user_story", "User Stories (Als X moechte ich Y, damit Z)"),
        ("flowchart", "Flowchart/Prozessdiagramm mit Schritten und Entscheidungen"),
    ]

    lines = ["Verfuegbare Formate:"]
    for fmt, desc in formats:
        lines.append(f"  - {fmt}: {desc}")

    lines.append("\nSage z.B. 'Formatiere als Kanban-Board' oder 'Mach eine Mind Map daraus'.")

    return "\n".join(lines)


# =============================================================================
# TOOL DEFINITIONS
# =============================================================================

CONVERT_FORMAT_DEFINITION = {
    "type": "function",
    "function": {
        "name": "convert_format",
        "description": "Konvertiert eine Idee in ein anderes Format (Tabelle, Aufgabenliste, Pro-Contra, Gliederung, Spezifikation, Notiz)",
        "parameters": {
            "type": "object",
            "properties": {
                "idea_name": {
                    "type": "string",
                    "description": "Name der Idee die konvertiert werden soll"
                },
                "target_format": {
                    "type": "string",
                    "enum": ["note", "table", "action_list", "pros_cons", "hierarchy", "specs"],
                    "description": "Zielformat"
                },
                "columns": {
                    "type": "string",
                    "description": "Optionale Spaltennamen fuer Tabellen (kommagetrennt)"
                }
            },
            "required": ["target_format"]
        }
    }
}

GET_FORMAT_DEFINITION = {
    "type": "function",
    "function": {
        "name": "get_idea_format",
        "description": "Zeigt das aktuelle Format einer Idee an",
        "parameters": {
            "type": "object",
            "properties": {
                "idea_name": {
                    "type": "string",
                    "description": "Name der Idee"
                }
            }
        }
    }
}

LIST_FORMATS_DEFINITION = {
    "type": "function",
    "function": {
        "name": "list_available_formats",
        "description": "Listet alle verfuegbaren Formattypen auf",
        "parameters": {
            "type": "object",
            "properties": {}
        }
    }
}

# =============================================================================
# INTENT EXECUTOR WRAPPERS
# These are used by IntentOrchestrator to handle specific format intents
# =============================================================================

def format_idea_table(params: Dict[str, Any]) -> str:
    """Format idea as table. Wrapper for convert_format with target_format=table."""
    params["target_format"] = "table"
    # Map custom_columns to columns if present (RAG classifier uses custom_columns)
    if "custom_columns" in params and "columns" not in params:
        cols = params["custom_columns"]
        if isinstance(cols, list):
            params["columns"] = ", ".join(cols)
    return convert_format(params)


def format_idea_note(params: Dict[str, Any]) -> str:
    """Format idea as simple note. Wrapper for convert_format with target_format=note."""
    params["target_format"] = "note"
    return convert_format(params)


def format_idea_action_list(params: Dict[str, Any]) -> str:
    """Format idea as action/task list. Wrapper for convert_format with target_format=action_list."""
    params["target_format"] = "action_list"
    return convert_format(params)


def format_idea_pros_cons(params: Dict[str, Any]) -> str:
    """Format idea as pros and cons list. Wrapper for convert_format with target_format=pros_cons."""
    params["target_format"] = "pros_cons"
    return convert_format(params)


def format_idea_hierarchy(params: Dict[str, Any]) -> str:
    """Format idea as hierarchy/outline. Wrapper for convert_format with target_format=hierarchy."""
    params["target_format"] = "hierarchy"
    return convert_format(params)


def format_idea_specs(params: Dict[str, Any]) -> str:
    """Format idea as technical specification. Wrapper for convert_format with target_format=specs."""
    params["target_format"] = "specs"
    return convert_format(params)


def format_idea_kanban(params: Dict[str, Any]) -> str:
    """Format idea as Kanban board. Wrapper for convert_format with target_format=kanban."""
    params["target_format"] = "kanban"
    return convert_format(params)


def format_idea_mindmap(params: Dict[str, Any]) -> str:
    """Format idea as mind map. Wrapper for convert_format with target_format=mindmap."""
    params["target_format"] = "mindmap"
    return convert_format(params)


def format_idea_swot(params: Dict[str, Any]) -> str:
    """Format idea as SWOT analysis. Wrapper for convert_format with target_format=swot."""
    params["target_format"] = "swot"
    return convert_format(params)


def format_idea_user_story(params: Dict[str, Any]) -> str:
    """Format idea as user stories. Wrapper for convert_format with target_format=user_story."""
    params["target_format"] = "user_story"
    return convert_format(params)


def format_idea_flowchart(params: Dict[str, Any]) -> str:
    """Format idea as flowchart/process diagram. Wrapper for convert_format with target_format=flowchart."""
    params["target_format"] = "flowchart"
    return convert_format(params)


# Registry for tool manager
FORMAT_TOOLS = {
    "convert_format": convert_format,
    "get_idea_format": get_idea_format,
    "list_available_formats": list_available_formats,
}

# Intent executor mappings (for IntentOrchestrator)
FORMAT_EXECUTORS = {
    "idea.format_table": format_idea_table,
    "idea.format_note": format_idea_note,
    "idea.format_action_list": format_idea_action_list,
    "idea.format_pros_cons": format_idea_pros_cons,
    "idea.format_hierarchy": format_idea_hierarchy,
    "idea.format_specs": format_idea_specs,
    "idea.format_kanban": format_idea_kanban,
    "idea.format_mindmap": format_idea_mindmap,
    "idea.format_swot": format_idea_swot,
    "idea.format_user_story": format_idea_user_story,
    "idea.format_flowchart": format_idea_flowchart,
    "idea.convert_format": convert_format,
    "idea.list_formats": list_available_formats,
}

FORMAT_TOOL_DEFINITIONS = [
    CONVERT_FORMAT_DEFINITION,
    GET_FORMAT_DEFINITION,
    LIST_FORMATS_DEFINITION,
]
