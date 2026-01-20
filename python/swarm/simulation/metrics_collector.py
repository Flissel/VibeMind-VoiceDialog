"""
Metrics Collector for Agent Simulation.

Collects and aggregates metrics from simulation runs including:
- Intent classification accuracy
- Tool execution success rates
- Latency statistics (P50, P95)
- Context retention rates
- LLM token usage and costs (Phase 6)
- Per-tool performance analytics (Phase 6)
- Context source effectiveness (Phase 6)
- Intent distribution and drift (Phase 6)
"""

import statistics
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime

# Import extended metrics collectors (Phase 6)
from swarm.simulation.llm_metrics import LLMMetricsCollector, AggregatedLLMMetrics
from swarm.simulation.tool_metrics import ToolMetricsCollector, AggregatedToolMetrics
from swarm.simulation.context_metrics import ContextMetricsCollector, AggregatedContextMetrics
from swarm.simulation.intent_analytics import IntentAnalytics, AggregatedIntentAnalytics


@dataclass
class TurnResult:
    """Result of a single conversation turn."""
    input_text: str
    expected_intent: Optional[str]
    actual_intent: str
    response: str
    latency_ms: float
    intent_match: bool
    error: Optional[str] = None
    context_state: Optional[Any] = None
    context_checks: Dict[str, bool] = field(default_factory=dict)
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class SimulationMetrics:
    """Aggregated metrics from a simulation run."""
    # Classification
    intent_accuracy: float
    intent_confusion: Dict[str, Dict[str, int]]  # expected -> actual -> count

    # Execution
    tool_success_rate: float
    error_count: int
    timeout_count: int

    # Latency
    latency_avg_ms: float
    latency_p50_ms: float
    latency_p95_ms: float
    latency_min_ms: float
    latency_max_ms: float

    # Context
    context_retention_rate: float  # How often rachel knew about previous actions
    context_checks_passed: int
    context_checks_total: int
    notification_queue_hits: int
    system_context_hits: int
    conversation_memory_hits: int

    # Totals
    total_turns: int
    successful_turns: int
    failed_turns: int


@dataclass
class ExtendedSimulationMetrics:
    """Extended metrics including Phase 6 additions."""
    # Base metrics
    base: SimulationMetrics

    # Phase 6: LLM Metrics
    llm: Optional[AggregatedLLMMetrics] = None

    # Phase 6: Tool Performance
    tools: Optional[AggregatedToolMetrics] = None

    # Phase 6: Context Source Analytics
    context_sources: Optional[AggregatedContextMetrics] = None

    # Phase 6: Intent Analytics
    intent_analytics: Optional[AggregatedIntentAnalytics] = None


class MetricsCollector:
    """Collects and aggregates simulation metrics."""

    def __init__(self):
        self.turns: List[TurnResult] = []
        self.context_source_hits: Dict[str, int] = {
            "notification_queue": 0,
            "system_context": 0,
            "conversation_memory": 0,
        }
        # Phase 6: Extended metrics collectors
        self.llm_metrics = LLMMetricsCollector()
        self.tool_metrics = ToolMetricsCollector()
        self.context_metrics = ContextMetricsCollector()
        self.intent_analytics = IntentAnalytics()

    def reset(self):
        """Reset all collected metrics."""
        self.turns = []
        self.context_source_hits = {
            "notification_queue": 0,
            "system_context": 0,
            "conversation_memory": 0,
        }
        # Phase 6: Reset extended collectors
        self.llm_metrics.reset()
        self.tool_metrics.reset()
        self.context_metrics.reset()
        self.intent_analytics.reset()

    def record_turn(self, result: TurnResult):
        """Record a single turn result."""
        self.turns.append(result)
        # Phase 6: Also record to intent analytics
        self.intent_analytics.record_classification(
            intent=result.actual_intent,
            correct=result.intent_match if result.expected_intent else True,
            confidence=0.0,  # Filled by LLM metrics if available
            latency_ms=result.latency_ms
        )

    def record_context_hit(self, source: str):
        """Record a hit from a context source."""
        if source in self.context_source_hits:
            self.context_source_hits[source] += 1
        # Phase 6: Also record to context metrics
        self.context_metrics.record_query(source, hit=True)

    def record_context_miss(self, source: str):
        """Record a miss from a context source (Phase 6)."""
        self.context_metrics.record_query(source, hit=False)

    def record_llm_call(self, response: dict, model: str, latency_ms: float, content: str = None):
        """Record an LLM API call (Phase 6)."""
        self.llm_metrics.record_from_response(response, model, latency_ms, content)

    def record_tool_call(self, tool_name: str, success: bool, latency_ms: float, error: str = None):
        """Record a tool execution (Phase 6)."""
        self.tool_metrics.record_call(tool_name, success, latency_ms, error)

    def summarize(self) -> SimulationMetrics:
        """Calculate all aggregated metrics."""
        if not self.turns:
            return self._empty_metrics()

        # Intent accuracy
        turns_with_expected = [t for t in self.turns if t.expected_intent]
        intent_matches = sum(1 for t in turns_with_expected if t.intent_match)
        intent_accuracy = intent_matches / len(turns_with_expected) if turns_with_expected else 0.0

        # Confusion matrix
        confusion = self._build_confusion_matrix()

        # Execution success
        errors = [t for t in self.turns if t.error]
        error_count = len(errors)
        tool_success_rate = (len(self.turns) - error_count) / len(self.turns) if self.turns else 0.0

        # Timeouts (>10s)
        timeout_count = sum(1 for t in self.turns if t.latency_ms > 10000)

        # Latency stats
        latencies = [t.latency_ms for t in self.turns]
        latency_avg = statistics.mean(latencies) if latencies else 0.0
        latency_p50 = statistics.median(latencies) if latencies else 0.0
        latency_p95 = self._percentile(latencies, 95)
        latency_min = min(latencies) if latencies else 0.0
        latency_max = max(latencies) if latencies else 0.0

        # Context retention
        context_checks_results = []
        for turn in self.turns:
            context_checks_results.extend(turn.context_checks.values())

        context_passed = sum(1 for c in context_checks_results if c)
        context_total = len(context_checks_results)
        context_retention = context_passed / context_total if context_total else 0.0

        return SimulationMetrics(
            intent_accuracy=intent_accuracy,
            intent_confusion=confusion,
            tool_success_rate=tool_success_rate,
            error_count=error_count,
            timeout_count=timeout_count,
            latency_avg_ms=latency_avg,
            latency_p50_ms=latency_p50,
            latency_p95_ms=latency_p95,
            latency_min_ms=latency_min,
            latency_max_ms=latency_max,
            context_retention_rate=context_retention,
            context_checks_passed=context_passed,
            context_checks_total=context_total,
            notification_queue_hits=self.context_source_hits["notification_queue"],
            system_context_hits=self.context_source_hits["system_context"],
            conversation_memory_hits=self.context_source_hits["conversation_memory"],
            total_turns=len(self.turns),
            successful_turns=len(self.turns) - error_count,
            failed_turns=error_count,
        )

    def _build_confusion_matrix(self) -> Dict[str, Dict[str, int]]:
        """Build confusion matrix from turn results."""
        confusion: Dict[str, Dict[str, int]] = {}

        for turn in self.turns:
            if not turn.expected_intent:
                continue

            expected = turn.expected_intent
            actual = turn.actual_intent

            if expected not in confusion:
                confusion[expected] = {}
            if actual not in confusion[expected]:
                confusion[expected][actual] = 0

            confusion[expected][actual] += 1

        return confusion

    def _percentile(self, data: List[float], percentile: int) -> float:
        """Calculate percentile of data."""
        if not data:
            return 0.0

        sorted_data = sorted(data)
        index = (percentile / 100) * (len(sorted_data) - 1)

        lower = int(index)
        upper = lower + 1

        if upper >= len(sorted_data):
            return sorted_data[-1]

        weight = index - lower
        return sorted_data[lower] * (1 - weight) + sorted_data[upper] * weight

    def _empty_metrics(self) -> SimulationMetrics:
        """Return empty metrics when no data."""
        return SimulationMetrics(
            intent_accuracy=0.0,
            intent_confusion={},
            tool_success_rate=0.0,
            error_count=0,
            timeout_count=0,
            latency_avg_ms=0.0,
            latency_p50_ms=0.0,
            latency_p95_ms=0.0,
            latency_min_ms=0.0,
            latency_max_ms=0.0,
            context_retention_rate=0.0,
            context_checks_passed=0,
            context_checks_total=0,
            notification_queue_hits=0,
            system_context_hits=0,
            conversation_memory_hits=0,
            total_turns=0,
            successful_turns=0,
            failed_turns=0,
        )

    def get_failures(self) -> List[TurnResult]:
        """Get all failed turns (intent mismatch or errors)."""
        failures = []
        for turn in self.turns:
            if turn.error or (turn.expected_intent and not turn.intent_match):
                failures.append(turn)
        return failures

    def get_slow_turns(self, threshold_ms: float = 5000) -> List[TurnResult]:
        """Get turns that exceeded latency threshold."""
        return [t for t in self.turns if t.latency_ms > threshold_ms]

    def summarize_extended(self) -> ExtendedSimulationMetrics:
        """Generate extended metrics including Phase 6 additions."""
        return ExtendedSimulationMetrics(
            base=self.summarize(),
            llm=self.llm_metrics.summarize(),
            tools=self.tool_metrics.summarize(),
            context_sources=self.context_metrics.summarize(),
            intent_analytics=self.intent_analytics.summarize()
        )


__all__ = [
    "MetricsCollector",
    "SimulationMetrics",
    "ExtendedSimulationMetrics",
    "TurnResult",
]
