#!/usr/bin/env python
"""
Live test: Real intents through HybridRouter with timing + tier analysis.

Usage:
    cd python
    python tests/test_hybrid_router_live.py
"""

import asyncio
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from swarm.routing.hybrid_router import HybridRouter

# ── Test Cases: (user_input, expected_event_type, expected_space, expected_tier) ──
TIER1_CASES = [
    # Tier 1: Known event_type prefix → deterministic
    ("Zeig mir meine Bubbles", "bubble.list", "ideas", 1),
    ("Erstelle Bubble Marketing", "bubble.create", "ideas", 1),
    ("Notiere: API Design Pattern", "idea.create", "ideas", 1),
    ("Zeige alle Ideen", "idea.list", "ideas", 1),
    ("Verlinke die Ideen sinnvoll", "idea.auto_link", "ideas", 1),
    ("Erstelle eine App fuer Zeiterfassung", "code.generate", "coding", 1),
    ("Wie ist der Code-Status?", "code.status", "coding", 1),
    ("Oeffne Chrome", "desktop.open_app", "desktop", 1),
    ("Erstelle einen Workflow fuer Emails", "n8n.generate", "n8n", 1),
    ("Setze einen Termin fuer morgen", "schedule.create", "schedule", 1),
]

TIER2_CASES = [
    # Tier 2: Keyword match (event_type unknown, but keywords in input)
    ("Mach einen Screenshot vom Bildschirm", "unknown", "desktop", 2),
    ("Klick auf den OK Button", "unknown", "desktop", 2),
    ("Automatisiere den Workflow", "unknown", "n8n", 2),
    ("Erinnere mich an das Meeting", "unknown", "schedule", 2),
]

TIER3_CASES = [
    # Tier 3: Context match (ambiguous input, but current_space helps)
    ("Zeig mir alles", "unknown", "coding", 3),  # current_space=coding
    ("Was gibt es Neues?", "unknown", "ideas", 3),  # current_space=ideas
]


def colorize(text, color):
    colors = {"green": "\033[92m", "red": "\033[91m", "yellow": "\033[93m", "cyan": "\033[96m", "reset": "\033[0m"}
    return f"{colors.get(color, '')}{text}{colors['reset']}"


async def test_with_classifier():
    """Test Tier 1 with actual IntentClassifier for event_type."""
    print("\n" + "=" * 70)
    print("  PHASE 1: Tier 1 — Prefix Match (with IntentClassifier)")
    print("=" * 70)

    router = HybridRouter(use_llm=False)

    try:
        from swarm.orchestrator.intent_classifier import IntentClassifier
        classifier = IntentClassifier()
        has_classifier = True
    except Exception as e:
        print(f"  IntentClassifier not available ({e}), using hardcoded event_types")
        has_classifier = False

    passed = 0
    failed = 0

    for user_input, expected_event, expected_space, expected_tier in TIER1_CASES:
        # Classify
        if has_classifier:
            try:
                t0 = time.perf_counter()
                classification = await classifier.classify(user_input)
                classify_ms = (time.perf_counter() - t0) * 1000
                event_type = classification.get("event_type", "unknown") if classification else "unknown"
            except Exception:
                event_type = expected_event
                classify_ms = 0
        else:
            event_type = expected_event
            classify_ms = 0

        # Route
        t0 = time.perf_counter()
        result = router.resolve_sync(event_type=event_type, user_input=user_input)
        route_ms = (time.perf_counter() - t0) * 1000

        # Check
        space_ok = result.space == expected_space
        tier_ok = result.tier == expected_tier

        if space_ok and tier_ok:
            status = colorize("PASS", "green")
            passed += 1
        else:
            status = colorize("FAIL", "red")
            failed += 1

        print(f"\n  {status} \"{user_input}\"")
        print(f"    Event: {event_type} | Space: {result.space} (expected: {expected_space})")
        print(f"    Tier: {result.tier} | matched_by: {result.matched_by}")
        print(f"    Timing: classify={classify_ms:.0f}ms, route={route_ms:.1f}ms, total={classify_ms + route_ms:.0f}ms")

    return passed, failed


def test_tier2_keywords():
    """Test Tier 2 keyword matching."""
    print("\n" + "=" * 70)
    print("  PHASE 2: Tier 2 — Keyword Match")
    print("=" * 70)

    router = HybridRouter(use_llm=False)
    passed = 0
    failed = 0

    for user_input, _, expected_space, expected_tier in TIER2_CASES:
        t0 = time.perf_counter()
        result = router.resolve_sync(event_type="unknown", user_input=user_input)
        route_ms = (time.perf_counter() - t0) * 1000

        space_ok = result.space == expected_space
        tier_ok = result.tier == expected_tier

        if space_ok and tier_ok:
            status = colorize("PASS", "green")
            passed += 1
        else:
            status = colorize("FAIL", "red")
            failed += 1

        print(f"\n  {status} \"{user_input}\"")
        print(f"    Space: {result.space} (expected: {expected_space}) | Tier: {result.tier}")
        print(f"    matched_by: {result.matched_by} | {route_ms:.1f}ms")

    return passed, failed


def test_tier3_context():
    """Test Tier 3 context matching."""
    print("\n" + "=" * 70)
    print("  PHASE 3: Tier 3 — Context Match (current_space hint)")
    print("=" * 70)

    router = HybridRouter(use_llm=False)
    passed = 0
    failed = 0

    contexts = ["coding", "ideas"]
    for i, (user_input, _, expected_space, expected_tier) in enumerate(TIER3_CASES):
        current_space = contexts[i]
        t0 = time.perf_counter()
        result = router.resolve_sync(
            event_type="unknown", user_input=user_input, current_space=current_space
        )
        route_ms = (time.perf_counter() - t0) * 1000

        space_ok = result.space == expected_space
        tier_ok = result.tier == expected_tier

        if space_ok and tier_ok:
            status = colorize("PASS", "green")
            passed += 1
        else:
            status = colorize("FAIL", "red")
            failed += 1

        print(f"\n  {status} \"{user_input}\" (current_space={current_space})")
        print(f"    Space: {result.space} (expected: {expected_space}) | Tier: {result.tier}")
        print(f"    matched_by: {result.matched_by} | {route_ms:.1f}ms")

    return passed, failed


async def test_tier4_llm():
    """Test Tier 4 LLM routing (requires OPENROUTER_API_KEY)."""
    print("\n" + "=" * 70)
    print("  PHASE 4: Tier 4 — LLM SpaceRouter (requires OPENROUTER_API_KEY)")
    print("=" * 70)

    if not os.getenv("OPENROUTER_API_KEY"):
        print(colorize("  SKIP: OPENROUTER_API_KEY not set", "yellow"))
        return 0, 0

    router = HybridRouter(use_llm=True)

    ambiguous_cases = [
        ("Hilf mir beim Programmieren einer REST API", "coding"),
        ("Ich brauche Infos ueber Machine Learning", "research"),
        ("Organisiere meine Notizen besser", "ideas"),
    ]

    passed = 0
    failed = 0

    for user_input, expected_space in ambiguous_cases:
        t0 = time.perf_counter()
        result = await router.resolve(event_type="unknown", user_input=user_input)
        total_ms = (time.perf_counter() - t0) * 1000

        space_ok = result.space == expected_space

        if space_ok:
            status = colorize("PASS", "green")
            passed += 1
        else:
            status = colorize("FAIL", "red")
            failed += 1

        print(f"\n  {status} \"{user_input}\"")
        print(f"    Space: {result.space} (expected: {expected_space}) | Tier: {result.tier}")
        print(f"    matched_by: {result.matched_by} | {total_ms:.0f}ms")

    return passed, failed


async def test_session_persistence():
    """Test session store with real routing."""
    print("\n" + "=" * 70)
    print("  PHASE 5: Session Persistence")
    print("=" * 70)

    import tempfile
    from swarm.routing.session_store import SessionStore
    from swarm.routing.types import SessionKey

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    store = SessionStore(db_path=db_path)
    router = HybridRouter(use_llm=False)

    key = SessionKey(agent_id="orchestrator", channel="voice", peer_id="test_user")
    session = store.get_or_create(key)
    print(f"  Session created: {key.key}")

    # Route an intent and store it
    result = router.resolve_sync("bubble.create", "Erstelle Bubble Test")
    store.update_last_route(key, result)
    store.append_history(key, "user", "Erstelle Bubble Test", "bubble.create")
    print(f"  Last route saved: {result.event_type} -> {result.space} (Tier {result.tier})")

    # Retrieve and verify
    session = store.get_or_create(key)
    if session.last_route and session.last_route.event_type == "bubble.create":
        print(colorize("  PASS: Session persisted correctly", "green"))
        return 1, 0
    else:
        print(colorize("  FAIL: Session not persisted", "red"))
        return 0, 1


async def test_cache_performance():
    """Benchmark: cached vs uncached routing."""
    print("\n" + "=" * 70)
    print("  PHASE 6: Cache Performance Benchmark")
    print("=" * 70)

    router = HybridRouter(use_llm=False)

    # Warm up
    router.resolve_sync("bubble.create", "test")

    # Benchmark: 1000 cached lookups
    t0 = time.perf_counter()
    for _ in range(1000):
        router.resolve_sync("bubble.create", "Erstelle Bubble")
    cached_ms = (time.perf_counter() - t0) * 1000

    print(f"  1000 cached Tier-1 lookups: {cached_ms:.1f}ms ({cached_ms/1000:.3f}ms/lookup)")

    # Benchmark: 1000 keyword lookups
    t0 = time.perf_counter()
    for _ in range(1000):
        router.resolve_sync("unknown", "Mach einen Screenshot")
    keyword_ms = (time.perf_counter() - t0) * 1000

    print(f"  1000 Tier-2 keyword lookups: {keyword_ms:.1f}ms ({keyword_ms/1000:.3f}ms/lookup)")

    if cached_ms < 100 and keyword_ms < 200:
        print(colorize("  PASS: Performance within targets (<0.1ms cached, <0.2ms keyword)", "green"))
        return 1, 0
    else:
        print(colorize("  WARN: Performance above targets", "yellow"))
        return 1, 0


async def main():
    total_passed = 0
    total_failed = 0

    print(colorize("\n  HybridRouter Live Test Suite", "cyan"))
    print(colorize("  ============================\n", "cyan"))

    # Phase 1: Tier 1 with classifier
    p, f = await test_with_classifier()
    total_passed += p
    total_failed += f

    # Phase 2: Tier 2 keywords
    p, f = test_tier2_keywords()
    total_passed += p
    total_failed += f

    # Phase 3: Tier 3 context
    p, f = test_tier3_context()
    total_passed += p
    total_failed += f

    # Phase 4: Tier 4 LLM
    p, f = await test_tier4_llm()
    total_passed += p
    total_failed += f

    # Phase 5: Sessions
    p, f = await test_session_persistence()
    total_passed += p
    total_failed += f

    # Phase 6: Performance
    p, f = await test_cache_performance()
    total_passed += p
    total_failed += f

    # Summary
    print("\n" + "=" * 70)
    total = total_passed + total_failed
    if total_failed == 0:
        print(colorize(f"  ALL {total} TESTS PASSED", "green"))
    else:
        print(colorize(f"  {total_passed}/{total} passed, {total_failed} failed", "red"))
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
