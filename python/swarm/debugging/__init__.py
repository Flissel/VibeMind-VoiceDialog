"""
Debugging Module - Post-session analysis and issue detection

This module provides automatic debugging capabilities for VibeMind voice sessions.
It analyzes completed sessions to identify issues and generate diagnostic reports.

Components:
- PostSessionAnalyzer: Main analyzer that gathers data and runs detectors
- DiagnosticReport: Data structures for representing analysis results
- Issue Detectors: Pattern detectors for various issue types

Usage:
    from swarm.debugging import analyze_session, get_post_session_analyzer

    # Analyze a completed session
    report = analyze_session("session_123")

    # Save the report
    report.save("diagnostic_reports/session_123.md")

Environment Variables:
    ENABLE_AUTO_DEBUG: Set to "true" to enable automatic post-session analysis
    AUTO_DEBUG_MIN_MESSAGES: Minimum messages before analysis runs (default: 5)
    DIAGNOSTIC_REPORT_PATH: Base path for diagnostic reports (default: diagnostic_reports/)
"""

from swarm.debugging.diagnostic_report import (
    DiagnosticReport,
    SessionData,
    Issue,
    Evidence,
    ProposedFix,
    IssueType,
    IssueSeverity,
    get_diagnostic_report_path,
)

from swarm.debugging.issue_detectors import (
    BaseIssueDetector,
    IntentMismatchDetector,
    ToolFailureDetector,
    FrustrationDetector,
    EmptyResponseDetector,
    ALL_DETECTORS,
    run_all_detectors,
)

from swarm.debugging.post_session_analyzer import (
    PostSessionAnalyzer,
    analyze_session,
    get_post_session_analyzer,
)

from swarm.debugging.agent_execution_logger import (
    AgentExecutionLogger,
    AgentExecutionLog,
    get_agent_execution_logger,
)


__all__ = [
    # Report classes
    "DiagnosticReport",
    "SessionData",
    "Issue",
    "Evidence",
    "ProposedFix",
    "IssueType",
    "IssueSeverity",
    "get_diagnostic_report_path",
    # Detectors
    "BaseIssueDetector",
    "IntentMismatchDetector",
    "ToolFailureDetector",
    "FrustrationDetector",
    "EmptyResponseDetector",
    "ALL_DETECTORS",
    "run_all_detectors",
    # Main analyzer
    "PostSessionAnalyzer",
    "analyze_session",
    "get_post_session_analyzer",
    # Agent execution logger
    "AgentExecutionLogger",
    "AgentExecutionLog",
    "get_agent_execution_logger",
]
