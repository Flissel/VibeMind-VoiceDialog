"""
Execution Validator Agent - Validates tool execution and triggers learning.

Part of the 3-Agent Enhancement Pipeline:
1. CollectorAgent - Accumulates short inputs
2. IntentEnhancer - Normalizes and enhances input
3. ExecutionValidator - Validates execution and triggers learning (THIS FILE)

Purpose:
- Monitor backend status for job completion
- Validate that tools actually executed
- Provide feedback to enhancement rules (evolutionary learning)
- Detect user corrections and update rules
"""

import asyncio
import time
import logging
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Callable
from enum import Enum

logger = logging.getLogger(__name__)


class ValidationStatus(Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CORRECTED = "corrected"


@dataclass
class ExecutionFeedback:
    """
    Feedback from an execution for rule learning.

    Captures all data needed to update enhancement rules
    based on whether the execution was successful.
    """
    job_id: str
    original_input: str
    enhanced_input: str
    rules_applied: List[str]
    detected_intent: str
    was_successful: bool

    # Optional: User correction if intent was wrong
    user_correction: Optional[str] = None
    expected_intent: Optional[str] = None

    # Metadata
    timestamp: float = field(default_factory=time.time)
    execution_time: Optional[float] = None
    error_message: Optional[str] = None


@dataclass
class ValidationResult:
    """Result of validating an execution."""
    valid: Optional[bool]  # None = still waiting
    status: ValidationStatus = ValidationStatus.PENDING
    result: Optional[Any] = None
    reason: Optional[str] = None
    execution_time: Optional[float] = None
    suggestion: Optional[str] = None


@dataclass
class PendingValidation:
    """Tracks a pending execution validation."""
    job_id: str
    event_type: str
    original_input: str
    enhanced_input: str
    rules_applied: List[str]
    expected_at: float
    timeout: float
    status: str = "waiting"


class ExecutionValidator:
    """
    Monitors backend status and validates tool execution.

    Integration Points:
    - Reads from NotificationQueue for job completion events
    - Reads from JobManager for job status
    - Triggers rule updates in IntentEnhancer

    Feedback Loop:
    1. Track expected execution (job_id, event_type)
    2. Wait for completion signal
    3. Validate success/failure
    4. Update enhancement rules based on result
    """

    def __init__(
        self,
        notification_queue=None,
        job_manager=None,
        enhancer=None,
        default_timeout: float = 5.0
    ):
        self.notification_queue = notification_queue
        self.job_manager = job_manager
        self.enhancer = enhancer
        self.default_timeout = default_timeout

        self.pending_validations: Dict[str, PendingValidation] = {}
        self.completed_feedback: List[ExecutionFeedback] = []

        # Callbacks
        self._on_success_callback: Optional[Callable] = None
        self._on_failure_callback: Optional[Callable] = None

        # Correction detection markers
        self.correction_markers = [
            "nein ich meinte",
            "nicht das",
            "falsch",
            "das andere",
            "ich wollte",
            "stattdessen",
            "nein das war",
            "das stimmt nicht"
        ]

    def set_enhancer(self, enhancer):
        """Set the IntentEnhancer for rule updates."""
        self.enhancer = enhancer

    def set_notification_queue(self, queue):
        """Set the NotificationQueue to monitor."""
        self.notification_queue = queue

    def set_job_manager(self, manager):
        """Set the JobManager to query."""
        self.job_manager = manager

    def on_success(self, callback: Callable):
        """Register callback for successful executions."""
        self._on_success_callback = callback

    def on_failure(self, callback: Callable):
        """Register callback for failed executions."""
        self._on_failure_callback = callback

    async def expect_execution(
        self,
        job_id: str,
        event_type: str,
        original_input: str,
        enhanced_input: str,
        rules_applied: List[str],
        timeout: Optional[float] = None
    ):
        """
        Register an expected tool execution for validation.

        Args:
            job_id: Unique job identifier
            event_type: Expected event type (e.g., "idea.create")
            original_input: User's original input
            enhanced_input: Enhanced/normalized input
            rules_applied: List of enhancement rule IDs applied
            timeout: Custom timeout in seconds
        """
        logger.debug("expect_execution: job_id=%s event_type=%s", job_id, event_type)
        self.pending_validations[job_id] = PendingValidation(
            job_id=job_id,
            event_type=event_type,
            original_input=original_input,
            enhanced_input=enhanced_input,
            rules_applied=rules_applied,
            expected_at=time.time(),
            timeout=timeout or self.default_timeout
        )

        logger.info(
            f"[Validator] Expecting execution: job={job_id}, "
            f"event={event_type}, rules={rules_applied}"
        )

    async def check_execution(self, job_id: str) -> ValidationResult:
        """
        Check if a registered execution completed.

        Returns:
            ValidationResult with status and details
        """
        logger.debug("check_execution: job_id=%s", job_id)
        if job_id not in self.pending_validations:
            return ValidationResult(
                valid=False,
                status=ValidationStatus.FAILED,
                reason="Job not registered"
            )

        validation = self.pending_validations[job_id]
        start_time = validation.expected_at

        # Check 1: Job Manager Status (if available)
        if self.job_manager:
            try:
                job = await self._get_job_status(job_id)
                if job and job.get("status") == "completed":
                    return ValidationResult(
                        valid=True,
                        status=ValidationStatus.SUCCESS,
                        result=job.get("result"),
                        execution_time=time.time() - start_time
                    )
                elif job and job.get("status") == "failed":
                    return ValidationResult(
                        valid=False,
                        status=ValidationStatus.FAILED,
                        reason=job.get("error", "Job failed"),
                        execution_time=time.time() - start_time
                    )
            except Exception as e:
                logger.warning(f"[Validator] Job manager check failed: {e}")

        # Check 2: Notification Queue (if available)
        if self.notification_queue:
            try:
                notifications = self._peek_notifications()
                for n in notifications:
                    if n.get("job_id") == job_id:
                        status = n.get("status", "completed")
                        return ValidationResult(
                            valid=status == "completed",
                            status=ValidationStatus.SUCCESS if status == "completed" else ValidationStatus.FAILED,
                            result=n.get("result"),
                            execution_time=time.time() - start_time
                        )
            except Exception as e:
                logger.warning(f"[Validator] Notification queue check failed: {e}")

        # Check 3: Timeout
        elapsed = time.time() - validation.expected_at
        if elapsed > validation.timeout:
            return ValidationResult(
                valid=False,
                status=ValidationStatus.TIMEOUT,
                reason=f"Execution timeout after {elapsed:.1f}s",
                suggestion="Tool may have failed silently"
            )

        # Still waiting
        return ValidationResult(
            valid=None,
            status=ValidationStatus.PENDING,
            reason=f"Waiting... ({elapsed:.1f}s)"
        )

    async def _get_job_status(self, job_id: str) -> Optional[Dict]:
        """Get job status from JobManager."""
        if not self.job_manager:
            return None

        if asyncio.iscoroutinefunction(self.job_manager.get_job):
            return await self.job_manager.get_job(job_id)
        else:
            return self.job_manager.get_job(job_id)

    def _peek_notifications(self) -> List[Dict]:
        """Peek at notification queue without clearing."""
        if not self.notification_queue:
            return []

        if hasattr(self.notification_queue, 'peek'):
            return self.notification_queue.peek()
        elif hasattr(self.notification_queue, 'get_all'):
            return self.notification_queue.get_all()

        return []

    async def validate_and_learn(
        self,
        job_id: str,
        force_result: Optional[bool] = None,
        user_feedback: Optional[str] = None
    ) -> ExecutionFeedback:
        """
        Validate execution and update enhancement rules.

        This is the main feedback loop entry point.

        Args:
            job_id: Job to validate
            force_result: Override validation result (for testing)
            user_feedback: User correction text (if any)

        Returns:
            ExecutionFeedback with all learning data
        """
        logger.debug("validate_and_learn: job_id=%s", job_id)
        if job_id not in self.pending_validations:
            raise ValueError(f"Unknown job: {job_id}")

        validation = self.pending_validations[job_id]

        # Get validation result
        if force_result is not None:
            was_successful = force_result
            result = ValidationResult(
                valid=force_result,
                status=ValidationStatus.SUCCESS if force_result else ValidationStatus.FAILED
            )
        else:
            result = await self.check_execution(job_id)
            was_successful = result.valid is True

        # Check for user correction
        user_correction = None
        expected_intent = None
        if user_feedback:
            if self.detect_correction(user_feedback):
                was_successful = False
                user_correction = user_feedback
                expected_intent = self._infer_expected_intent(user_feedback)

        # Create feedback
        feedback = ExecutionFeedback(
            job_id=job_id,
            original_input=validation.original_input,
            enhanced_input=validation.enhanced_input,
            rules_applied=validation.rules_applied,
            detected_intent=validation.event_type,
            was_successful=was_successful,
            user_correction=user_correction,
            expected_intent=expected_intent,
            execution_time=result.execution_time,
            error_message=result.reason if not was_successful else None
        )

        # Update enhancement rules
        await self._update_rules(feedback)

        # Store completed feedback
        self.completed_feedback.append(feedback)
        del self.pending_validations[job_id]

        # Trigger callbacks
        if was_successful and self._on_success_callback:
            await self._maybe_async_call(self._on_success_callback, feedback)
        elif not was_successful and self._on_failure_callback:
            await self._maybe_async_call(self._on_failure_callback, feedback)

        logger.info(
            f"[Validator] Validated job={job_id}: "
            f"success={was_successful}, rules_updated={len(feedback.rules_applied)}"
        )

        return feedback

    async def _update_rules(self, feedback: ExecutionFeedback):
        """Update enhancement rules based on feedback."""
        if not self.enhancer:
            logger.warning("[Validator] No enhancer set - skipping rule update")
            return

        # Update all applied rules
        self.enhancer.update_rules_batch(feedback.rules_applied, feedback.was_successful)

        # If user corrected, try to generate new rule
        if feedback.user_correction and not feedback.was_successful:
            new_rule = self.enhancer.add_rule_from_correction(
                original=feedback.original_input,
                corrected=feedback.user_correction
            )
            if new_rule:
                logger.info(f"[Validator] Generated new rule from correction: {new_rule.id}")

    def detect_correction(self, text: str) -> bool:
        """Detect if user input is a correction."""
        logger.debug("detect_correction: text=%s", text[:50])
        text_lower = text.lower()
        return any(marker in text_lower for marker in self.correction_markers)

    def _infer_expected_intent(self, correction_text: str) -> Optional[str]:
        """
        Try to infer what intent the user actually wanted.

        This is a simple heuristic - could be enhanced with LLM.
        """
        text_lower = correction_text.lower()

        # Simple keyword matching
        intent_keywords = {
            "idea.list": ["zeig", "liste", "alle ideen"],
            "idea.create": ["erstell", "neu", "hinzufüg"],
            "idea.delete": ["lösch", "entfern", "weg"],
            "bubble.enter": ["geh", "rein", "öffne"],
            "bubble.create": ["space erstell", "bubble erstell"],
            "idea.summarize": ["zusammenfass", "fass zusammen"],
            "idea.whitepaper": ["whitepaper", "paper"],
        }

        for intent, keywords in intent_keywords.items():
            if any(kw in text_lower for kw in keywords):
                return intent

        return None

    async def _maybe_async_call(self, func: Callable, *args):
        """Call function, handling both sync and async."""
        if asyncio.iscoroutinefunction(func):
            await func(*args)
        else:
            func(*args)

    def generate_feedback_text(self, result: ValidationResult) -> str:
        """Generate human-readable feedback text."""
        if result.status == ValidationStatus.SUCCESS:
            return f"Erfolgreich ausgefuehrt"
        elif result.status == ValidationStatus.FAILED:
            return f"Fehlgeschlagen: {result.reason}"
        elif result.status == ValidationStatus.TIMEOUT:
            return f"Zeitueberschreitung - bitte erneut versuchen"
        elif result.status == ValidationStatus.CORRECTED:
            return "Korrektur erkannt - Regel aktualisiert"
        else:
            return "Wird ausgefuehrt..."

    def get_pending_count(self) -> int:
        """Get number of pending validations."""
        return len(self.pending_validations)

    def get_stats(self) -> Dict[str, Any]:
        """Get validation statistics."""
        logger.debug("get_stats called")
        if not self.completed_feedback:
            return {
                "total": 0,
                "success_rate": 0.0,
                "corrections": 0
            }

        total = len(self.completed_feedback)
        successful = sum(1 for f in self.completed_feedback if f.was_successful)
        corrections = sum(1 for f in self.completed_feedback if f.user_correction)

        return {
            "total": total,
            "successful": successful,
            "failed": total - successful,
            "success_rate": successful / total if total > 0 else 0.0,
            "corrections": corrections,
            "pending": len(self.pending_validations)
        }

    def clear_history(self):
        """Clear completed feedback history."""
        self.completed_feedback.clear()


class EvolutionaryValidator(ExecutionValidator):
    """
    Extended validator with automatic rule evolution.

    Additional features:
    - Automatic rule pruning (remove bad rules)
    - Suggested new rules based on failure patterns
    - Periodic rule optimization
    """

    def __init__(self, *args, prune_threshold: float = 0.3, **kwargs):
        super().__init__(*args, **kwargs)
        self.prune_threshold = prune_threshold
        self.failure_patterns: List[Dict] = []

    async def validate_and_learn(self, *args, **kwargs) -> ExecutionFeedback:
        """Override to add evolutionary features."""
        feedback = await super().validate_and_learn(*args, **kwargs)

        # Track failure patterns
        if not feedback.was_successful:
            self.failure_patterns.append({
                "input": feedback.original_input,
                "intent": feedback.detected_intent,
                "expected": feedback.expected_intent,
                "timestamp": time.time()
            })

        # Periodic pruning (every 50 validations)
        if len(self.completed_feedback) % 50 == 0:
            await self._periodic_maintenance()

        return feedback

    async def _periodic_maintenance(self):
        """Run periodic maintenance tasks."""
        if self.enhancer:
            # Prune bad rules
            pruned = self.enhancer.prune_bad_rules(threshold=self.prune_threshold)
            if pruned > 0:
                logger.info(f"[EvoValidator] Pruned {pruned} underperforming rules")

            # Analyze failure patterns and suggest new rules
            suggestions = self._analyze_failures()
            if suggestions:
                logger.info(f"[EvoValidator] Suggested {len(suggestions)} new rules")

    def _analyze_failures(self) -> List[Dict]:
        """
        Analyze failure patterns to suggest new rules.

        Groups similar failures and identifies potential patterns.
        """
        # Keep recent failures only (last 24 hours)
        cutoff = time.time() - 86400
        recent = [f for f in self.failure_patterns if f["timestamp"] > cutoff]

        # Group by similar inputs (simple similarity)
        groups = {}
        for failure in recent:
            key = failure["input"][:20]  # Rough grouping
            if key not in groups:
                groups[key] = []
            groups[key].append(failure)

        # Find patterns with 3+ failures
        suggestions = []
        for key, failures in groups.items():
            if len(failures) >= 3:
                suggestions.append({
                    "pattern": failures[0]["input"],
                    "count": len(failures),
                    "common_expected": self._most_common([f.get("expected") for f in failures])
                })

        return suggestions

    def _most_common(self, items: List) -> Optional[str]:
        """Find most common item in list."""
        items = [i for i in items if i]
        if not items:
            return None
        return max(set(items), key=items.count)


# Singleton instance
_validator: Optional[ExecutionValidator] = None


def get_execution_validator() -> ExecutionValidator:
    """Get or create the singleton ExecutionValidator instance."""
    global _validator
    if _validator is None:
        _validator = EvolutionaryValidator()
    return _validator


def reset_execution_validator():
    """Reset the singleton instance."""
    global _validator
    _validator = None
