"""Tests for HybridRouter components."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from swarm.routing.types import SpaceBinding, RouteResult, SessionKey
from swarm.routing.bindings_registry import (
    _get_static_fallback, match_keyword, KEYWORD_BINDINGS,
)


# === Task 1: Types + Bindings ===

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
    assert len(bindings) >= 12


def test_prefix_binding_format():
    """Each prefix must end with a dot."""
    bindings = _get_static_fallback()
    for prefix in bindings.keys():
        assert prefix.endswith("."), f"Prefix {prefix} must end with '.'"


def test_keyword_match_desktop():
    result = match_keyword("Mach einen Screenshot")
    assert result is not None
    assert result.space == "desktop"


def test_keyword_match_schedule():
    result = match_keyword("Erstelle einen Termin")
    assert result is not None
    assert result.space == "schedule"


def test_keyword_match_n8n():
    result = match_keyword("Erstelle einen Workflow")
    assert result is not None
    assert result.space == "n8n"


def test_keyword_no_match():
    result = match_keyword("Hallo wie geht es dir")
    assert result is None


def test_session_key_format():
    key = SessionKey(agent_id="ideas", channel="voice", peer_id="felix")
    assert key.key == "agent:ideas:voice:direct:felix"
    assert key.main_key == "agent:ideas:main"


def test_session_key_with_thread():
    key = SessionKey(agent_id="ideas", channel="voice", peer_id="felix", thread_id="t123")
    assert key.key == "agent:ideas:voice:direct:felix:thread:t123"


def test_route_result_matched_by():
    result = RouteResult(
        space="ideas", agent="BubblesAgent", event_type="bubble.create",
        matched_by="binding.prefix:bubble.*", cached=True, tier=1,
    )
    assert result.matched_by == "binding.prefix:bubble.*"
    assert result.tier == 1
    assert result.cached is True


# === Task 2: Route Cache ===

import time
from swarm.routing.route_cache import EventTypeCache, ClassificationCache


def test_event_type_cache_hit():
    cache = EventTypeCache()
    binding = SpaceBinding(space="ideas", agent="BubblesAgent")
    cache.put("bubble.create", binding)
    assert cache.get("bubble.create") == binding


def test_event_type_cache_miss():
    cache = EventTypeCache()
    assert cache.get("unknown.event") is None


def test_classification_cache_ttl():
    cache = ClassificationCache(ttl_seconds=1, max_entries=100)
    cache.put("test input", {"event_type": "bubble.create", "space": "ideas"})
    assert cache.get("test input") is not None
    time.sleep(1.1)
    assert cache.get("test input") is None


def test_classification_cache_overflow():
    cache = ClassificationCache(ttl_seconds=300, max_entries=3)
    for i in range(4):
        cache.put(f"input_{i}", {"event_type": f"event.{i}"})
    assert cache.get("input_0") is None
    assert cache.get("input_3") is not None


# === Task 4: Session Store + Identity Links ===

import tempfile
from swarm.routing.session_store import SessionStore
from swarm.routing.identity_links import IdentityLinkResolver


def test_session_store_create_and_get():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    store = SessionStore(db_path=db_path)
    key = SessionKey(agent_id="ideas", channel="voice", peer_id="felix")
    entry = store.get_or_create(key)
    assert entry.agent_id == "ideas"
    assert entry.channel == "voice"


def test_session_store_last_route():
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
    resolver = IdentityLinkResolver()
    resolver.add_link("voice", "user_voice_123", "canonical:felix")
    resolver.add_link("chat", "dashboard_user", "canonical:felix")
    assert resolver.resolve("voice", "user_voice_123") == "canonical:felix"
    assert resolver.resolve("chat", "dashboard_user") == "canonical:felix"
    assert resolver.resolve("voice", "unknown") == "unknown"


# === Task 5: MultiSpaceExecutor ===

from swarm.routing.multi_space_executor import MultiSpaceExecutor
from swarm.routing.types import MultiSpaceStrategy, ExecutionStep


def test_build_phases_parallel():
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
    executor = MultiSpaceExecutor()
    step = ExecutionStep(space="ideas", depends_on=["research"], context_fields=["findings"])
    prior = {"research": {"findings": ["trend1", "trend2"], "summary": "2 trends found"}}
    payload = {"title": "KI"}
    enriched = executor._inject_context(payload, step, prior)
    assert enriched["from_research_findings"] == ["trend1", "trend2"]
    assert "prior_context" in enriched
    assert enriched["title"] == "KI"


# === Task 3: HybridRouter Core ===

import asyncio
from unittest.mock import AsyncMock, MagicMock
from swarm.routing.hybrid_router import HybridRouter


def test_tier1_prefix_match():
    router = HybridRouter(use_llm=False)
    result = router.resolve_sync(event_type="bubble.create", user_input="Erstelle Bubble")
    assert result.space == "ideas"
    assert result.tier == 1
    assert "binding.prefix" in result.matched_by


def test_tier1_cached_on_second_call():
    router = HybridRouter(use_llm=False)
    r1 = router.resolve_sync(event_type="bubble.create", user_input="x")
    r2 = router.resolve_sync(event_type="bubble.create", user_input="x")
    assert r2.cached is True


def test_tier2_keyword_match():
    router = HybridRouter(use_llm=False)
    result = router.resolve_sync(event_type="unknown.action", user_input="Mach einen Screenshot")
    assert result.space == "desktop"
    assert result.tier == 2
    assert "binding.keyword" in result.matched_by


def test_tier3_context_match():
    router = HybridRouter(use_llm=False)
    result = router.resolve_sync(
        event_type="unknown.action",
        user_input="Zeig mir alles",
        current_space="coding",
    )
    assert result.space == "coding"
    assert result.tier == 3
    assert "binding.context" in result.matched_by


def test_all_known_prefixes_resolve():
    router = HybridRouter(use_llm=False)
    test_events = [
        ("bubble.list", "ideas"), ("idea.create", "ideas"),
        ("code.generate", "coding"), ("desktop.screenshot", "desktop"),
        ("schedule.create", "schedule"), ("n8n.list", "n8n"),
        ("roarboot.query", "rowboat"), ("research.search", "research"),
    ]
    for event_type, expected_space in test_events:
        result = router.resolve_sync(event_type=event_type, user_input="test")
        assert result.space == expected_space, f"{event_type} -> {result.space}, expected {expected_space}"
        assert result.tier == 1


def test_tier4_llm_single_space():
    router = HybridRouter(use_llm=True)
    mock_decision = MagicMock()
    mock_decision.primary_space = "coding"
    mock_decision.secondary_spaces = []
    mock_decision.is_multi_space = False
    mock_decision.confidence = 0.8

    mock_router = AsyncMock()
    mock_router.route = AsyncMock(return_value=mock_decision)
    router._space_router = mock_router

    result = asyncio.get_event_loop().run_until_complete(
        router.resolve(event_type="unknown.action", user_input="Generiere Code fuer API")
    )
    assert result.space == "coding"
    assert result.tier == 4
    assert "binding.llm" in result.matched_by


def test_tier5_multi_space_detected():
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


# === Task 8: E2E Integration ===

def test_e2e_routing_flow():
    router = HybridRouter(use_llm=False)

    # Tier 1
    result = router.resolve_sync("bubble.create", "Erstelle Bubble Marketing")
    assert result.tier == 1 and result.space == "ideas"

    # Tier 2
    result = router.resolve_sync("unknown.action", "Mach Screenshot")
    assert result.tier == 2 and result.space == "desktop"

    # Session update
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    store = SessionStore(db_path=db_path)
    key = SessionKey(agent_id="ideas", channel="voice", peer_id="test_user")
    store.get_or_create(key)
    store.update_last_route(key, result)
    entry = store.get_or_create(key)
    assert entry.last_route is not None


if __name__ == "__main__":
    tests = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    for t in tests:
        t()
        print(f"  PASS: {t.__name__}")
    print(f"\nAll {len(tests)} tests passed!")
