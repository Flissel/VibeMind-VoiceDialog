"""
Adapted Idea Tools for AutoGen Swarm

Typed wrappers around the original Dict-based idea/note tools.
These can be used directly as FunctionTool in AssistantAgent.
"""

from typing import Optional, List
import sys
from pathlib import Path

# Add parent directories to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def list_ideas() -> str:
    """
    List all notes/ideas in the current bubble/space.

    Must be inside a bubble first (use enter_bubble).

    Returns:
        Formatted list of notes in current bubble
    """
    from tools.idea_tools import list_ideas as _list_ideas
    return _list_ideas({})


def create_idea(title: str = None, content: str = "", type: str = "note") -> str:
    """
    Create a new note/idea in the current bubble.

    Args:
        title: Short title for the note (required)
        content: Full content/description (optional)
        type: Type of node - 'idea', 'note', 'link', 'image' (default: 'note')

    Returns:
        Confirmation message
    """
    if not title:
        return "Fehler: Kein Titel angegeben. Bitte sag mir wie die Idee heissen soll."
    from tools.idea_tools import create_idea as _create_idea
    return _create_idea({"title": title, "content": content, "type": type})


def add_image(url: str = None, title: str = "Image") -> str:
    """
    Add an image to the current bubble/space.

    Args:
        url: URL of the image (required)
        title: Caption/title for the image (optional)

    Returns:
        Confirmation message
    """
    if not url:
        return "Fehler: Keine URL angegeben. Bitte sag mir welches Bild hinzugefuegt werden soll."
    from tools.idea_tools import add_image as _add_image
    return _add_image({"url": url, "title": title})


def find_idea(query: str = None) -> str:
    """
    Search for notes matching a query.

    Args:
        query: Search text

    Returns:
        Matching notes or 'no matches'
    """
    if not query:
        return "Fehler: Kein Suchbegriff angegeben. Bitte sag mir wonach du suchen moechtest."
    from tools.idea_tools import find_idea as _find_idea
    return _find_idea({"query": query})


def update_idea(idea_name: str = None, new_content: str = "", new_title: str = "") -> str:
    """
    Update an existing note/idea.

    Args:
        idea_name: Name/title of the idea to update
        new_content: New content (optional)
        new_title: New title (optional)

    Returns:
        Confirmation message
    """
    if not idea_name:
        return "Fehler: Kein Ideen-Name angegeben. Bitte sag mir welche Idee aktualisiert werden soll."
    from tools.idea_tools import update_idea as _update_idea
    return _update_idea({
        "idea_name": idea_name,
        "new_content": new_content,
        "new_title": new_title,
    })


def connect_ideas(idea1: str = None, idea2: str = None) -> str:
    """
    Connect two ideas with an edge/link.

    Args:
        idea1: First idea name
        idea2: Second idea name

    Returns:
        Confirmation message
    """
    if not idea1 or not idea2:
        return "Fehler: Zwei Ideen-Namen benoetigt. Bitte sag mir welche Ideen verbunden werden sollen."
    from tools.idea_tools import connect_ideas as _connect_ideas
    return _connect_ideas({"idea1": idea1, "idea2": idea2})


def delete_idea(idea_name: str = None) -> str:
    """
    Delete a note/idea.

    Args:
        idea_name: Name of idea to delete

    Returns:
        Confirmation message
    """
    if not idea_name:
        return "Fehler: Kein Ideen-Name angegeben. Bitte sag mir welche Idee geloescht werden soll."
    from tools.idea_tools import delete_idea as _delete_idea
    return _delete_idea({"idea_name": idea_name})


def get_current_space() -> str:
    """
    Get information about current location (which bubble/space).

    Returns:
        Current location description
    """
    from tools.idea_tools import get_current_space as _get_current_space
    return _get_current_space({})


def auto_link_ideas(threshold: float = 0.5, max_links: int = 10) -> str:
    """
    Automatically analyze all ideas in current bubble and create links
    between semantically related pairs using embedding similarity.

    Voice triggers: "Verlinke die Ideen sinnvoll", "Link related ideas",
                   "Verbinde ähnliche Notizen automatisch"

    Args:
        threshold: Minimum similarity score (0-1), default 0.5
        max_links: Maximum number of links to create, default 10

    Returns:
        Summary of created links
    """
    from tools.idea_tools import auto_link_ideas as _auto_link_ideas
    return _auto_link_ideas({"threshold": threshold, "max_links": max_links})


def format_idea_as_table(
    idea_name: str = None,
    custom_columns: List[str] = None,
    format_instruction: str = ""
) -> str:
    """
    Format an existing idea's content into a structured table.

    Voice triggers: "Formatiere die Idee X als Tabelle",
                   "Erstelle eine Tabelle aus der Idee X",
                   "Mach eine Tabelle mit Spalten X, Y, Z"

    Args:
        idea_name: Name/title of the idea to format (required)
        custom_columns: Optional custom column headers (e.g., ["Calls ID", "Requirement", "Content"])
        format_instruction: Optional formatting instruction

    Returns:
        Confirmation with table preview
    """
    if not idea_name:
        return "Fehler: Kein Ideen-Name angegeben. Bitte sag mir welche Idee formatiert werden soll."
    from tools.structured_formatting_tools import format_idea_as_table as _format_idea_as_table
    return _format_idea_as_table(
        idea_name=idea_name,
        custom_columns=custom_columns,
        format_instruction=format_instruction
    )


def summarize_idea(idea_name: str = None, style: str = "concise") -> str:
    """
    Summarize a specific idea or the current bubble using AI.

    Voice triggers: "Fasse die Idee zusammen", "Erstelle eine Zusammenfassung",
                   "Summarize this idea"

    Args:
        idea_name: Name of the idea to summarize (optional - uses current bubble if not specified)
        style: Summary style - "concise", "detailed", "actionable" (default: "concise")

    Returns:
        AI-generated summary of the idea
    """
    from tools.summary_tools import summarize_idea as _summarize_idea
    return _summarize_idea({"idea_name": idea_name, "style": style})


def generate_white_paper(start_node: str = None, task: str = "project overview", max_depth: int = 5) -> str:
    """
    Generate a structured White Paper document from linked ideas using graph traversal.

    Voice triggers: "Erstelle ein Whitepaper", "Generiere eine Projektübersicht",
                   "Mach ein White Paper aus den Ideen"

    Args:
        start_node: Name of the idea to start from (uses first idea if not specified)
        task: Description of what kind of document to create (default: "project overview")
        max_depth: Maximum graph traversal depth (default: 5)

    Returns:
        Structured White Paper document
    """
    from tools.summary_tools import generate_white_paper as _generate_white_paper
    return _generate_white_paper({"start_node": start_node, "task": task, "max_depth": max_depth})


def expand_ideas(idea_name: str = None, count: int = 3) -> str:
    """
    Expand existing ideas using AI to generate related concepts.

    Voice triggers: "Erweitere die Ideen", "Generiere verwandte Ideen",
                   "Mach mehr Ideen aus den bestehenden"

    Args:
        idea_name: Optional - specific idea to expand (uses all ideas if not specified)
        count: Number of ideas to generate (default: 3)

    Returns:
        Summary of newly generated ideas
    """
    from tools.idea_tools import expand_ideas as _expand_ideas
    return _expand_ideas({"source_idea": idea_name, "count": count})


def analyze_and_suggest_links() -> str:
    """
    Analyze all ideas in current bubble and suggest meaningful links
    WITHOUT creating them. User can confirm to create links.

    Voice triggers: "Analysiere die Ideen", "Schlage Verlinkungen vor",
                   "Welche Ideen gehören zusammen"

    Returns:
        Top 5 suggested link pairs with reasoning
    """
    from tools.idea_tools import analyze_and_suggest_links as _analyze_and_suggest_links
    return _analyze_and_suggest_links({})


# Collect all tools for export
IDEA_TOOLS = [
    list_ideas,
    create_idea,
    add_image,
    find_idea,
    update_idea,
    connect_ideas,
    delete_idea,
    get_current_space,
    auto_link_ideas,
    format_idea_as_table,
    summarize_idea,
    generate_white_paper,
    expand_ideas,
    analyze_and_suggest_links,
]


__all__ = [
    "list_ideas",
    "create_idea",
    "add_image",
    "find_idea",
    "update_idea",
    "connect_ideas",
    "delete_idea",
    "get_current_space",
    "auto_link_ideas",
    "format_idea_as_table",
    "summarize_idea",
    "generate_white_paper",
    "expand_ideas",
    "analyze_and_suggest_links",
    "IDEA_TOOLS",
]
