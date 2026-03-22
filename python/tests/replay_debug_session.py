#!/usr/bin/env python
"""
Replay Debug Sessions: Reads JSONL intent logs and replays them through HybridRouter.

Usage:
    # Replay today's session
    cd python
    python tests/replay_debug_session.py

    # Replay a specific date
    python tests/replay_debug_session.py --date 2026-03-22

    # Replay and compare (shows regressions)
    python tests/replay_debug_session.py --compare

    # Generate test fixtures from session
    python tests/replay_debug_session.py --export-fixtures

    # Replay with Ollama classifier (full E2E)
    python tests/replay_debug_session.py --with-classifier --model qwen2.5:3b
"""

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from swarm.routing.hybrid_router import HybridRouter
from swarm.routing.types import RouteResult


def colorize(text, color):
    colors = {
        "green": "\033[92m", "red": "\033[91m", "yellow": "\033[93m",
        "cyan": "\033[96m", "dim": "\033[90m", "bold": "\033[1m",
        "reset": "\033[0m"
    }
    return f"{colors.get(color, '')}{text}{colors['reset']}"


def load_session(log_dir: str, date: str = None) -> list:
    """Load JSONL intent log entries for a given date."""
    log_path = Path(log_dir)
    if date:
        target = log_path / f"intents_{date}.jsonl"
    else:
        # Find most recent log file
        files = sorted(log_path.glob("intents_*.jsonl"), reverse=True)
        if not files:
            print(colorize("  No intent logs found in logs/intents/", "red"))
            return []
        target = files[0]

    if not target.exists():
        print(colorize(f"  Log file not found: {target}", "red"))
        return []

    entries = []
    with open(target, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    print(f"  Loaded {len(entries)} intents from {target.name}")
    return entries


def replay_through_router(entries: list, router: HybridRouter) -> list:
    """Replay all entries through HybridRouter and return results."""
    results = []
    for entry in entries:
        user_input = entry.get("user_input", "")
        event_type = entry.get("classification", {}).get("event_type", "unknown")

        if not user_input or not event_type:
            continue

        t0 = time.perf_counter()
        route = router.resolve_sync(event_type=event_type, user_input=user_input)
        route_ms = (time.perf_counter() - t0) * 1000

        original_routing = entry.get("routing", {})

        results.append({
            "user_input": user_input,
            "event_type": event_type,
            "original": {
                "space": original_routing.get("space"),
                "tier": original_routing.get("tier"),
                "matched_by": original_routing.get("matched_by"),
            },
            "replayed": {
                "space": route.space,
                "tier": route.tier,
                "matched_by": route.matched_by,
                "route_ms": round(route_ms, 3),
            },
            "match": original_routing.get("space") == route.space if original_routing.get("space") else None,
            "timestamp": entry.get("timestamp"),
        })

    return results


async def replay_with_classifier(entries: list, router: HybridRouter, model: str) -> list:
    """Full E2E replay: re-classify with Ollama + route through HybridRouter."""
    try:
        from swarm.routing.keyword_classifier import KeywordClassifier
    except ImportError:
        print(colorize("  KeywordClassifier not available", "red"))
        return []

    # Try Ollama
    use_ollama = False
    try:
        from swarm.ollama_client import OllamaClient
        client = OllamaClient(model=model)
        use_ollama = True
        print(f"  Using Ollama model: {model}")
    except Exception:
        print(colorize(f"  Ollama not available, using KeywordClassifier only", "yellow"))
        kw_classifier = KeywordClassifier()

    results = []
    for i, entry in enumerate(entries):
        user_input = entry.get("user_input", "")
        original_event = entry.get("classification", {}).get("event_type", "unknown")

        if not user_input:
            continue

        # Re-classify
        t0 = time.perf_counter()
        if use_ollama:
            try:
                from swarm.orchestrator.intent_classifier import IntentClassifier
                classifier = IntentClassifier()
                classification = await classifier.classify(user_input)
                new_event = classification.get("event_type", "unknown") if classification else "unknown"
            except Exception as e:
                new_event = "error"
        else:
            new_event = kw_classifier.classify(user_input)

        classify_ms = (time.perf_counter() - t0) * 1000

        # Route
        t0 = time.perf_counter()
        route = router.resolve_sync(event_type=new_event, user_input=user_input)
        route_ms = (time.perf_counter() - t0) * 1000

        results.append({
            "user_input": user_input,
            "original_event": original_event,
            "reclassified_event": new_event,
            "event_match": original_event == new_event,
            "space": route.space,
            "tier": route.tier,
            "matched_by": route.matched_by,
            "classify_ms": round(classify_ms, 1),
            "route_ms": round(route_ms, 3),
        })

        # Progress
        print(f"  [{i+1}/{len(entries)}] {user_input[:40]}... → {new_event} → {route.space} (T{route.tier})")

    return results


def print_results(results: list, compare: bool = False):
    """Pretty-print replay results."""
    print(f"\n{'='*70}")
    print(f"  Replay Results: {len(results)} intents")
    print(f"{'='*70}\n")

    tier_counts = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    regressions = []
    total_ms = 0

    for r in results:
        tier = r["replayed"]["tier"]
        tier_counts[tier] = tier_counts.get(tier, 0) + 1
        total_ms += r["replayed"]["route_ms"]

        if compare and r["match"] is False:
            regressions.append(r)

        # Print each entry
        tier_label = f"T{tier}" if tier > 0 else "T0(default)"
        ms = r["replayed"]["route_ms"]
        space = r["replayed"]["space"]
        matched = r["replayed"]["matched_by"]

        print(f"  {colorize(tier_label, 'cyan'):>12}  {space:<12} {ms:>7.3f}ms  {r['event_type']:<25} {colorize(r['user_input'][:45], 'dim')}")

    # Summary
    print(f"\n{'─'*70}")
    print(f"  Tier Distribution:")
    for tier in sorted(tier_counts.keys()):
        count = tier_counts[tier]
        if count > 0:
            pct = count / len(results) * 100
            bar = "█" * int(pct / 2)
            print(f"    Tier {tier}: {count:>3} ({pct:>5.1f}%) {bar}")

    avg_ms = total_ms / len(results) if results else 0
    print(f"\n  Avg route time: {avg_ms:.3f}ms")
    print(f"  Total intents:  {len(results)}")

    if compare and regressions:
        print(f"\n  {colorize(f'⚠ {len(regressions)} REGRESSIONS:', 'red')}")
        for r in regressions:
            print(f"    {r['user_input'][:50]}")
            print(f"      Original: {r['original']['space']} (T{r['original']['tier']})")
            print(f"      Replayed: {r['replayed']['space']} (T{r['replayed']['tier']})")
    elif compare:
        print(colorize(f"\n  ✓ No regressions detected", "green"))


def export_fixtures(results: list, output_path: str = "tests/fixtures/intent_regression.json"):
    """Export replay results as test fixtures for automated regression testing."""
    fixtures = []
    for r in results:
        fixtures.append({
            "user_input": r["user_input"],
            "event_type": r["event_type"],
            "expected_space": r["replayed"]["space"],
            "expected_tier": r["replayed"]["tier"],
        })

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(fixtures, f, ensure_ascii=False, indent=2)

    print(colorize(f"\n  Exported {len(fixtures)} fixtures to {output_path}", "green"))
    print(f"  Use with: python -m pytest tests/test_hybrid_router_regression.py")


async def main():
    parser = argparse.ArgumentParser(description="Replay debug sessions through HybridRouter")
    parser.add_argument("--date", help="Date to replay (YYYY-MM-DD), default: most recent")
    parser.add_argument("--log-dir", default="logs/intents", help="Intent log directory")
    parser.add_argument("--compare", action="store_true", help="Compare with original routing")
    parser.add_argument("--export-fixtures", action="store_true", help="Export as test fixtures")
    parser.add_argument("--with-classifier", action="store_true", help="Re-classify with Ollama")
    parser.add_argument("--model", default="qwen2.5:3b", help="Ollama model for re-classification")
    args = parser.parse_args()

    print(colorize("\n  HybridRouter Session Replay", "bold"))
    print(colorize("  ===========================\n", "bold"))

    # Load session
    entries = load_session(args.log_dir, args.date)
    if not entries:
        return

    # Init router
    router = HybridRouter(use_llm=False)

    if args.with_classifier:
        results = await replay_with_classifier(entries, router, args.model)
        # Simple output for E2E
        for r in results:
            status = colorize("✓", "green") if r["event_match"] else colorize("✗", "red")
            print(f"  {status} {r['user_input'][:40]:<40} {r['original_event']:<25} → {r['reclassified_event']:<25} → {r['space']}")
    else:
        results = replay_through_router(entries, router)
        print_results(results, compare=args.compare)

    if args.export_fixtures and results:
        export_fixtures(results)


if __name__ == "__main__":
    asyncio.run(main())
