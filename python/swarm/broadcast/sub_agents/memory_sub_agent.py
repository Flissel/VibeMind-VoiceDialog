"""
MemorySubAgent - User profiling from a specific domain perspective.

Each main agent has one MemorySubAgent that:
1. Analyzes intents from its perspective (even when not responsible)
2. Identifies user patterns, preferences, habits
3. Uploads insights to Supermemory for future retrieval

Examples:
- Ideas agent's MemorySubAgent: "User frequently creates action_list formats,
  prefers German, works on marketing topics"
- Desktop agent's MemorySubAgent: "User often asks about Chrome,
  works in the morning, multi-tasks between apps"
"""

import logging
import os
import json
from datetime import datetime
from typing import Dict, Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from swarm.broadcast.dispatcher import IntentPayload

logger = logging.getLogger(__name__)

# Use lightweight model for cost-efficient profiling
PROFILING_MODEL = os.getenv("PROFILING_MODEL", "openai/gpt-4o-mini")


class MemorySubAgent:
    """
    Collects user insights from a specific domain perspective.

    Instantiated per main agent (e.g., ideas_memory, coding_memory).
    Stores profiling data to Supermemory with domain-specific container tags.
    """

    CONTAINER_TAG_PREFIX = "vibemind-profile"

    def __init__(self, agent_name: str, domain: str, perspective: str):
        """
        Args:
            agent_name: Parent agent name (e.g., "ideas_agent")
            domain: Domain identifier (e.g., "ideas", "coding", "desktop")
            perspective: Description of what this agent observes
        """
        self.agent_name = agent_name
        self.domain = domain
        self.perspective = perspective
        self._supermemory_client = None
        self._call_count = 0
        self._profile_interval = int(os.getenv("PROFILING_INTERVAL", "3"))

    @property
    def container_tag(self) -> str:
        return f"{self.CONTAINER_TAG_PREFIX}-{self.domain}"

    async def analyze_intent(
        self,
        intent: "IntentPayload",
        perspective: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Analyze an intent from this agent's domain perspective.

        Called for EVERY intent, even when not responsible.
        Uses LLM to extract behavioral insights.

        Rate-limited: only runs every N intents to save costs.

        Returns:
            Profiling insight dict, or None if nothing noteworthy.
        """
        self._call_count += 1

        # Rate-limit: only profile every N-th intent
        if self._call_count % self._profile_interval != 0:
            logger.debug(
                f"[{self.agent_name}_memory] Skipping profiling "
                f"(call {self._call_count}, interval {self._profile_interval})"
            )
            return None

        try:
            insight = await self._extract_insight(intent, perspective)

            if insight and insight.get("confidence", 0) > 0.5:
                await self._store_to_supermemory(insight, intent)
                return insight

        except Exception as e:
            logger.debug(
                f"[{self.agent_name}_memory] Profiling failed (non-critical): {e}"
            )

        return None

    async def _extract_insight(
        self, intent: "IntentPayload", perspective: str
    ) -> Optional[Dict[str, Any]]:
        """
        Use LLM to extract behavioral insight from intent.

        Returns:
            Dict with: insight, category, confidence
            Or None if no significant insight.
        """
        prompt = (
            f"Analyze this user intent from the {perspective}:\n\n"
            f"User said: \"{intent.user_input}\"\n"
            f"Classified as: {intent.event_type}\n"
            f"Parameters: {json.dumps(intent.payload, ensure_ascii=False)}\n\n"
            f"Extract ONE behavioral insight about the user:\n"
            f"- What pattern does this reveal?\n"
            f"- What preference can we infer?\n"
            f"- What topic/theme recurs?\n\n"
            f"Return JSON: {{\"insight\": \"...\", \"category\": \"pattern|preference|affinity|cross_domain\", \"confidence\": 0.0-1.0}}\n"
            f"Return {{\"insight\": null}} if nothing noteworthy."
        )

        try:
            from swarm.cloud_client import get_openrouter_client
            client = get_openrouter_client()

            response = await client.chat.completions.create(
                model=PROFILING_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=200,
            )

            content = response.choices[0].message.content.strip()

            # Parse JSON from response
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]

            result = json.loads(content)

            if result.get("insight") is None:
                return None

            return result

        except Exception as e:
            logger.debug(f"[{self.agent_name}_memory] LLM insight extraction failed: {e}")
            return None

    async def _store_to_supermemory(
        self, insight: Dict[str, Any], intent: "IntentPayload"
    ):
        """Upload insight to Supermemory for future retrieval."""
        client = self._get_supermemory_client()
        if not client:
            logger.debug(f"[{self.agent_name}_memory] Supermemory not available")
            return

        content = (
            f"[{self.agent_name}] User behavior: {insight['insight']}\n"
            f"Category: {insight.get('category', 'general')}\n"
            f"Source intent: {intent.event_type}\n"
            f"Perspective: {self.perspective}"
        )

        now = datetime.utcnow()

        try:
            await client.memories.add(
                content=content,
                container_tag=self.container_tag,
                metadata={
                    "type": "domain_profile_insight",
                    "agent": self.agent_name,
                    "domain": self.domain,
                    "category": insight.get("category", "general"),
                    "confidence": insight.get("confidence", 0.7),
                    "source_intent": intent.event_type,
                    "timestamp": now.isoformat(),
                    "hour": now.hour,
                    "weekday": now.weekday(),
                },
            )
            logger.info(
                f"[{self.agent_name}_memory] Stored insight to "
                f"{self.container_tag}: {insight['insight'][:80]}..."
            )
        except Exception as e:
            logger.debug(f"[{self.agent_name}_memory] Supermemory store failed: {e}")

    async def get_domain_profile(self, limit: int = 10) -> str:
        """
        Retrieve accumulated profile for this domain.

        Returns recent insights as formatted string.
        """
        client = self._get_supermemory_client()
        if not client:
            return f"Kein {self.domain}-Profil verfuegbar (Supermemory nicht verbunden)."

        try:
            response = await client.search.execute(
                q=f"user behavior {self.domain}",
                container_tags=[self.container_tag],
                limit=limit,
            )

            if not response.results:
                return f"Noch keine {self.domain}-Profil-Daten gespeichert."

            lines = [f"[{self.domain.upper()} Profil] {len(response.results)} Insights:"]
            for r in response.results:
                lines.append(f"  - {r.content[:120]}")

            return "\n".join(lines)

        except Exception as e:
            logger.debug(f"[{self.agent_name}_memory] Profile retrieval failed: {e}")
            return f"{self.domain}-Profil konnte nicht abgerufen werden."

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
            logger.debug(
                f"[{self.agent_name}_memory] supermemory package not installed"
            )
            return None


__all__ = ["MemorySubAgent"]
