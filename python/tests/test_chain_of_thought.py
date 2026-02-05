"""
Autonomous Test: Chain-of-Thought Logging & Context Enrichment

Tests:
1. BubbleContextProvider can get current context
2. RAG classifier accepts bubble_context parameter
3. Reasoning is logged to stderr and ReasoningLogger
4. Context is included in LLM prompt

Run: python test_chain_of_thought.py
"""

import asyncio
import sys
import os
from pathlib import Path

# Add python directory to path
sys.path.insert(0, str(Path(__file__).parent))

# Capture stderr for testing
import io
captured_stderr = io.StringIO()

def test_bubble_context_provider():
    """Test 1: BubbleContextProvider works"""
    print("\n" + "="*60)
    print("TEST 1: BubbleContextProvider")
    print("="*60)

    try:
        from swarm.context import get_bubble_context_provider
        provider = get_bubble_context_provider()

        # Get context (will return multiverse if no bubble entered)
        context = provider.get_current_context()

        print(f"  Context retrieved: {context}")
        print(f"  bubble_id: {context.get('bubble_id')}")
        print(f"  bubble_name: {context.get('bubble_name')}")
        print(f"  idea_count: {context.get('idea_count')}")
        print(f"  idea_titles: {context.get('idea_titles')}")

        # Verify structure
        assert "bubble_id" in context, "Missing bubble_id"
        assert "bubble_name" in context, "Missing bubble_name"
        assert "idea_titles" in context, "Missing idea_titles"
        assert "idea_count" in context, "Missing idea_count"

        print("  [PASS] BubbleContextProvider works correctly")
        return True

    except Exception as e:
        print(f"  [FAIL] Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_rag_classifier_signature():
    """Test 2: RAG classifier accepts bubble_context parameter"""
    print("\n" + "="*60)
    print("TEST 2: RAG Classifier Signature")
    print("="*60)

    try:
        from swarm.orchestrator.rag_intent_classifier import RAGIntentClassifier
        import inspect

        # Check classify method signature
        sig = inspect.signature(RAGIntentClassifier.classify)
        params = list(sig.parameters.keys())

        print(f"  classify() parameters: {params}")

        assert "bubble_context" in params, "Missing bubble_context parameter"
        print("  [PASS] classify() accepts bubble_context parameter")

        # Check _call_llm method signature
        sig_llm = inspect.signature(RAGIntentClassifier._call_llm)
        params_llm = list(sig_llm.parameters.keys())

        print(f"  _call_llm() parameters: {params_llm}")

        assert "bubble_context" in params_llm, "Missing bubble_context in _call_llm"
        print("  [PASS] _call_llm() accepts bubble_context parameter")

        return True

    except Exception as e:
        print(f"  [FAIL] Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_prompt_template():
    """Test 3: Prompt template has context_section placeholder"""
    print("\n" + "="*60)
    print("TEST 3: Prompt Template")
    print("="*60)

    try:
        from swarm.orchestrator.rag_intent_classifier import RAG_CLASSIFIER_PROMPT

        print(f"  Prompt template length: {len(RAG_CLASSIFIER_PROMPT)} chars")

        # Check for context_section placeholder
        has_context_section = "{context_section}" in RAG_CLASSIFIER_PROMPT
        print(f"  Has {{context_section}}: {has_context_section}")

        assert has_context_section, "Missing {context_section} placeholder"
        print("  [PASS] Prompt template has context_section placeholder")

        # Test formatting with context
        test_prompt = RAG_CLASSIFIER_PROMPT.format(
            context_section="## Aktueller Kontext\n- Space: Test\n\n",
            rules_context="1. test.rule",
            user_input="test input"
        )

        assert "Aktueller Kontext" in test_prompt, "Context not included in formatted prompt"
        print("  [PASS] Context is included in formatted prompt")

        return True

    except Exception as e:
        print(f"  [FAIL] Error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_full_classification_flow():
    """Test 4: Full classification with context and reasoning logging"""
    print("\n" + "="*60)
    print("TEST 4: Full Classification Flow (requires API key)")
    print("="*60)

    # Check if API key is available
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("  [SKIP] OPENROUTER_API_KEY not set - skipping live test")
        return None

    try:
        from swarm.orchestrator.rag_intent_classifier import get_rag_intent_classifier
        from swarm.context import get_bubble_context_provider

        classifier = get_rag_intent_classifier()
        provider = get_bubble_context_provider()

        # Get context
        bubble_context = provider.get_current_context()
        print(f"  Context: {bubble_context.get('bubble_name')}")

        # Test classification with context
        test_input = "Verlinke die Ideen sinnvoll"
        print(f"  Input: '{test_input}'")

        # Capture stderr
        old_stderr = sys.stderr
        sys.stderr = captured_stderr

        result = await classifier.classify(test_input, bubble_context=bubble_context)

        # Restore stderr
        sys.stderr = old_stderr
        stderr_output = captured_stderr.getvalue()

        print(f"  Result event_type: {result.event_type}")
        print(f"  Result confidence: {result.confidence}")
        print(f"  Result reasoning: {result.reasoning}")
        print(f"  Result used_rules: {result.used_rules}")

        # Verify result structure
        assert result.event_type, "Missing event_type"
        assert result.confidence >= 0, "Invalid confidence"
        assert result.reasoning, "Missing reasoning"

        print("  [PASS] Classification returned valid result")

        # Check if reasoning is populated
        if result.reasoning:
            print(f"  [PASS] Reasoning populated: '{result.reasoning[:50]}...'")
        else:
            print("  [WARN] Reasoning is empty")

        return True

    except Exception as e:
        print(f"  [FAIL] Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_reasoning_logger():
    """Test 5: ReasoningLogger integration"""
    print("\n" + "="*60)
    print("TEST 5: ReasoningLogger Integration")
    print("="*60)

    try:
        from swarm.reasoning import get_reasoning_logger

        logger = get_reasoning_logger()
        print(f"  Logger instance: {logger}")
        print(f"  Log directory: {logger._log_dir}")

        # Test start_job
        test_job_id = "test-chain-of-thought-001"
        ctx = logger.start_job(test_job_id, "test-session", "test input")
        print(f"  Started job: {test_job_id}")

        assert ctx is not None, "start_job returned None"
        print("  [PASS] start_job works")

        # Test log_intent_reasoning (async)
        async def test_log():
            await logger.log_intent_reasoning(
                job_id=test_job_id,
                event_type="test.intent",
                confidence=0.95,
                reasoning="Test reasoning for autonomous evaluation",
                used_rules=["test.rule1", "test.rule2"]
            )

        asyncio.run(test_log())
        print("  [PASS] log_intent_reasoning works")

        # Check log file exists
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        log_file = logger._log_dir / f"reasoning_{today}.jsonl"

        if log_file.exists():
            print(f"  [PASS] Log file created: {log_file}")

            # Read last line
            with open(log_file, "r") as f:
                lines = f.readlines()
                if lines:
                    last_line = lines[-1]
                    if "test-chain-of-thought-001" in last_line:
                        print("  [PASS] Test entry found in log file")
                    else:
                        print("  [WARN] Test entry not found in last line")
        else:
            print(f"  [WARN] Log file not found: {log_file}")

        return True

    except Exception as e:
        print(f"  [FAIL] Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_intent_orchestrator_integration():
    """Test 6: IntentOrchestrator has context integration"""
    print("\n" + "="*60)
    print("TEST 6: IntentOrchestrator Integration")
    print("="*60)

    try:
        # Read the orchestrator file and check for context imports
        orchestrator_path = Path(__file__).parent / "swarm" / "orchestrator" / "intent_orchestrator.py"

        with open(orchestrator_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Check for context import
        has_context_import = "get_bubble_context_provider" in content
        print(f"  Has bubble context import: {has_context_import}")

        # Check for reasoning logger import
        has_reasoning_import = "get_reasoning_logger" in content
        print(f"  Has reasoning logger import: {has_reasoning_import}")

        # Check for [CONTEXT] debug logging
        has_context_logging = "[CONTEXT]" in content
        print(f"  Has [CONTEXT] debug logging: {has_context_logging}")

        # Check for [RAG REASONING] debug logging
        has_reasoning_logging = "[RAG REASONING]" in content
        print(f"  Has [RAG REASONING] debug logging: {has_reasoning_logging}")

        if has_context_import and has_reasoning_import and has_context_logging and has_reasoning_logging:
            print("  [PASS] All integration points present")
            return True
        else:
            print("  [FAIL] Missing integration points")
            return False

    except Exception as e:
        print(f"  [FAIL] Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests and generate evaluation report"""
    print("\n" + "#"*60)
    print("# AUTONOMOUS TEST: Chain-of-Thought Logging")
    print("# Context Enrichment")
    print("#"*60)

    results = {}

    # Run tests
    results["BubbleContextProvider"] = test_bubble_context_provider()
    results["RAG Classifier Signature"] = test_rag_classifier_signature()
    results["Prompt Template"] = test_prompt_template()
    results["ReasoningLogger"] = test_reasoning_logger()
    results["Orchestrator Integration"] = test_intent_orchestrator_integration()

    # Run async test
    try:
        results["Full Classification"] = asyncio.run(test_full_classification_flow())
    except Exception as e:
        print(f"  [FAIL] Async test failed: {e}")
        results["Full Classification"] = False

    # Generate evaluation report
    print("\n" + "="*60)
    print("EVALUATION REPORT")
    print("="*60)

    passed = sum(1 for v in results.values() if v is True)
    failed = sum(1 for v in results.values() if v is False)
    skipped = sum(1 for v in results.values() if v is None)
    total = len(results)

    print(f"\n  Total Tests: {total}")
    print(f"  Passed: {passed}")
    print(f"  Failed: {failed}")
    print(f"  Skipped: {skipped}")

    print("\n  Details:")
    for name, result in results.items():
        status = "[PASS]" if result is True else "[FAIL]" if result is False else "[SKIP]"
        print(f"    {status} {name}")

    print("\n" + "="*60)

    if failed == 0:
        print("  OVERALL: SUCCESS - All tests passed!")
        print("="*60)
        return 0
    else:
        print(f"  OVERALL: FAILED - {failed} test(s) failed")
        print("="*60)
        return 1


if __name__ == "__main__":
    exit(main())
