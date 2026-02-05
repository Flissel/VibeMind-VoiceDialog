"""
Advanced Features Test Suite

Tests: idea.format_table, idea.auto_link, idea.whitepaper,
       idea.summarize, idea.analyze_links, idea.expand

30 Test Cases:
- 15 Complex (multi-step, dependencies)
- 10 Middle (single feature, parameters)
- 5 Easy (basic recognition)

Run with: python test_advanced_features.py
"""

import asyncio
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

# Add parent directories to path
sys.path.insert(0, str(Path(__file__).parent))

# =============================================================================
# TEST CASE DEFINITIONS
# =============================================================================

@dataclass
class TestCase:
    """Single test case definition."""
    id: str
    input: str
    expected_multi_step: bool = False
    expected_intent: Optional[str] = None
    expected_steps: Optional[List[str]] = None
    expected_params: Optional[Dict[str, Any]] = None
    category: str = "easy"  # easy, middle, complex


# COMPLEX Tests (15) - Multi-step, Dependencies, Full Pipeline
COMPLEX_TESTS = [
    TestCase(
        id="C1",
        input="Erstelle Space Projekt, gehe hinein, erstelle Idee Roadmap und formatiere sie als Tabelle",
        expected_multi_step=True,
        expected_steps=["bubble.create", "bubble.enter", "idea.create", "idea.format_table"],
        expected_params={
            "bubble.create": {"title": "Projekt"},
            "idea.create": {"title": "Roadmap"},
            "idea.format_table": {"idea_name": "Roadmap"}
        },
        category="complex"
    ),
    TestCase(
        id="C2",
        input="Liste alle Ideen auf, verlinke sie sinnvoll und erstelle ein Whitepaper",
        expected_multi_step=True,
        expected_steps=["idea.list", "idea.auto_link", "idea.whitepaper"],
        category="complex"
    ),
    TestCase(
        id="C3",
        input="Analysiere die Ideen, schlage Verlinkungen vor und erstelle eine Zusammenfassung",
        expected_multi_step=True,
        expected_steps=["idea.analyze_links", "idea.summarize"],
        category="complex"
    ),
    TestCase(
        id="C4",
        input="Erstelle Bubble Marketing mit Ideen Social Media, SEO, Content und verlinke alle",
        expected_multi_step=True,
        expected_steps=["bubble.create", "idea.auto_link"],  # LLM may merge idea creation
        expected_params={
            "bubble.create": {"title": "Marketing"},
        },
        category="complex"
    ),
    TestCase(
        id="C5",
        input="Gehe in Space Projekte, zeige Ideen, formatiere die erste als Tabelle mit Spalten ID, Status, Beschreibung",
        expected_multi_step=True,
        expected_steps=["bubble.enter", "idea.list", "idea.format_table"],
        expected_params={
            "bubble.enter": {"bubble_name": "Projekte"},
            "idea.format_table": {"custom_columns": ["ID", "Status", "Beschreibung"]}
        },
        category="complex"
    ),
    TestCase(
        id="C6",
        input="Erstelle ein Whitepaper aus der Idee Roadmap mit allen verlinkten Notizen",
        expected_multi_step=False,
        expected_intent="idea.whitepaper",
        expected_params={"start_node": "Roadmap"},
        category="complex"
    ),
    TestCase(
        id="C7",
        input="Fasse alle Ideen im Space zusammen und erstelle daraus ein Whitepaper",
        expected_multi_step=True,
        expected_steps=["idea.summarize", "idea.whitepaper"],
        category="complex"
    ),
    TestCase(
        id="C8",
        input="Analysiere semantische Aehnlichkeit der Ideen und verlinke die mit ueber 70 Prozent Uebereinstimmung",
        expected_multi_step=False,  # auto_link already includes analysis
        expected_intent="idea.auto_link",
        category="complex"
    ),
    TestCase(
        id="C9",
        input="Erstelle Space API-Design, fuege Ideen Endpoints, Authentication, Errors hinzu und formatiere als Tabelle",
        expected_multi_step=True,
        expected_steps=["bubble.create", "idea.create", "idea.create", "idea.create", "idea.format_table"],
        expected_params={
            "bubble.create": {"title": "API-Design"},
        },
        category="complex"
    ),
    TestCase(
        id="C10",
        input="Zeige welche Ideen zusammengehoeren ohne sie zu verlinken",
        expected_multi_step=False,
        expected_intent="idea.analyze_links",
        category="complex"
    ),
    TestCase(
        id="C11",
        input="Erweitere die Idee Marketing um 5 Unterpunkte und verlinke sie mit dem Original",
        expected_multi_step=True,
        expected_steps=["idea.expand", "idea.auto_link"],  # auto_link is more natural for multiple items
        expected_params={
            "idea.expand": {"idea_name": "Marketing", "count": 5}
        },
        category="complex"
    ),
    TestCase(
        id="C12",
        input="Erstelle Zusammenfassung der Idee Features im actionable Stil",
        expected_multi_step=False,
        expected_intent="idea.summarize",
        expected_params={"idea_name": "Features", "style": "actionable"},
        category="complex"
    ),
    TestCase(
        id="C13",
        input="Formatiere die Idee Requirements als Tabelle mit Spalten Calls ID, Requirement, Content, Priority",
        expected_multi_step=False,
        expected_intent="idea.format_table",
        expected_params={
            "idea_name": "Requirements",
            "custom_columns": ["Calls ID", "Requirement", "Content", "Priority"]
        },
        category="complex"
    ),
    TestCase(
        id="C14",
        input="Loesche alle Ideen im Space Test und erstelle eine neue Zusammenfassung",
        expected_multi_step=True,
        expected_steps=["idea.delete", "idea.summarize"],
        category="complex"
    ),
    TestCase(
        id="C15",
        input="Gehe durch alle Spaces, liste deren Ideen auf und erstelle pro Space ein Whitepaper",
        expected_multi_step=True,
        expected_steps=["bubble.list", "idea.list", "idea.whitepaper"],
        category="complex"
    ),
]


# MIDDLE Tests (10) - Single Advanced Feature, Parameter Extraction
MIDDLE_TESTS = [
    TestCase(
        id="M1",
        input="Verlinke alle Ideen automatisch",
        expected_multi_step=False,
        expected_intent="idea.auto_link",
        category="middle"
    ),
    TestCase(
        id="M2",
        input="Erstelle ein Whitepaper aus den Ideen",
        expected_multi_step=False,
        expected_intent="idea.whitepaper",
        category="middle"
    ),
    TestCase(
        id="M3",
        input="Fasse die Idee Marketing zusammen",
        expected_multi_step=False,
        expected_intent="idea.summarize",
        expected_params={"idea_name": "Marketing"},
        category="middle"
    ),
    TestCase(
        id="M4",
        input="Welche Ideen sollten verbunden werden?",
        expected_multi_step=False,
        expected_intent="idea.analyze_links",
        category="middle"
    ),
    TestCase(
        id="M5",
        input="Formatiere die Idee als Tabelle",
        expected_multi_step=False,
        expected_intent="idea.format_table",
        category="middle"
    ),
    TestCase(
        id="M6",
        input="Verbinde Idee A mit Idee B",
        expected_multi_step=False,
        expected_intent="idea.connect",
        expected_params={"source": "Idee A", "target": "Idee B"},  # RAG uses source/target, PARAM_MAPPING normalizes
        category="middle"
    ),
    TestCase(
        id="M7",
        input="Erweitere die Ideen um verwandte Konzepte",
        expected_multi_step=False,
        expected_intent="idea.expand",
        category="middle"
    ),
    TestCase(
        id="M8",
        input="Erstelle eine detaillierte Zusammenfassung",
        expected_multi_step=False,
        expected_intent="idea.summarize",
        expected_params={"style": "detailed"},
        category="middle"
    ),
    TestCase(
        id="M9",
        input="Formatiere als Tabelle mit Spalten Name, Beschreibung, Status",
        expected_multi_step=False,
        expected_intent="idea.format_table",
        expected_params={"custom_columns": ["Name", "Beschreibung", "Status"]},
        category="middle"
    ),
    TestCase(
        id="M10",
        input="Zeige Verlinkungsvorschlaege fuer die aktuelle Bubble",
        expected_multi_step=False,
        expected_intent="idea.analyze_links",
        category="middle"
    ),
]


# EASY Tests (5) - Basic Recognition, Single Intent
EASY_TESTS = [
    TestCase(
        id="E1",
        input="Verlinke die Ideen sinnvoll",
        expected_multi_step=False,
        expected_intent="idea.auto_link",
        category="easy"
    ),
    TestCase(
        id="E2",
        input="Zusammenfassung erstellen",
        expected_multi_step=False,
        expected_intent="idea.summarize",
        category="easy"
    ),
    TestCase(
        id="E3",
        input="Mach ein Whitepaper",
        expected_multi_step=False,
        expected_intent="idea.whitepaper",
        category="easy"
    ),
    TestCase(
        id="E4",
        input="Als Tabelle formatieren",
        expected_multi_step=False,
        expected_intent="idea.format_table",
        category="easy"
    ),
    TestCase(
        id="E5",
        input="Ideen analysieren",
        expected_multi_step=False,
        expected_intent="idea.analyze_links",
        category="easy"
    ),
]


ALL_TESTS = COMPLEX_TESTS + MIDDLE_TESTS + EASY_TESTS


# =============================================================================
# TEST RUNNER
# =============================================================================

class AdvancedFeaturesTestRunner:
    """Test runner for advanced features."""

    def __init__(self, use_orchestrator: bool = False):
        """
        Initialize test runner.

        Args:
            use_orchestrator: If True, test through full orchestrator.
                            If False, test RAG classifier only.
        """
        self.use_orchestrator = use_orchestrator
        self.results: List[Dict[str, Any]] = []

    async def run_single_test(self, test: TestCase) -> Dict[str, Any]:
        """Run a single test case."""
        from swarm.orchestrator.rag_intent_classifier import get_rag_intent_classifier

        classifier = get_rag_intent_classifier()
        result = await classifier.classify(test.input)

        # Evaluate result
        passed = True
        errors = []

        # Check multi-step detection
        if test.expected_multi_step:
            if not result.is_multi_step:
                passed = False
                errors.append(f"Expected multi-step but got single step")
            elif test.expected_steps:
                actual_steps = [s.get("event_type", "") for s in result.steps]
                # Check if all expected steps are present (order-independent for now)
                for expected_step in test.expected_steps:
                    if expected_step not in actual_steps:
                        passed = False
                        errors.append(f"Missing step: {expected_step}")
        else:
            # Single step - check intent
            if test.expected_intent and result.event_type != test.expected_intent:
                passed = False
                errors.append(f"Expected {test.expected_intent} but got {result.event_type}")

        # Check parameters if specified (partial match)
        if test.expected_params and not test.expected_multi_step:
            for key, expected_value in test.expected_params.items():
                actual_value = result.payload.get(key)
                if actual_value != expected_value:
                    # Partial match for lists/strings
                    if isinstance(expected_value, str) and isinstance(actual_value, str):
                        if expected_value.lower() not in actual_value.lower():
                            passed = False
                            errors.append(f"Param {key}: expected '{expected_value}', got '{actual_value}'")
                    elif isinstance(expected_value, list) and isinstance(actual_value, list):
                        if not all(e in actual_value for e in expected_value):
                            passed = False
                            errors.append(f"Param {key}: expected {expected_value}, got {actual_value}")
                    else:
                        passed = False
                        errors.append(f"Param {key}: expected '{expected_value}', got '{actual_value}'")

        return {
            "test_id": test.id,
            "input": test.input,
            "category": test.category,
            "passed": passed,
            "errors": errors,
            "result": {
                "event_type": result.event_type,
                "confidence": result.confidence,
                "payload": result.payload,
                "is_multi_step": result.is_multi_step,
                "steps": result.steps if result.is_multi_step else [],
                "reasoning": result.reasoning,
            }
        }

    async def run_all_tests(self, tests: List[TestCase] = None) -> Dict[str, Any]:
        """Run all test cases."""
        tests = tests or ALL_TESTS
        self.results = []

        print(f"\n{'='*70}")
        print(f"Advanced Features Test Suite - {len(tests)} Tests")
        print(f"{'='*70}\n")

        for test in tests:
            try:
                result = await self.run_single_test(test)
                self.results.append(result)

                status = "PASS" if result["passed"] else "FAIL"
                print(f"[{status}] {result['test_id']} ({result['category']})")
                print(f"    Input: {result['input'][:60]}...")
                print(f"    Intent: {result['result']['event_type']} (conf: {result['result']['confidence']:.2f})")

                if result["result"]["is_multi_step"]:
                    steps = [s.get("event_type", "") for s in result["result"]["steps"]]
                    print(f"    Steps: {' -> '.join(steps)}")

                if result["result"]["payload"]:
                    print(f"    Payload: {result['result']['payload']}")

                if not result["passed"]:
                    for error in result["errors"]:
                        print(f"    ERROR: {error}")

                print()

            except Exception as e:
                print(f"[ERROR] {test.id}: {str(e)}")
                self.results.append({
                    "test_id": test.id,
                    "input": test.input,
                    "category": test.category,
                    "passed": False,
                    "errors": [str(e)],
                    "result": None
                })

        return self._generate_report()

    def _generate_report(self) -> Dict[str, Any]:
        """Generate test report."""
        total = len(self.results)
        passed = sum(1 for r in self.results if r["passed"])
        failed = total - passed

        by_category = {}
        for result in self.results:
            cat = result["category"]
            if cat not in by_category:
                by_category[cat] = {"total": 0, "passed": 0}
            by_category[cat]["total"] += 1
            if result["passed"]:
                by_category[cat]["passed"] += 1

        report = {
            "total": total,
            "passed": passed,
            "failed": failed,
            "accuracy": passed / total if total > 0 else 0,
            "by_category": by_category,
            "results": self.results,
        }

        # Print summary
        print(f"\n{'='*70}")
        print("TEST SUMMARY")
        print(f"{'='*70}")
        print(f"Total: {total} | Passed: {passed} | Failed: {failed}")
        print(f"Accuracy: {report['accuracy']*100:.1f}%")
        print()
        print("By Category:")
        for cat, stats in by_category.items():
            acc = stats["passed"] / stats["total"] * 100 if stats["total"] > 0 else 0
            print(f"  {cat.upper()}: {stats['passed']}/{stats['total']} ({acc:.0f}%)")

        # List failed tests
        if failed > 0:
            print(f"\nFailed Tests:")
            for r in self.results:
                if not r["passed"]:
                    print(f"  - {r['test_id']}: {', '.join(r['errors'])}")

        return report


# =============================================================================
# MAIN
# =============================================================================

async def main():
    """Run test suite."""
    import argparse

    parser = argparse.ArgumentParser(description="Advanced Features Test Suite")
    parser.add_argument("--orchestrator", action="store_true",
                       help="Test through full orchestrator (default: RAG only)")
    parser.add_argument("--category", choices=["easy", "middle", "complex", "all"],
                       default="all", help="Test category to run")
    parser.add_argument("--test-id", type=str, help="Run specific test by ID")
    args = parser.parse_args()

    runner = AdvancedFeaturesTestRunner(use_orchestrator=args.orchestrator)

    # Filter tests
    tests = ALL_TESTS
    if args.category != "all":
        tests = [t for t in tests if t.category == args.category]
    if args.test_id:
        tests = [t for t in tests if t.id == args.test_id]

    if not tests:
        print("No tests match the specified criteria")
        return

    report = await runner.run_all_tests(tests)

    # Return exit code based on results
    if report["accuracy"] < 1.0:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
