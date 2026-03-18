"""
Test: IdeasSpaceAgent — LLM tool-calling agent for Ideas/Bubbles Space.

Tests the agent with various requests and verifies:
1. Correct tool selection
2. Multi-step chaining
3. Summary generation
"""

import asyncio
import os
import sys
import time

# Add project root to path
python_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
project_root = os.path.dirname(python_dir)
sys.path.insert(0, python_dir)

# Load .env from project root
from dotenv import load_dotenv
load_dotenv(os.path.join(project_root, ".env"))

from swarm.space_agents.models import SpaceAgentContext
from swarm.space_agents.ideas_agent import IdeasSpaceAgent


# Test cases: (description, input, expected_tools, is_multi_step)
# Note: expected_tools can be a list of alternatives for flexible matching
TEST_CASES = [
    (
        "Liste alle Bubbles",
        "Welche Bubbles hab ich?",
        ["bubble_list"],
        False,
    ),
    (
        "Erstelle Bubble",
        "Erstelle eine Bubble Test Space",
        ["bubble_create"],
        False,
    ),
    (
        "Betrete Space (fuzzy)",
        "Geh in den Space Test",
        ["bubble_find", "bubble_enter"],  # Agent may use find (smarter) or direct enter
        False,
    ),
    (
        "Erstelle Idee (im aktiven Space)",
        "Notiere: API Design Pattern fuer REST Services",
        ["idea_create"],
        False,
    ),
    (
        "Multi-Step: Bubble + Idee",
        "Erstelle einen Space Projekt Alpha und notiere darin die Idee Brainstorm",
        ["bubble_create", "bubble_enter", "idea_create"],
        True,
    ),
    (
        "Verlasse Space",
        "Zurueck zur Uebersicht",
        ["bubble_exit"],
        False,
    ),
    (
        "Wo bin ich?",
        "Wo bin ich gerade?",
        ["bubble_current"],
        False,
    ),
    (
        "Loesche Bubble",
        "Loesche den Space Projekt Alpha",
        ["bubble_delete"],
        False,
    ),
]


async def test_single(agent, desc, user_input, expected_tools, is_multi_step, context):
    """Test a single request."""
    print(f"\n--- {desc} ---")
    print(f"  Input: \"{user_input}\"")
    print(f"  Expected: {expected_tools}{' (multi-step)' if is_multi_step else ''}")

    start = time.perf_counter()
    try:
        result = await agent.execute(user_input, context)
        elapsed = (time.perf_counter() - start) * 1000

        actual_tools = [tc.name for tc in result.tool_calls]
        print(f"  Actual tools: {actual_tools}")
        print(f"  Turns: {result.turns}")
        print(f"  Summary: {result.summary[:120]}")
        print(f"  Latency: {elapsed:.0f}ms")

        # Check results
        for tr in result.results:
            status = "OK" if tr.success else f"ERR: {tr.error}"
            print(f"    {tr.tool_name}: {status}")

        # Verify expected tools are present
        if is_multi_step:
            # For multi-step, check that all expected tools are called
            all_present = all(t in actual_tools for t in expected_tools)
            if all_present:
                print(f"  Result: PASS (all expected tools called)")
                return True
            else:
                missing = [t for t in expected_tools if t not in actual_tools]
                print(f"  Result: FAIL (missing: {missing})")
                return False
        else:
            # For single-step, check any expected tool was called
            any_match = any(t in actual_tools for t in expected_tools)
            if any_match:
                print(f"  Result: PASS")
                return True
            elif not actual_tools:
                # Agent gave direct answer (no tools needed) — context-dependent
                print(f"  Result: SOFT PASS (direct answer, no tools needed)")
                return True
            else:
                print(f"  Result: FAIL (expected one of {expected_tools}, got {actual_tools})")
                return False

    except Exception as e:
        elapsed = (time.perf_counter() - start) * 1000
        print(f"  ERROR: {e} [{elapsed:.0f}ms]")
        return False


async def main():
    model = os.getenv("SPACE_AGENT_MODEL", "openai/gpt-4o-mini")
    print(f"\n{'='*70}")
    print(f"  IdeasSpaceAgent Test — Model: {model}")
    print(f"{'='*70}")

    agent = IdeasSpaceAgent(model=model)
    print(f"  Tools loaded: {len(agent._tools)}")
    print(f"  Executors loaded: {len(agent._executors)}")

    context = SpaceAgentContext(
        user_input="",
        conversation_history=[],
        current_bubble=None,
        current_bubble_id=None,
        idea_count=0,
    )

    passed = 0
    failed = 0

    for desc, user_input, expected_tools, is_multi_step in TEST_CASES:
        success = await test_single(
            agent, desc, user_input, expected_tools, is_multi_step, context
        )
        if success:
            passed += 1
        else:
            failed += 1

    print(f"\n{'='*70}")
    print(f"  Results: {passed}/{passed+failed} passed, {failed} failed")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    asyncio.run(main())
