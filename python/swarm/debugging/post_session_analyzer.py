"""
Post Session Analyzer - Automatic debugging after voice sessions

Analyzes completed voice sessions to identify issues and generate
diagnostic reports with proposed fixes.
"""

import os
import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from pathlib import Path

from swarm.debugging.diagnostic_report import (
    DiagnosticReport,
    SessionData,
    Issue,
    get_diagnostic_report_path,
)
from swarm.debugging.issue_detectors import run_all_detectors
from swarm.debugging.agent_execution_logger import get_agent_execution_logger

logger = logging.getLogger(__name__)


class PostSessionAnalyzer:
    """
    Analyzes completed voice sessions to identify issues.

    Gathers data from multiple sources:
    - Conversation messages from database
    - Intent classification logs
    - Tool execution logs
    - Error logs

    Then runs issue detectors to find problems and generate reports.
    """

    def __init__(self):
        """Initialize the analyzer with data sources."""
        self._conversation_repo = None
        self._db = None
        self._logs_base_path = os.path.join(
            os.path.dirname(__file__), "..", "..", "logs"
        )

    @property
    def conversation_repo(self):
        """Lazy-load conversation repository."""
        if self._conversation_repo is None:
            try:
                from data import ConversationRepository, get_database
                self._db = get_database()
                self._conversation_repo = ConversationRepository(self._db)
            except ImportError as e:
                logger.warning(f"[PostSessionAnalyzer] Could not load ConversationRepository: {e}")
        return self._conversation_repo

    def analyze(self, session_id: str) -> DiagnosticReport:
        """
        Analyze a completed session and generate a diagnostic report.

        Args:
            session_id: The session ID to analyze

        Returns:
            DiagnosticReport with findings and recommendations
        """
        logger.info(f"[PostSessionAnalyzer] Starting analysis for session: {session_id}")

        # 1. Gather all session data
        session_data = self._gather_session_data(session_id)

        # 2. Run all issue detectors
        issues = run_all_detectors(session_data)

        # 3. Prioritize issues by impact
        issues = self._prioritize_issues(issues)
        top_issue = issues[0] if issues else None

        # 4. Generate the report
        report = DiagnosticReport(
            session_id=session_id,
            created_at=datetime.utcnow(),
            duration_seconds=session_data.duration_seconds,
            total_messages=len(session_data.messages),
            user_messages=session_data.user_message_count,
            tools_called=len(session_data.tool_logs),
            errors_count=len(session_data.errors),
            issues=issues,
            top_issue=top_issue,
            summary=self._generate_summary(session_data, issues),
        )

        logger.info(
            f"[PostSessionAnalyzer] Analysis complete. "
            f"Found {len(issues)} issues. "
            f"Top issue: {top_issue.title if top_issue else 'None'}"
        )

        return report

    def _gather_session_data(self, session_id: str) -> SessionData:
        """
        Gather all available data for a session.

        Args:
            session_id: The session ID

        Returns:
            SessionData object with all gathered data
        """
        # Get session start/end times (approximate if not available)
        start_time = datetime.utcnow() - timedelta(hours=1)
        end_time = datetime.utcnow()

        # Gather messages from database
        messages = self._load_conversation_messages(session_id)

        # Gather intent logs
        intent_logs = self._load_intent_logs(session_id, start_time, end_time)

        # Gather tool logs
        tool_logs = self._load_tool_logs(session_id, start_time, end_time)

        # Gather agent execution logs
        agent_execution_logs = self._load_agent_execution_logs(session_id, start_time, end_time)

        # Gather errors
        errors = self._extract_errors(intent_logs, tool_logs, agent_execution_logs)

        # Try to get actual session times from messages
        if messages:
            first_msg_time = messages[0].get("timestamp")
            last_msg_time = messages[-1].get("timestamp")
            if first_msg_time:
                try:
                    start_time = datetime.fromisoformat(str(first_msg_time).replace("Z", "+00:00"))
                except:
                    pass
            if last_msg_time:
                try:
                    end_time = datetime.fromisoformat(str(last_msg_time).replace("Z", "+00:00"))
                except:
                    pass

        return SessionData(
            session_id=session_id,
            start_time=start_time,
            end_time=end_time,
            messages=messages,
            intent_logs=intent_logs,
            tool_logs=tool_logs,
            agent_execution_logs=agent_execution_logs,
            errors=errors,
        )

    def _load_conversation_messages(self, session_id: str) -> List[Dict[str, Any]]:
        """Load conversation messages from database."""
        if not self.conversation_repo:
            logger.debug("[PostSessionAnalyzer] ConversationRepository not available")
            return []

        try:
            messages = self.conversation_repo.get_session_messages(session_id)
            return [
                {
                    "role": m.role,
                    "content": m.content,
                    "timestamp": m.timestamp.isoformat() if hasattr(m, 'timestamp') else None,
                }
                for m in messages
            ]
        except Exception as e:
            logger.warning(f"[PostSessionAnalyzer] Could not load messages: {e}")
            return []

    def _load_intent_logs(
        self,
        session_id: str,
        start_time: datetime,
        end_time: datetime,
    ) -> List[Dict[str, Any]]:
        """Load intent classification logs."""
        logs = []
        intent_logs_path = os.path.join(self._logs_base_path, "intents")

        if not os.path.exists(intent_logs_path):
            logger.debug(f"[PostSessionAnalyzer] Intent logs path not found: {intent_logs_path}")
            return logs

        try:
            # Load from JSONL files
            for log_file in Path(intent_logs_path).glob("*.jsonl"):
                with open(log_file, "r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            entry = json.loads(line.strip())
                            # Filter by session ID if available
                            if entry.get("session_id") == session_id:
                                logs.append(entry)
                            # Or filter by time range
                            elif "timestamp" in entry:
                                entry_time = datetime.fromisoformat(entry["timestamp"].replace("Z", "+00:00"))
                                if start_time <= entry_time <= end_time:
                                    logs.append(entry)
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            logger.warning(f"[PostSessionAnalyzer] Error loading intent logs: {e}")

        return logs

    def _load_tool_logs(
        self,
        session_id: str,
        start_time: datetime,
        end_time: datetime,
    ) -> List[Dict[str, Any]]:
        """Load tool execution logs."""
        logs = []
        tool_logs_path = os.path.join(self._logs_base_path, "tools")

        if not os.path.exists(tool_logs_path):
            logger.debug(f"[PostSessionAnalyzer] Tool logs path not found: {tool_logs_path}")
            return logs

        try:
            # Load from JSONL files
            for log_file in Path(tool_logs_path).glob("*.jsonl"):
                with open(log_file, "r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            entry = json.loads(line.strip())
                            # Filter by session ID if available
                            if entry.get("session_id") == session_id:
                                logs.append(entry)
                            # Or filter by time range
                            elif "timestamp" in entry:
                                entry_time = datetime.fromisoformat(entry["timestamp"].replace("Z", "+00:00"))
                                if start_time <= entry_time <= end_time:
                                    logs.append(entry)
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            logger.warning(f"[PostSessionAnalyzer] Error loading tool logs: {e}")

        return logs

    def _load_agent_execution_logs(
        self,
        session_id: str,
        start_time: datetime,
        end_time: datetime,
    ) -> List[Dict[str, Any]]:
        """Load backend agent execution logs from JSONL files."""
        logs = []
        agent_logs_path = os.path.join(self._logs_base_path, "agents")

        if not os.path.exists(agent_logs_path):
            logger.debug(f"[PostSessionAnalyzer] Agent logs path not found: {agent_logs_path}")
            return logs

        try:
            # Load from JSONL files (format: agent_execution_YYYYMMDD.jsonl)
            for log_file in Path(agent_logs_path).glob("agent_execution_*.jsonl"):
                with open(log_file, "r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            entry = json.loads(line.strip())
                            # Filter by session ID if available
                            if entry.get("session_id") == session_id:
                                logs.append(entry)
                            # Or filter by time range
                            elif "timestamp" in entry:
                                entry_time = datetime.fromisoformat(entry["timestamp"].replace("Z", "+00:00"))
                                if start_time <= entry_time <= end_time:
                                    logs.append(entry)
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            logger.warning(f"[PostSessionAnalyzer] Error loading agent execution logs: {e}")

        return logs

    def _extract_errors(
        self,
        intent_logs: List[Dict],
        tool_logs: List[Dict],
        agent_execution_logs: List[Dict] = None,
    ) -> List[str]:
        """Extract error messages from logs."""
        errors = []

        for log in intent_logs:
            if log.get("error"):
                errors.append(str(log["error"]))
            if log.get("status") == "error":
                errors.append(log.get("message", "Intent classification error"))

        for log in tool_logs:
            if log.get("error"):
                errors.append(str(log["error"]))
            if log.get("status") in ("error", "failed"):
                errors.append(log.get("message", f"Tool {log.get('tool_name', 'unknown')} failed"))

        # Extract errors from agent execution logs
        if agent_execution_logs:
            for log in agent_execution_logs:
                if log.get("event_type") == "error":
                    error_msg = log.get("error", "Unknown error")
                    tool_name = log.get("tool_name", "unknown")
                    agent_name = log.get("agent_name", "unknown")
                    errors.append(f"[{agent_name}] {tool_name}: {error_msg}")

        return errors

    def _prioritize_issues(self, issues: List[Issue]) -> List[Issue]:
        """
        Sort issues by impact score (highest first).

        Impact = severity_weight * frequency * confidence
        """
        return sorted(
            issues,
            key=lambda i: i.calculate_impact_score(),
            reverse=True,
        )

    def _generate_summary(self, data: SessionData, issues: List[Issue]) -> str:
        """Generate a human-readable summary of the analysis."""
        parts = []

        # Session overview
        parts.append(
            f"Session lasted {data.duration_seconds:.0f}s with "
            f"{data.user_message_count} user messages and "
            f"{len(data.tool_logs)} tool calls."
        )

        # Issues summary
        if not issues:
            parts.append("No significant issues were detected.")
        else:
            issue_types = {}
            for issue in issues:
                t = issue.issue_type.value
                issue_types[t] = issue_types.get(t, 0) + 1

            parts.append(f"Found {len(issues)} issue(s):")
            for issue_type, count in issue_types.items():
                parts.append(f"  - {issue_type}: {count}")

        return "\n".join(parts)


def analyze_session(session_id: str, save_report: bool = True) -> DiagnosticReport:
    """
    Convenience function to analyze a session.

    Args:
        session_id: The session ID to analyze
        save_report: Whether to save the report to disk

    Returns:
        DiagnosticReport
    """
    analyzer = PostSessionAnalyzer()
    report = analyzer.analyze(session_id)

    if save_report:
        report_path = get_diagnostic_report_path(session_id)
        report.save(report_path)

    return report


# Singleton instance
_analyzer: Optional[PostSessionAnalyzer] = None


def get_post_session_analyzer() -> PostSessionAnalyzer:
    """Get or create the singleton PostSessionAnalyzer."""
    global _analyzer
    if _analyzer is None:
        _analyzer = PostSessionAnalyzer()
    return _analyzer


__all__ = [
    "PostSessionAnalyzer",
    "analyze_session",
    "get_post_session_analyzer",
]
