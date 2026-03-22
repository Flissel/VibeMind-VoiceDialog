"""HybridRouter -- 5-tier routing: prefix -> keyword -> context -> LLM -> multi-space."""

import logging
import os
from typing import Optional

from .types import RouteResult, SpaceBinding, SessionEntry, MultiSpaceStrategy, ExecutionStep
from .bindings_registry import build_prefix_bindings, match_keyword, _get_static_fallback
from .route_cache import EventTypeCache, ClassificationCache

logger = logging.getLogger(__name__)


class HybridRouter:
    """
    Resolves intents to spaces via 5-tier matching.
    First match wins. Results are cached for performance.
    """

    def __init__(self, use_llm: bool = True):
        self._use_llm = use_llm
        self._debug = os.getenv("HYBRID_ROUTER_DEBUG", "false").lower() == "true"

        # Build prefix bindings from agents (with static fallback)
        try:
            self._prefix_bindings = build_prefix_bindings()
        except Exception:
            logger.warning("Dynamic binding generation failed, using static fallback")
            self._prefix_bindings = _get_static_fallback()

        # Caches
        ttl = int(os.getenv("HYBRID_ROUTER_CACHE_TTL", "300"))
        max_entries = int(os.getenv("HYBRID_ROUTER_CACHE_MAX", "2000"))
        self._event_cache = EventTypeCache()
        self._event_cache.populate_from_bindings(self._prefix_bindings)
        self._classification_cache = ClassificationCache(ttl_seconds=ttl, max_entries=max_entries)

        # Space router for Tier 4 (lazy loaded)
        self._space_router = None

        logger.info(
            f"HybridRouter initialized: {self._event_cache.size()} prefix bindings, "
            f"LLM={'on' if use_llm else 'off'}"
        )

    def resolve_sync(
        self,
        event_type: str,
        user_input: str,
        session: Optional[SessionEntry] = None,
        current_space: Optional[str] = None,
        force_reclassify: bool = False,
    ) -> RouteResult:
        """Synchronous resolve -- for non-async callers. Tiers 1-3 only."""
        result = self._try_tier1_prefix(event_type)
        if result:
            return result

        result = self._try_tier2_keyword(event_type, user_input)
        if result:
            return result

        result = self._try_tier3_context(event_type, user_input, current_space)
        if result:
            return result

        return RouteResult(
            space="ideas", agent="IdeasAgent", event_type=event_type,
            matched_by="default", tier=0,
        )

    async def resolve(
        self,
        event_type: str,
        user_input: str,
        session: Optional[SessionEntry] = None,
        current_space: Optional[str] = None,
        force_reclassify: bool = False,
    ) -> RouteResult:
        """Async resolve -- full 5-tier matching."""
        result = self._try_tier1_prefix(event_type)
        if result:
            return result

        result = self._try_tier2_keyword(event_type, user_input)
        if result:
            return result

        result = self._try_tier3_context(event_type, user_input, current_space)
        if result:
            return result

        if self._use_llm:
            result = await self._try_tier4_llm(event_type, user_input, force_reclassify)
            if result:
                return result

        return RouteResult(
            space="ideas", agent="IdeasAgent", event_type=event_type,
            matched_by="default", tier=0,
        )

    def _try_tier1_prefix(self, event_type) -> Optional[RouteResult]:
        """Tier 1: Exact prefix match from EVENT_TO_TOOL bindings."""
        if not event_type or event_type == "unknown":
            return None
        # Guard: Ollama sometimes returns list instead of string
        if not isinstance(event_type, str):
            event_type = str(event_type)

        prefix = event_type.split(".")[0] + "."
        binding = self._event_cache.get(prefix)
        if binding:
            result = RouteResult(
                space=binding.space, agent=binding.agent,
                event_type=event_type,
                matched_by=f"binding.prefix:{prefix}*",
                cached=True, tier=1,
            )
            if self._debug:
                logger.info(f"Tier 1 match: {event_type} -> {binding.space} (prefix={prefix})")
            return result
        return None

    def _try_tier2_keyword(self, event_type: str, user_input: str) -> Optional[RouteResult]:
        """Tier 2: Keyword regex match against user input."""
        binding = match_keyword(user_input)
        if binding:
            result = RouteResult(
                space=binding.space, agent=binding.agent,
                event_type=event_type,
                matched_by=f"binding.keyword:{binding.pattern}",
                cached=False, tier=2,
            )
            if self._debug:
                logger.info(f"Tier 2 match: '{user_input}' -> {binding.space}")
            return result
        return None

    def _try_tier3_context(
        self, event_type: str, user_input: str, current_space: Optional[str]
    ) -> Optional[RouteResult]:
        """Tier 3: Use current space as routing hint."""
        if not current_space:
            return None

        space_to_agent = {
            b.space: b.agent
            for b in self._prefix_bindings.values()
        }
        agent = space_to_agent.get(current_space)
        if agent:
            result = RouteResult(
                space=current_space, agent=agent,
                event_type=event_type,
                matched_by=f"binding.context:{current_space}",
                cached=False, tier=3,
            )
            if self._debug:
                logger.info(f"Tier 3 match: current_space={current_space}")
            return result
        return None

    async def _try_tier4_llm(
        self, event_type: str, user_input: str, force_reclassify: bool
    ) -> Optional[RouteResult]:
        """Tier 4: LLM-based SpaceRouter classification."""
        # Check classification cache first
        if not force_reclassify:
            cached = self._classification_cache.get(user_input)
            if cached:
                return RouteResult(
                    space=cached["space"], agent=cached.get("agent", ""),
                    event_type=event_type,
                    matched_by="binding.llm:cached",
                    cached=True, tier=4,
                )

        # Lazy-load SpaceRouter
        if self._space_router is None:
            try:
                from spaces.minibook.enrichment.space_router import SpaceRouter
                self._space_router = SpaceRouter()
            except ImportError:
                logger.warning("SpaceRouter not available for Tier 4")
                return None

        try:
            routing_decision = await self._space_router.route(
                event_type=event_type,
                user_text=user_input,
                payload={},
            )

            if routing_decision and routing_decision.primary_space:
                # Check if multi-space
                if routing_decision.is_multi_space and routing_decision.secondary_spaces:
                    # Tier 5 -- return with multi_space strategy
                    steps = [ExecutionStep(space=routing_decision.primary_space)]
                    for sec in routing_decision.secondary_spaces:
                        steps.append(ExecutionStep(space=sec))
                    strategy = MultiSpaceStrategy(strategy="parallel", steps=steps)

                    return RouteResult(
                        space=routing_decision.primary_space,
                        agent="", event_type=event_type,
                        matched_by="binding.minibook:multi-space",
                        tier=5, multi_space=strategy,
                    )

                # Single space from LLM
                space_to_agent = {b.space: b.agent for b in self._prefix_bindings.values()}
                agent = space_to_agent.get(routing_decision.primary_space, "")

                # Cache the classification
                self._classification_cache.put(user_input, {
                    "space": routing_decision.primary_space,
                    "agent": agent,
                    "confidence": routing_decision.confidence,
                })

                return RouteResult(
                    space=routing_decision.primary_space, agent=agent,
                    event_type=event_type,
                    matched_by="binding.llm",
                    cached=False, tier=4,
                )
        except Exception as e:
            logger.warning(f"Tier 4 LLM routing failed: {e}")
            return None

        return None
