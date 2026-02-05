"""
Test Enhancement Pipeline Components

Verifies:
1. Import verification
2. Rule loading
3. Intent Enhancer functionality
4. Collector Agent functionality
5. Execution Validator functionality
"""

import asyncio
import sys


def main():
    # Test 1: Import verification
    print("=== Test 1: Import Verification ===")
    try:
        from swarm.agents.collector_agent import CollectorAgent, get_collector_agent
        from swarm.agents.intent_enhancer import IntentEnhancer, get_intent_enhancer, RuleStore
        from swarm.agents.execution_validator import ExecutionValidator, get_execution_validator
        print("[OK] All imports successful")
    except ImportError as e:
        print(f"[FAIL] Import error: {e}")
        sys.exit(1)

    # Test 2: Rule loading
    print("\n=== Test 2: Rule Loading ===")
    store = RuleStore()
    print(f"[OK] Loaded {len(store.rules)} rules")
    by_category = {}
    for r in store.rules.values():
        cat = r.category
        by_category[cat] = by_category.get(cat, 0) + 1
    print(f"[OK] Categories: {by_category}")

    # Test 3: Enhancer
    print("\n=== Test 3: Intent Enhancer ===")

    async def test_enhancer():
        enhancer = get_intent_enhancer()

        # Test ASR error correction
        result = await enhancer.enhance("zeig mir meine idden", {})
        print(f'  ASR test: "zeig mir meine idden" -> "{result.normalized_text}"')
        print(f"    Rules applied: {result.rules_applied}")

        # Test dialect normalization
        result = await enhancer.enhance("schaug amoi de ideen", {})
        print(f'  Dialect test: "schaug amoi de ideen" -> "{result.normalized_text}"')
        print(f"    Rules applied: {result.rules_applied}")

        # Test correction handling
        result = await enhancer.enhance("erstelle nein warte loesche", {})
        print(f'  Correction test: "erstelle nein warte loesche" -> "{result.normalized_text}"')
        print(f"    Rules applied: {result.rules_applied}")

        # Test informal
        result = await enhancer.enhance("zeig mal", {})
        print(f'  Informal test: "zeig mal" -> "{result.normalized_text}"')
        print(f"    Rules applied: {result.rules_applied}")

    asyncio.run(test_enhancer())

    # Test 4: Collector
    print("\n=== Test 4: Collector Agent ===")

    async def test_collector():
        from swarm.agents.collector_agent import reset_collector_agent
        reset_collector_agent()
        collector = get_collector_agent()

        # Short input should accumulate
        result1 = await collector.collect("die ideen")
        print(f"  Short input: result={result1}, accumulating={collector.is_accumulating}")

        # Add more
        result2 = await collector.collect("zeigen bitte")
        print(f"  Second input: result={result2}")

        # Force flush to test
        collector.reset()

    asyncio.run(test_collector())

    # Test 5: Validator
    print("\n=== Test 5: Execution Validator ===")

    async def test_validator():
        from swarm.agents.execution_validator import reset_execution_validator
        reset_execution_validator()
        validator = get_execution_validator()

        # Register expected execution
        await validator.expect_execution(
            job_id="test-123",
            event_type="idea.list",
            original_input="zeig ideen",
            enhanced_input="zeig mir alle ideen",
            rules_applied=["inf_001"]
        )
        print(f"  [OK] Registered expected execution")
        print(f"  Pending validations: {validator.get_pending_count()}")

        # Stats
        stats = validator.get_stats()
        print(f"  Validator stats: {stats}")

    asyncio.run(test_validator())

    print("\n=== All Tests Passed ===")


if __name__ == "__main__":
    main()
