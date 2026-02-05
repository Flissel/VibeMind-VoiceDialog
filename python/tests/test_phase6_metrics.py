#!/usr/bin/env python
"""Test script for Phase 6 Extended Metrics."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from swarm.simulation import (
    MetricsCollector,
    ExtendedSimulationMetrics,
    LLMMetricsCollector,
    ToolMetricsCollector,
    ContextMetricsCollector,
    IntentAnalytics,
    SimulationReportGenerator
)

def test_extended_metrics():
    """Test all Phase 6 extended metrics components."""
    print("=" * 60)
    print("   Phase 6 Extended Metrics Test")
    print("=" * 60)

    # Test MetricsCollector with extended metrics
    mc = MetricsCollector()
    print("\n[OK] MetricsCollector initialized")

    # Record some test LLM calls
    mc.record_llm_call(
        {'usage': {'prompt_tokens': 100, 'completion_tokens': 50}},
        'anthropic/claude-3.5-haiku',
        500.0
    )
    mc.record_llm_call(
        {'usage': {'prompt_tokens': 200, 'completion_tokens': 100}},
        'anthropic/claude-sonnet-4',
        1200.0
    )
    print("[OK] LLM calls recorded")

    # Record tool calls
    mc.record_tool_call('bubble.create', True, 250.0)
    mc.record_tool_call('bubble.list', True, 120.0)
    mc.record_tool_call('idea.list', True, 180.0)
    mc.record_tool_call('idea.expand', False, 5000.0, 'Timeout error')
    mc.record_tool_call('idea.expand', True, 3500.0)
    print("[OK] Tool calls recorded")

    # Record context queries
    mc.record_context_hit('notification_queue')
    mc.record_context_hit('notification_queue')
    mc.record_context_miss('system_context')
    mc.record_context_hit('conversation_memory')
    print("[OK] Context queries recorded")

    # Generate extended metrics
    extended = mc.summarize_extended()
    print("[OK] Extended metrics generated")

    # Display results
    print("\n--- LLM Metrics ---")
    print(f"  Total API calls: {extended.llm.total_calls}")
    print(f"  Total tokens: {extended.llm.total_tokens}")
    print(f"  Estimated cost: ${extended.llm.total_cost_usd:.4f}")
    print(f"  Avg latency: {extended.llm.avg_latency_ms:.0f}ms")

    print("\n--- Tool Metrics ---")
    print(f"  Total calls: {extended.tools.total_calls}")
    print(f"  Success rate: {extended.tools.overall_success_rate:.1%}")
    print(f"  Total failures: {extended.tools.total_failures}")
    print(f"  Avg latency: {extended.tools.avg_latency_ms:.0f}ms")

    print("\n--- Context Metrics ---")
    print(f"  Total queries: {extended.context_sources.total_queries}")
    print(f"  Overall hit rate: {extended.context_sources.overall_hit_rate:.1%}")
    print(f"  Most useful: {extended.context_sources.most_useful_source}")

    print("\n--- Intent Analytics ---")
    print(f"  Total classifications: {extended.intent_analytics.total_classifications}")
    print(f"  Unique intents: {extended.intent_analytics.unique_intents}")

    # Test report generation
    print("\n--- Report Generator Test ---")
    report_gen = SimulationReportGenerator()

    # Test the new sections directly
    llm_section = report_gen._generate_llm_section(extended.llm)
    print(f"[OK] LLM section generated ({len(llm_section)} lines)")

    tool_section = report_gen._generate_tool_performance_section(extended.tools)
    print(f"[OK] Tool performance section generated ({len(tool_section)} lines)")

    ctx_section = report_gen._generate_context_analytics_section(extended.context_sources)
    print(f"[OK] Context analytics section generated ({len(ctx_section)} lines)")

    intent_section = report_gen._generate_intent_analytics_section(extended.intent_analytics)
    print(f"[OK] Intent analytics section generated ({len(intent_section)} lines)")

    print("\n" + "=" * 60)
    print("   ALL PHASE 6 TESTS PASSED!")
    print("=" * 60)

    return True

if __name__ == "__main__":
    success = test_extended_metrics()
    sys.exit(0 if success else 1)
