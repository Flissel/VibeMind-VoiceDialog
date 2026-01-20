"""
Evaluation Runner - Batch testing of intent classification.

Runs synthetic utterances through the classifier and compares
predicted vs expected results.
"""

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Dict, List, Any, Optional, Callable
from collections import defaultdict

from .intent_taxonomy import IntentCategory, INTENT_TAXONOMY, get_category
from .conversation_generator import (
    SyntheticUtterance,
    UTTERANCE_TEMPLATES,
    get_all_utterances,
    get_utterances_by_intent,
    get_utterances_by_category,
    get_utterances_by_difficulty,
)

logger = logging.getLogger(__name__)


@dataclass
class EvaluationResult:
    """Result of a single intent classification test."""
    id: str
    utterance: SyntheticUtterance
    predicted_intent: str
    predicted_payload: Dict[str, Any]
    confidence: float
    is_correct: bool
    intent_match: bool
    payload_match: bool
    latency_ms: float
    hypotheses: List[Dict] = field(default_factory=list)
    error: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "input_text": self.utterance.text,
            "expected_intent": self.utterance.expected_intent,
            "expected_payload": self.utterance.expected_payload,
            "predicted_intent": self.predicted_intent,
            "predicted_payload": self.predicted_payload,
            "confidence": self.confidence,
            "is_correct": self.is_correct,
            "intent_match": self.intent_match,
            "payload_match": self.payload_match,
            "latency_ms": self.latency_ms,
            "difficulty": self.utterance.difficulty,
            "category": self.utterance.category.value,
            "tags": self.utterance.tags,
            "error": self.error,
            "timestamp": self.timestamp,
        }


@dataclass
class EvaluationReport:
    """Aggregated evaluation report."""
    id: str
    name: str
    started_at: str
    completed_at: str

    # Overall metrics
    total_tests: int
    correct: int
    incorrect: int
    accuracy: float

    # Per-intent breakdown
    per_intent_accuracy: Dict[str, Dict[str, Any]]

    # Per-category breakdown
    per_category_accuracy: Dict[str, Dict[str, Any]]

    # Per-difficulty breakdown
    per_difficulty_accuracy: Dict[str, Dict[str, Any]]

    # Latency stats
    avg_latency_ms: float
    min_latency_ms: float
    max_latency_ms: float
    p95_latency_ms: float

    # Confusion matrix: {expected: {predicted: count}}
    confusion_matrix: Dict[str, Dict[str, int]]

    # Problem cases
    failures: List[Dict[str, Any]]

    # Configuration
    config: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

    def to_markdown(self) -> str:
        """Generate markdown report."""
        md = []
        md.append(f"# Intent Evaluation Report\n")
        md.append(f"**Run ID:** {self.id}")
        md.append(f"**Name:** {self.name}")
        md.append(f"**Started:** {self.started_at}")
        md.append(f"**Completed:** {self.completed_at}")
        md.append(f"**Total Tests:** {self.total_tests}")
        md.append(f"**Accuracy:** {self.accuracy * 100:.1f}%\n")

        # Category breakdown
        md.append("## Per-Category Accuracy\n")
        md.append("| Category | Tests | Correct | Accuracy |")
        md.append("|----------|-------|---------|----------|")
        for cat, stats in sorted(self.per_category_accuracy.items()):
            md.append(f"| {cat} | {stats['total']} | {stats['correct']} | {stats['accuracy']*100:.1f}% |")
        md.append("")

        # Difficulty breakdown
        md.append("## Per-Difficulty Accuracy\n")
        md.append("| Difficulty | Tests | Correct | Accuracy |")
        md.append("|------------|-------|---------|----------|")
        for diff, stats in self.per_difficulty_accuracy.items():
            md.append(f"| {diff} | {stats['total']} | {stats['correct']} | {stats['accuracy']*100:.1f}% |")
        md.append("")

        # Latency
        md.append("## Latency Statistics\n")
        md.append(f"- Average: {self.avg_latency_ms:.1f}ms")
        md.append(f"- Min: {self.min_latency_ms:.1f}ms")
        md.append(f"- Max: {self.max_latency_ms:.1f}ms")
        md.append(f"- P95: {self.p95_latency_ms:.1f}ms")
        md.append("")

        # Top failures
        if self.failures:
            md.append("## Top Failures\n")
            for i, fail in enumerate(self.failures[:10], 1):
                md.append(f"{i}. **Input:** \"{fail['input_text']}\"")
                md.append(f"   - Expected: `{fail['expected_intent']}`")
                md.append(f"   - Predicted: `{fail['predicted_intent']}`")
                md.append(f"   - Confidence: {fail.get('confidence', 0):.2f}")
                md.append("")

        return "\n".join(md)


class EvaluationRunner:
    """Runs batch evaluation tests."""

    def __init__(self, classifier=None, use_analysis_team: bool = False):
        """
        Initialize the evaluation runner.

        Args:
            classifier: IntentClassifier instance (optional, will create if None)
            use_analysis_team: Whether to use multi-agent analysis team
        """
        self._classifier = classifier
        self._use_analysis_team = use_analysis_team
        self._analysis_team = None
        self.results: List[EvaluationResult] = []

    @property
    def classifier(self):
        """Get or create classifier."""
        if self._classifier is None:
            from ..orchestrator.intent_classifier import get_intent_classifier
            self._classifier = get_intent_classifier()
        return self._classifier

    @property
    def analysis_team(self):
        """Get or create analysis team."""
        if self._use_analysis_team and self._analysis_team is None:
            try:
                from ..analysis.intent_analysis_team import IntentAnalysisTeam
                self._analysis_team = IntentAnalysisTeam()
            except ImportError:
                logger.warning("IntentAnalysisTeam not available")
        return self._analysis_team

    async def run_single(self, utterance: SyntheticUtterance) -> EvaluationResult:
        """
        Test a single utterance.

        Args:
            utterance: The synthetic utterance to test

        Returns:
            EvaluationResult with comparison
        """
        result_id = str(uuid.uuid4())[:8]
        start = time.time()
        error = None

        try:
            # Classify using the appropriate method
            if self._use_analysis_team and self.analysis_team:
                # Create mock context for evaluation
                from ..analysis.user_context import UserContext
                mock_context = UserContext(
                    user_id="test_user",
                    session_id="test_session",
                    current_space="test_space",
                    recent_actions=[],
                    mentioned_entities=[],
                    preferences={}
                )
                hypotheses = await self.analysis_team.analyze(utterance.text, mock_context)
                top_hypothesis = hypotheses[0] if hypotheses else None
                classification = {
                    "event_type": top_hypothesis.event_type if top_hypothesis else "conversation.unknown",
                    "payload": top_hypothesis.payload if top_hypothesis else {},
                    "confidence": top_hypothesis.confidence if top_hypothesis else 0.0,
                    "hypotheses": [h.to_dict() for h in hypotheses],
                }
            else:
                classification = await self.classifier.classify(utterance.text)

            predicted_intent = classification.get("event_type", "conversation.unknown")
            predicted_payload = classification.get("payload", {})
            confidence = classification.get("confidence", 0.0)
            hypotheses = classification.get("hypotheses", [])

        except Exception as e:
            logger.error(f"Classification error for '{utterance.text}': {e}")
            predicted_intent = "error"
            predicted_payload = {}
            confidence = 0.0
            hypotheses = []
            error = str(e)

        latency = (time.time() - start) * 1000

        # Compare results
        intent_match = predicted_intent == utterance.expected_intent
        payload_match = self._compare_payload(
            predicted_payload,
            utterance.expected_payload
        )
        # Primary metric is intent matching - payload is secondary
        # This gives us a clearer picture of classification accuracy
        is_correct = intent_match  # Focus on intent accuracy

        return EvaluationResult(
            id=result_id,
            utterance=utterance,
            predicted_intent=predicted_intent,
            predicted_payload=predicted_payload,
            confidence=confidence,
            is_correct=is_correct,
            intent_match=intent_match,
            payload_match=payload_match,
            latency_ms=latency,
            hypotheses=hypotheses,
            error=error,
        )

    def _compare_payload(self, predicted: Dict, expected: Dict) -> bool:
        """
        Compare predicted vs expected payload.

        Uses fuzzy matching for string values.
        """
        if not expected:
            return True  # No expected payload means any is acceptable

        for key, expected_value in expected.items():
            if key not in predicted:
                return False

            predicted_value = predicted[key]

            # Fuzzy string matching
            if isinstance(expected_value, str) and isinstance(predicted_value, str):
                # Check if expected is contained in predicted (case-insensitive)
                if expected_value.lower() not in predicted_value.lower():
                    # Also check if predicted is contained in expected
                    if predicted_value.lower() not in expected_value.lower():
                        return False
            elif expected_value != predicted_value:
                return False

        return True

    async def run_all(
        self,
        utterances: Optional[List[SyntheticUtterance]] = None,
        name: str = "Evaluation Run",
        progress_callback: Optional[Callable[['EvaluationResult'], None]] = None
    ) -> EvaluationReport:
        """
        Run all tests and generate report.

        Args:
            utterances: List of utterances to test (defaults to all)
            name: Name for this evaluation run
            progress_callback: Optional callback called after each test with the result

        Returns:
            EvaluationReport with aggregated metrics
        """
        if utterances is None:
            utterances = get_all_utterances()

        run_id = str(uuid.uuid4())[:8]
        started_at = datetime.now().isoformat()

        self.results = []
        logger.info(f"Starting evaluation run '{name}' with {len(utterances)} utterances")

        for i, utt in enumerate(utterances):
            result = await self.run_single(utt)
            self.results.append(result)

            # Call progress callback if provided
            if progress_callback:
                try:
                    progress_callback(result)
                except Exception as e:
                    logger.warning(f"Progress callback error: {e}")

            if (i + 1) % 10 == 0:
                logger.info(f"Progress: {i + 1}/{len(utterances)}")

        completed_at = datetime.now().isoformat()
        report = self._generate_report(run_id, name, started_at, completed_at)

        logger.info(f"Evaluation complete: {report.accuracy * 100:.1f}% accuracy")
        return report

    async def run_by_category(
        self,
        category: IntentCategory,
        name: Optional[str] = None
    ) -> EvaluationReport:
        """Run tests for a specific category."""
        utterances = get_utterances_by_category(category)
        name = name or f"Category: {category.value}"
        return await self.run_all(utterances, name)

    async def run_by_intent(
        self,
        intent: str,
        name: Optional[str] = None
    ) -> EvaluationReport:
        """Run tests for a specific intent."""
        utterances = get_utterances_by_intent(intent)
        name = name or f"Intent: {intent}"
        return await self.run_all(utterances, name)

    async def run_by_difficulty(
        self,
        difficulty: str,
        name: Optional[str] = None
    ) -> EvaluationReport:
        """Run tests for a specific difficulty level."""
        utterances = get_utterances_by_difficulty(difficulty)
        name = name or f"Difficulty: {difficulty}"
        return await self.run_all(utterances, name)

    def _generate_report(
        self,
        run_id: str,
        name: str,
        started_at: str,
        completed_at: str
    ) -> EvaluationReport:
        """Generate evaluation report from results."""

        total = len(self.results)
        correct = sum(1 for r in self.results if r.is_correct)
        incorrect = total - correct
        accuracy = correct / total if total > 0 else 0.0

        # Per-intent stats
        per_intent = defaultdict(lambda: {"total": 0, "correct": 0})
        for r in self.results:
            intent = r.utterance.expected_intent
            per_intent[intent]["total"] += 1
            if r.is_correct:
                per_intent[intent]["correct"] += 1

        per_intent_accuracy = {}
        for intent, stats in per_intent.items():
            acc = stats["correct"] / stats["total"] if stats["total"] > 0 else 0.0
            per_intent_accuracy[intent] = {
                "total": stats["total"],
                "correct": stats["correct"],
                "accuracy": acc,
            }

        # Per-category stats
        per_category = defaultdict(lambda: {"total": 0, "correct": 0})
        for r in self.results:
            cat = r.utterance.category.value
            per_category[cat]["total"] += 1
            if r.is_correct:
                per_category[cat]["correct"] += 1

        per_category_accuracy = {}
        for cat, stats in per_category.items():
            acc = stats["correct"] / stats["total"] if stats["total"] > 0 else 0.0
            per_category_accuracy[cat] = {
                "total": stats["total"],
                "correct": stats["correct"],
                "accuracy": acc,
            }

        # Per-difficulty stats
        per_difficulty = defaultdict(lambda: {"total": 0, "correct": 0})
        for r in self.results:
            diff = r.utterance.difficulty
            per_difficulty[diff]["total"] += 1
            if r.is_correct:
                per_difficulty[diff]["correct"] += 1

        per_difficulty_accuracy = {}
        for diff, stats in per_difficulty.items():
            acc = stats["correct"] / stats["total"] if stats["total"] > 0 else 0.0
            per_difficulty_accuracy[diff] = {
                "total": stats["total"],
                "correct": stats["correct"],
                "accuracy": acc,
            }

        # Latency stats
        latencies = [r.latency_ms for r in self.results]
        if latencies:
            avg_latency = sum(latencies) / len(latencies)
            min_latency = min(latencies)
            max_latency = max(latencies)
            sorted_latencies = sorted(latencies)
            p95_index = int(len(sorted_latencies) * 0.95)
            p95_latency = sorted_latencies[p95_index] if p95_index < len(sorted_latencies) else max_latency
        else:
            avg_latency = min_latency = max_latency = p95_latency = 0.0

        # Confusion matrix
        confusion = defaultdict(lambda: defaultdict(int))
        for r in self.results:
            expected = r.utterance.expected_intent
            predicted = r.predicted_intent
            confusion[expected][predicted] += 1

        confusion_matrix = {k: dict(v) for k, v in confusion.items()}

        # Failures
        failures = [
            r.to_dict() for r in self.results
            if not r.is_correct
        ]
        # Sort by confidence (lowest first - worst mistakes)
        failures.sort(key=lambda x: x.get("confidence", 0))

        return EvaluationReport(
            id=run_id,
            name=name,
            started_at=started_at,
            completed_at=completed_at,
            total_tests=total,
            correct=correct,
            incorrect=incorrect,
            accuracy=accuracy,
            per_intent_accuracy=per_intent_accuracy,
            per_category_accuracy=per_category_accuracy,
            per_difficulty_accuracy=per_difficulty_accuracy,
            avg_latency_ms=avg_latency,
            min_latency_ms=min_latency,
            max_latency_ms=max_latency,
            p95_latency_ms=p95_latency,
            confusion_matrix=confusion_matrix,
            failures=failures,
            config={
                "use_analysis_team": self._use_analysis_team,
            },
        )


async def run_evaluation(
    name: str = "Full Evaluation",
    utterances: Optional[List[SyntheticUtterance]] = None,
    use_analysis_team: bool = False,
) -> EvaluationReport:
    """
    Convenience function to run evaluation.

    Args:
        name: Name for this run
        utterances: Utterances to test (defaults to all)
        use_analysis_team: Whether to use multi-agent analysis

    Returns:
        EvaluationReport
    """
    runner = EvaluationRunner(use_analysis_team=use_analysis_team)
    return await runner.run_all(utterances, name)


__all__ = [
    "EvaluationResult",
    "EvaluationReport",
    "EvaluationRunner",
    "run_evaluation",
]
