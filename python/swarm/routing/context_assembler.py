"""ContextAssembler — gathers VibeMind workspace context for Brain + OpenFang.

Collects from 5 context providers (all optional, graceful degradation):
- RealTimeState: current space, active tasks, recent completions
- BubbleContextProvider: bubble name, idea titles, idea count
- SessionContext: conversation history (last 3 turns)
- UserProfileService: user habits (Supermemory)
- ConversationRouter: similar past intents (Supermemory)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class WorkspaceContext:
    """VibeMind workspace state snapshot for external systems."""

    current_space: Optional[str] = None
    current_bubble: Optional[str] = None
    idea_count: int = 0
    idea_titles: List[str] = field(default_factory=list)
    active_task_count: int = 0
    recent_intents: List[str] = field(default_factory=list)
    user_habits: Optional[str] = None
    similar_past: Optional[str] = None
    conversation_turns: List[Dict[str, Any]] = field(default_factory=list)


class ContextAssembler:
    """Gathers workspace context from all available VibeMind providers."""

    def assemble(self) -> WorkspaceContext:
        """Collect context from all available providers. Never raises."""
        ctx = WorkspaceContext()

        # 1. RealTimeState — current space, active tasks, recent completions
        try:
            from swarm.context.real_time_state import get_real_time_state
            rt = get_real_time_state()
            if rt and rt.state:
                ctx.current_space = rt.state.current_space
                ctx.current_bubble = rt.state.current_bubble
                ctx.active_task_count = len(rt.state.active_tasks) if rt.state.active_tasks else 0
                if rt.state.recent_completions:
                    ctx.recent_intents = [
                        c.get("intent", "") for c in rt.state.recent_completions[:3]
                    ]
        except Exception as e:
            logger.debug(f"[ContextAssembler] RealTimeState unavailable: {e}")

        # 2. BubbleContextProvider — current bubble, ideas
        try:
            from swarm.context.bubble_context_provider import get_bubble_context_provider
            bp = get_bubble_context_provider()
            bubble_ctx = bp.get_current_context()
            if bubble_ctx:
                ctx.current_bubble = ctx.current_bubble or bubble_ctx.get("bubble_name")
                ctx.idea_count = bubble_ctx.get("idea_count", 0)
                ctx.idea_titles = (bubble_ctx.get("idea_titles") or [])[:5]
        except Exception as e:
            logger.debug(f"[ContextAssembler] BubbleContext unavailable: {e}")

        # 3. SessionContext — last 3 conversation turns
        try:
            from swarm.context.session_context import get_session_context
            sc = get_session_context()
            if sc and sc.conversation_history:
                ctx.conversation_turns = sc.conversation_history[-3:]
        except Exception as e:
            logger.debug(f"[ContextAssembler] SessionContext unavailable: {e}")

        # 4. UserProfileService — top intents / preferences
        try:
            from memory import get_user_profile_service
            ups = get_user_profile_service()
            if ups and ups.is_available:
                ctx.user_habits = ups.get_user_context_sync() if hasattr(ups, 'get_user_context_sync') else None
        except Exception as e:
            logger.debug(f"[ContextAssembler] UserProfile unavailable: {e}")

        # 5. ConversationRouter — similar past intents
        try:
            from memory import get_conversation_router
            cr = get_conversation_router("default", "default")
            if cr and cr.is_available:
                # Sync wrapper not available — will be called async in bridge
                pass
        except Exception as e:
            logger.debug(f"[ContextAssembler] ConversationRouter unavailable: {e}")

        return ctx

    async def assemble_async(self, user_input: str = "") -> WorkspaceContext:
        """Async version that also fetches Supermemory data."""
        ctx = self.assemble()

        # Fetch async Supermemory data
        try:
            from memory import get_user_profile_service
            ups = get_user_profile_service()
            if ups and ups.is_available:
                ctx.user_habits = await ups.get_user_context()
        except Exception as e:
            logger.debug(f"[ContextAssembler] Async UserProfile failed: {e}")

        if user_input:
            try:
                from memory import get_conversation_router
                cr = get_conversation_router("default", "default")
                if cr and cr.is_available:
                    ctx.similar_past = await cr.get_routing_context(user_input, limit=3)
            except Exception as e:
                logger.debug(f"[ContextAssembler] Async ConversationRouter failed: {e}")

        return ctx

    @staticmethod
    def to_brain_prefix(ctx: WorkspaceContext) -> str:
        """Compact prefix for Brain's SeedEncoder input.

        Format: [space:X bubble:Y ideas:N tasks:M]
        Keeps it short so the embedding stays focused on the user intent.
        """
        parts = []
        if ctx.current_space:
            parts.append(f"space:{ctx.current_space}")
        if ctx.current_bubble:
            parts.append(f"bubble:{ctx.current_bubble}")
        if ctx.idea_count:
            parts.append(f"ideas:{ctx.idea_count}")
        if ctx.active_task_count:
            parts.append(f"tasks:{ctx.active_task_count}")
        if not parts:
            return ""
        return f"[{' '.join(parts)}]"

    @staticmethod
    def to_brain_context_dict(ctx: WorkspaceContext) -> Dict[str, Any]:
        """Structured context dict for Brain /api/cortex/route."""
        d: Dict[str, Any] = {}
        if ctx.current_space:
            d["current_space"] = ctx.current_space
        if ctx.current_bubble:
            d["current_bubble"] = ctx.current_bubble
        if ctx.idea_count:
            d["idea_count"] = ctx.idea_count
        if ctx.active_task_count:
            d["active_task_count"] = ctx.active_task_count
        if ctx.recent_intents:
            d["recent_intents"] = ctx.recent_intents
        return d

    @staticmethod
    def to_openfang_block(ctx: WorkspaceContext) -> str:
        """Structured context block prepended to OpenFang agent messages.

        Format:
        [VibeMind Context]
        Space: X (space_type)
        Ideas: A, B, C
        Active Tasks: N
        Recent: intent1 ✓, intent2 ✓
        [End Context]
        """
        lines = ["[VibeMind Context]"]

        if ctx.current_bubble or ctx.current_space:
            space_info = ctx.current_bubble or "unknown"
            if ctx.current_space:
                space_info += f" ({ctx.current_space})"
            lines.append(f"Space: {space_info}")

        if ctx.idea_titles:
            lines.append(f"Ideas: {', '.join(ctx.idea_titles)}")
        elif ctx.idea_count:
            lines.append(f"Idea Count: {ctx.idea_count}")

        if ctx.active_task_count:
            lines.append(f"Active Tasks: {ctx.active_task_count}")

        if ctx.recent_intents:
            recent_str = ", ".join(f"{i} (ok)" for i in ctx.recent_intents)
            lines.append(f"Recent: {recent_str}")

        if ctx.user_habits:
            # Truncate to keep message compact
            habits_short = ctx.user_habits[:200]
            lines.append(f"User: {habits_short}")

        if ctx.conversation_turns:
            lines.append("Last Turns:")
            for turn in ctx.conversation_turns[-2:]:
                speaker = turn.get("speaker", "?")
                text = (turn.get("text", ""))[:80]
                lines.append(f"  {speaker}: {text}")

        lines.append("[End Context]")
        return "\n".join(lines)

    @staticmethod
    def to_json_context(
        ctx: WorkspaceContext, fields: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Return selected context fields as a JSON-serializable dict.

        Used in the `vibemind.intent.v1` envelope sent to OpenFang agents.
        When `fields` is None, returns all non-empty fields.
        """
        all_fields = {
            "current_space": ctx.current_space,
            "current_bubble": ctx.current_bubble,
            "idea_count": ctx.idea_count,
            "idea_titles": ctx.idea_titles,
            "active_task_count": ctx.active_task_count,
            "recent_intents": ctx.recent_intents,
            "user_habits": ctx.user_habits,
            "similar_past": ctx.similar_past,
            "conversation_turns": ctx.conversation_turns,
        }
        if fields:
            return {k: all_fields.get(k) for k in fields if all_fields.get(k)}
        return {k: v for k, v in all_fields.items() if v}
