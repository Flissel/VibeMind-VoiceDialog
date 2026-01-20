"""
Ideas Agent - Backend agent for Bubble and Idea tools

Listens to events:tasks:ideas stream and executes:
- Bubble tools: list, create, enter, exit, delete, stats, score, evaluate, promote
- Idea tools: list, create, find, update, delete, connect, add_image, get_current_space
"""

import logging
from typing import Dict, Callable, Optional

from swarm.backend_agents.base_agent import BaseBackendAgent
from swarm.event_bus import EventBus

logger = logging.getLogger(__name__)


class IdeasAgent(BaseBackendAgent):
    """
    Backend agent for Ideas and Bubbles domain.

    Handles 17 tools for managing spaces (bubbles) and ideas within them.
    """

    # Event type to tool name mapping
    EVENT_TO_TOOL = {
        # Bubble events
        "bubble.list": "list_bubbles",
        "bubble.create": "create_bubble",
        "bubble.enter": "enter_bubble",
        "bubble.exit": "exit_bubble",
        "bubble.delete": "delete_bubble",
        "bubble.update": "update_bubble",
        "bubble.stats": "get_bubble_stats",
        "bubble.score": "score_bubble",
        "bubble.evaluate": "evaluate_bubble_evolution",
        "bubble.promote": "promote_bubble",
        # Idea events
        "idea.list": "list_ideas",
        "idea.create": "create_idea",
        "idea.find": "find_idea",
        "idea.update": "update_idea",
        "idea.delete": "delete_idea",
        "idea.connect": "connect_ideas",
        "idea.auto_link": "auto_link_ideas",
        "idea.add_image": "add_image",
        "idea.current_space": "get_current_space",
        "idea.format_table": "format_idea_as_table",
        # Format conversion tools (format_dispatcher)
        "idea.format_note": "convert_format",
        "idea.format_action_list": "convert_format",
        "idea.format_pros_cons": "convert_format",
        "idea.format_hierarchy": "convert_format",
        "idea.format_specs": "convert_format",
        "idea.convert_format": "convert_format",
        "idea.list_formats": "list_available_formats",
        # Advanced idea tools
        "idea.summarize": "summarize_idea",
        "idea.whitepaper": "generate_white_paper",
        "idea.expand": "expand_ideas",
        "idea.analyze_links": "analyze_and_suggest_links",
    }

    # Parameter normalization: map classifier output to tool expected params
    # The classifier might extract "title" or "name", but tools expect specific names
    PARAM_MAPPING = {
        # bubble.create expects "title" but classifier might use bubble_name/name/space
        "bubble.create": {"bubble_name": "title", "name": "title", "space": "title", "space_name": "title"},
        # Bubble tools expect "bubble_name" but classifier might use title/name/space
        "bubble.enter": {"title": "bubble_name", "name": "bubble_name", "space": "bubble_name", "space_name": "bubble_name"},
        "bubble.delete": {"title": "bubble_name", "name": "bubble_name", "space": "bubble_name", "space_name": "bubble_name"},
        "bubble.stats": {"title": "bubble_name", "name": "bubble_name", "space": "bubble_name", "space_name": "bubble_name"},
        "bubble.score": {"title": "bubble_name", "name": "bubble_name", "space": "bubble_name", "space_name": "bubble_name"},
        "bubble.evaluate": {"title": "bubble_name", "name": "bubble_name", "space": "bubble_name", "space_name": "bubble_name"},
        "bubble.promote": {"title": "bubble_name", "name": "bubble_name", "space": "bubble_name", "space_name": "bubble_name"},
        # bubble.update expects "new_title" but classifier might use title/name
        "bubble.update": {
            "title": "new_title",
            "name": "new_title",
            "neuer_name": "new_title",
            "description": "new_description",
            "beschreibung": "new_description",
        },
        # idea.create expects "title" and "content" but classifier might use various names
        "idea.create": {
            "name": "title",
            "idea_name": "title",
            "idea": "title",
            "idea_title": "title",
            "idea_description": "content",  # Map description to content
            "description": "content",
            "text": "content",
            "body": "content",
        },
        # Idea tools
        "idea.find": {"text": "query", "search": "query", "term": "query", "title": "query", "name": "query"},
        "idea.update": {"title": "idea_name", "name": "idea_name", "description": "new_content", "text": "new_content"},
        "idea.delete": {"title": "idea_name", "name": "idea_name"},
        "idea.connect": {"source": "idea1", "target": "idea2", "from_idea": "idea1", "to_idea": "idea2"},
        # idea.format_table expects "idea_name" and optionally "custom_columns"
        "idea.format_table": {
            "name": "idea_name",
            "title": "idea_name",
            "idea": "idea_name",
            "columns": "custom_columns",
            "headers": "custom_columns",
            "spalten": "custom_columns",
            "instruction": "format_instruction",
            "format": "format_instruction",
        },
        # Advanced idea tools parameter mappings
        "idea.summarize": {
            "name": "idea_name",
            "title": "idea_name",
            "idea": "idea_name",
            "stil": "style",
        },
        "idea.whitepaper": {
            "name": "start_node",
            "title": "start_node",
            "idea": "start_node",
            "idee": "start_node",
        },
        "idea.expand": {
            "name": "idea_name",
            "title": "idea_name",
            "idea": "idea_name",
            "anzahl": "count",
            "number": "count",
        },
        # idea.analyze_links needs no params (operates on current bubble)
        "idea.analyze_links": {},
        # Format conversion tools (all use convert_format with target_format)
        "idea.format_note": {
            "name": "idea_name", "title": "idea_name", "idea": "idea_name",
            "_inject": {"target_format": "note"},
        },
        "idea.format_action_list": {
            "name": "idea_name", "title": "idea_name", "idea": "idea_name",
            "_inject": {"target_format": "action_list"},
        },
        "idea.format_pros_cons": {
            "name": "idea_name", "title": "idea_name", "idea": "idea_name",
            "_inject": {"target_format": "pros_cons"},
        },
        "idea.format_hierarchy": {
            "name": "idea_name", "title": "idea_name", "idea": "idea_name",
            "_inject": {"target_format": "hierarchy"},
        },
        "idea.format_specs": {
            "name": "idea_name", "title": "idea_name", "idea": "idea_name",
            "_inject": {"target_format": "specs"},
        },
        "idea.convert_format": {
            "name": "idea_name", "title": "idea_name", "idea": "idea_name",
            "format": "target_format", "zielformat": "target_format",
        },
        "idea.list_formats": {},
    }

    @property
    def stream(self) -> str:
        return EventBus.STREAM_TASKS_IDEAS

    @property
    def name(self) -> str:
        return "IdeasAgent"

    def _load_tools(self) -> Dict[str, Callable]:
        """Load bubble and idea tools."""
        tools = {}

        # Load bubble tools
        try:
            from swarm.tools.adapted_bubble_tools import (
                list_bubbles, create_bubble, enter_bubble, exit_bubble,
                delete_bubble, get_bubble_stats, score_bubble,
                evaluate_bubble_evolution, promote_bubble, update_bubble
            )
            tools.update({
                "list_bubbles": list_bubbles,
                "create_bubble": create_bubble,
                "enter_bubble": enter_bubble,
                "exit_bubble": exit_bubble,
                "delete_bubble": delete_bubble,
                "update_bubble": update_bubble,
                "get_bubble_stats": get_bubble_stats,
                "score_bubble": score_bubble,
                "evaluate_bubble_evolution": evaluate_bubble_evolution,
                "promote_bubble": promote_bubble,
            })
            logger.info(f"{self.name}: Loaded {len(tools)} bubble tools")
        except ImportError as e:
            logger.warning(f"{self.name}: Could not load bubble tools: {e}")

        # Load idea tools (all from adapted_idea_tools for consistency)
        try:
            from swarm.tools.adapted_idea_tools import (
                list_ideas, create_idea, find_idea, update_idea,
                delete_idea, connect_ideas, add_image, get_current_space,
                auto_link_ideas, format_idea_as_table,
                summarize_idea, generate_white_paper, expand_ideas, analyze_and_suggest_links
            )
            tools.update({
                "list_ideas": list_ideas,
                "create_idea": create_idea,
                "find_idea": find_idea,
                "update_idea": update_idea,
                "delete_idea": delete_idea,
                "connect_ideas": connect_ideas,
                "auto_link_ideas": auto_link_ideas,
                "add_image": add_image,
                "get_current_space": get_current_space,
                "format_idea_as_table": format_idea_as_table,
                "summarize_idea": summarize_idea,
                "generate_white_paper": generate_white_paper,
                "expand_ideas": expand_ideas,
                "analyze_and_suggest_links": analyze_and_suggest_links,
            })
            logger.info(f"{self.name}: Loaded {len(tools)} idea tools (including advanced tools)")
        except ImportError as e:
            logger.warning(f"{self.name}: Could not load idea tools: {e}")

        # Load format dispatcher tools
        try:
            from tools.format_dispatcher import convert_format, list_available_formats
            tools.update({
                "convert_format": convert_format,
                "list_available_formats": list_available_formats,
            })
            logger.info(f"{self.name}: Loaded format dispatcher tools")
        except ImportError as e:
            logger.warning(f"{self.name}: Could not load format dispatcher tools: {e}")

        return tools

    def _get_tool_name(self, event_type: str) -> Optional[str]:
        """Map event type to tool name."""
        return self.EVENT_TO_TOOL.get(event_type)


# Singleton instance
_ideas_agent: Optional[IdeasAgent] = None


def get_ideas_agent() -> IdeasAgent:
    """Get or create IdeasAgent singleton."""
    global _ideas_agent
    if _ideas_agent is None:
        _ideas_agent = IdeasAgent()
    return _ideas_agent


__all__ = ["IdeasAgent", "get_ideas_agent"]
