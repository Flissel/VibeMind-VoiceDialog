"""
Test script for the Self-Debugging System

Tests:
1. DiagnosticReport creation and markdown generation
2. Issue detection patterns
3. PostSessionAnalyzer with mock data
"""

import sys
import os
from datetime import datetime, timedelta

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from swarm.debugging import (
    DiagnosticReport,
    SessionData,
    Issue,
    Evidence,
    ProposedFix,
    IssueType,
    IssueSeverity,
    run_all_detectors,
    PostSessionAnalyzer,
    get_diagnostic_report_path,
)


def test_diagnostic_report():
    """Test DiagnosticReport creation and markdown generation."""
    print("=" * 60)
    print("Test 1: DiagnosticReport Creation")
    print("=" * 60)

    # Create a sample issue
    issue = Issue(
        issue_type=IssueType.INTENT_MISCLASSIFICATION,
        severity=IssueSeverity.HIGH,
        title="Intent Misclassification: idea.auto_link",
        description="User requested to link ideas but system classified as bubble.enter",
        evidence=[
            Evidence(
                description="User correction detected: 'nein, verlinke die Ideen'",
                data={"message_index": 3, "pattern": "nein"},
            ),
            Evidence(
                description="Previous intent: bubble.enter (confidence: 0.45)",
                data={"event_type": "bubble.enter", "confidence": 0.45},
            ),
        ],
        proposed_fixes=[
            ProposedFix(
                description="Add example to intent rules",
                file_path="python/data/intent_rule_repository.py",
                line_number=73,
                code_snippet='"Gehe systematisch durch die Ideen und verlinke relevante",',
                confidence=0.8,
            )
        ],
        confidence=0.85,
        user_input="Gehe systematisch durch die Ideen und verlinke relevante",
        expected_result="idea.auto_link",
        actual_result="bubble.enter",
    )

    # Create a report
    report = DiagnosticReport(
        session_id="test_session_123",
        created_at=datetime.utcnow(),
        duration_seconds=123.5,
        total_messages=10,
        user_messages=5,
        tools_called=3,
        errors_count=1,
        issues=[issue],
        top_issue=issue,
        summary="Test session with 1 intent misclassification issue detected.",
    )

    # Generate markdown
    markdown = report.to_markdown()
    print(markdown[:1500])  # Print first 1500 chars
    print("\n... (truncated)")

    # Save to test file
    test_report_path = "diagnostic_reports/test_session_123.md"
    os.makedirs("diagnostic_reports", exist_ok=True)
    report.save(test_report_path)
    print(f"\n[OK] Report saved to: {test_report_path}")

    return True


def test_issue_detectors():
    """Test issue detection patterns."""
    print("\n" + "=" * 60)
    print("Test 2: Issue Detection Patterns")
    print("=" * 60)

    # Create mock session data with issues
    session_data = SessionData(
        session_id="test_detection_session",
        start_time=datetime.utcnow() - timedelta(minutes=5),
        end_time=datetime.utcnow(),
        messages=[
            {"role": "user", "content": "Verlinke die Ideen sinnvoll"},
            {"role": "assistant", "content": "Ich wechsle in den Space..."},
            {"role": "user", "content": "Nein, ich meinte verlinke die Ideen!"},  # Correction
            {"role": "assistant", "content": ""},  # Empty response
            {"role": "user", "content": "Das funktioniert nicht, verdammt!"},  # Frustration
        ],
        intent_logs=[
            {
                "user_input": "Verlinke die Ideen sinnvoll",
                "event_type": "bubble.enter",
                "confidence": 0.45,
            }
        ],
        tool_logs=[
            {
                "tool_name": "enter_bubble",
                "status": "error",
                "error": "Bubble not found",
            }
        ],
        errors=["Bubble not found"],
    )

    # Run all detectors
    issues = run_all_detectors(session_data)

    print(f"\nDetected {len(issues)} issues:")
    for i, issue in enumerate(issues, 1):
        print(f"\n{i}. {issue.title}")
        print(f"   Type: {issue.issue_type.value}")
        print(f"   Severity: {issue.severity.value}")
        print(f"   Confidence: {issue.confidence:.0%}")

    return len(issues) > 0


def test_post_session_analyzer():
    """Test PostSessionAnalyzer with mock data."""
    print("\n" + "=" * 60)
    print("Test 3: PostSessionAnalyzer")
    print("=" * 60)

    analyzer = PostSessionAnalyzer()

    # Run analysis (will use mock data since no real session exists)
    report = analyzer.analyze("test_analyzer_session")

    print(f"\nAnalysis complete for session: {report.session_id}")
    print(f"Duration: {report.duration_seconds:.0f}s")
    print(f"Messages: {report.total_messages}")
    print(f"Issues found: {len(report.issues)}")

    if report.top_issue:
        print(f"\nTop Issue: {report.top_issue.title}")
        print(f"Severity: {report.top_issue.severity.value}")
    else:
        print("\nNo issues detected (expected with no real data)")

    return True


def test_report_path():
    """Test report path generation."""
    print("\n" + "=" * 60)
    print("Test 4: Report Path Generation")
    print("=" * 60)

    path = get_diagnostic_report_path("session_abc123")
    print(f"Report path: {path}")

    return "diagnostic_reports" in path and "session_abc123" in path


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("Self-Debugging System Tests")
    print("=" * 60 + "\n")

    tests = [
        ("DiagnosticReport", test_diagnostic_report),
        ("Issue Detectors", test_issue_detectors),
        ("PostSessionAnalyzer", test_post_session_analyzer),
        ("Report Path", test_report_path),
    ]

    results = []
    for name, test_func in tests:
        try:
            success = test_func()
            results.append((name, success, None))
        except Exception as e:
            results.append((name, False, str(e)))
            import traceback
            traceback.print_exc()

    print("\n" + "=" * 60)
    print("Test Results")
    print("=" * 60)

    passed = 0
    for name, success, error in results:
        status = "[PASS]" if success else "[FAIL]"
        print(f"{status}: {name}")
        if error:
            print(f"       Error: {error}")
        if success:
            passed += 1

    print(f"\nTotal: {passed}/{len(tests)} tests passed")

    return passed == len(tests)


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
