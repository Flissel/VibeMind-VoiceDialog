"""
Context Source Metrics for Agent Simulation.

Tracks hit rates, relevance scores, and effectiveness of context sources:
- NotificationQueue: Immediate task results (5-min TTL)
- SystemContextStore: Recent actions (10-min window)
- ConversationMemory: Long-term SQLite history
"""

import statistics
from dataclasses import dataclass, field
from typing import List, Dict, Optional


@dataclass
class ContextSourceMetrics:
    """Metrics for a single context source."""
    source_name: str                        # "notification_queue", "system_context", "conversation_memory"
    queries: int = 0                        # How often queried
    hits: int = 0                           # How often relevant data found
    misses: int = 0                         # How often no data found
    relevance_scores: List[float] = field(default_factory=list)  # Relevance of found data
    latencies_ms: List[float] = field(default_factory=list)      # Query latencies
    evictions: int = 0                      # How often data was evicted/expired
    items_returned: List[int] = field(default_factory=list)      # Number of items per query

    @property
    def hit_rate(self) -> float:
        """Calculate hit rate as a ratio (0-1)."""
        if self.queries == 0:
            return 0.0
        return self.hits / self.queries

    @property
    def miss_rate(self) -> float:
        """Calculate miss rate as a ratio (0-1)."""
        return 1.0 - self.hit_rate

    @property
    def avg_relevance(self) -> float:
        """Average relevance score of returned results."""
        if not self.relevance_scores:
            return 0.0
        return statistics.mean(self.relevance_scores)

    @property
    def avg_latency_ms(self) -> float:
        """Average query latency in milliseconds."""
        if not self.latencies_ms:
            return 0.0
        return statistics.mean(self.latencies_ms)

    @property
    def avg_items_returned(self) -> float:
        """Average number of items returned per query."""
        if not self.items_returned:
            return 0.0
        return statistics.mean(self.items_returned)

    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            "source_name": self.source_name,
            "queries": self.queries,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": self.hit_rate,
            "avg_relevance": self.avg_relevance,
            "avg_latency_ms": self.avg_latency_ms,
            "avg_items_returned": self.avg_items_returned,
            "evictions": self.evictions,
        }


@dataclass
class AggregatedContextMetrics:
    """Aggregated context metrics across all sources."""
    total_queries: int = 0
    total_hits: int = 0
    total_misses: int = 0
    overall_hit_rate: float = 0.0
    most_useful_source: str = ""
    least_useful_source: str = ""
    per_source: Dict[str, Dict] = field(default_factory=dict)


class ContextMetricsCollector:
    """Collects and aggregates context source metrics."""

    # Standard context source names
    NOTIFICATION_QUEUE = "notification_queue"
    SYSTEM_CONTEXT = "system_context"
    CONVERSATION_MEMORY = "conversation_memory"

    def __init__(self):
        self._sources: Dict[str, ContextSourceMetrics] = {
            self.NOTIFICATION_QUEUE: ContextSourceMetrics(self.NOTIFICATION_QUEUE),
            self.SYSTEM_CONTEXT: ContextSourceMetrics(self.SYSTEM_CONTEXT),
            self.CONVERSATION_MEMORY: ContextSourceMetrics(self.CONVERSATION_MEMORY),
        }

    def record_query(
        self,
        source: str,
        hit: bool,
        relevance: float = 0.0,
        latency_ms: float = 0.0,
        items_count: int = 0
    ):
        """
        Record a context source query.

        Args:
            source: Name of the context source
            hit: Whether relevant data was found
            relevance: Relevance score of returned data (0-1)
            latency_ms: Query latency in milliseconds
            items_count: Number of items returned
        """
        # Create source if not exists
        if source not in self._sources:
            self._sources[source] = ContextSourceMetrics(source)

        metrics = self._sources[source]
        metrics.queries += 1

        if hit:
            metrics.hits += 1
            if relevance > 0:
                metrics.relevance_scores.append(relevance)
            if items_count > 0:
                metrics.items_returned.append(items_count)
        else:
            metrics.misses += 1
            metrics.items_returned.append(0)

        if latency_ms > 0:
            metrics.latencies_ms.append(latency_ms)

    def record_eviction(self, source: str, count: int = 1):
        """
        Record that items were evicted/expired from a context source.

        Args:
            source: Name of the context source
            count: Number of items evicted
        """
        if source not in self._sources:
            self._sources[source] = ContextSourceMetrics(source)
        self._sources[source].evictions += count

    def reset(self):
        """Clear all recorded metrics."""
        for source in self._sources.values():
            source.queries = 0
            source.hits = 0
            source.misses = 0
            source.relevance_scores = []
            source.latencies_ms = []
            source.evictions = 0
            source.items_returned = []

    def get_source(self, source: str) -> Optional[ContextSourceMetrics]:
        """Get metrics for a specific source."""
        return self._sources.get(source)

    def get_all_sources(self) -> List[ContextSourceMetrics]:
        """Get metrics for all sources."""
        return list(self._sources.values())

    def get_most_useful_source(self) -> str:
        """
        Determine which source is most useful based on hit rate.

        Returns:
            Name of the source with highest hit rate
        """
        active_sources = [s for s in self._sources.values() if s.queries > 0]
        if not active_sources:
            return ""
        return max(active_sources, key=lambda s: s.hit_rate).source_name

    def get_least_useful_source(self) -> str:
        """
        Determine which source is least useful based on hit rate.

        Returns:
            Name of the source with lowest hit rate
        """
        active_sources = [s for s in self._sources.values() if s.queries > 0]
        if not active_sources:
            return ""
        return min(active_sources, key=lambda s: s.hit_rate).source_name

    def get_sources_by_effectiveness(self) -> List[ContextSourceMetrics]:
        """
        Get sources sorted by effectiveness (hit rate * avg relevance).

        Returns:
            List of sources sorted by effectiveness score (descending)
        """
        def effectiveness(s: ContextSourceMetrics) -> float:
            if s.queries == 0:
                return 0.0
            return s.hit_rate * (s.avg_relevance if s.avg_relevance > 0 else 0.5)

        return sorted(self._sources.values(), key=effectiveness, reverse=True)

    def summarize(self) -> AggregatedContextMetrics:
        """Generate aggregated metrics summary."""
        # Calculate totals
        total_queries = sum(s.queries for s in self._sources.values())
        total_hits = sum(s.hits for s in self._sources.values())
        total_misses = sum(s.misses for s in self._sources.values())

        # Overall hit rate
        overall_hit_rate = total_hits / total_queries if total_queries > 0 else 0.0

        # Per-source breakdown
        per_source = {name: s.to_dict() for name, s in self._sources.items()}

        return AggregatedContextMetrics(
            total_queries=total_queries,
            total_hits=total_hits,
            total_misses=total_misses,
            overall_hit_rate=overall_hit_rate,
            most_useful_source=self.get_most_useful_source(),
            least_useful_source=self.get_least_useful_source(),
            per_source=per_source
        )


__all__ = [
    "ContextSourceMetrics",
    "AggregatedContextMetrics",
    "ContextMetricsCollector",
]
