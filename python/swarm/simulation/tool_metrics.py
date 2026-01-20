"""
Tool Metrics for Agent Simulation.

Tracks per-tool performance metrics including latency, success rates, and call frequency.
"""

import statistics
from dataclasses import dataclass, field
from typing import List, Dict, Optional


def _percentile(data: List[float], p: int) -> float:
    """Calculate the p-th percentile of a list."""
    if not data:
        return 0.0
    sorted_data = sorted(data)
    k = (len(sorted_data) - 1) * (p / 100)
    f = int(k)
    c = f + 1 if f + 1 < len(sorted_data) else f
    return sorted_data[f] + (k - f) * (sorted_data[c] - sorted_data[f]) if c != f else sorted_data[f]


@dataclass
class ToolMetrics:
    """Performance metrics for a single tool."""
    tool_name: str
    call_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    latencies_ms: List[float] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        """Calculate success rate as a ratio (0-1)."""
        if self.call_count == 0:
            return 1.0
        return self.success_count / self.call_count

    @property
    def failure_rate(self) -> float:
        """Calculate failure rate as a ratio (0-1)."""
        return 1.0 - self.success_rate

    @property
    def latency_min(self) -> float:
        """Minimum latency in milliseconds."""
        return min(self.latencies_ms) if self.latencies_ms else 0.0

    @property
    def latency_max(self) -> float:
        """Maximum latency in milliseconds."""
        return max(self.latencies_ms) if self.latencies_ms else 0.0

    @property
    def latency_avg(self) -> float:
        """Average latency in milliseconds."""
        return statistics.mean(self.latencies_ms) if self.latencies_ms else 0.0

    @property
    def latency_p50(self) -> float:
        """Median (P50) latency in milliseconds."""
        return statistics.median(self.latencies_ms) if self.latencies_ms else 0.0

    @property
    def latency_p95(self) -> float:
        """95th percentile latency in milliseconds."""
        return _percentile(self.latencies_ms, 95)

    @property
    def latency_p99(self) -> float:
        """99th percentile latency in milliseconds."""
        return _percentile(self.latencies_ms, 99)

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            "tool_name": self.tool_name,
            "call_count": self.call_count,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "success_rate": self.success_rate,
            "latency_avg_ms": self.latency_avg,
            "latency_p50_ms": self.latency_p50,
            "latency_p95_ms": self.latency_p95,
            "latency_p99_ms": self.latency_p99,
            "latency_min_ms": self.latency_min,
            "latency_max_ms": self.latency_max,
            "recent_errors": self.errors[-5:] if self.errors else [],
        }


@dataclass
class AggregatedToolMetrics:
    """Aggregated tool metrics across all tools."""
    total_calls: int = 0
    total_successes: int = 0
    total_failures: int = 0
    overall_success_rate: float = 1.0
    avg_latency_ms: float = 0.0
    slowest_tools: List[Dict] = field(default_factory=list)
    least_reliable_tools: List[Dict] = field(default_factory=list)
    most_used_tools: List[Dict] = field(default_factory=list)
    per_tool: Dict[str, Dict] = field(default_factory=dict)


class ToolMetricsCollector:
    """Collects and aggregates tool-specific performance metrics."""

    def __init__(self):
        self._tools: Dict[str, ToolMetrics] = {}

    def record_call(
        self,
        tool_name: str,
        success: bool,
        latency_ms: float,
        error: Optional[str] = None
    ):
        """
        Record a tool call.

        Args:
            tool_name: Name of the tool that was called
            success: Whether the call succeeded
            latency_ms: Duration of the call in milliseconds
            error: Error message if the call failed
        """
        if tool_name not in self._tools:
            self._tools[tool_name] = ToolMetrics(tool_name=tool_name)

        metrics = self._tools[tool_name]
        metrics.call_count += 1
        metrics.latencies_ms.append(latency_ms)

        if success:
            metrics.success_count += 1
        else:
            metrics.failure_count += 1
            if error:
                metrics.errors.append(error)

    def reset(self):
        """Clear all recorded metrics."""
        self._tools = {}

    def get_tool(self, tool_name: str) -> Optional[ToolMetrics]:
        """Get metrics for a specific tool."""
        return self._tools.get(tool_name)

    def get_all_tools(self) -> List[ToolMetrics]:
        """Get metrics for all tools."""
        return list(self._tools.values())

    def get_slowest_tools(self, limit: int = 5) -> List[ToolMetrics]:
        """
        Get the slowest tools by P95 latency.

        Args:
            limit: Maximum number of tools to return

        Returns:
            List of ToolMetrics sorted by P95 latency (descending)
        """
        return sorted(
            self._tools.values(),
            key=lambda t: t.latency_p95,
            reverse=True
        )[:limit]

    def get_least_reliable(self, limit: int = 5) -> List[ToolMetrics]:
        """
        Get the least reliable tools by success rate.

        Args:
            limit: Maximum number of tools to return

        Returns:
            List of ToolMetrics sorted by success rate (ascending)
        """
        return sorted(
            self._tools.values(),
            key=lambda t: t.success_rate
        )[:limit]

    def get_most_used(self, limit: int = 5) -> List[ToolMetrics]:
        """
        Get the most frequently used tools.

        Args:
            limit: Maximum number of tools to return

        Returns:
            List of ToolMetrics sorted by call count (descending)
        """
        return sorted(
            self._tools.values(),
            key=lambda t: t.call_count,
            reverse=True
        )[:limit]

    def summarize(self) -> AggregatedToolMetrics:
        """Generate aggregated metrics summary."""
        if not self._tools:
            return AggregatedToolMetrics()

        # Calculate totals
        total_calls = sum(t.call_count for t in self._tools.values())
        total_successes = sum(t.success_count for t in self._tools.values())
        total_failures = sum(t.failure_count for t in self._tools.values())

        # Overall success rate
        overall_success_rate = total_successes / total_calls if total_calls > 0 else 1.0

        # Average latency across all calls
        all_latencies = []
        for t in self._tools.values():
            all_latencies.extend(t.latencies_ms)
        avg_latency = statistics.mean(all_latencies) if all_latencies else 0.0

        # Get top lists
        slowest = [t.to_dict() for t in self.get_slowest_tools(5)]
        least_reliable = [
            t.to_dict() for t in self.get_least_reliable(5)
            if t.failure_count > 0  # Only include tools with failures
        ]
        most_used = [t.to_dict() for t in self.get_most_used(5)]

        # Per-tool breakdown
        per_tool = {name: m.to_dict() for name, m in self._tools.items()}

        return AggregatedToolMetrics(
            total_calls=total_calls,
            total_successes=total_successes,
            total_failures=total_failures,
            overall_success_rate=overall_success_rate,
            avg_latency_ms=avg_latency,
            slowest_tools=slowest,
            least_reliable_tools=least_reliable,
            most_used_tools=most_used,
            per_tool=per_tool
        )


__all__ = [
    "ToolMetrics",
    "AggregatedToolMetrics",
    "ToolMetricsCollector",
]
