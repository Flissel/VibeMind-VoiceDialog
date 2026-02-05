"""
Full Intent-to-Tool Coverage Tests

Tests ALL intent types through the complete pipeline:
User Input → Intent Classification → Parameter Extraction → Tool Execution → Result

With full monitoring:
- SystemStatusMonitor for operation tracking
- ToolLogger for execution logging
- MetricsCollector for latency and accuracy stats
"""

import asyncio
import sys
import os
import time
import json
import logging
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

# Import from same directory
from intent_test_cases import (
    ALL_TEST_CASES,
    TEST_CASES_BY_CATEGORY,
    IntentToolTestCase,
    get_coverage_stats,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class TestResult:
    """Result of a single test case execution."""
    test_case: IntentToolTestCase
    passed: bool
    classification_time_ms: float = 0.0
    tool_execution_time_ms: float = 0.0
    actual_intent: str = ""
    actual_params: Dict[str, Any] = field(default_factory=dict)
    tool_result: str = ""
    error: Optional[str] = None
    event_emitted: bool = False
    keywords_matched: bool = True


@dataclass
class CategoryReport:
    """Report for a single category of tests."""
    category: str
    total: int
    passed: int
    failed: int
    pass_rate: float
    avg_classification_ms: float
    avg_tool_execution_ms: float
    results: List[TestResult] = field(default_factory=list)


@dataclass
class FullTestReport:
    """Complete test report with all metrics."""
    timestamp: str
    total_tests: int
    passed: int
    failed: int
    pass_rate: float
    avg_classification_ms: float
    avg_tool_execution_ms: float
    p95_classification_ms: float
    p95_tool_execution_ms: float
    categories: Dict[str, CategoryReport] = field(default_factory=dict)
    failed_tests: List[TestResult] = field(default_factory=list)
    monitoring_metrics: Dict[str, Any] = field(default_factory=dict)


class IntentToolTestRunner:
    """
    Runs intent→tool tests with full monitoring.

    Usage:
        runner = IntentToolTestRunner()
        await runner.setup()
        report = await runner.run_all_tests()
        runner.save_report(report)
    """

    def __init__(self):
        self.orchestrator = None
        self.classifier = None
        self.status_monitor = None
        self.tool_logger = None
        self.metrics_collector = None
        self.results: List[TestResult] = []
        self.events_captured: List[Dict] = []

    async def setup(self):
        """Initialize all components."""
        logger.info("Setting up test runner...")

        # Load orchestrator (synchronous - not awaitable)
        try:
            from swarm.orchestrator.intent_orchestrator import get_orchestrator
            self.orchestrator = get_orchestrator()  # Not async
            logger.info("Orchestrator loaded")
        except Exception as e:
            logger.warning(f"Could not load orchestrator: {e}")

        # Load classifier
        try:
            from swarm.orchestrator.rag_intent_classifier import get_rag_classifier
            self.classifier = get_rag_classifier()
            logger.info("RAG Classifier loaded")
        except ImportError:
            try:
                from swarm.orchestrator.intent_classifier import get_intent_classifier
                self.classifier = get_intent_classifier()
                logger.info("Rule Classifier loaded")
            except Exception as e:
                logger.warning(f"Could not load classifier: {e}")

        # Load monitoring
        try:
            from swarm.monitoring.system_status import get_status_monitor
            self.status_monitor = get_status_monitor()
            logger.info("Status monitor loaded")
        except ImportError:
            logger.warning("Status monitor not available")

        try:
            from swarm.logging.tool_logger import get_tool_logger
            self.tool_logger = get_tool_logger()
            logger.info("Tool logger loaded")
        except ImportError:
            logger.warning("Tool logger not available")

        try:
            from swarm.simulation.metrics_collector import MetricsCollector
            self.metrics_collector = MetricsCollector()
            logger.info("Metrics collector loaded")
        except ImportError:
            logger.warning("Metrics collector not available")

        logger.info("Setup complete")

    async def run_single_test(self, test_case: IntentToolTestCase) -> TestResult:
        """Execute a single test case through the full pipeline."""
        result = TestResult(test_case=test_case, passed=False)

        # Start monitoring
        op_id = None
        if self.status_monitor:
            op_id = self.status_monitor.start_operation("test", test_case.intent_type)

        try:
            # 1. Classify the intent
            start_classify = time.perf_counter()
            classification = await self._classify(test_case.user_input)
            result.classification_time_ms = (time.perf_counter() - start_classify) * 1000

            if classification:
                result.actual_intent = classification.get("event_type", "")
                result.actual_params = classification.get("parameters", {})

            # 2. Check if classification matches expected
            intent_match = result.actual_intent == test_case.intent_type

            # 3. Check parameters (flexible matching)
            params_match = self._validate_params(
                result.actual_params,
                test_case.expected_params
            )

            # 4. Execute tool if we have an expected tool
            if test_case.expected_tool and intent_match:
                start_tool = time.perf_counter()
                tool_result, event = await self._execute_tool(
                    test_case.intent_type,
                    result.actual_params
                )
                result.tool_execution_time_ms = (time.perf_counter() - start_tool) * 1000
                result.tool_result = str(tool_result) if tool_result else ""

                # Check event emission
                if test_case.validation_event:
                    result.event_emitted = event == test_case.validation_event

                # Check keywords in result
                if test_case.validation_keywords:
                    result.keywords_matched = any(
                        kw.lower() in result.tool_result.lower()
                        for kw in test_case.validation_keywords
                    )

            # 5. Determine overall pass/fail
            if not test_case.expected_tool:
                # Conversation intents - just check classification
                result.passed = intent_match
            else:
                result.passed = intent_match and (
                    params_match or not test_case.expected_params
                )

            # Complete monitoring
            if self.status_monitor and op_id:
                self.status_monitor.complete_operation(op_id, success=result.passed)

        except Exception as e:
            result.error = str(e)
            result.passed = False
            if self.status_monitor and op_id:
                self.status_monitor.complete_operation(op_id, success=False, error=str(e))
            logger.error(f"Test error for {test_case.intent_type}: {e}")

        return result

    async def _classify(self, user_input: str) -> Optional[Dict[str, Any]]:
        """Classify user input using available classifier."""
        # Use classifier directly (faster, doesn't execute tools)
        if self.classifier:
            try:
                result = await self.classifier.classify(user_input)
                if result:
                    # Handle both RAGClassificationResult and Dict
                    if hasattr(result, 'event_type'):
                        # RAGClassificationResult dataclass
                        return {
                            "event_type": result.event_type,
                            "parameters": getattr(result, 'payload', {}) or {}
                        }
                    elif isinstance(result, dict):
                        # Dict result from standard classifier
                        return {
                            "event_type": result.get("event_type", ""),
                            "parameters": result.get("payload", result.get("parameters", {})) or {}
                        }
                return None
            except Exception as e:
                logger.warning(f"Classifier failed: {e}")

        # Fallback: use orchestrator's internal classifier
        if self.orchestrator and hasattr(self.orchestrator, '_classifier'):
            try:
                result = await self.orchestrator._classifier.classify(user_input)
                if result:
                    if hasattr(result, 'event_type'):
                        return {
                            "event_type": result.event_type,
                            "parameters": getattr(result, 'payload', {}) or {}
                        }
                    elif isinstance(result, dict):
                        return {
                            "event_type": result.get("event_type", ""),
                            "parameters": result.get("payload", result.get("parameters", {})) or {}
                        }
            except Exception as e:
                logger.debug(f"Orchestrator classifier failed: {e}")

        return None

    async def _execute_tool(
        self,
        intent_type: str,
        params: Dict[str, Any]
    ) -> Tuple[Any, Optional[str]]:
        """Execute the tool for an intent type."""
        if not self.orchestrator:
            return None, None

        try:
            # Get executor from orchestrator
            executor = self.orchestrator._tool_executors.get(intent_type)
            if not executor:
                return f"No executor for {intent_type}", None

            # Execute
            result = executor(params) if params else executor({})

            # TODO: Capture emitted event from broadcast
            event = None

            return result, event

        except Exception as e:
            return f"Error: {e}", None

    def _validate_params(
        self,
        actual: Dict[str, Any],
        expected: Dict[str, Any]
    ) -> bool:
        """Validate extracted parameters match expected (flexible)."""
        if not expected:
            return True

        for key, exp_value in expected.items():
            # Check various possible key names
            possible_keys = [key]
            if key == "title":
                possible_keys.extend(["bubble_name", "name", "idea_name"])
            elif key == "bubble_name":
                possible_keys.extend(["title", "name"])
            elif key == "idea_name":
                possible_keys.extend(["title", "name", "query"])

            found = False
            for pk in possible_keys:
                if pk in actual:
                    # Flexible value matching (case-insensitive, contains)
                    actual_val = str(actual[pk]).lower()
                    exp_val = str(exp_value).lower()
                    if exp_val in actual_val or actual_val in exp_val:
                        found = True
                        break

            if not found and exp_value:  # Only fail if expected value is not empty
                return False

        return True

    async def run_all_tests(
        self,
        categories: Optional[List[str]] = None,
        difficulty: Optional[str] = None
    ) -> FullTestReport:
        """Run all test cases and generate report."""
        logger.info("Starting full test run...")

        # Filter test cases
        test_cases = ALL_TEST_CASES
        if categories:
            test_cases = [tc for tc in test_cases if tc.category in categories]
        if difficulty:
            test_cases = [tc for tc in test_cases if tc.difficulty == difficulty]

        logger.info(f"Running {len(test_cases)} test cases...")

        # Run tests
        self.results = []
        for i, tc in enumerate(test_cases):
            logger.info(f"[{i+1}/{len(test_cases)}] Testing {tc.intent_type}: {tc.user_input[:40]}...")
            result = await self.run_single_test(tc)
            self.results.append(result)

            status = "PASS" if result.passed else "FAIL"
            logger.info(f"  -> {status} (classify: {result.classification_time_ms:.0f}ms)")

        # Generate report
        report = self._generate_report()
        return report

    def _generate_report(self) -> FullTestReport:
        """Generate full test report from results."""
        passed = [r for r in self.results if r.passed]
        failed = [r for r in self.results if not r.passed]

        # Latency stats
        classify_times = [r.classification_time_ms for r in self.results if r.classification_time_ms > 0]
        tool_times = [r.tool_execution_time_ms for r in self.results if r.tool_execution_time_ms > 0]

        def percentile(data, p):
            if not data:
                return 0
            sorted_data = sorted(data)
            idx = int(len(sorted_data) * p / 100)
            return sorted_data[min(idx, len(sorted_data) - 1)]

        # Category reports
        categories = {}
        for cat, test_cases in TEST_CASES_BY_CATEGORY.items():
            cat_results = [r for r in self.results if r.test_case.category == cat]
            if not cat_results:
                continue

            cat_passed = [r for r in cat_results if r.passed]
            cat_classify = [r.classification_time_ms for r in cat_results if r.classification_time_ms > 0]
            cat_tool = [r.tool_execution_time_ms for r in cat_results if r.tool_execution_time_ms > 0]

            categories[cat] = CategoryReport(
                category=cat,
                total=len(cat_results),
                passed=len(cat_passed),
                failed=len(cat_results) - len(cat_passed),
                pass_rate=len(cat_passed) / len(cat_results) if cat_results else 0,
                avg_classification_ms=sum(cat_classify) / len(cat_classify) if cat_classify else 0,
                avg_tool_execution_ms=sum(cat_tool) / len(cat_tool) if cat_tool else 0,
                results=cat_results,
            )

        # Monitoring metrics
        monitoring = {}
        if self.status_monitor:
            status = self.status_monitor.get_status()
            monitoring = {
                "total_operations": status.get("total_operations", 0),
                "errors": status.get("total_errors", 0),
                "error_rate": status.get("error_rate", 0),
            }

        return FullTestReport(
            timestamp=datetime.now().isoformat(),
            total_tests=len(self.results),
            passed=len(passed),
            failed=len(failed),
            pass_rate=len(passed) / len(self.results) if self.results else 0,
            avg_classification_ms=sum(classify_times) / len(classify_times) if classify_times else 0,
            avg_tool_execution_ms=sum(tool_times) / len(tool_times) if tool_times else 0,
            p95_classification_ms=percentile(classify_times, 95),
            p95_tool_execution_ms=percentile(tool_times, 95),
            categories=categories,
            failed_tests=failed,
            monitoring_metrics=monitoring,
        )

    def generate_markdown_report(self, report: FullTestReport) -> str:
        """Generate markdown report."""
        lines = [
            "# Intent-to-Tool Test Report",
            "",
            f"**Generated:** {report.timestamp}",
            "",
            "## Summary",
            "",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Total Tests | {report.total_tests} |",
            f"| Passed | {report.passed} ({report.pass_rate*100:.1f}%) |",
            f"| Failed | {report.failed} |",
            f"| Avg Classification | {report.avg_classification_ms:.0f}ms |",
            f"| Avg Tool Execution | {report.avg_tool_execution_ms:.0f}ms |",
            f"| P95 Classification | {report.p95_classification_ms:.0f}ms |",
            f"| P95 Tool Execution | {report.p95_tool_execution_ms:.0f}ms |",
            "",
        ]

        # Category results
        lines.append("## Results by Category")
        lines.append("")

        for cat, cat_report in report.categories.items():
            lines.append(f"### {cat} ({cat_report.total} tests)")
            lines.append("")
            lines.append("| Intent | Status | Classify (ms) | Tool (ms) | Error |")
            lines.append("|--------|--------|--------------|-----------|-------|")

            for r in cat_report.results:
                status = "PASS" if r.passed else "FAIL"
                error = r.error[:30] if r.error else "-"
                lines.append(
                    f"| {r.test_case.intent_type} | {status} | "
                    f"{r.classification_time_ms:.0f} | {r.tool_execution_time_ms:.0f} | {error} |"
                )
            lines.append("")

        # Failed tests detail
        if report.failed_tests:
            lines.append("## Failed Tests")
            lines.append("")
            lines.append("| Intent | Input | Expected | Actual | Error |")
            lines.append("|--------|-------|----------|--------|-------|")

            for r in report.failed_tests:
                input_short = r.test_case.user_input[:30] + "..."
                lines.append(
                    f"| {r.test_case.intent_type} | {input_short} | "
                    f"{r.test_case.intent_type} | {r.actual_intent} | {r.error or 'mismatch'} |"
                )
            lines.append("")

        # Monitoring metrics
        if report.monitoring_metrics:
            lines.append("## Monitoring Metrics")
            lines.append("")
            for key, value in report.monitoring_metrics.items():
                lines.append(f"- **{key}:** {value}")
            lines.append("")

        return "\n".join(lines)

    def save_report(self, report: FullTestReport, output_dir: str = "test_reports"):
        """Save report to files."""
        output_path = Path(__file__).parent / output_dir
        output_path.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Save markdown
        md_path = output_path / f"intent_tool_report_{timestamp}.md"
        md_content = self.generate_markdown_report(report)
        md_path.write_text(md_content, encoding="utf-8")
        logger.info(f"Markdown report saved to {md_path}")

        # Save JSON
        json_path = output_path / f"intent_tool_report_{timestamp}.json"
        json_data = {
            "timestamp": report.timestamp,
            "summary": {
                "total": report.total_tests,
                "passed": report.passed,
                "failed": report.failed,
                "pass_rate": report.pass_rate,
            },
            "latency": {
                "avg_classification_ms": report.avg_classification_ms,
                "avg_tool_execution_ms": report.avg_tool_execution_ms,
                "p95_classification_ms": report.p95_classification_ms,
                "p95_tool_execution_ms": report.p95_tool_execution_ms,
            },
            "categories": {
                cat: {
                    "total": cr.total,
                    "passed": cr.passed,
                    "pass_rate": cr.pass_rate,
                }
                for cat, cr in report.categories.items()
            },
            "monitoring": report.monitoring_metrics,
        }
        json_path.write_text(json.dumps(json_data, indent=2), encoding="utf-8")
        logger.info(f"JSON report saved to {json_path}")

        return md_path, json_path


async def main():
    """Run the full test suite."""
    print("=" * 60)
    print("VibeMind Intent-to-Tool Full Coverage Test Suite")
    print("=" * 60)
    print()

    # Show coverage stats
    stats = get_coverage_stats()
    print(f"Test cases loaded: {stats['total_tests']}")
    print(f"Unique intents: {stats['unique_intents']}")
    print(f"Categories: {list(stats['by_category'].keys())}")
    print()

    # Create and setup runner
    runner = IntentToolTestRunner()
    await runner.setup()
    print()

    # Run tests
    print("Running tests...")
    print("-" * 60)

    report = await runner.run_all_tests()

    print("-" * 60)
    print()

    # Print summary
    print("SUMMARY")
    print(f"  Total: {report.total_tests}")
    print(f"  Passed: {report.passed} ({report.pass_rate*100:.1f}%)")
    print(f"  Failed: {report.failed}")
    print(f"  Avg Classification: {report.avg_classification_ms:.0f}ms")
    print(f"  Avg Tool Execution: {report.avg_tool_execution_ms:.0f}ms")
    print()

    # Save reports
    md_path, json_path = runner.save_report(report)
    print(f"Reports saved to:")
    print(f"  {md_path}")
    print(f"  {json_path}")

    # Print failed tests
    if report.failed_tests:
        print()
        print("FAILED TESTS:")
        for r in report.failed_tests[:10]:  # Show first 10
            print(f"  - {r.test_case.intent_type}: {r.test_case.user_input[:40]}...")
            print(f"    Expected: {r.test_case.intent_type}, Got: {r.actual_intent}")
            if r.error:
                print(f"    Error: {r.error}")

    return report


if __name__ == "__main__":
    asyncio.run(main())
