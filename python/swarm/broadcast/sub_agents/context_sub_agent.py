"""
ContextSubAgent - Running transcript summary for AI restart.

Maintains a continuously updated summary of the conversation
so that if the AI system restarts, it can resume with full context.

Features:
- Records every executed intent and result
- Compresses summary every N messages via LLM
- Stores to Supermemory for persistence
- Retrieves context on system restart
"""

import logging
import os
import json
from datetime import datetime
from typing import Any, Optional, Dict, List, TYPE_CHECKING

if TYPE_CHECKING:
    from swarm.broadcast.dispatcher import IntentPayload

from llm_config import get_model, get_async_client

logger = logging.getLogger(__name__)

CONTEXT_MODEL = get_model("context")
COMPRESS_EVERY_N = int(os.getenv("CONTEXT_COMPRESS_INTERVAL", "5"))


class ContextSubAgent:
    """
    Creates and maintains a running context summary.

    After every interaction:
    1. Updates the running summary with new information
    2. Periodically compresses via LLM
    3. Stores the summary to Supermemory
    4. On restart, retrieves the latest summary to restore context

    Singleton: shared across all broadcast agents.
    """

    CONTAINER_TAG = "vibemind-context-summary"

    def __init__(self, session_id: str = ""):
        self.session_id = session_id or f"session_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        self._running_summary = ""
        self._recent_actions: List[Dict[str, str]] = []
        self._message_count = 0
        self._supermemory_client = None

    async def record_execution(
        self, intent: "IntentPayload", result: Any
    ):
        """
        Record an execution event and update running summary.

        Called by the responsible agent after tool execution.
        """
        self._message_count += 1
        now = datetime.utcnow().isoformat()

        result_str = str(result)[:300] if result else "(kein Ergebnis)"

        action = {
            "n": self._message_count,
            "ts": now,
            "user": intent.user_input[:200] if intent.user_input else "",
            "intent": intent.event_type,
            "params": json.dumps(intent.payload, ensure_ascii=False)[:200],
            "result": result_str,
        }
        self._recent_actions.append(action)

        # Keep last 20 actions in memory
        if len(self._recent_actions) > 20:
            self._recent_actions = self._recent_actions[-20:]

        # Entry for running summary
        entry = (
            f"[{self._message_count}] User: {intent.user_input[:150]}\n"
            f"  -> {intent.event_type}: {result_str[:150]}\n"
        )

        # Compress every N messages
        if self._message_count % COMPRESS_EVERY_N == 0:
            await self._compress_summary(entry)
        else:
            self._running_summary += entry

        # Persist to Supermemory
        await self._persist_summary()

        logger.debug(
            f"[ContextSubAgent] Recorded action #{self._message_count}: "
            f"{intent.event_type}"
        )

    async def get_restart_context(self) -> str:
        """
        Retrieve context summary for AI restart.

        Called on system startup to restore conversation state.
        First checks Supermemory, falls back to in-memory state.
        """
        # Try Supermemory first
        client = self._get_supermemory_client()
        if client:
            try:
                response = await client.search.execute(
                    q="latest conversation context summary",
                    container_tags=[self.CONTAINER_TAG],
                    limit=1,
                )
                if response.results:
                    context = response.results[0].content
                    logger.info(
                        f"[ContextSubAgent] Restored context from Supermemory "
                        f"({len(context)} chars)"
                    )
                    return context
            except Exception as e:
                logger.debug(f"[ContextSubAgent] Supermemory retrieval failed: {e}")

        # Fall back to in-memory
        if self._running_summary:
            return self._running_summary

        return ""

    def get_current_summary(self) -> str:
        """Get the current in-memory summary (no API call)."""
        return self._running_summary

    def get_recent_actions(self, limit: int = 10) -> List[Dict[str, str]]:
        """Get the most recent recorded actions."""
        return self._recent_actions[-limit:]

    async def _compress_summary(self, new_entry: str):
        """Use LLM to compress the running summary + new entry."""
        try:
            client = get_async_client("context")

            prompt = (
                "Compress this conversation transcript into a concise summary.\n"
                "Keep: user preferences, current state, active tasks, recent decisions.\n"
                "Drop: routine confirmations, duplicate information.\n\n"
                f"Current summary:\n{self._running_summary}\n\n"
                f"New entry:\n{new_entry}\n\n"
                "Return a compressed summary (max 500 words, German or English)."
            )

            from llm_config import token_kwargs
            response = await client.chat.completions.create(
                model=CONTEXT_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                **token_kwargs(CONTEXT_MODEL, 800),
            )

            compressed = response.choices[0].message.content.strip()
            self._running_summary = compressed
            logger.info(
                f"[ContextSubAgent] Compressed summary to {len(compressed)} chars "
                f"(was {len(self._running_summary) + len(new_entry)} chars)"
            )

        except Exception as e:
            # Fallback: just append
            logger.debug(f"[ContextSubAgent] Compression failed, appending: {e}")
            self._running_summary += new_entry

            # Hard limit: truncate if too long
            if len(self._running_summary) > 10000:
                self._running_summary = self._running_summary[-8000:]

    async def _persist_summary(self):
        """Store current summary to Supermemory."""
        client = self._get_supermemory_client()
        if not client:
            return

        if not self._running_summary:
            return

        now = datetime.utcnow()
        content = (
            f"Session context ({self.session_id}):\n"
            f"{self._running_summary}\n\n"
            f"Recent actions ({len(self._recent_actions)}):\n"
        )
        for a in self._recent_actions[-5:]:
            content += f"  [{a['n']}] {a['intent']}: {a['user'][:80]}\n"

        try:
            await client.memories.add(
                content=content,
                container_tag=self.CONTAINER_TAG,
                custom_id=f"context_{self.session_id}",
                metadata={
                    "type": "restart_context",
                    "session_id": self.session_id,
                    "timestamp": now.isoformat(),
                    "message_count": self._message_count,
                    "action_count": len(self._recent_actions),
                },
            )
        except Exception as e:
            logger.debug(f"[ContextSubAgent] Persist failed: {e}")

    def _get_supermemory_client(self):
        """Lazy-load Supermemory async client."""
        if self._supermemory_client is not None:
            return self._supermemory_client

        api_key = os.getenv("SUPERMEMORY_API_KEY", "")
        if not api_key:
            return None

        try:
            from supermemory import AsyncSupermemory
            self._supermemory_client = AsyncSupermemory(api_key=api_key)
            return self._supermemory_client
        except ImportError:
            return None


# --- Singleton ---

_context_sub_agent: Optional[ContextSubAgent] = None


def get_context_sub_agent(session_id: str = "") -> ContextSubAgent:
    """Get or create ContextSubAgent singleton."""
    global _context_sub_agent
    if _context_sub_agent is None:
        _context_sub_agent = ContextSubAgent(session_id=session_id)
    return _context_sub_agent


def reset_context_sub_agent():
    """Reset singleton (for testing)."""
    global _context_sub_agent
    _context_sub_agent = None


__all__ = [
    "ContextSubAgent",
    "get_context_sub_agent",
    "reset_context_sub_agent",
]
