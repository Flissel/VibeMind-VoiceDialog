"""
Agent Simulation Framework for VibeMind.

Provides tools for simulating complex multi-turn conversations
and capturing swarm backend metrics.

Components:
- ScenarioRunner: Executes multi-turn conversation scenarios
- MetricsCollector: Collects and aggregates simulation metrics
- ContextInspector: Inspects Rachel's context sources during simulation
- ReportGenerator: Generates Markdown reports from simulation results

Phase 6 Extended Metrics:
- LLMMetricsCollector: Token usage, costs, confidence scores
- ToolMetricsCollector: Per-tool performance analytics
- ContextMetricsCollector: Context source hit rates
- IntentAnalytics: Intent distribution and drift detection
"""

from swarm.simulation.metrics_collector import (
    MetricsCollector,
    SimulationMetrics,
    ExtendedSimulationMetrics,
    TurnResult,
)
from swarm.simulation.context_inspector import (
    ContextInspector,
    ContextSnapshot,
)
from swarm.simulation.scenario_runner import (
    ScenarioRunner,
    ConversationTurn,
    SimulationScenario,
    ScenarioResult,
)
from swarm.simulation.report_generator import (
    SimulationReportGenerator,
)
# Phase 6: Extended Metrics Collectors
from swarm.simulation.llm_metrics import (
    LLMMetrics,
    AggregatedLLMMetrics,
    LLMMetricsCollector,
    extract_llm_metrics,
    TOKEN_PRICES,
)
from swarm.simulation.tool_metrics import (
    ToolMetrics,
    AggregatedToolMetrics,
    ToolMetricsCollector,
)
from swarm.simulation.context_metrics import (
    ContextSourceMetrics,
    AggregatedContextMetrics,
    ContextMetricsCollector,
)
from swarm.simulation.intent_analytics import (
    IntentStats,
    ClassificationRecord,
    DriftAnalysis,
    AggregatedIntentAnalytics,
    IntentAnalytics,
)

__all__ = [
    # Metrics
    "MetricsCollector",
    "SimulationMetrics",
    "ExtendedSimulationMetrics",
    "TurnResult",
    # Context Inspector
    "ContextInspector",
    "ContextSnapshot",
    # Runner
    "ScenarioRunner",
    "ConversationTurn",
    "SimulationScenario",
    "ScenarioResult",
    # Report
    "SimulationReportGenerator",
    # Phase 6: LLM Metrics
    "LLMMetrics",
    "AggregatedLLMMetrics",
    "LLMMetricsCollector",
    "extract_llm_metrics",
    "TOKEN_PRICES",
    # Phase 6: Tool Metrics
    "ToolMetrics",
    "AggregatedToolMetrics",
    "ToolMetricsCollector",
    # Phase 6: Context Metrics
    "ContextSourceMetrics",
    "AggregatedContextMetrics",
    "ContextMetricsCollector",
    # Phase 6: Intent Analytics
    "IntentStats",
    "ClassificationRecord",
    "DriftAnalysis",
    "AggregatedIntentAnalytics",
    "IntentAnalytics",
]
