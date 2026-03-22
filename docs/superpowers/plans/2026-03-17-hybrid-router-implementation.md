# HybridRouter Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add tier-based deterministic routing, route caching, session management, and multi-space pipeline coordination to VibeMind's intent routing system.

**Architecture:** HybridRouter sits as Phase 0 in IntentOrchestrator, resolving 90% of intents via deterministic prefix/keyword matching before MinibookHub. Sessions are SQLite-backed with cross-channel identity links. Multi-space requests use a new MultiSpaceExecutor with pipeline/parallel/mixed strategies.

**Tech Stack:** Python 3.11+, SQLite (existing vibemind.db), asyncio, existing OpenRouter LLM for Tier 4

**Spec:** `docs/superpowers/specs/2026-03-17-hybrid-router-design.md`

---

## File Structure

### New Files (in order of creation)

| File | Responsibility |
|------|---------------|
| `python/swarm/routing/__init__.py` | Public API exports |
| `python/swarm/routing/types.py` | Dataclasses: SpaceBinding, RouteResult, SessionKey, SessionEntry, MultiSpaceStrategy, ExecutionStep |
| `python/swarm/routing/bindings_registry.py` | Auto-generates SPACE_BINDINGS from agent EVENT_TO_TOOL dicts |
| `python/swarm/routing/route_cache.py` | EventTypeCache + ClassificationCache with TTL |
| `python/swarm/routing/hybrid_router.py` | 5-tier resolve() logic |
| `python/swarm/routing/session_store.py` | SQLite-backed SessionStore |
| `python/swarm/routing/identity_links.py` | Cross-channel canonical ID resolution |
| `python/swarm/routing/multi_space_executor.py` | Pipeline/parallel/mixed execution strategies |
| `python/tests/test_hybrid_router.py` | Tests for all routing components |

### Modified Files

| File | Change |
|------|--------|
| `python/data/database.py` | Add 3 tables (sessions, session_history, identity_links), bump to v17 |
| `python/swarm/orchestrator/intent_orchestrator.py` | Replace MinibookHub exclusive block with HybridRouter Phase 0 |
| `python/spaces/minibook/enrichment/space_router.py` | Deprecate `_route_by_event_type()`, keep LLM routing |
| `python/spaces/minibook/minibook_hub.py` | Delegate multi-space to MultiSpaceExecutor |
| `python/swarm/orchestrator/reference_resolver.py` | Read `last_route` from SessionStore |
| `python/config.py` | Add HYBRID_ROUTER env vars |

---

## Task 1: Types + Bindings Registry

**Files:**
- Create: `python/swarm/routing/__init__.py`
- Create: `python/swarm/routing/types.py`
- Create: `python/swarm/routing/bindings_registry.py`
- Create: `python/tests/test_hybrid_router.py`
- Read: `python/swarm/backend_agents/base_agent.py` (EVENT_TO_TOOL pattern)
- Read: `python/spaces/minibook/enrichment/space_router.py:40-51` (EVENT_TYPE_TO_SPACE to absorb)

- [ ] **Step 1: Create types.py with all dataclasses**

```python
# python/swarm/routing/types.py
"""HybridRouter type definitions."""

from dataclasses import dataclass, field
from typing import List, Optional, Literal


@dataclass
class SpaceBinding:
    """Maps an event_type prefix or keyword pattern to a space + agent."""
    space: str
    agent: str
    stream: str = ""
    pattern: str = ""  # The prefix or keyword pattern that matched


@dataclass
class RouteResult:
    """Result of a routing decision with debugging metadata."""
    space: str
    agent: str
    event_type: str
    matched_by: str          # e.g. "binding.prefix:bubble.*"
    cached: bool = False
    tier: int = 0
    multi_space: Optional["MultiSpaceStrategy"] = None


@dataclass
class ExecutionStep:
    """A single step in a multi-space execution plan."""
    space: str
    depends_on: List[str] = field(default_factory=list)
    context_fields: List[str] = field(default_factory=list)


@dataclass
class MultiSpaceStrategy:
    """Execution strategy for multi-space requests."""
    strategy: Literal["pipeline", "parallel", "mixed"]
    steps: List[ExecutionStep] = field(default_factory=list)


@dataclass
class SessionKey:
    """Identifies a routing session."""
    agent_id: str
    channel: str
    scope: str = "direct"
    peer_id: str = "anonymous"
    thread_id: Optional[str] = None

    @property
    def key(self) -> str:
        base = f"agent:{self.agent_id}:{self.channel}:{self.scope}:{self.peer_id}"
        if self.thread_id:
            return f"{base}:thread:{self.thread_id}"
        return base

    @property
    def main_key(self) -> str:
        return f"agent:{self.agent_id}:main"


@dataclass
class SessionEntry:
    """A session's stored state."""
    session_key: str
    agent_id: str
    channel: str
    canonical_id: Optional[str] = None
    space_state: Optional[dict] = None
    last_route: Optional[RouteResult] = None
    last_active: Optional[str] = None
```

- [ ] **Step 2: Create bindings_registry.py**

```python
# python/swarm/routing/bindings_registry.py
"""Auto-generates SPACE_BINDINGS from registered backend agents."""

import logging
import re
from typing import Dict, Optional

from .types import SpaceBinding

logger = logging.getLogger(__name__)

# Tier 2: Keyword patterns → Space (German + English)
KEYWORD_BINDINGS: Dict[str, SpaceBinding] = {
    r"screenshot|bildschirm|klick|browser|click": SpaceBinding(
        space="desktop", agent="DesktopAgent", pattern="keyword:desktop"
    ),
    r"workflow|automatisierung|n8n|automation": SpaceBinding(
        space="n8n", agent="N8nBackendAgent", pattern="keyword:n8n"
    ),
    r"termin|erinnerung|wecker|timer|schedule|reminder": SpaceBinding(
        space="schedule", agent="ScheduleBackendAgent", pattern="keyword:schedule"
    ),
}

# Compiled keyword regexes (built once)
_COMPILED_KEYWORDS: Dict[re.Pattern, SpaceBinding] = {}


def _compile_keywords():
    """Compile keyword patterns once."""
    global _COMPILED_KEYWORDS
    if not _COMPILED_KEYWORDS:
        _COMPILED_KEYWORDS = {
            re.compile(pattern, re.IGNORECASE): binding
            for pattern, binding in KEYWORD_BINDINGS.items()
        }


def build_prefix_bindings() -> Dict[str, SpaceBinding]:
    """
    Scan all registered backend agents and extract prefix → space mappings
    from their EVENT_TO_TOOL dicts.

    Returns dict like {"bubble.": SpaceBinding(space="ideas", ...), ...}
    """
    bindings: Dict[str, SpaceBinding] = {}

    try:
        from swarm.backend_agents import (
            get_bubbles_agent, get_ideas_agent, get_desktop_agent,
            get_coding_agent, get_roarboot_agent, get_n8n_agent,
            get_schedule_agent, get_minibook_agent, get_zeroclaw_research_agent,
        )
    except ImportError:
        logger.warning("Could not import backend agents for binding generation")
        return _get_static_fallback()

    # Map of getter → (space_name, agent_name, stream)
    agent_registry = {
        "bubbles": ("ideas", "BubblesAgent", "events:tasks:bubbles"),
        "ideas": ("ideas", "IdeasAgent", "events:tasks:ideas"),
        "desktop": ("desktop", "DesktopAgent", "events:tasks:desktop"),
        "coding": ("coding", "CodingAgent", "events:tasks:coding"),
        "rowboat": ("rowboat", "RoarbootBackendAgent", "events:tasks:roarboot"),
        "n8n": ("n8n", "N8nBackendAgent", "events:tasks:n8n"),
        "schedule": ("schedule", "ScheduleBackendAgent", "events:tasks:schedule"),
        "minibook": ("minibook", "MinibookBackendAgent", "events:tasks:minibook"),
        "research": ("research", "ZeroClawResearchAgent", "events:tasks:zeroclaw"),
        "video": ("video", "VideoBackendAgent", "events:tasks:video"),
    }

    # Try dynamic extraction from agent instances
    for agent_key, (space, agent_name, stream) in agent_registry.items():
        try:
            # Get agent class and extract EVENT_TO_TOOL
            module = __import__("swarm.backend_agents", fromlist=[f"get_{agent_key}_agent"])
            getter = getattr(module, f"get_{agent_key}_agent", None)
            if not getter:
                continue
            agent_instance = getter()
            if not agent_instance:
                continue

            event_to_tool = getattr(agent_instance, "EVENT_TO_TOOL", {})

            # Extract unique prefixes
            prefixes = set()
            for event_type in event_to_tool.keys():
                prefix = event_type.split(".")[0] + "."
                prefixes.add(prefix)

            for prefix in prefixes:
                bindings[prefix] = SpaceBinding(
                    space=space, agent=agent_name,
                    stream=stream, pattern=f"prefix:{prefix}*"
                )
        except Exception as e:
            logger.debug(f"Could not load agent {agent_key}: {e}")
            continue

    # If dynamic extraction failed, use static fallback
    if not bindings:
        bindings = _get_static_fallback()

    logger.info(f"Built {len(bindings)} prefix bindings from agents")
    return bindings


def _get_static_fallback() -> Dict[str, SpaceBinding]:
    """Static fallback bindings if agent introspection fails."""
    return {
        "bubble.": SpaceBinding(space="ideas", agent="BubblesAgent", stream="events:tasks:bubbles", pattern="prefix:bubble.*"),
        "idea.": SpaceBinding(space="ideas", agent="IdeasAgent", stream="events:tasks:ideas", pattern="prefix:idea.*"),
        "code.": SpaceBinding(space="coding", agent="CodingAgent", stream="events:tasks:coding", pattern="prefix:code.*"),
        "desktop.": SpaceBinding(space="desktop", agent="DesktopAgent", stream="events:tasks:desktop", pattern="prefix:desktop.*"),
        "web.": SpaceBinding(space="desktop", agent="DesktopAgent", stream="events:tasks:desktop", pattern="prefix:web.*"),
        "messaging.": SpaceBinding(space="desktop", agent="DesktopAgent", stream="events:tasks:desktop", pattern="prefix:messaging.*"),
        "openclaw.": SpaceBinding(space="desktop", agent="DesktopAgent", stream="events:tasks:desktop", pattern="prefix:openclaw.*"),
        "roarboot.": SpaceBinding(space="rowboat", agent="RoarbootBackendAgent", stream="events:tasks:roarboot", pattern="prefix:roarboot.*"),
        "research.": SpaceBinding(space="research", agent="ZeroClawResearchAgent", stream="events:tasks:zeroclaw", pattern="prefix:research.*"),
        "minibook.": SpaceBinding(space="minibook", agent="MinibookBackendAgent", stream="events:tasks:minibook", pattern="prefix:minibook.*"),
        "schedule.": SpaceBinding(space="schedule", agent="ScheduleBackendAgent", stream="events:tasks:schedule", pattern="prefix:schedule.*"),
        "n8n.": SpaceBinding(space="n8n", agent="N8nBackendAgent", stream="events:tasks:n8n", pattern="prefix:n8n.*"),
        "video.": SpaceBinding(space="video", agent="VideoBackendAgent", stream="events:tasks:video", pattern="prefix:video.*"),
    }


def match_keyword(user_input: str) -> Optional[SpaceBinding]:
    """Tier 2: Match user input against keyword patterns."""
    _compile_keywords()
    normalized = user_input.lower().strip()
    for pattern, binding in _COMPILED_KEYWORDS.items():
        if pattern.search(normalized):
            return binding
    return None
```

- [ ] **Step 3: Create __init__.py**

```python
# python/swarm/routing/__init__.py
"""HybridRouter — Tier-based deterministic routing for VibeMind."""

from .types import (
    SpaceBinding, RouteResult, ExecutionStep,
    MultiSpaceStrategy, SessionKey, SessionEntry,
)
from .bindings_registry import build_prefix_bindings, match_keyword

__all__ = [
    "SpaceBinding", "RouteResult", "ExecutionStep",
    "MultiSpaceStrategy", "SessionKey", "SessionEntry",
    "build_prefix_bindings", "match_keyword",
]
```

- [ ] **Step 4: Write test for bindings registry**

```python
# python/tests/test_hybrid_router.py
"""Tests for HybridRouter components."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from swarm.routing.types import SpaceBinding, RouteResult, SessionKey
from swarm.routing.bindings_registry import (
    _get_static_fallback, match_keyword, KEYWORD_BINDINGS,
)


def test_static_fallback_covers_all_spaces():
    """All 10+ spaces must have prefix bindings."""
    bindings = _get_static_fallback()
    spaces = {b.space for b in bindings.values()}
    assert "ideas" in spaces
    assert "coding" in spaces
    assert "desktop" in spaces
    assert "rowboat" in spaces
    assert "research" in spaces
    assert "minibook" in spaces
    assert "schedule" in spaces
    assert "n8n" in spaces
    assert "video" in spaces
    assert len(bindings) >= 12  # 13 prefixes in fallback


def test_prefix_binding_format():
    """Each prefix must end with a dot."""
    bindings = _get_static_fallback()
    for prefix in bindings.keys():
        assert prefix.endswith("."), f"Prefix {prefix} must end with '.'"


def test_keyword_match_desktop():
    """Keyword 'screenshot' should match desktop."""
    result = match_keyword("Mach einen Screenshot")
    assert result is not None
    assert result.space == "desktop"


def test_keyword_match_schedule():
    """Keyword 'termin' should match schedule."""
    result = match_keyword("Erstelle einen Termin")
    assert result is not None
    assert result.space == "schedule"


def test_keyword_match_n8n():
    """Keyword 'workflow' should match n8n."""
    result = match_keyword("Erstelle einen Workflow")
    assert result is not None
    assert result.space == "n8n"


def test_keyword_no_match():
    """Random text should not match any keyword."""
    result = match_keyword("Hallo wie geht es dir")
    assert result is None


def test_session_key_format():
    """SessionKey produces correct key strings."""
    key = SessionKey(agent_id="ideas", channel="voice", peer_id="felix")
    assert key.key == "agent:ideas:voice:direct:felix"
    assert key.main_key == "agent:ideas:main"


def test_session_key_with_thread():
    """SessionKey with thread appends thread segment."""
    key = SessionKey(agent_id="ideas", channel="voice", peer_id="felix", thread_id="t123")
    assert key.key == "agent:ideas:voice:direct:felix:thread:t123"


def test_route_result_matched_by():
    """RouteResult stores matched_by for debugging."""
    result = RouteResult(
        space="ideas", agent="BubblesAgent", event_type="bubble.create",
        matched_by="binding.prefix:bubble.*", cached=True, tier=1,
    )
    assert result.matched_by == "binding.prefix:bubble.*"
    assert result.tier == 1
    assert result.cached is True


if __name__ == "__main__":
    test_static_fallback_covers_all_spaces()
    test_prefix_binding_format()
    test_keyword_match_desktop()
    test_keyword_match_schedule()
    test_keyword_match_n8n()
    test_keyword_no_match()
    test_session_key_format()
    test_session_key_with_thread()
    test_route_result_matched_by()
    print("All Task 1 tests passed!")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd python && python tests/test_hybrid_router.py`
Expected: "All Task 1 tests passed!"

- [ ] **Step 6: Commit**

```bash
git add python/swarm/routing/ python/tests/test_hybrid_router.py
git commit -m "feat(routing): add types, bindings registry, and keyword matching"
```

---

## Task 2: Route Cache

**Files:**
- Create: `python/swarm/routing/route_cache.py`
- Modify: `python/tests/test_hybrid_router.py` (add cache tests)

- [ ] **Step 1: Write failing tests for route cache**

Add to `python/tests/test_hybrid_router.py`:

```python
import time
from swarm.routing.route_cache import EventTypeCache, ClassificationCache
from swarm.routing.types import SpaceBinding, RouteResult


def test_event_type_cache_hit():
    """Cached event_type returns immediately."""
    cache = EventTypeCache()
    binding = SpaceBinding(space="ideas", agent="BubblesAgent")
    cache.put("bubble.create", binding)
    assert cache.get("bubble.create") == binding


def test_event_type_cache_miss():
    """Unknown event_type returns None."""
    cache = EventTypeCache()
    assert cache.get("unknown.event") is None


def test_classification_cache_ttl():
    """Classification cache entries expire after TTL."""
    cache = ClassificationCache(ttl_seconds=1, max_entries=100)
    cache.put("test input", {"event_type": "bubble.create", "space": "ideas"})
    assert cache.get("test input") is not None
    time.sleep(1.1)
    assert cache.get("test input") is None


def test_classification_cache_overflow():
    """Cache clears when max entries exceeded."""
    cache = ClassificationCache(ttl_seconds=300, max_entries=3)
    for i in range(4):
        cache.put(f"input_{i}", {"event_type": f"event.{i}"})
    # After overflow, cache was cleared and only has the latest entry
    assert cache.get("input_0") is None
    assert cache.get("input_3") is not None


def test_classification_cache_bypass():
    """force_reclassify should be handled by caller, not cache."""
    cache = ClassificationCache(ttl_seconds=300, max_entries=100)
    cache.put("test", {"event_type": "x"})
    assert cache.get("test") is not None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd python && python tests/test_hybrid_router.py`
Expected: ImportError for `route_cache`

- [ ] **Step 3: Create route_cache.py**

```python
# python/swarm/routing/route_cache.py
"""Route caching for HybridRouter — EventType (permanent) + Classification (TTL)."""

import hashlib
import logging
import time
from typing import Any, Dict, Optional

from .types import SpaceBinding

logger = logging.getLogger(__name__)


class EventTypeCache:
    """Tier 1 cache: event_type → SpaceBinding. Permanent, invalidated on config reload."""

    def __init__(self):
        self._cache: Dict[str, SpaceBinding] = {}

    def put(self, event_type: str, binding: SpaceBinding):
        self._cache[event_type] = binding

    def get(self, event_type: str) -> Optional[SpaceBinding]:
        return self._cache.get(event_type)

    def clear(self):
        self._cache.clear()

    def size(self) -> int:
        return len(self._cache)

    def populate_from_bindings(self, prefix_bindings: Dict[str, SpaceBinding]):
        """Pre-populate cache with all known event_type prefixes."""
        self._cache.update(prefix_bindings)
        logger.info(f"EventTypeCache populated with {len(prefix_bindings)} entries")


class ClassificationCache:
    """Tier 4 cache: normalized user input hash → classification result. TTL-based."""

    def __init__(self, ttl_seconds: int = 300, max_entries: int = 2000):
        self._ttl = ttl_seconds
        self._max = max_entries
        self._cache: Dict[str, tuple[float, Any]] = {}  # key → (timestamp, value)

    def put(self, user_input: str, classification: dict):
        if len(self._cache) >= self._max:
            logger.info(f"ClassificationCache overflow ({self._max}), clearing")
            self._cache.clear()
        key = self._hash(user_input)
        self._cache[key] = (time.monotonic(), classification)

    def get(self, user_input: str) -> Optional[dict]:
        key = self._hash(user_input)
        entry = self._cache.get(key)
        if entry is None:
            return None
        timestamp, value = entry
        if time.monotonic() - timestamp > self._ttl:
            del self._cache[key]
            return None
        return value

    def clear(self):
        self._cache.clear()

    def size(self) -> int:
        return len(self._cache)

    @staticmethod
    def _hash(user_input: str) -> str:
        normalized = user_input.lower().strip()
        return hashlib.md5(normalized.encode()).hexdigest()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd python && python tests/test_hybrid_router.py`
Expected: All tests pass

- [ ] **Step 5: Update __init__.py exports**

Add to `python/swarm/routing/__init__.py`:

```python
from .route_cache import EventTypeCache, ClassificationCache
```

- [ ] **Step 6: Commit**

```bash
git add python/swarm/routing/route_cache.py python/swarm/routing/__init__.py python/tests/test_hybrid_router.py
git commit -m "feat(routing): add EventTypeCache and ClassificationCache"
```

---

## Task 3: HybridRouter Core (Tiers 1-4)

**Files:**
- Create: `python/swarm/routing/hybrid_router.py`
- Modify: `python/tests/test_hybrid_router.py`
- Read: `python/spaces/minibook/enrichment/space_router.py:91-135` (LLM routing to wrap)

- [ ] **Step 1: Write failing tests for HybridRouter**

Add to `python/tests/test_hybrid_router.py`:

```python
import asyncio
from swarm.routing.hybrid_router import HybridRouter


def test_tier1_prefix_match():
    """Known event_type prefix resolves via Tier 1."""
    router = HybridRouter()
    result = router.resolve_sync(event_type="bubble.create", user_input="Erstelle Bubble")
    assert result.space == "ideas"
    assert result.tier == 1
    assert "binding.prefix" in result.matched_by


def test_tier1_cached_on_second_call():
    """Second call for same event_type returns cached=True."""
    router = HybridRouter()
    r1 = router.resolve_sync(event_type="bubble.create", user_input="x")
    r2 = router.resolve_sync(event_type="bubble.create", user_input="x")
    assert r2.cached is True


def test_tier2_keyword_match():
    """Keyword in user_input matches via Tier 2 when event_type is ambiguous."""
    router = HybridRouter()
    result = router.resolve_sync(event_type="unknown.action", user_input="Mach einen Screenshot")
    assert result.space == "desktop"
    assert result.tier == 2
    assert "binding.keyword" in result.matched_by


def test_tier3_context_match():
    """Current space context is used as hint for Tier 3."""
    router = HybridRouter()
    result = router.resolve_sync(
        event_type="unknown.action",
        user_input="Zeig mir alles",
        current_space="coding",
    )
    assert result.space == "coding"
    assert result.tier == 3
    assert "binding.context" in result.matched_by


def test_all_known_prefixes_resolve():
    """Every known event prefix resolves via Tier 1."""
    router = HybridRouter()
    test_events = [
        ("bubble.list", "ideas"), ("idea.create", "ideas"),
        ("code.generate", "coding"), ("desktop.screenshot", "desktop"),
        ("schedule.create", "schedule"), ("n8n.list", "n8n"),
        ("roarboot.query", "rowboat"), ("research.search", "research"),
    ]
    for event_type, expected_space in test_events:
        result = router.resolve_sync(event_type=event_type, user_input="test")
        assert result.space == expected_space, f"{event_type} → {result.space}, expected {expected_space}"
        assert result.tier == 1
```

```python
# Tier 4 + 5 tests (mocked LLM)
from unittest.mock import AsyncMock, patch, MagicMock


def test_tier4_llm_single_space():
    """Tier 4: LLM resolves ambiguous input to single space."""
    router = HybridRouter(use_llm=True)
    # Mock SpaceRouter
    mock_decision = MagicMock()
    mock_decision.primary_space = "coding"
    mock_decision.secondary_spaces = []
    mock_decision.is_multi_space = False
    mock_decision.confidence = 0.8

    mock_router = AsyncMock()
    mock_router.route = AsyncMock(return_value=mock_decision)
    router._space_router = mock_router

    result = asyncio.get_event_loop().run_until_complete(
        router.resolve(event_type="unknown.action", user_input="Generiere Code für API")
    )
    assert result.space == "coding"
    assert result.tier == 4
    assert "binding.llm" in result.matched_by


def test_tier5_multi_space_detected():
    """Tier 5: LLM detects multi-space request."""
    router = HybridRouter(use_llm=True)
    mock_decision = MagicMock()
    mock_decision.primary_space = "research"
    mock_decision.secondary_spaces = ["ideas"]
    mock_decision.is_multi_space = True
    mock_decision.confidence = 0.8

    mock_router = AsyncMock()
    mock_router.route = AsyncMock(return_value=mock_decision)
    router._space_router = mock_router

    result = asyncio.get_event_loop().run_until_complete(
        router.resolve(event_type="unknown.action", user_input="Recherchiere und erstelle Idee")
    )
    assert result.tier == 5
    assert result.multi_space is not None
    assert result.multi_space.strategy == "parallel"
    assert len(result.multi_space.steps) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd python && python tests/test_hybrid_router.py`
Expected: ImportError for `hybrid_router`

- [ ] **Step 3: Create hybrid_router.py (Tiers 1-4)**

```python
# python/swarm/routing/hybrid_router.py
"""HybridRouter — 5-tier routing: prefix → keyword → context → LLM → multi-space."""

import logging
import os
from typing import Optional

from .types import RouteResult, SpaceBinding, SessionEntry
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
        """Synchronous resolve — for non-async callers."""
        # Tier 1: Prefix match
        result = self._try_tier1_prefix(event_type)
        if result:
            return result

        # Tier 2: Keyword match
        result = self._try_tier2_keyword(event_type, user_input)
        if result:
            return result

        # Tier 3: Context match
        result = self._try_tier3_context(event_type, user_input, current_space)
        if result:
            return result

        # Tier 4 + 5 need async — return default for sync callers
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
        """
        Async resolve — full 5-tier matching.
        Tier 5 returns multi_space strategy for caller to execute.
        """
        # Tier 1: Prefix match
        result = self._try_tier1_prefix(event_type)
        if result:
            return result

        # Tier 2: Keyword match
        result = self._try_tier2_keyword(event_type, user_input)
        if result:
            return result

        # Tier 3: Context match
        result = self._try_tier3_context(event_type, user_input, current_space)
        if result:
            return result

        # Tier 4: LLM SpaceRouter
        if self._use_llm:
            result = await self._try_tier4_llm(event_type, user_input, force_reclassify)
            if result:
                return result

        # Default fallback
        return RouteResult(
            space="ideas", agent="IdeasAgent", event_type=event_type,
            matched_by="default", tier=0,
        )

    def _try_tier1_prefix(self, event_type: str) -> Optional[RouteResult]:
        """Tier 1: Exact prefix match from EVENT_TO_TOOL bindings."""
        if not event_type or event_type == "unknown":
            return None

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
                logger.info(f"Tier 1 match: {event_type} → {binding.space} (prefix={prefix})")
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
                logger.info(f"Tier 2 match: '{user_input}' → {binding.space}")
            return result
        return None

    def _try_tier3_context(
        self, event_type: str, user_input: str, current_space: Optional[str]
    ) -> Optional[RouteResult]:
        """Tier 3: Use current space as routing hint."""
        if not current_space:
            return None

        # Map space name to agent name
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
                    # Tier 5 territory — return with multi_space flag
                    from .types import MultiSpaceStrategy, ExecutionStep
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd python && python tests/test_hybrid_router.py`
Expected: All tests pass

- [ ] **Step 5: Update __init__.py**

Add to `python/swarm/routing/__init__.py`:

```python
from .hybrid_router import HybridRouter
```

- [ ] **Step 6: Commit**

```bash
git add python/swarm/routing/hybrid_router.py python/swarm/routing/__init__.py python/tests/test_hybrid_router.py
git commit -m "feat(routing): add HybridRouter with 5-tier resolve logic"
```

---

## Task 4: Database Schema + Session Store

**Files:**
- Modify: `python/data/database.py` (add 3 tables, bump to v17)
- Create: `python/swarm/routing/session_store.py`
- Create: `python/swarm/routing/identity_links.py`
- Modify: `python/tests/test_hybrid_router.py`

- [ ] **Step 1: Write failing tests for session store**

Add to `python/tests/test_hybrid_router.py`:

```python
import tempfile
import sqlite3
from swarm.routing.session_store import SessionStore
from swarm.routing.identity_links import IdentityLinkResolver
from swarm.routing.types import SessionKey, RouteResult


def test_session_store_create_and_get():
    """SessionStore creates and retrieves sessions."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    store = SessionStore(db_path=db_path)
    key = SessionKey(agent_id="ideas", channel="voice", peer_id="felix")
    entry = store.get_or_create(key)
    assert entry.agent_id == "ideas"
    assert entry.channel == "voice"


def test_session_store_last_route():
    """SessionStore persists last_route."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    store = SessionStore(db_path=db_path)
    key = SessionKey(agent_id="ideas", channel="voice", peer_id="felix")
    store.get_or_create(key)
    route = RouteResult(space="ideas", agent="IdeasAgent", event_type="bubble.create",
                        matched_by="binding.prefix:bubble.*", tier=1)
    store.update_last_route(key, route)
    entry = store.get_or_create(key)
    assert entry.last_route is not None
    assert entry.last_route.event_type == "bubble.create"


def test_identity_links_resolve():
    """Identity links resolve different channel peers to canonical ID."""
    resolver = IdentityLinkResolver()
    resolver.add_link("voice", "user_voice_123", "canonical:felix")
    resolver.add_link("chat", "dashboard_user", "canonical:felix")
    assert resolver.resolve("voice", "user_voice_123") == "canonical:felix"
    assert resolver.resolve("chat", "dashboard_user") == "canonical:felix"
    assert resolver.resolve("voice", "unknown") == "unknown"  # passthrough
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd python && python tests/test_hybrid_router.py`
Expected: ImportError for `session_store`

- [ ] **Step 3: Add schema migration to database.py**

Read `python/data/database.py` and add migration v16→v17. Add after the existing v15→v16 migration block:

```python
# Migration v16 → v17: HybridRouter sessions + identity links
if from_version < 17:
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_key   TEXT PRIMARY KEY,
            agent_id      TEXT NOT NULL,
            channel       TEXT NOT NULL,
            canonical_id  TEXT,
            space_state   TEXT,
            last_route    TEXT,
            last_active   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS session_history (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            session_key   TEXT NOT NULL REFERENCES sessions(session_key),
            speaker       TEXT NOT NULL,
            text          TEXT NOT NULL,
            event_type    TEXT,
            timestamp     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS identity_links (
            channel       TEXT NOT NULL,
            peer_id       TEXT NOT NULL,
            canonical_id  TEXT NOT NULL,
            PRIMARY KEY (channel, peer_id)
        )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_session_history_key ON session_history(session_key)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_identity_canonical ON identity_links(canonical_id)")
    cursor.execute("UPDATE schema_version SET version = 17")
    logger.info("Schema migrated to v17: sessions + identity_links")
```

Also update `SCHEMA_VERSION = 17` at the top of the file.

- [ ] **Step 4: Create session_store.py**

```python
# python/swarm/routing/session_store.py
"""SQLite-backed session store for HybridRouter."""

import json
import logging
import sqlite3
from typing import List, Optional

from .types import SessionKey, SessionEntry, RouteResult

logger = logging.getLogger(__name__)


class SessionStore:
    """Manages routing sessions in SQLite."""

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            import os
            # routing/ → swarm/ → python/  (3 levels up)
            db_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                "vibemind.db"
            )
        self._db_path = db_path
        self._ensure_tables()

    def _ensure_tables(self):
        """Create tables if they don't exist (for standalone/test usage)."""
        conn = sqlite3.connect(self._db_path)
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_key TEXT PRIMARY KEY, agent_id TEXT NOT NULL,
                    channel TEXT NOT NULL, canonical_id TEXT,
                    space_state TEXT, last_route TEXT,
                    last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS session_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_key TEXT NOT NULL, speaker TEXT NOT NULL,
                    text TEXT NOT NULL, event_type TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
        finally:
            conn.close()

    def get_or_create(self, key: SessionKey) -> SessionEntry:
        """Load existing session or create new one."""
        conn = sqlite3.connect(self._db_path)
        try:
            row = conn.execute(
                "SELECT session_key, agent_id, channel, canonical_id, space_state, last_route, last_active "
                "FROM sessions WHERE session_key = ?",
                (key.key,)
            ).fetchone()

            if row:
                last_route = None
                if row[5]:
                    try:
                        lr = json.loads(row[5])
                        last_route = RouteResult(**lr)
                    except Exception:
                        pass
                return SessionEntry(
                    session_key=row[0], agent_id=row[1], channel=row[2],
                    canonical_id=row[3],
                    space_state=json.loads(row[4]) if row[4] else None,
                    last_route=last_route, last_active=row[6],
                )

            # Create new session
            conn.execute(
                "INSERT INTO sessions (session_key, agent_id, channel, canonical_id) VALUES (?, ?, ?, ?)",
                (key.key, key.agent_id, key.channel, key.peer_id)
            )
            conn.commit()
            return SessionEntry(
                session_key=key.key, agent_id=key.agent_id, channel=key.channel,
                canonical_id=key.peer_id,
            )
        finally:
            conn.close()

    def update_last_route(self, key: SessionKey, route: RouteResult):
        """Store the last routing decision for DroPE integration."""
        conn = sqlite3.connect(self._db_path)
        try:
            route_json = json.dumps({
                "space": route.space, "agent": route.agent,
                "event_type": route.event_type, "matched_by": route.matched_by,
                "tier": route.tier,
            })
            conn.execute(
                "UPDATE sessions SET last_route = ?, last_active = CURRENT_TIMESTAMP "
                "WHERE session_key = ?",
                (route_json, key.key)
            )
            conn.commit()
        finally:
            conn.close()

    def append_history(self, key: SessionKey, speaker: str, text: str, event_type: str = ""):
        """Add a routing turn to session history."""
        conn = sqlite3.connect(self._db_path)
        try:
            conn.execute(
                "INSERT INTO session_history (session_key, speaker, text, event_type) VALUES (?, ?, ?, ?)",
                (key.key, speaker, text, event_type)
            )
            # Keep only last 20 entries per session
            conn.execute("""
                DELETE FROM session_history WHERE id NOT IN (
                    SELECT id FROM session_history WHERE session_key = ?
                    ORDER BY timestamp DESC LIMIT 20
                ) AND session_key = ?
            """, (key.key, key.key))
            conn.commit()
        finally:
            conn.close()

    def get_cross_space_context(self, canonical_id: str) -> List[SessionEntry]:
        """Get all sessions for a user across all spaces."""
        conn = sqlite3.connect(self._db_path)
        try:
            rows = conn.execute(
                "SELECT session_key, agent_id, channel, canonical_id, space_state, last_route, last_active "
                "FROM sessions WHERE canonical_id = ? ORDER BY last_active DESC",
                (canonical_id,)
            ).fetchall()
            return [
                SessionEntry(
                    session_key=r[0], agent_id=r[1], channel=r[2],
                    canonical_id=r[3],
                    space_state=json.loads(r[4]) if r[4] else None,
                    last_route=None, last_active=r[6],
                )
                for r in rows
            ]
        finally:
            conn.close()
```

- [ ] **Step 5: Create identity_links.py**

```python
# python/swarm/routing/identity_links.py
"""Cross-channel identity linking for session continuity."""

import logging
import sqlite3
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class IdentityLinkResolver:
    """
    Resolves channel-specific peer IDs to canonical user IDs.
    Enables: voice user + chat user → same session.
    """

    def __init__(self, db_path: Optional[str] = None):
        self._db_path = db_path
        # In-memory cache for fast lookups
        self._cache: Dict[Tuple[str, str], str] = {}

    def add_link(self, channel: str, peer_id: str, canonical_id: str):
        """Register a channel+peer → canonical mapping."""
        self._cache[(channel, peer_id)] = canonical_id
        if self._db_path:
            self._persist(channel, peer_id, canonical_id)

    def resolve(self, channel: str, peer_id: str) -> str:
        """Resolve peer_id to canonical form. Returns peer_id unchanged if no link exists."""
        canonical = self._cache.get((channel, peer_id))
        if canonical:
            return canonical

        # Try DB if not in cache
        if self._db_path:
            canonical = self._load_from_db(channel, peer_id)
            if canonical:
                self._cache[(channel, peer_id)] = canonical
                return canonical

        return peer_id  # passthrough

    def _persist(self, channel: str, peer_id: str, canonical_id: str):
        """Save link to SQLite."""
        try:
            conn = sqlite3.connect(self._db_path)
            conn.execute(
                "INSERT OR REPLACE INTO identity_links (channel, peer_id, canonical_id) VALUES (?, ?, ?)",
                (channel, peer_id, canonical_id)
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning(f"Failed to persist identity link: {e}")

    def _load_from_db(self, channel: str, peer_id: str) -> Optional[str]:
        """Load link from SQLite."""
        try:
            conn = sqlite3.connect(self._db_path)
            row = conn.execute(
                "SELECT canonical_id FROM identity_links WHERE channel = ? AND peer_id = ?",
                (channel, peer_id)
            ).fetchone()
            conn.close()
            return row[0] if row else None
        except Exception:
            return None
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd python && python tests/test_hybrid_router.py`
Expected: All tests pass

- [ ] **Step 7: Update __init__.py**

Add to `python/swarm/routing/__init__.py`:

```python
from .session_store import SessionStore
from .identity_links import IdentityLinkResolver
```

- [ ] **Step 8: Commit**

```bash
git add python/swarm/routing/session_store.py python/swarm/routing/identity_links.py python/data/database.py python/tests/test_hybrid_router.py python/swarm/routing/__init__.py
git commit -m "feat(routing): add SessionStore, IdentityLinks, and schema v17"
```

---

## Task 5: MultiSpaceExecutor

**Files:**
- Create: `python/swarm/routing/multi_space_executor.py`
- Modify: `python/tests/test_hybrid_router.py`
- Read: `python/spaces/minibook/result_aggregator.py` (existing pattern)

- [ ] **Step 1: Write failing tests**

Add to `python/tests/test_hybrid_router.py`:

```python
from swarm.routing.multi_space_executor import MultiSpaceExecutor
from swarm.routing.types import MultiSpaceStrategy, ExecutionStep


def test_build_phases_parallel():
    """Two independent steps form one phase."""
    executor = MultiSpaceExecutor()
    strategy = MultiSpaceStrategy(
        strategy="parallel",
        steps=[
            ExecutionStep(space="ideas", depends_on=[]),
            ExecutionStep(space="schedule", depends_on=[]),
        ]
    )
    phases = executor._build_phases(strategy.steps)
    assert len(phases) == 1
    assert len(phases[0]) == 2


def test_build_phases_pipeline():
    """Dependent steps form separate phases."""
    executor = MultiSpaceExecutor()
    strategy = MultiSpaceStrategy(
        strategy="pipeline",
        steps=[
            ExecutionStep(space="research", depends_on=[]),
            ExecutionStep(space="ideas", depends_on=["research"], context_fields=["findings"]),
        ]
    )
    phases = executor._build_phases(strategy.steps)
    assert len(phases) == 2
    assert phases[0][0].space == "research"
    assert phases[1][0].space == "ideas"


def test_build_phases_mixed():
    """Mixed: research + schedule parallel, then ideas depends on research."""
    executor = MultiSpaceExecutor()
    strategy = MultiSpaceStrategy(
        strategy="mixed",
        steps=[
            ExecutionStep(space="research", depends_on=[]),
            ExecutionStep(space="schedule", depends_on=[]),
            ExecutionStep(space="ideas", depends_on=["research"], context_fields=["findings"]),
        ]
    )
    phases = executor._build_phases(strategy.steps)
    assert len(phases) == 2
    assert len(phases[0]) == 2  # research + schedule
    assert len(phases[1]) == 1  # ideas


def test_inject_context():
    """Context injection adds prior results to payload."""
    executor = MultiSpaceExecutor()
    step = ExecutionStep(space="ideas", depends_on=["research"], context_fields=["findings"])
    prior = {"research": {"findings": ["trend1", "trend2"], "summary": "2 trends found"}}
    payload = {"title": "KI"}
    enriched = executor._inject_context(payload, step, prior)
    assert enriched["from_research_findings"] == ["trend1", "trend2"]
    assert "prior_context" in enriched
    assert enriched["title"] == "KI"  # original preserved
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd python && python tests/test_hybrid_router.py`
Expected: ImportError for `multi_space_executor`

- [ ] **Step 3: Create multi_space_executor.py**

```python
# python/swarm/routing/multi_space_executor.py
"""Multi-space execution: pipeline, parallel, and mixed strategies."""

import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional

from .types import ExecutionStep, MultiSpaceStrategy

logger = logging.getLogger(__name__)

# Default timeout for entire multi-space operation
MULTI_SPACE_TIMEOUT = 120  # seconds


class MultiSpaceExecutor:
    """
    Executes multi-space requests with dependency-aware phasing.
    Replaces MinibookHub's ResultAggregator.track_multi() for pipeline/mixed.
    """

    def __init__(self, space_executor: Optional[Callable] = None):
        """
        Args:
            space_executor: async callable(space, payload) → dict result.
                           Injected by IntentOrchestrator at init.
        """
        self._execute_fn = space_executor

    async def execute(
        self, strategy: MultiSpaceStrategy, payload: dict, timeout: float = MULTI_SPACE_TIMEOUT
    ) -> dict:
        """Execute multi-space strategy with phased coordination."""
        if not self._execute_fn:
            return {"success": False, "error": "No space executor configured"}

        results: Dict[str, Any] = {}
        phases = self._build_phases(strategy.steps)

        try:
            async with asyncio.timeout(timeout):
                for phase_idx, phase in enumerate(phases):
                    logger.info(
                        f"Multi-space phase {phase_idx + 1}/{len(phases)}: "
                        f"{[s.space for s in phase]}"
                    )
                    tasks = []
                    for step in phase:
                        enriched = self._inject_context(payload, step, results)
                        tasks.append(self._execute_step(step.space, enriched))

                    phase_results = await asyncio.gather(*tasks, return_exceptions=True)

                    for step, result in zip(phase, phase_results):
                        if isinstance(result, Exception):
                            logger.error(f"Space {step.space} failed: {result}")
                            results[step.space] = {
                                "success": False, "error": str(result)
                            }
                        else:
                            results[step.space] = result

        except asyncio.TimeoutError:
            logger.warning(f"Multi-space execution timed out after {timeout}s")
            results["_timeout"] = True

        return self._merge_results(results)

    async def _execute_step(self, space: str, payload: dict) -> dict:
        """Execute a single space step."""
        try:
            return await self._execute_fn(space, payload)
        except Exception as e:
            logger.error(f"Space {space} execution error: {e}")
            return {"success": False, "error": str(e), "space": space}

    def _build_phases(self, steps: List[ExecutionStep]) -> List[List[ExecutionStep]]:
        """
        Group steps into execution phases based on dependencies.
        Steps with no unresolved dependencies run in the same phase.
        """
        phases: List[List[ExecutionStep]] = []
        resolved: set = set()
        remaining = list(steps)

        while remaining:
            # Find all steps whose dependencies are resolved
            current_phase = []
            still_remaining = []

            for step in remaining:
                deps_met = all(dep in resolved for dep in step.depends_on)
                if deps_met:
                    current_phase.append(step)
                else:
                    still_remaining.append(step)

            if not current_phase:
                # Circular dependency or unresolvable — force remaining into one phase
                logger.warning(f"Unresolvable dependencies: {[s.space for s in still_remaining]}")
                phases.append(still_remaining)
                break

            phases.append(current_phase)
            resolved.update(step.space for step in current_phase)
            remaining = still_remaining

        return phases

    def _inject_context(
        self, payload: dict, step: ExecutionStep, prior_results: Dict[str, Any]
    ) -> dict:
        """Enrich payload with results from dependent spaces."""
        enriched = {**payload}

        for dep_space in step.depends_on:
            dep_result = prior_results.get(dep_space)
            if not dep_result or not isinstance(dep_result, dict):
                continue

            # Copy requested fields
            for field_name in step.context_fields:
                if field_name in dep_result:
                    enriched[f"from_{dep_space}_{field_name}"] = dep_result[field_name]

            # Add summary as LLM context
            summary = dep_result.get("summary", dep_result.get("message", ""))
            if summary:
                enriched["prior_context"] = f"Ergebnis aus {dep_space}: {summary}"

        return enriched

    def _merge_results(self, results: Dict[str, Any]) -> dict:
        """Combine results from all spaces into a single response."""
        spaces = [k for k in results.keys() if not k.startswith("_")]
        success = all(
            isinstance(r, dict) and r.get("success", False)
            for r in results.values()
            if isinstance(r, dict) and not isinstance(r, bool)
        )

        messages = []
        for space, result in results.items():
            if space.startswith("_"):
                continue
            if isinstance(result, dict):
                msg = result.get("message", result.get("summary", ""))
                if msg:
                    messages.append(f"[{space}] {msg}")

        return {
            "success": success,
            "multi_space": True,
            "spaces": spaces,
            "results": results,
            "message": " | ".join(messages) if messages else "Multi-space execution complete",
            "timed_out": results.get("_timeout", False),
        }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd python && python tests/test_hybrid_router.py`
Expected: All tests pass

- [ ] **Step 5: Update __init__.py**

Add to `python/swarm/routing/__init__.py`:

```python
from .multi_space_executor import MultiSpaceExecutor
```

- [ ] **Step 6: Commit**

```bash
git add python/swarm/routing/multi_space_executor.py python/swarm/routing/__init__.py python/tests/test_hybrid_router.py
git commit -m "feat(routing): add MultiSpaceExecutor with pipeline/parallel/mixed strategies"
```

---

## Task 6: Integration — IntentOrchestrator + MinibookHub

**Files:**
- Modify: `python/swarm/orchestrator/intent_orchestrator.py` (lines ~1233-1263)
- Modify: `python/spaces/minibook/minibook_hub.py`
- Modify: `python/spaces/minibook/enrichment/space_router.py`
- Modify: `python/swarm/orchestrator/reference_resolver.py`

This is the critical integration task. Read the files first, then make targeted changes.

- [ ] **Step 1: Read current process_intent MinibookHub block**

Read: `python/swarm/orchestrator/intent_orchestrator.py` lines 1220-1270

- [ ] **Step 2: Add HybridRouter initialization to IntentOrchestrator**

In `IntentOrchestrator.__init__()` (around line 449), add:

```python
# HybridRouter (Phase 0)
self._hybrid_router = None
if os.getenv("USE_HYBRID_ROUTER", "true").lower() == "true":
    try:
        from swarm.routing.hybrid_router import HybridRouter
        self._hybrid_router = HybridRouter()
        logger.info("HybridRouter enabled")
    except Exception as e:
        logger.warning(f"HybridRouter init failed, using MinibookHub only: {e}")
```

- [ ] **Step 3: Replace MinibookHub exclusive block with HybridRouter Phase 0**

Replace the exclusive MinibookHub block (lines ~1233-1263) with:

```python
# ── PHASE 0: HybridRouter (deterministic fast-path) ──
if self._hybrid_router and not domain_hint:
    try:
        route_result = await self._hybrid_router.resolve(
            event_type=event_type or "",
            user_input=intent_text,
            current_space=getattr(self, '_current_space', None),
        )

        if route_result.tier <= 4 and route_result.multi_space is None:
            # Single-space, deterministic → direct execute (skip MinibookHub)
            logger.info(
                f"HybridRouter Tier {route_result.tier}: "
                f"{route_result.event_type} → {route_result.space} "
                f"({route_result.matched_by})"
            )
            # Use existing _tool_executors for direct execution
            tool_name = route_result.event_type
            if tool_name in self._tool_executors:
                tool_fn = self._tool_executors[tool_name]
                try:
                    result = tool_fn(**tool_params) if tool_params else tool_fn()
                    if asyncio.iscoroutine(result):
                        result = await result
                    return self._format_result(event_type, result, route_result)
                except Exception as e:
                    logger.error(f"Direct execution failed: {e}")
                    # Fall through to MinibookHub

        elif route_result.tier == 5 and route_result.multi_space:
            # Multi-space → delegate to MinibookHub with MultiSpaceExecutor
            if self._minibook_hub:
                hub_result = await self._minibook_hub.dispatch(intent_text, context)
                if hub_result and getattr(hub_result, "success", False):
                    return hub_result
    except Exception as e:
        logger.warning(f"HybridRouter phase failed: {e}, falling through to MinibookHub")

# ── PHASE 0.5: MinibookHub fallback (when HybridRouter didn't resolve) ──
if self._minibook_hub and not domain_hint:
    try:
        hub_result = await self._minibook_hub.dispatch(intent_text, context)
        if hub_result and hub_result.get("success"):
            return hub_result
    except Exception as e:
        logger.warning(f"MinibookHub fallback failed: {e}")
```

- [ ] **Step 4: Add _format_result helper to IntentOrchestrator**

```python
def _format_result(self, event_type: str, tool_result: Any, route: "RouteResult"):
    """Format tool execution result as OrchestrationResult-compatible object."""
    # Reuse existing _make_result pattern from MinibookHub
    result = self._make_orchestration_result(
        event_type=event_type,
        success=tool_result.get("success", True) if isinstance(tool_result, dict) else True,
        response_hint=tool_result.get("message", "") if isinstance(tool_result, dict) else str(tool_result),
        stream=route.agent,
    )
    # Attach routing metadata for debugging
    if hasattr(result, '__dict__'):
        result._route = {"matched_by": route.matched_by, "tier": route.tier, "space": route.space}
    return result
```

- [ ] **Step 5: Add USE_HYBRID_ROUTER to config loading**

In `python/config.py`, no changes needed — env vars are read directly via `os.getenv()` in HybridRouter. But add to `.env.example`:

```bash
# HybridRouter
USE_HYBRID_ROUTER=true
HYBRID_ROUTER_CACHE_TTL=300
HYBRID_ROUTER_CACHE_MAX=2000
HYBRID_ROUTER_SESSION_SCOPE=main
HYBRID_ROUTER_DEBUG=false
```

- [ ] **Step 6: Deprecate SpaceRouter._route_by_event_type()**

In `python/spaces/minibook/enrichment/space_router.py`, add deprecation warning to `_route_by_event_type()` (line ~137):

```python
async def _route_by_event_type(self, event_type: str) -> Optional[RoutingDecision]:
    """DEPRECATED: This logic has moved to HybridRouter Tier 1. Kept for fallback."""
    import warnings
    warnings.warn(
        "_route_by_event_type is deprecated, use HybridRouter Tier 1",
        DeprecationWarning, stacklevel=2,
    )
    # ... existing code unchanged ...
```

- [ ] **Step 7: Wire MultiSpaceExecutor into MinibookHub**

In `python/spaces/minibook/minibook_hub.py`, modify the `dispatch()` method (around line 164-188) to use MultiSpaceExecutor for pipeline/mixed strategies instead of `ResultAggregator.track_multi()`:

```python
# In MinibookHub.__init__(), add:
from swarm.routing.multi_space_executor import MultiSpaceExecutor
self._multi_executor = MultiSpaceExecutor(space_executor=self._execute_single_space)

# In dispatch(), replace the multi-space block (lines ~164-188):
if routing.is_multi_space and routing.secondary_spaces:
    # Use MultiSpaceExecutor for dependency-aware phasing
    from swarm.routing.types import MultiSpaceStrategy, ExecutionStep
    strategy = MultiSpaceStrategy(
        strategy="parallel",  # Default; LLM dependency detection upgrades to pipeline/mixed
        steps=[ExecutionStep(space=routing.primary_space)]
        + [ExecutionStep(space=s) for s in routing.secondary_spaces],
    )
    multi_result = await self._multi_executor.execute(strategy, enriched_payload)
    return self._make_result(
        event_type=pipeline_result.event_type,
        success=multi_result.get("success", False),
        response_hint=multi_result.get("message", ""),
    )
```

Add the helper method for single-space execution:

```python
async def _execute_single_space(self, space: str, payload: dict) -> dict:
    """Execute a single space via the existing tool orchestrator."""
    if self._fallback_executor:
        result = await self._fallback_executor(payload.get("event_type", ""), payload)
        return result if isinstance(result, dict) else {"success": True, "message": str(result)}
    return {"success": False, "error": f"No executor for space {space}"}
```

- [ ] **Step 8: Test full integration manually**

Run: `cd python && python tests/test_hybrid_router.py`
Then: `cd python && python tests/test_intent_to_tool.py` (existing tests still pass)

- [ ] **Step 9: Commit**

```bash
git add python/swarm/orchestrator/intent_orchestrator.py python/spaces/minibook/enrichment/space_router.py python/spaces/minibook/minibook_hub.py python/config.py .env.example
git commit -m "feat(routing): integrate HybridRouter as Phase 0 in IntentOrchestrator"
```

---

## Task 7: DroPE + Session Integration

**Files:**
- Modify: `python/swarm/orchestrator/reference_resolver.py`
- Modify: `python/swarm/orchestrator/intent_orchestrator.py` (session lifecycle)

- [ ] **Step 1: Add SessionStore to reference_resolver.py**

In `DroPEReferenceResolver`, add session-aware `last_route` lookup. Read the file first (lines 153-197 `resolve()` method), then add:

```python
async def resolve(self, utterance: str, conversation_history: list = None,
                  session_store=None, session_key=None) -> str:
    """Resolve ambiguous references using context + session last_route."""
    if not self.needs_resolution(utterance):
        return utterance

    # Try session last_route for "nochmal" / "wieder" references
    if session_store and session_key:
        try:
            entry = session_store.get_or_create(session_key)
            if entry.last_route and any(w in utterance.lower() for w in ["nochmal", "wieder"]):
                return f"Wiederhole: {entry.last_route.event_type}"
        except Exception as e:
            logger.debug(f"Session last_route lookup failed: {e}")

    # ... existing inference code ...
```

- [ ] **Step 2: Add session lifecycle to process_intent**

In `IntentOrchestrator.process_intent()`, add session create/update around the HybridRouter block:

```python
# Session lifecycle (if HybridRouter active)
session_key = None
if self._hybrid_router:
    from swarm.routing.session_store import SessionStore
    from swarm.routing.types import SessionKey
    store = SessionStore()
    session_key = SessionKey(
        agent_id="orchestrator", channel=context.get("channel", "voice"),
        peer_id=context.get("user_id", "anonymous"),
    )
    session = store.get_or_create(session_key)

# ... after successful execution ...
if session_key and route_result:
    store.update_last_route(session_key, route_result)
    store.append_history(session_key, "user", intent_text, event_type)
```

- [ ] **Step 3: Run all tests**

Run: `cd python && python tests/test_hybrid_router.py`
Run: `cd python && python tests/test_intent_to_tool.py`
Expected: All pass

- [ ] **Step 4: Commit**

```bash
git add python/swarm/orchestrator/reference_resolver.py python/swarm/orchestrator/intent_orchestrator.py
git commit -m "feat(routing): integrate sessions with DroPE resolver and orchestrator lifecycle"
```

---

## Task 8: Final Integration Test + Cleanup

**Files:**
- Modify: `python/tests/test_hybrid_router.py` (add integration test)

- [ ] **Step 1: Add end-to-end routing test**

```python
def test_e2e_routing_flow():
    """Full flow: event_type → HybridRouter → RouteResult → session update."""
    import tempfile
    from swarm.routing.hybrid_router import HybridRouter
    from swarm.routing.session_store import SessionStore
    from swarm.routing.types import SessionKey

    router = HybridRouter(use_llm=False)  # No LLM for unit test

    # 1. Tier 1: Known event
    result = router.resolve_sync("bubble.create", "Erstelle Bubble Marketing")
    assert result.tier == 1
    assert result.space == "ideas"

    # 2. Tier 2: Keyword match
    result = router.resolve_sync("unknown.action", "Mach Screenshot")
    assert result.tier == 2
    assert result.space == "desktop"

    # 3. Session update
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    store = SessionStore(db_path=db_path)
    key = SessionKey(agent_id="ideas", channel="voice", peer_id="test_user")
    store.get_or_create(key)
    store.update_last_route(key, result)
    entry = store.get_or_create(key)
    assert entry.last_route is not None

    print("E2E routing flow test passed!")
```

- [ ] **Step 2: Run full test suite**

Run: `cd python && python tests/test_hybrid_router.py`
Expected: "All tests passed!" including E2E

- [ ] **Step 3: Run existing tests to verify no regressions**

Run: `cd python && python tests/test_intent_to_tool.py`
Run: `cd python && python tests/test_data_layer.py`
Expected: All existing tests still pass

- [ ] **Step 4: Final commit**

```bash
git add python/tests/test_hybrid_router.py
git commit -m "test(routing): add end-to-end HybridRouter integration test"
```
