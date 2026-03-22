#!/usr/bin/env python
"""
Regression test: Replays exported fixtures through HybridRouter.

Fixtures are generated from real debug sessions via:
    python tests/replay_debug_session.py --export-fixtures

Usage:
    cd python
    python tests/test_hybrid_router_regression.py
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from swarm.routing.hybrid_router import HybridRouter

FIXTURES_PATH = Path(__file__).parent / "fixtures" / "intent_regression.json"


def test_regression():
    if not FIXTURES_PATH.exists():
        print("  No fixtures found. Generate them first:")
        print("    python tests/replay_debug_session.py --export-fixtures")
        return

    with open(FIXTURES_PATH, "r", encoding="utf-8") as f:
        fixtures = json.load(f)

    router = HybridRouter(use_llm=False)
    passed = 0
    failed = 0

    for case in fixtures:
        result = router.resolve_sync(
            event_type=case["event_type"],
            user_input=case["user_input"],
        )

        space_ok = result.space == case["expected_space"]
        tier_ok = result.tier == case["expected_tier"]

        if space_ok and tier_ok:
            passed += 1
        else:
            failed += 1
            print(f"  FAIL: \"{case['user_input'][:50]}\"")
            print(f"    Expected: space={case['expected_space']} tier={case['expected_tier']}")
            print(f"    Got:      space={result.space} tier={result.tier} ({result.matched_by})")

    total = passed + failed
    if failed == 0:
        print(f"  \033[92mALL {total} REGRESSION TESTS PASSED\033[0m")
    else:
        print(f"\n  \033[91m{failed}/{total} FAILED\033[0m")


if __name__ == "__main__":
    test_regression()
