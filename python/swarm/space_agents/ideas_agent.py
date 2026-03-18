"""
IdeasSpaceAgent — LLM tool-calling agent for the Ideas/Bubbles Space.

Has all ~40 bubble/idea/summary/format/exploration tools available.
Receives user input + context, decides which tools to call and in what order.
"""

import logging
import os
from typing import Optional

from .base_space_agent import BaseSpaceAgent
from .ideas_tool_definitions import get_ideas_tools, TOOL_TO_EVENT_TYPE
from .models import SpaceAgentContext

logger = logging.getLogger(__name__)


IDEAS_AGENT_SYSTEM_PROMPT = """Du bist der Ideas-Agent im VibeMind System. Du verwaltest Spaces (Bubbles) und Ideen/Notizen.

## Konzepte
- **Bubble/Space**: Container fuer Ideen (wie Ordner). User kann "in" einem Space sein.
- **Idee/Notiz**: Inhalt innerhalb eines Spaces (Titel + Content). Jede Idee hat eine Position (x,y) im Canvas.
- **Multiverse**: Uebersicht aller Spaces (wenn kein Space betreten ist).
- **Verbindungen**: Ideen koennen miteinander verknuepft werden (Kanten im Graph).

## Aktueller Kontext
- Aktueller Space: {current_bubble}
- Ideen im Space: {idea_count}
- Letzte Nachrichten: {conversation_history}

## Regeln
1. Extrahiere EXAKT die Namen/Woerter die der User sagt — erfinde keine Titel
2. Bei Multi-Step Anfragen: Fuehre Tools in logischer Reihenfolge aus
   Beispiel: "Erstelle Bubble Marketing und notiere darin: Social Media Strategie"
   → bubble_create(title="Marketing") → bubble_enter(bubble_name="Marketing") → idea_create(title="Social Media Strategie")
3. WICHTIG: Vor idea_create/idea_list muss der User in einem Space sein. Wenn nicht, erst bubble_enter oder bubble_find aufrufen.
4. Bei unklarem Space-Name: Nutze bubble_find (fuzzy Suche).
5. Antworte am Ende mit einer kurzen, natuerlichen Zusammenfassung auf Deutsch.
6. Bei einfachen Abfragen (Liste, Status): Ein Tool reicht.
7. Nutze bubble_list wenn der User nach allen Spaces/Bubbles fragt.
8. Wenn der User "zurueck" oder "raus" sagt: bubble_exit.

## Format-Konvertierung
Wenn der User eine Idee formatieren will (als Tabelle, Kanban, Mindmap, etc.):
→ Nutze idea_format mit dem passenden format_type.
Verfuegbare Formate: table, action_list, pros_cons, hierarchy, specs, kanban, mindmap, swot, user_story, flowchart, note.
"""


class IdeasSpaceAgent(BaseSpaceAgent):
    """Tool-calling agent for the Ideas/Bubbles Space."""

    @property
    def space_name(self) -> str:
        return "ideas"

    @property
    def system_prompt(self) -> str:
        return IDEAS_AGENT_SYSTEM_PROMPT

    def _load_tools(self):
        """Load all Ideas/Bubbles tool schemas and executors."""
        self._tools = get_ideas_tools()
        self._load_executors()

    def _load_executors(self):
        """Map tool names to Python functions."""

        # === BUBBLE TOOLS ===
        try:
            from spaces.ideas.tools.bubble_tools import (
                list_bubbles, find_bubble, create_bubble, update_bubble,
                delete_bubble, delete_all_bubbles_except,
                enter_bubble, exit_bubble,
                get_bubble_stats, score_bubble, promote_bubble,
                evaluate_bubble_evolution,
            )
            from spaces.ideas.tools.idea_tools import get_current_space

            self._executors.update({
                "bubble_list": list_bubbles,
                "bubble_find": find_bubble,
                "bubble_create": create_bubble,
                "bubble_update": update_bubble,
                "bubble_delete": delete_bubble,
                "bubble_delete_all_except": delete_all_bubbles_except,
                "bubble_enter": enter_bubble,
                "bubble_exit": exit_bubble,
                "bubble_stats": get_bubble_stats,
                "bubble_score": score_bubble,
                "bubble_promote": promote_bubble,
                "bubble_evaluate": evaluate_bubble_evolution,
                "bubble_current": get_current_space,
            })
        except ImportError as e:
            logger.warning(f"[IdeasAgent] Could not load bubble tools: {e}")

        # === IDEA TOOLS ===
        try:
            from spaces.ideas.tools.idea_tools import (
                list_ideas, count_ideas, create_idea, create_idea_batch,
                find_idea, update_idea, delete_idea,
                connect_ideas, disconnect_ideas, connect_ideas_multi,
                link_idea_to_root, add_image, expand_ideas,
                move_idea, classify_idea, explain_idea,
                auto_link_ideas, analyze_and_suggest_links,
                format_idea_as_table,
            )

            self._executors.update({
                "idea_list": list_ideas,
                "idea_count": count_ideas,
                "idea_create": create_idea,
                "idea_find": find_idea,
                "idea_update": update_idea,
                "idea_delete": delete_idea,
                "idea_connect": connect_ideas,
                "idea_disconnect": disconnect_ideas,
                "idea_connect_multi": connect_ideas_multi,
                "idea_link_to_root": link_idea_to_root,
                "idea_add_image": add_image,
                "idea_expand": expand_ideas,
                "idea_move": move_idea,
                "idea_classify": classify_idea,
                "idea_explain": explain_idea,
                "idea_auto_link": auto_link_ideas,
                "idea_analyze_links": analyze_and_suggest_links,
                "idea_format_table": format_idea_as_table,
                "idea_create_batch": create_idea_batch,
            })
        except ImportError as e:
            logger.warning(f"[IdeasAgent] Could not load idea tools: {e}")

        # === SUMMARY TOOLS ===
        try:
            from spaces.ideas.tools.summary_tools import (
                summarize_idea, list_summaries, get_summary,
                generate_white_paper, generate_project_structure,
                generate_feature_docs,
            )

            self._executors.update({
                "idea_summarize": summarize_idea,
                "idea_whitepaper": generate_white_paper,
                "idea_project_structure": generate_project_structure,
                "idea_feature_docs": generate_feature_docs,
                "summary_list": list_summaries,
                "summary_get": get_summary,
            })
        except ImportError as e:
            logger.warning(f"[IdeasAgent] Could not load summary tools: {e}")

        # === FORMAT TOOLS (parametric — one tool covers all 11 formats) ===
        try:
            from spaces.ideas.tools.format_dispatcher import (
                convert_format, list_available_formats,
            )

            def _format_wrapper(params):
                """Wrap idea_format → convert_format with correct params."""
                return convert_format({
                    "idea_name": params.get("idea_name", ""),
                    "target_format": params.get("format_type", "table"),
                })

            self._executors.update({
                "idea_format": _format_wrapper,
                "idea_list_formats": list_available_formats,
            })
        except ImportError as e:
            logger.warning(f"[IdeasAgent] Could not load format tools: {e}")

        # === EXPLORATION TOOLS ===
        try:
            from spaces.ideas.tools.exploration_tools import (
                start_exploration, stop_exploration, get_exploration_status,
                accept_connection, reject_connection, explore_deeper,
                visualize_exploration,
            )
            from spaces.ideas.tools.bubble_tools import get_current_bubble_db_id

            def _exploration_start(params):
                bubble_id = get_current_bubble_db_id()
                return start_exploration(
                    bubble_id=bubble_id,
                    depth=params.get("depth", 4),
                    context=params.get("context"),
                    mode=params.get("mode", "auto"),
                )

            def _exploration_stop(params):
                return stop_exploration(params.get("session_id", ""))

            def _exploration_status(params):
                return get_exploration_status(params.get("session_id", ""))

            def _exploration_accept(params):
                return accept_connection(
                    params.get("session_id", ""),
                    params.get("connection_id", ""),
                )

            def _exploration_reject(params):
                return reject_connection(
                    params.get("session_id", ""),
                    params.get("connection_id", ""),
                )

            def _exploration_deeper(params):
                return explore_deeper(
                    params.get("session_id", ""),
                    params.get("node_id", ""),
                    params.get("depth", 2),
                )

            def _exploration_visualize(params):
                return visualize_exploration(params.get("session_id", ""))

            self._executors.update({
                "exploration_start": _exploration_start,
                "exploration_stop": _exploration_stop,
                "exploration_status": _exploration_status,
                "exploration_accept": _exploration_accept,
                "exploration_reject": _exploration_reject,
                "exploration_deeper": _exploration_deeper,
                "exploration_visualize": _exploration_visualize,
            })
        except ImportError as e:
            logger.warning(f"[IdeasAgent] Could not load exploration tools: {e}")

        logger.info(
            f"[IdeasAgent] Loaded {len(self._executors)} executors"
        )


# =============================================================================
# Singleton
# =============================================================================

_ideas_agent: Optional[IdeasSpaceAgent] = None


def get_ideas_space_agent() -> IdeasSpaceAgent:
    """Get or create IdeasSpaceAgent singleton."""
    global _ideas_agent
    if _ideas_agent is None:
        _ideas_agent = IdeasSpaceAgent()
    return _ideas_agent


def reset_ideas_space_agent():
    """Reset singleton (for testing)."""
    global _ideas_agent
    _ideas_agent = None
