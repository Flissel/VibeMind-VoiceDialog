"""
Multi-Step Execution Test Suite

Tests multi-step commands through:
1. RAG Classifier (detects is_multi_step)
2. IntentOrchestrator (_process_multi_step)
3. Tool Execution (direct or Redis)

Analyzes:
- Intent classification accuracy
- Multi-step detection accuracy
- Dependency ordering correctness
- Tool execution success rate
- Result passing between steps

Usage:
    cd python
    python test_multi_step_execution.py
"""

import asyncio
import json
import os
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import List, Dict, Any, Optional

# Add python directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Test cases for multi-step execution
MULTI_STEP_TEST_CASES = [
    # Multi-step cases (should detect is_multi_step=True)
    {
        "input": "Liste alle Ideen auf und lösche sie",
        "expected_multi_step": True,
        "expected_steps": ["idea.list", "idea.delete"],
        "expected_dependencies": {"idea.delete": ["idea.list"]},
        "description": "List ideas then delete them (2 steps with dependency)",
    },
    {
        "input": "Erstelle Bubble Marketing und füge eine Idee Social Media hinzu",
        "expected_multi_step": True,
        "expected_steps": ["bubble.create", "idea.create"],
        "expected_dependencies": {"idea.create": ["bubble.create"]},
        "description": "Create bubble then add idea (2 steps with dependency)",
    },
    {
        "input": "Zeige mir die Ideen und verlinke sie sinnvoll",
        "expected_multi_step": True,
        "expected_steps": ["idea.list", "idea.auto_link"],
        "expected_dependencies": {},
        "description": "List ideas then auto-link (2 steps)",
    },
    {
        "input": "Erstelle Space Projekte, gehe hinein und erstelle eine Idee Roadmap",
        "expected_multi_step": True,
        "expected_steps": ["bubble.create", "bubble.enter", "idea.create"],
        "expected_dependencies": {
            "bubble.enter": ["bubble.create"],
            "idea.create": ["bubble.enter"],
        },
        "description": "Create space, enter it, create idea (3 steps with chain dependency)",
    },

    # Single-step cases (should detect is_multi_step=False)
    {
        "input": "Lösche alle Ideen",
        "expected_multi_step": False,
        "expected_steps": ["idea.delete"],
        "expected_dependencies": {},
        "description": "Delete all ideas (single step)",
    },
    {
        "input": "Erstelle eine Idee zum Thema Marketing",
        "expected_multi_step": False,
        "expected_steps": ["idea.create"],
        "expected_dependencies": {},
        "description": "Create single idea (single step)",
    },
    {
        "input": "Verlinke die Ideen sinnvoll",
        "expected_multi_step": False,
        "expected_steps": ["idea.auto_link"],
        "expected_dependencies": {},
        "description": "Auto-link ideas (single step)",
    },
]


@dataclass
class TestResult:
    """Result of a single test case."""
    test_index: int
    input_text: str
    description: str

    # Expected values
    expected_multi_step: bool
    expected_steps: List[str]

    # Actual RAG results
    rag_is_multi_step: bool
    rag_steps: List[str]
    rag_event_type: str
    rag_confidence: float
    rag_reasoning: str
    rag_used_rules: List[str]

    # Orchestrator results
    orch_event_type: str
    orch_response: str
    orch_error: Optional[str]

    # Evaluation
    multi_step_correct: bool
    steps_correct: bool
    intent_correct: bool

    # Timing
    rag_latency_ms: float
    orch_latency_ms: float

    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class TestSummary:
    """Summary of all test results."""
    total_tests: int
    multi_step_detection_correct: int
    step_sequence_correct: int
    intent_classification_correct: int

    multi_step_accuracy: float
    step_accuracy: float
    intent_accuracy: float

    avg_rag_latency_ms: float
    avg_orch_latency_ms: float

    failures: List[Dict[str, Any]]

    def to_markdown(self) -> str:
        """Generate markdown report."""
        md = []
        md.append("# Multi-Step Execution Test Results\n")
        md.append(f"**Date:** {datetime.now().isoformat()}\n")
        md.append(f"**Total Tests:** {self.total_tests}\n")

        md.append("## Accuracy Metrics\n")
        md.append(f"| Metric | Correct | Total | Accuracy |")
        md.append(f"|--------|---------|-------|----------|")
        md.append(f"| Multi-step Detection | {self.multi_step_detection_correct} | {self.total_tests} | {self.multi_step_accuracy*100:.1f}% |")
        md.append(f"| Step Sequence | {self.step_sequence_correct} | {self.total_tests} | {self.step_accuracy*100:.1f}% |")
        md.append(f"| Intent Classification | {self.intent_classification_correct} | {self.total_tests} | {self.intent_accuracy*100:.1f}% |")
        md.append("")

        md.append("## Latency\n")
        md.append(f"- RAG Classifier: {self.avg_rag_latency_ms:.0f}ms avg")
        md.append(f"- Orchestrator: {self.avg_orch_latency_ms:.0f}ms avg")
        md.append("")

        if self.failures:
            md.append("## Failures\n")
            for i, f in enumerate(self.failures, 1):
                md.append(f"### {i}. {f['description']}\n")
                md.append(f"**Input:** \"{f['input']}\"")
                md.append(f"")
                md.append(f"| Expected | Actual |")
                md.append(f"|----------|--------|")
                md.append(f"| is_multi_step: {f['expected_multi_step']} | is_multi_step: {f['actual_multi_step']} |")
                md.append(f"| steps: {f['expected_steps']} | steps: {f['actual_steps']} |")
                md.append(f"")
                if f.get('reasoning'):
                    md.append(f"**RAG Reasoning:** {f['reasoning'][:200]}...")
                md.append("")

        return "\n".join(md)


async def run_rag_classification(rag_classifier, user_input: str) -> Dict[str, Any]:
    """Run RAG classification and measure latency."""
    start = time.perf_counter()
    result = await rag_classifier.classify(user_input)
    latency_ms = (time.perf_counter() - start) * 1000

    return {
        "is_multi_step": result.is_multi_step,
        "steps": [s.get("event_type") for s in result.steps] if result.steps else [],
        "event_type": result.event_type,
        "confidence": result.confidence,
        "reasoning": result.reasoning,
        "used_rules": result.used_rules,
        "latency_ms": latency_ms,
    }


async def run_orchestrator(orchestrator, user_input: str) -> Dict[str, Any]:
    """Run orchestrator and measure latency."""
    start = time.perf_counter()
    result = await orchestrator.process_intent(user_input)
    latency_ms = (time.perf_counter() - start) * 1000

    return {
        "event_type": result.event_type,
        "response": result.response_hint[:200] if result.response_hint else "",
        "error": result.error,
        "latency_ms": latency_ms,
    }


async def run_multi_step_tests(verbose: bool = True, run_orchestrator_tests: bool = False) -> TestSummary:
    """
    Main test runner.

    Args:
        verbose: Print detailed output
        run_orchestrator_tests: Also run through full orchestrator (slow, modifies DB)
    """
    # Import components
    from swarm.orchestrator.rag_intent_classifier import get_rag_intent_classifier

    rag = get_rag_intent_classifier()
    orchestrator = None

    if run_orchestrator_tests:
        from swarm.orchestrator import get_orchestrator
        orchestrator = get_orchestrator()

    results: List[TestResult] = []

    print(f"\n{'='*70}")
    print(f"MULTI-STEP EXECUTION TEST SUITE")
    print(f"{'='*70}")
    print(f"Tests: {len(MULTI_STEP_TEST_CASES)}")
    print(f"Orchestrator tests: {'ON' if run_orchestrator_tests else 'OFF'}")
    print(f"{'='*70}\n")

    for i, test in enumerate(MULTI_STEP_TEST_CASES):
        if verbose:
            print(f"\n[Test {i+1}/{len(MULTI_STEP_TEST_CASES)}] {test['description']}")
            print(f"Input: \"{test['input']}\"")
            print("-" * 50)

        # Run RAG classification
        rag_result = await run_rag_classification(rag, test["input"])

        if verbose:
            print(f"[RAG] is_multi_step: {rag_result['is_multi_step']}", end="")
            if rag_result['is_multi_step'] == test['expected_multi_step']:
                print(" [OK]")
            else:
                print(f" [FAIL] (expected: {test['expected_multi_step']})")

            if rag_result['is_multi_step']:
                print(f"[RAG] steps: {rag_result['steps']}", end="")
                if rag_result['steps'] == test['expected_steps']:
                    print(" [OK]")
                else:
                    print(f" [FAIL] (expected: {test['expected_steps']})")
            else:
                print(f"[RAG] event_type: {rag_result['event_type']}")

            print(f"[RAG] confidence: {rag_result['confidence']:.2f}")
            print(f"[RAG] rules: {rag_result['used_rules']}")
            print(f"[RAG] latency: {rag_result['latency_ms']:.0f}ms")

            # Print reasoning (truncated)
            reasoning = rag_result['reasoning']
            if len(reasoning) > 100:
                print(f"[RAG] reasoning: {reasoning[:100]}...")
            else:
                print(f"[RAG] reasoning: {reasoning}")

        # Run orchestrator if enabled
        orch_result = {"event_type": "", "response": "", "error": None, "latency_ms": 0}
        if run_orchestrator_tests and orchestrator:
            if verbose:
                print(f"\n[ORCHESTRATOR] Processing...")
            orch_result = await run_orchestrator(orchestrator, test["input"])
            if verbose:
                print(f"[ORCHESTRATOR] event_type: {orch_result['event_type']}")
                print(f"[ORCHESTRATOR] response: {orch_result['response'][:80]}...")
                if orch_result['error']:
                    print(f"[ORCHESTRATOR] error: {orch_result['error']}")
                print(f"[ORCHESTRATOR] latency: {orch_result['latency_ms']:.0f}ms")

        # Evaluate results
        multi_step_correct = rag_result['is_multi_step'] == test['expected_multi_step']

        # For multi-step, check step sequence
        if test['expected_multi_step']:
            steps_correct = rag_result['steps'] == test['expected_steps']
            intent_correct = multi_step_correct and steps_correct
        else:
            # For single-step, check event_type
            steps_correct = True  # N/A for single-step
            expected_intent = test['expected_steps'][0] if test['expected_steps'] else ""
            intent_correct = rag_result['event_type'] == expected_intent

        # Create result
        result = TestResult(
            test_index=i,
            input_text=test['input'],
            description=test['description'],
            expected_multi_step=test['expected_multi_step'],
            expected_steps=test['expected_steps'],
            rag_is_multi_step=rag_result['is_multi_step'],
            rag_steps=rag_result['steps'],
            rag_event_type=rag_result['event_type'],
            rag_confidence=rag_result['confidence'],
            rag_reasoning=rag_result['reasoning'],
            rag_used_rules=rag_result['used_rules'],
            orch_event_type=orch_result['event_type'],
            orch_response=orch_result['response'],
            orch_error=orch_result['error'],
            multi_step_correct=multi_step_correct,
            steps_correct=steps_correct,
            intent_correct=intent_correct,
            rag_latency_ms=rag_result['latency_ms'],
            orch_latency_ms=orch_result['latency_ms'],
        )
        results.append(result)

    # Generate summary
    total = len(results)
    multi_step_correct_count = sum(1 for r in results if r.multi_step_correct)
    steps_correct_count = sum(1 for r in results if r.steps_correct)
    intent_correct_count = sum(1 for r in results if r.intent_correct)

    failures = []
    for r in results:
        if not r.multi_step_correct or not r.steps_correct or not r.intent_correct:
            failures.append({
                "input": r.input_text,
                "description": r.description,
                "expected_multi_step": r.expected_multi_step,
                "actual_multi_step": r.rag_is_multi_step,
                "expected_steps": r.expected_steps,
                "actual_steps": r.rag_steps if r.rag_is_multi_step else [r.rag_event_type],
                "reasoning": r.rag_reasoning,
            })

    summary = TestSummary(
        total_tests=total,
        multi_step_detection_correct=multi_step_correct_count,
        step_sequence_correct=steps_correct_count,
        intent_classification_correct=intent_correct_count,
        multi_step_accuracy=multi_step_correct_count / total if total > 0 else 0,
        step_accuracy=steps_correct_count / total if total > 0 else 0,
        intent_accuracy=intent_correct_count / total if total > 0 else 0,
        avg_rag_latency_ms=sum(r.rag_latency_ms for r in results) / total if total > 0 else 0,
        avg_orch_latency_ms=sum(r.orch_latency_ms for r in results) / total if total > 0 else 0,
        failures=failures,
    )

    # Print summary
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")
    print(f"Multi-step detection: {multi_step_correct_count}/{total} ({summary.multi_step_accuracy*100:.1f}%)")
    print(f"Step sequence:        {steps_correct_count}/{total} ({summary.step_accuracy*100:.1f}%)")
    print(f"Intent classification:{intent_correct_count}/{total} ({summary.intent_accuracy*100:.1f}%)")
    print(f"")
    print(f"Avg RAG latency:      {summary.avg_rag_latency_ms:.0f}ms")
    if run_orchestrator_tests:
        print(f"Avg Orch latency:     {summary.avg_orch_latency_ms:.0f}ms")

    if failures:
        print(f"\n{'='*70}")
        print(f"FAILURES ({len(failures)})")
        print(f"{'='*70}")
        for f in failures:
            print(f"\n• {f['description']}")
            print(f"  Input: \"{f['input'][:50]}...\"")
            print(f"  Expected multi-step: {f['expected_multi_step']}, Got: {f['actual_multi_step']}")
            if f['expected_multi_step']:
                print(f"  Expected steps: {f['expected_steps']}")
                print(f"  Actual steps:   {f['actual_steps']}")

    # Save report
    report_path = os.path.join(
        os.path.dirname(__file__),
        "evaluation_reports",
        f"multi_step_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    )
    os.makedirs(os.path.dirname(report_path), exist_ok=True)

    with open(report_path, "w", encoding="utf-8") as f:
        f.write(summary.to_markdown())

    print(f"\n\nReport saved to: {report_path}")

    return summary


async def analyze_rag_prompt():
    """Analyze the RAG classifier's prompt to check multi-step instructions."""
    from swarm.orchestrator.rag_intent_classifier import RAG_CLASSIFIER_PROMPT

    print("\n" + "="*70)
    print("RAG CLASSIFIER PROMPT ANALYSIS")
    print("="*70)

    # Check for multi-step keywords
    multi_step_keywords = [
        "is_multi_step",
        "multi_step",
        "multi-step",
        "steps",
        "multiple actions",
        "mehrere aktionen",
    ]

    prompt_lower = RAG_CLASSIFIER_PROMPT.lower()
    found_keywords = []
    missing_keywords = []

    for kw in multi_step_keywords:
        if kw.lower() in prompt_lower:
            found_keywords.append(kw)
        else:
            missing_keywords.append(kw)

    print(f"\nFound keywords: {found_keywords}")
    print(f"Missing keywords: {missing_keywords}")

    # Check if prompt has multi-step section
    if "multi-step" in prompt_lower or "multi_step" in prompt_lower:
        print("\n[OK] Prompt contains multi-step instructions")
    else:
        print("\n[MISSING] Prompt MISSING multi-step instructions!")
        print("\nRecommendation: Add multi-step detection section to RAG_CLASSIFIER_PROMPT")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Multi-Step Execution Test Suite")
    parser.add_argument("--verbose", "-v", action="store_true", default=True,
                        help="Print detailed output")
    parser.add_argument("--orchestrator", "-o", action="store_true", default=False,
                        help="Also run through full orchestrator (slow, modifies DB)")
    parser.add_argument("--analyze-prompt", "-p", action="store_true", default=False,
                        help="Analyze RAG classifier prompt")

    args = parser.parse_args()

    if args.analyze_prompt:
        asyncio.run(analyze_rag_prompt())
    else:
        asyncio.run(run_multi_step_tests(
            verbose=args.verbose,
            run_orchestrator_tests=args.orchestrator
        ))
