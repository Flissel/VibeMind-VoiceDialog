"""
Issue Detectors - Pattern detection for session analysis

Contains detector classes that analyze session data to identify
specific types of issues.
"""

import logging
import re
from typing import Dict, List, Any, Optional
from datetime import datetime
from abc import ABC, abstractmethod

from swarm.debugging.diagnostic_report import (
    Issue,
    Evidence,
    ProposedFix,
    IssueType,
    IssueSeverity,
    SessionData,
)

logger = logging.getLogger(__name__)


class BaseIssueDetector(ABC):
    """Base class for issue detectors."""

    @abstractmethod
    def detect(self, data: SessionData) -> List[Issue]:
        """
        Analyze session data and return detected issues.

        Args:
            data: SessionData containing messages, logs, etc.

        Returns:
            List of detected Issue objects
        """
        pass


class IntentMismatchDetector(BaseIssueDetector):
    """
    Detects intent misclassification issues.

    Looks for patterns like:
    - User repeating similar request after system response
    - User corrections ("nein", "nicht das", "ich meinte")
    - Low confidence classifications
    """

    # Correction phrases in German and English
    CORRECTION_PATTERNS = [
        r"\bnein\b",
        r"\bnicht das\b",
        r"\bich meinte\b",
        r"\bich meine\b",
        r"\bfalsch\b",
        r"\bwrong\b",
        r"\bno\s*,?\s*i\s*(meant|mean)\b",
        r"\bthat's not\b",
        r"\bdas stimmt nicht\b",
        r"\bich wollte\b",
        r"\beigentlich\b",
    ]

    def detect(self, data: SessionData) -> List[Issue]:
        issues = []

        # Pattern 1: User corrections
        issues.extend(self._detect_user_corrections(data))

        # Pattern 2: Repeated similar requests
        issues.extend(self._detect_repeated_requests(data))

        # Pattern 3: Low confidence classifications
        issues.extend(self._detect_low_confidence(data))

        return issues

    def _detect_user_corrections(self, data: SessionData) -> List[Issue]:
        """Detect when user explicitly corrects the system."""
        issues = []

        for i, msg in enumerate(data.messages):
            if msg.get("role") != "user":
                continue

            content = msg.get("content", "").lower()

            for pattern in self.CORRECTION_PATTERNS:
                if re.search(pattern, content, re.IGNORECASE):
                    # Found a correction - try to find what was misclassified
                    prev_intent = self._find_previous_intent(data, i)

                    evidence = [
                        Evidence(
                            description=f"User correction detected: '{content[:100]}'",
                            data={"message_index": i, "pattern": pattern},
                            timestamp=datetime.utcnow(),
                        )
                    ]

                    if prev_intent:
                        evidence.append(Evidence(
                            description=f"Previous intent: {prev_intent.get('event_type', 'unknown')}",
                            data=prev_intent,
                        ))

                    issue = Issue(
                        issue_type=IssueType.INTENT_MISCLASSIFICATION,
                        severity=IssueSeverity.HIGH,
                        title="Intent Misclassification (User Correction)",
                        description=f"User explicitly corrected the system response, indicating the intent was misclassified.",
                        evidence=evidence,
                        confidence=0.85,
                        user_input=data.messages[i - 1].get("content", "") if i > 0 else None,
                        actual_result=prev_intent.get("event_type") if prev_intent else "unknown",
                        proposed_fixes=self._suggest_intent_fix(prev_intent, content),
                    )
                    issues.append(issue)
                    break

        return issues

    def _detect_repeated_requests(self, data: SessionData) -> List[Issue]:
        """Detect when user repeats similar requests (frustration indicator)."""
        issues = []

        user_messages = [m for m in data.messages if m.get("role") == "user"]

        # Check for semantically similar messages within 3 turns
        for i in range(1, len(user_messages)):
            current = user_messages[i].get("content", "").lower()
            for j in range(max(0, i - 3), i):
                previous = user_messages[j].get("content", "").lower()

                similarity = self._calculate_similarity(current, previous)
                if similarity > 0.6:  # 60% word overlap
                    evidence = [
                        Evidence(
                            description=f"Similar request repeated: '{current[:50]}...'",
                            data={
                                "current_message": current,
                                "previous_message": previous,
                                "similarity": similarity,
                            },
                        )
                    ]

                    issue = Issue(
                        issue_type=IssueType.INTENT_MISCLASSIFICATION,
                        severity=IssueSeverity.MEDIUM,
                        title="Repeated Request (Possible Misclassification)",
                        description=f"User repeated a similar request, possibly indicating the first wasn't handled correctly.",
                        evidence=evidence,
                        confidence=0.7,
                        user_input=previous,
                    )
                    issues.append(issue)
                    break

        return issues

    def _detect_low_confidence(self, data: SessionData) -> List[Issue]:
        """Detect classifications with low confidence scores."""
        issues = []

        for log in data.intent_logs:
            confidence = log.get("confidence", 1.0)
            if confidence < 0.5:
                evidence = [
                    Evidence(
                        description=f"Low confidence classification: {confidence:.0%}",
                        data=log,
                    )
                ]

                issue = Issue(
                    issue_type=IssueType.INTENT_MISCLASSIFICATION,
                    severity=IssueSeverity.LOW,
                    title="Low Confidence Classification",
                    description=f"Intent was classified with low confidence ({confidence:.0%}), suggesting ambiguity.",
                    evidence=evidence,
                    confidence=0.5,
                    user_input=log.get("user_input"),
                    actual_result=log.get("event_type"),
                )
                issues.append(issue)

        return issues

    def _find_previous_intent(self, data: SessionData, message_index: int) -> Optional[Dict]:
        """Find the intent classification for the previous user message."""
        # Find the timestamp range for the previous message
        if message_index < 1:
            return None

        # Return the most recent intent log before this message
        for log in reversed(data.intent_logs):
            return log  # Return the most recent for simplicity

        return None

    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate word overlap similarity between two texts."""
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())

        if not words1 or not words2:
            return 0.0

        intersection = words1.intersection(words2)
        union = words1.union(words2)

        return len(intersection) / len(union) if union else 0.0

    def _suggest_intent_fix(self, intent_log: Optional[Dict], correction: str) -> List[ProposedFix]:
        """Suggest fixes for misclassified intents."""
        fixes = []

        if intent_log:
            event_type = intent_log.get("event_type", "unknown")
            user_input = intent_log.get("user_input", "")

            fixes.append(ProposedFix(
                description=f"Add example phrase to intent rules for better classification",
                file_path="python/data/intent_rule_repository.py",
                line_number=58,
                code_snippet=f'"{user_input}",  # Example for correct intent',
                confidence=0.7,
            ))

        return fixes


class ToolFailureDetector(BaseIssueDetector):
    """
    Detects tool execution failures.

    Looks for:
    - Exception stack traces in tool logs
    - "error" status in tool execution
    - Missing required parameters
    """

    def detect(self, data: SessionData) -> List[Issue]:
        issues = []

        for log in data.tool_logs:
            status = log.get("status", "success")

            if status in ("error", "failed", "exception"):
                evidence = [
                    Evidence(
                        description=f"Tool execution failed: {log.get('tool_name', 'unknown')}",
                        data=log,
                        timestamp=datetime.fromisoformat(log.get("timestamp")) if log.get("timestamp") else None,
                    )
                ]

                error_message = log.get("error", log.get("message", "Unknown error"))

                # Determine severity based on error type
                severity = IssueSeverity.HIGH
                if "timeout" in str(error_message).lower():
                    severity = IssueSeverity.MEDIUM

                issue = Issue(
                    issue_type=IssueType.TOOL_FAILURE,
                    severity=severity,
                    title=f"Tool Failure: {log.get('tool_name', 'unknown')}",
                    description=f"Tool execution failed with error: {error_message[:200]}",
                    evidence=evidence,
                    confidence=0.95,
                    actual_result=f"Error: {error_message}",
                    proposed_fixes=self._suggest_tool_fix(log),
                )
                issues.append(issue)

        # Also check for errors in session data
        for error in data.errors:
            evidence = [
                Evidence(
                    description=f"Error logged during session: {error[:100]}",
                    data={"error": error},
                )
            ]

            issue = Issue(
                issue_type=IssueType.TOOL_FAILURE,
                severity=IssueSeverity.HIGH,
                title="Session Error",
                description=error[:500],
                evidence=evidence,
                confidence=0.9,
            )
            issues.append(issue)

        return issues

    def _suggest_tool_fix(self, log: Dict) -> List[ProposedFix]:
        """Suggest fixes for tool failures."""
        fixes = []

        tool_name = log.get("tool_name", "")
        error = log.get("error", "")

        # Check for common error patterns
        if "import" in str(error).lower() or "module" in str(error).lower():
            fixes.append(ProposedFix(
                description="Check import statements and module availability",
                file_path=f"python/tools/{tool_name}.py" if tool_name else "python/tools/",
                confidence=0.6,
            ))

        if "api" in str(error).lower() or "key" in str(error).lower():
            fixes.append(ProposedFix(
                description="Verify API keys are configured in .env",
                file_path=".env",
                confidence=0.7,
            ))

        if "timeout" in str(error).lower():
            fixes.append(ProposedFix(
                description="Increase timeout or optimize the operation",
                file_path=f"python/tools/{tool_name}.py" if tool_name else "python/tools/",
                confidence=0.5,
            ))

        return fixes


class FrustrationDetector(BaseIssueDetector):
    """
    Detects signs of user frustration.

    Looks for:
    - Same request 3+ times
    - Escalating language
    - Session abandonment
    """

    # Frustration indicators in German and English
    FRUSTRATION_PHRASES = [
        r"\bverdammt\b",
        r"\bscheiße\b",
        r"\bmist\b",
        r"\bfunktioniert nicht\b",
        r"\bgeht nicht\b",
        r"\bdamn\b",
        r"\bshit\b",
        r"\bdoesn't work\b",
        r"\bwhy won't\b",
        r"\bstill not\b",
        r"\bimmer noch nicht\b",
        r"\bschon wieder\b",
    ]

    def detect(self, data: SessionData) -> List[Issue]:
        issues = []

        # Pattern 1: Frustration language
        issues.extend(self._detect_frustration_language(data))

        # Pattern 2: Short session with abrupt end
        issues.extend(self._detect_abandonment(data))

        return issues

    def _detect_frustration_language(self, data: SessionData) -> List[Issue]:
        """Detect explicit frustration in user messages."""
        issues = []
        frustration_count = 0

        for msg in data.messages:
            if msg.get("role") != "user":
                continue

            content = msg.get("content", "").lower()

            for pattern in self.FRUSTRATION_PHRASES:
                if re.search(pattern, content, re.IGNORECASE):
                    frustration_count += 1
                    break

        if frustration_count > 0:
            issue = Issue(
                issue_type=IssueType.USER_FRUSTRATION,
                severity=IssueSeverity.HIGH if frustration_count > 2 else IssueSeverity.MEDIUM,
                title="User Frustration Detected",
                description=f"User expressed frustration {frustration_count} time(s) during the session.",
                frequency=frustration_count,
                confidence=0.8,
                evidence=[
                    Evidence(
                        description=f"Frustration indicators found: {frustration_count} instances",
                        data={"count": frustration_count},
                    )
                ],
            )
            issues.append(issue)

        return issues

    def _detect_abandonment(self, data: SessionData) -> List[Issue]:
        """Detect potential session abandonment."""
        issues = []

        # Short session with few messages might indicate abandonment
        if data.duration_seconds < 60 and data.user_message_count >= 3:
            issue = Issue(
                issue_type=IssueType.USER_FRUSTRATION,
                severity=IssueSeverity.MEDIUM,
                title="Possible Session Abandonment",
                description=f"Short session ({data.duration_seconds:.0f}s) with {data.user_message_count} user messages might indicate the user gave up.",
                confidence=0.5,
                evidence=[
                    Evidence(
                        description=f"Session duration: {data.duration_seconds:.0f}s, Messages: {data.user_message_count}",
                        data={
                            "duration": data.duration_seconds,
                            "user_messages": data.user_message_count,
                        },
                    )
                ],
            )
            issues.append(issue)

        return issues


class EmptyResponseDetector(BaseIssueDetector):
    """
    Detects empty or unhelpful system responses.
    """

    MIN_RESPONSE_LENGTH = 10

    def detect(self, data: SessionData) -> List[Issue]:
        issues = []
        empty_count = 0

        for msg in data.messages:
            if msg.get("role") != "assistant":
                continue

            content = msg.get("content", "").strip()

            if len(content) < self.MIN_RESPONSE_LENGTH:
                empty_count += 1

        if empty_count > 0:
            issue = Issue(
                issue_type=IssueType.EMPTY_RESPONSE,
                severity=IssueSeverity.MEDIUM,
                title="Empty/Short Responses",
                description=f"System gave {empty_count} empty or very short response(s).",
                frequency=empty_count,
                confidence=0.75,
                evidence=[
                    Evidence(
                        description=f"Found {empty_count} responses shorter than {self.MIN_RESPONSE_LENGTH} characters",
                        data={"count": empty_count},
                    )
                ],
            )
            issues.append(issue)

        return issues


# Registry of all detectors
ALL_DETECTORS: List[BaseIssueDetector] = [
    IntentMismatchDetector(),
    ToolFailureDetector(),
    FrustrationDetector(),
    EmptyResponseDetector(),
]


def run_all_detectors(data: SessionData) -> List[Issue]:
    """
    Run all detectors on the session data.

    Args:
        data: SessionData to analyze

    Returns:
        List of all detected issues
    """
    all_issues = []

    for detector in ALL_DETECTORS:
        try:
            issues = detector.detect(data)
            all_issues.extend(issues)
            logger.debug(f"[{detector.__class__.__name__}] Found {len(issues)} issues")
        except Exception as e:
            logger.error(f"[{detector.__class__.__name__}] Detection failed: {e}")

    return all_issues


__all__ = [
    "BaseIssueDetector",
    "IntentMismatchDetector",
    "ToolFailureDetector",
    "FrustrationDetector",
    "EmptyResponseDetector",
    "ALL_DETECTORS",
    "run_all_detectors",
]
