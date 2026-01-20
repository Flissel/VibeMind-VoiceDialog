"""
Intent Analytics for Agent Simulation.

Tracks intent classification distribution, accuracy trends, and drift detection.
"""

import statistics
import time
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from collections import Counter


@dataclass
class IntentStats:
    """Statistics for a single intent type."""
    intent: str
    count: int = 0
    correct_count: int = 0
    incorrect_count: int = 0
    avg_confidence: float = 0.0
    avg_latency_ms: float = 0.0

    @property
    def accuracy(self) -> float:
        """Calculate accuracy as a ratio (0-1)."""
        if self.count == 0:
            return 0.0
        return self.correct_count / self.count

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            "intent": self.intent,
            "count": self.count,
            "correct_count": self.correct_count,
            "incorrect_count": self.incorrect_count,
            "accuracy": self.accuracy,
            "avg_confidence": self.avg_confidence,
            "avg_latency_ms": self.avg_latency_ms,
        }


@dataclass
class ClassificationRecord:
    """Record of a single intent classification."""
    intent: str
    correct: bool
    confidence: float
    latency_ms: float
    timestamp: float


@dataclass
class DriftAnalysis:
    """Results of accuracy drift analysis."""
    has_drift: bool = False
    drift_direction: str = ""  # "improving", "degrading", "stable"
    drift_magnitude: float = 0.0  # Difference between early and late accuracy
    early_accuracy: float = 0.0
    late_accuracy: float = 0.0
    window_size: int = 0
    recommendation: str = ""


@dataclass
class AggregatedIntentAnalytics:
    """Aggregated intent analytics."""
    total_classifications: int = 0
    unique_intents: int = 0
    overall_accuracy: float = 0.0
    avg_confidence: float = 0.0
    distribution: Dict[str, int] = field(default_factory=dict)
    top_intents: List[Dict] = field(default_factory=list)
    lowest_accuracy_intents: List[Dict] = field(default_factory=list)
    drift_analysis: Optional[DriftAnalysis] = None
    per_intent: Dict[str, Dict] = field(default_factory=dict)


class IntentAnalytics:
    """Analyzes intent classification distribution and trends."""

    def __init__(self):
        self._records: List[ClassificationRecord] = []
        self._intents: Dict[str, List[ClassificationRecord]] = {}

    def record_classification(
        self,
        intent: str,
        correct: bool,
        confidence: float = 0.0,
        latency_ms: float = 0.0,
        timestamp: float = None
    ):
        """
        Record an intent classification.

        Args:
            intent: The classified intent type
            correct: Whether the classification was correct
            confidence: Confidence score (0-1)
            latency_ms: Classification latency in milliseconds
            timestamp: Unix timestamp (defaults to current time)
        """
        record = ClassificationRecord(
            intent=intent,
            correct=correct,
            confidence=confidence,
            latency_ms=latency_ms,
            timestamp=timestamp or time.time()
        )

        self._records.append(record)

        if intent not in self._intents:
            self._intents[intent] = []
        self._intents[intent].append(record)

    def reset(self):
        """Clear all recorded data."""
        self._records = []
        self._intents = {}

    def get_distribution(self) -> Dict[str, int]:
        """
        Get intent frequency distribution.

        Returns:
            Dictionary mapping intent names to counts
        """
        return {intent: len(records) for intent, records in self._intents.items()}

    def get_top_intents(self, limit: int = 10) -> List[IntentStats]:
        """
        Get the most frequently classified intents.

        Args:
            limit: Maximum number of intents to return

        Returns:
            List of IntentStats sorted by count (descending)
        """
        stats = []
        for intent, records in self._intents.items():
            correct = sum(1 for r in records if r.correct)
            confidences = [r.confidence for r in records if r.confidence > 0]
            latencies = [r.latency_ms for r in records if r.latency_ms > 0]

            stats.append(IntentStats(
                intent=intent,
                count=len(records),
                correct_count=correct,
                incorrect_count=len(records) - correct,
                avg_confidence=statistics.mean(confidences) if confidences else 0.0,
                avg_latency_ms=statistics.mean(latencies) if latencies else 0.0
            ))

        return sorted(stats, key=lambda s: s.count, reverse=True)[:limit]

    def get_lowest_accuracy_intents(self, limit: int = 5, min_samples: int = 3) -> List[IntentStats]:
        """
        Get intents with lowest accuracy.

        Args:
            limit: Maximum number of intents to return
            min_samples: Minimum number of samples required

        Returns:
            List of IntentStats sorted by accuracy (ascending)
        """
        stats = self.get_top_intents(limit=100)  # Get all stats

        # Filter by minimum samples and sort by accuracy
        filtered = [s for s in stats if s.count >= min_samples]
        return sorted(filtered, key=lambda s: s.accuracy)[:limit]

    def get_intent_stats(self, intent: str) -> Optional[IntentStats]:
        """
        Get statistics for a specific intent.

        Args:
            intent: The intent type to look up

        Returns:
            IntentStats or None if not found
        """
        records = self._intents.get(intent, [])
        if not records:
            return None

        correct = sum(1 for r in records if r.correct)
        confidences = [r.confidence for r in records if r.confidence > 0]
        latencies = [r.latency_ms for r in records if r.latency_ms > 0]

        return IntentStats(
            intent=intent,
            count=len(records),
            correct_count=correct,
            incorrect_count=len(records) - correct,
            avg_confidence=statistics.mean(confidences) if confidences else 0.0,
            avg_latency_ms=statistics.mean(latencies) if latencies else 0.0
        )

    def detect_accuracy_drift(self, window_size: int = 50) -> DriftAnalysis:
        """
        Detect if classification accuracy is drifting over time.

        Compares accuracy of early classifications vs recent classifications
        to detect improvement or degradation.

        Args:
            window_size: Number of samples in each window

        Returns:
            DriftAnalysis with drift detection results
        """
        if len(self._records) < window_size * 2:
            return DriftAnalysis(
                has_drift=False,
                drift_direction="stable",
                recommendation="Not enough data for drift analysis (need at least {} samples)".format(
                    window_size * 2
                )
            )

        # Sort by timestamp
        sorted_records = sorted(self._records, key=lambda r: r.timestamp)

        # Get early and late windows
        early_records = sorted_records[:window_size]
        late_records = sorted_records[-window_size:]

        # Calculate accuracies
        early_correct = sum(1 for r in early_records if r.correct)
        late_correct = sum(1 for r in late_records if r.correct)

        early_accuracy = early_correct / window_size
        late_accuracy = late_correct / window_size

        # Calculate drift
        drift_magnitude = late_accuracy - early_accuracy
        drift_threshold = 0.05  # 5% change is considered drift

        has_drift = abs(drift_magnitude) > drift_threshold

        if drift_magnitude > drift_threshold:
            direction = "improving"
            recommendation = "Accuracy is improving. Continue current approach."
        elif drift_magnitude < -drift_threshold:
            direction = "degrading"
            recommendation = "Accuracy is degrading. Review recent classifier changes or check for new input patterns."
        else:
            direction = "stable"
            recommendation = "Accuracy is stable."

        return DriftAnalysis(
            has_drift=has_drift,
            drift_direction=direction,
            drift_magnitude=drift_magnitude,
            early_accuracy=early_accuracy,
            late_accuracy=late_accuracy,
            window_size=window_size,
            recommendation=recommendation
        )

    def get_confusion_pairs(self, limit: int = 10) -> List[Tuple[str, str, int]]:
        """
        Get most common misclassification pairs.

        Note: This requires external data about expected intents.
        For now, returns empty list. Implement when integrated with evaluation.

        Returns:
            List of (expected, actual, count) tuples
        """
        # This would need expected vs actual data from evaluation
        # For now, return empty
        return []

    def summarize(self, drift_window: int = 50) -> AggregatedIntentAnalytics:
        """
        Generate comprehensive analytics summary.

        Args:
            drift_window: Window size for drift detection

        Returns:
            AggregatedIntentAnalytics with all metrics
        """
        if not self._records:
            return AggregatedIntentAnalytics()

        # Basic counts
        total = len(self._records)
        correct = sum(1 for r in self._records if r.correct)
        overall_accuracy = correct / total if total > 0 else 0.0

        # Confidence
        confidences = [r.confidence for r in self._records if r.confidence > 0]
        avg_confidence = statistics.mean(confidences) if confidences else 0.0

        # Distribution
        distribution = self.get_distribution()

        # Top intents
        top_intents = [s.to_dict() for s in self.get_top_intents(10)]

        # Lowest accuracy
        lowest_accuracy = [s.to_dict() for s in self.get_lowest_accuracy_intents(5)]

        # Drift analysis
        drift = self.detect_accuracy_drift(drift_window)

        # Per-intent breakdown
        per_intent = {}
        for intent in self._intents.keys():
            stats = self.get_intent_stats(intent)
            if stats:
                per_intent[intent] = stats.to_dict()

        return AggregatedIntentAnalytics(
            total_classifications=total,
            unique_intents=len(self._intents),
            overall_accuracy=overall_accuracy,
            avg_confidence=avg_confidence,
            distribution=distribution,
            top_intents=top_intents,
            lowest_accuracy_intents=lowest_accuracy,
            drift_analysis=drift,
            per_intent=per_intent
        )


__all__ = [
    "IntentStats",
    "ClassificationRecord",
    "DriftAnalysis",
    "AggregatedIntentAnalytics",
    "IntentAnalytics",
]
