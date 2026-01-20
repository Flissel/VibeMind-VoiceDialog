"""
Report Generator for Agent Simulation.

Generates comprehensive Markdown reports from simulation results.
"""

import statistics
from datetime import datetime
from typing import List, Dict, Any

from swarm.simulation.metrics_collector import (
    SimulationMetrics, ExtendedSimulationMetrics, TurnResult
)
from swarm.simulation.scenario_runner import ScenarioResult
from swarm.simulation.llm_metrics import AggregatedLLMMetrics
from swarm.simulation.tool_metrics import AggregatedToolMetrics
from swarm.simulation.context_metrics import AggregatedContextMetrics
from swarm.simulation.intent_analytics import AggregatedIntentAnalytics


class SimulationReportGenerator:
    """Generates Markdown reports from simulation results."""

    def generate(self, results: List[ScenarioResult], title: str = None) -> str:
        """
        Generate comprehensive report from scenario results.

        Args:
            results: List of ScenarioResults
            title: Optional custom title

        Returns:
            Markdown formatted report
        """
        lines = []

        # Header
        report_title = title or "VibeMind Agent Simulation Report"
        lines.extend([
            f"# {report_title}",
            "",
            f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Scenarios Run:** {len(results)}",
            f"**Total Duration:** {self._calc_total_duration(results):.1f}s",
            "",
        ])

        # Executive Summary
        lines.extend(self._generate_summary(results))

        # Per-Scenario Results
        lines.extend(self._generate_scenario_details(results))

        # Failure Analysis
        lines.extend(self._generate_failure_analysis(results))

        # Recommendations
        lines.extend(self._generate_recommendations(results))

        return "\n".join(lines)

    def _calc_total_duration(self, results: List[ScenarioResult]) -> float:
        """Calculate total duration of all scenarios."""
        return sum(r.completed_at - r.started_at for r in results)

    def _generate_summary(self, results: List[ScenarioResult]) -> List[str]:
        """Generate executive summary section."""
        lines = [
            "## Executive Summary",
            "",
        ]

        if not results:
            lines.append("No results to summarize.")
            return lines

        # Aggregate metrics
        all_metrics = [r.metrics for r in results]

        avg_accuracy = statistics.mean(m.intent_accuracy for m in all_metrics)
        avg_success = statistics.mean(m.tool_success_rate for m in all_metrics)
        avg_context = statistics.mean(m.context_retention_rate for m in all_metrics)
        avg_latency = statistics.mean(m.latency_avg_ms for m in all_metrics)
        p95_latencies = [m.latency_p95_ms for m in all_metrics]
        max_p95 = max(p95_latencies) if p95_latencies else 0

        total_turns = sum(m.total_turns for m in all_metrics)
        total_errors = sum(m.error_count for m in all_metrics)
        total_timeouts = sum(m.timeout_count for m in all_metrics)

        # Status indicator
        overall_status = "PASS" if avg_accuracy >= 0.85 and avg_success >= 0.9 else "NEEDS IMPROVEMENT"
        status_emoji = "+" if overall_status == "PASS" else "!"

        lines.extend([
            f"**Overall Status:** [{status_emoji}] {overall_status}",
            "",
            "| Metric | Value | Target | Status |",
            "|--------|-------|--------|--------|",
            f"| Intent Accuracy | {avg_accuracy*100:.1f}% | >=85% | {'OK' if avg_accuracy >= 0.85 else 'FAIL'} |",
            f"| Tool Success Rate | {avg_success*100:.1f}% | >=90% | {'OK' if avg_success >= 0.9 else 'FAIL'} |",
            f"| Context Retention | {avg_context*100:.1f}% | >=80% | {'OK' if avg_context >= 0.8 else 'FAIL'} |",
            f"| Avg Latency | {avg_latency:.0f}ms | <3000ms | {'OK' if avg_latency < 3000 else 'WARN'} |",
            f"| P95 Latency | {max_p95:.0f}ms | <10000ms | {'OK' if max_p95 < 10000 else 'WARN'} |",
            "",
            f"**Total Turns:** {total_turns}",
            f"**Errors:** {total_errors}",
            f"**Timeouts:** {total_timeouts}",
            "",
        ])

        # Context source usage
        total_notif_hits = sum(m.notification_queue_hits for m in all_metrics)
        total_sys_hits = sum(m.system_context_hits for m in all_metrics)
        total_mem_hits = sum(m.conversation_memory_hits for m in all_metrics)

        lines.extend([
            "### Context Source Usage",
            "",
            f"- NotificationQueue Hits: {total_notif_hits}",
            f"- SystemContextStore Hits: {total_sys_hits}",
            f"- ConversationMemory Hits: {total_mem_hits}",
            "",
        ])

        return lines

    def _generate_scenario_details(self, results: List[ScenarioResult]) -> List[str]:
        """Generate detailed results per scenario."""
        lines = [
            "## Scenario Results",
            "",
        ]

        for result in results:
            scenario = result.scenario
            metrics = result.metrics

            status = "PASS" if result.success else "FAIL"
            status_emoji = "+" if result.success else "x"

            lines.extend([
                f"### [{status_emoji}] {scenario.name}",
                "",
                f"**Description:** {scenario.description}",
                f"**Status:** {status}",
                f"**Duration:** {result.completed_at - result.started_at:.1f}s",
                "",
                "| Metric | Value |",
                "|--------|-------|",
                f"| Turns | {metrics.total_turns} |",
                f"| Intent Accuracy | {metrics.intent_accuracy*100:.1f}% |",
                f"| Tool Success | {metrics.tool_success_rate*100:.1f}% |",
                f"| Context Retention | {metrics.context_retention_rate*100:.1f}% |",
                f"| Avg Latency | {metrics.latency_avg_ms:.0f}ms |",
                f"| P95 Latency | {metrics.latency_p95_ms:.0f}ms |",
                "",
            ])

            # Show turns with issues
            failed_turns = [
                t for t in result.turn_results
                if not t.intent_match or t.error
            ]
            if failed_turns:
                lines.append("**Failed Turns:**")
                lines.append("")
                for i, turn in enumerate(failed_turns, 1):
                    lines.append(f"{i}. **Input:** \"{turn.input_text}\"")
                    if turn.expected_intent:
                        lines.append(f"   - Expected: `{turn.expected_intent}`")
                        lines.append(f"   - Got: `{turn.actual_intent}`")
                    if turn.error:
                        lines.append(f"   - Error: {turn.error}")
                lines.append("")

            # Show context check failures
            context_failures = []
            for turn in result.turn_results:
                for check, passed in turn.context_checks.items():
                    if not passed:
                        context_failures.append((turn.input_text, check))

            if context_failures:
                lines.append("**Context Check Failures:**")
                lines.append("")
                for input_text, check in context_failures:
                    lines.append(f"- After \"{input_text[:40]}...\": `{check}` FAILED")
                lines.append("")

        return lines

    def _generate_failure_analysis(self, results: List[ScenarioResult]) -> List[str]:
        """Generate failure analysis section."""
        lines = [
            "## Failure Analysis",
            "",
        ]

        # Collect all failures
        all_failures: List[TurnResult] = []
        for result in results:
            for turn in result.turn_results:
                if not turn.intent_match or turn.error:
                    all_failures.append(turn)

        if not all_failures:
            lines.append("No failures detected.")
            lines.append("")
            return lines

        lines.append(f"**Total Failures:** {len(all_failures)}")
        lines.append("")

        # Build confusion matrix
        confusion: Dict[str, Dict[str, int]] = {}
        for turn in all_failures:
            if turn.expected_intent and not turn.intent_match:
                expected = turn.expected_intent
                actual = turn.actual_intent
                if expected not in confusion:
                    confusion[expected] = {}
                if actual not in confusion[expected]:
                    confusion[expected][actual] = 0
                confusion[expected][actual] += 1

        if confusion:
            lines.append("### Intent Confusion Matrix")
            lines.append("")
            lines.append("| Expected | Predicted | Count |")
            lines.append("|----------|-----------|-------|")
            for expected, actuals in sorted(confusion.items()):
                for actual, count in sorted(actuals.items(), key=lambda x: -x[1]):
                    lines.append(f"| `{expected}` | `{actual}` | {count} |")
            lines.append("")

        # Error summary
        errors = [t for t in all_failures if t.error]
        if errors:
            lines.append("### Errors")
            lines.append("")
            for turn in errors[:10]:  # Limit to 10
                lines.append(f"- **\"{turn.input_text[:50]}...\"**: {turn.error}")
            lines.append("")

        return lines

    def _generate_recommendations(self, results: List[ScenarioResult]) -> List[str]:
        """Generate recommendations based on results."""
        lines = [
            "## Recommendations",
            "",
        ]

        recommendations = []

        # Analyze metrics
        all_metrics = [r.metrics for r in results]

        avg_accuracy = statistics.mean(m.intent_accuracy for m in all_metrics) if all_metrics else 0
        avg_context = statistics.mean(m.context_retention_rate for m in all_metrics) if all_metrics else 0
        avg_latency = statistics.mean(m.latency_avg_ms for m in all_metrics) if all_metrics else 0

        # Context issues
        if avg_context < 0.8:
            recommendations.append({
                "issue": "Low Context Retention",
                "details": f"Context retention is {avg_context*100:.0f}% (target: 80%)",
                "suggestions": [
                    "Increase NotificationQueue TTL from 5 minutes",
                    "Ensure SystemContextStore events are being recorded after tool execution",
                    "Check if ConversationMemory is properly storing interactions",
                    "Consider increasing result truncation limits in _format_notifications()"
                ]
            })

        # Accuracy issues
        if avg_accuracy < 0.85:
            recommendations.append({
                "issue": "Intent Classification Issues",
                "details": f"Intent accuracy is {avg_accuracy*100:.0f}% (target: 85%)",
                "suggestions": [
                    "Review failed classifications in the confusion matrix above",
                    "Add more post-processing rules for common misclassifications",
                    "Expand IntentClassifier prompt with more examples for problematic intents",
                    "Consider adding more context to classification (current bubble, recent actions)"
                ]
            })

        # Latency issues
        if avg_latency > 3000:
            recommendations.append({
                "issue": "High Latency",
                "details": f"Average latency is {avg_latency:.0f}ms (target: <3000ms)",
                "suggestions": [
                    "Profile slow operations to identify bottlenecks",
                    "Consider caching for repeated queries",
                    "Optimize database queries in tools",
                    "Use async execution where possible"
                ]
            })

        # Notification queue underutilization
        total_notif_hits = sum(m.notification_queue_hits for m in all_metrics)
        total_turns = sum(m.total_turns for m in all_metrics)
        if total_turns > 0 and total_notif_hits / total_turns < 0.3:
            recommendations.append({
                "issue": "NotificationQueue Underutilized",
                "details": f"Only {total_notif_hits} notification hits across {total_turns} turns",
                "suggestions": [
                    "Verify tools are pushing results to NotificationQueue",
                    "Check Rachel's process_input() is checking NotificationQueue",
                    "Ensure notifications aren't expiring before being consumed"
                ]
            })

        # Format recommendations
        if recommendations:
            for i, rec in enumerate(recommendations, 1):
                lines.append(f"### {i}. {rec['issue']}")
                lines.append("")
                lines.append(f"**Details:** {rec['details']}")
                lines.append("")
                lines.append("**Suggestions:**")
                for suggestion in rec['suggestions']:
                    lines.append(f"- {suggestion}")
                lines.append("")
        else:
            lines.append("No specific recommendations. All metrics are within acceptable ranges.")
            lines.append("")

        return lines

    def _generate_llm_section(self, llm: AggregatedLLMMetrics) -> List[str]:
        """Generate LLM Metrics section (Phase 6)."""
        lines = [
            "## LLM Metrics",
            "",
        ]

        if llm.total_calls == 0:
            lines.append("No LLM calls recorded.")
            lines.append("")
            return lines

        lines.extend([
            f"**Total API Calls:** {llm.total_calls}",
            f"**Total Tokens:** {llm.total_tokens:,}",
            f"**Estimated Cost:** ${llm.total_cost_usd:.4f}",
            f"**Avg Confidence:** {llm.avg_confidence:.1%}",
            f"**Avg Latency:** {llm.avg_latency_ms:.0f}ms",
            "",
            "### Token Breakdown",
            "",
            f"- Input Tokens: {llm.total_input_tokens:,}",
            f"- Output Tokens: {llm.total_output_tokens:,}",
            "",
        ])

        # Per-model breakdown
        if llm.by_model:
            lines.extend([
                "### Per-Model Usage",
                "",
                "| Model | Calls | Tokens | Cost | Avg Latency |",
                "|-------|-------|--------|------|-------------|",
            ])
            for model, stats in sorted(llm.by_model.items()):
                lines.append(
                    f"| {model} | {stats['calls']} | {stats['total_tokens']:,} | "
                    f"${stats['cost_usd']:.4f} | {stats['avg_latency_ms']:.0f}ms |"
                )
            lines.append("")

        return lines

    def _generate_tool_performance_section(self, tools: AggregatedToolMetrics) -> List[str]:
        """Generate Tool Performance section (Phase 6)."""
        lines = [
            "## Tool Performance",
            "",
        ]

        if tools.total_calls == 0:
            lines.append("No tool calls recorded.")
            lines.append("")
            return lines

        lines.extend([
            f"**Total Tool Calls:** {tools.total_calls}",
            f"**Overall Success Rate:** {tools.overall_success_rate:.1%}",
            f"**Avg Latency:** {tools.avg_latency_ms:.0f}ms",
            f"**Total Failures:** {tools.total_failures}",
            "",
        ])

        # Slowest tools
        if tools.slowest_tools:
            lines.extend([
                "### Slowest Tools (by P95 Latency)",
                "",
                "| Tool | P95 Latency | Avg Latency | Calls | Success Rate |",
                "|------|-------------|-------------|-------|--------------|",
            ])
            for tool in tools.slowest_tools[:5]:
                lines.append(
                    f"| {tool['tool_name']} | {tool['latency_p95_ms']:.0f}ms | "
                    f"{tool['latency_avg_ms']:.0f}ms | {tool['call_count']} | "
                    f"{tool['success_rate']:.1%} |"
                )
            lines.append("")

        # Least reliable tools
        if tools.least_reliable_tools:
            lines.extend([
                "### Least Reliable Tools",
                "",
            ])
            for tool in tools.least_reliable_tools[:5]:
                lines.append(
                    f"- **{tool['tool_name']}**: {tool['success_rate']:.1%} success "
                    f"({tool['failure_count']} failures)"
                )
                if tool.get('recent_errors'):
                    for err in tool['recent_errors'][:2]:
                        lines.append(f"  - Error: {err[:80]}...")
            lines.append("")

        # Most used tools
        if tools.most_used_tools:
            lines.extend([
                "### Most Used Tools",
                "",
                "| Tool | Calls | Success Rate | Avg Latency |",
                "|------|-------|--------------|-------------|",
            ])
            for tool in tools.most_used_tools[:5]:
                lines.append(
                    f"| {tool['tool_name']} | {tool['call_count']} | "
                    f"{tool['success_rate']:.1%} | {tool['latency_avg_ms']:.0f}ms |"
                )
            lines.append("")

        return lines

    def _generate_context_analytics_section(self, ctx: AggregatedContextMetrics) -> List[str]:
        """Generate Context Source Analytics section (Phase 6)."""
        lines = [
            "## Context Source Analytics",
            "",
        ]

        if ctx.total_queries == 0:
            lines.append("No context queries recorded.")
            lines.append("")
            return lines

        lines.extend([
            f"**Total Queries:** {ctx.total_queries}",
            f"**Overall Hit Rate:** {ctx.overall_hit_rate:.1%}",
            f"**Most Useful Source:** {ctx.most_useful_source or 'N/A'}",
            f"**Least Useful Source:** {ctx.least_useful_source or 'N/A'}",
            "",
            "### Per-Source Breakdown",
            "",
            "| Source | Queries | Hits | Hit Rate | Avg Relevance | Avg Latency |",
            "|--------|---------|------|----------|---------------|-------------|",
        ])

        for source_name, stats in sorted(ctx.per_source.items()):
            if stats['queries'] > 0:
                lines.append(
                    f"| {source_name} | {stats['queries']} | {stats['hits']} | "
                    f"{stats['hit_rate']:.1%} | {stats['avg_relevance']:.2f} | "
                    f"{stats['avg_latency_ms']:.0f}ms |"
                )

        lines.append("")

        # Add insight about context effectiveness
        if ctx.total_hits > 0:
            lines.append("### Insights")
            lines.append("")
            if ctx.most_useful_source:
                useful_stats = ctx.per_source.get(ctx.most_useful_source, {})
                lines.append(
                    f"- **{ctx.most_useful_source}** is the most effective context source "
                    f"with {useful_stats.get('hit_rate', 0):.1%} hit rate"
                )
            if ctx.least_useful_source and ctx.least_useful_source != ctx.most_useful_source:
                least_stats = ctx.per_source.get(ctx.least_useful_source, {})
                lines.append(
                    f"- **{ctx.least_useful_source}** has lowest effectiveness "
                    f"({least_stats.get('hit_rate', 0):.1%} hit rate) - consider optimization"
                )
            lines.append("")

        return lines

    def _generate_intent_analytics_section(self, intent: AggregatedIntentAnalytics) -> List[str]:
        """Generate Intent Distribution & Analytics section (Phase 6)."""
        lines = [
            "## Intent Analytics",
            "",
        ]

        if intent.total_classifications == 0:
            lines.append("No classifications recorded.")
            lines.append("")
            return lines

        lines.extend([
            f"**Total Classifications:** {intent.total_classifications}",
            f"**Unique Intents:** {intent.unique_intents}",
            f"**Overall Accuracy:** {intent.overall_accuracy:.1%}",
            f"**Avg Confidence:** {intent.avg_confidence:.1%}",
            "",
        ])

        # Intent distribution
        if intent.distribution:
            lines.extend([
                "### Intent Distribution",
                "",
                "| Intent | Count | Share |",
                "|--------|-------|-------|",
            ])
            total = sum(intent.distribution.values())
            sorted_dist = sorted(intent.distribution.items(), key=lambda x: -x[1])
            for intent_name, count in sorted_dist[:10]:
                share = count / total if total > 0 else 0
                lines.append(f"| {intent_name} | {count} | {share:.1%} |")
            lines.append("")

        # Top intents by accuracy
        if intent.top_intents:
            lines.extend([
                "### Top Intents Performance",
                "",
                "| Intent | Count | Accuracy | Avg Confidence |",
                "|--------|-------|----------|----------------|",
            ])
            for i_stats in intent.top_intents[:10]:
                lines.append(
                    f"| {i_stats['intent']} | {i_stats['count']} | "
                    f"{i_stats['accuracy']:.1%} | {i_stats['avg_confidence']:.1%} |"
                )
            lines.append("")

        # Lowest accuracy intents (problem areas)
        if intent.lowest_accuracy_intents:
            lines.extend([
                "### Problem Intents (Lowest Accuracy)",
                "",
            ])
            for i_stats in intent.lowest_accuracy_intents[:5]:
                if i_stats['accuracy'] < 1.0:
                    lines.append(
                        f"- **{i_stats['intent']}**: {i_stats['accuracy']:.1%} accuracy "
                        f"({i_stats['incorrect_count']} misclassifications)"
                    )
            lines.append("")

        # Drift analysis
        if intent.drift_analysis:
            drift = intent.drift_analysis
            lines.extend([
                "### Accuracy Drift Analysis",
                "",
            ])
            if drift.has_drift:
                direction_emoji = "📈" if drift.drift_direction == "improving" else "📉"
                lines.append(
                    f"{direction_emoji} **Drift Detected:** {drift.drift_direction.upper()}"
                )
                lines.append(
                    f"- Early Accuracy: {drift.early_accuracy:.1%}"
                )
                lines.append(
                    f"- Late Accuracy: {drift.late_accuracy:.1%}"
                )
                lines.append(
                    f"- Magnitude: {abs(drift.drift_magnitude):.1%}"
                )
            else:
                lines.append("✅ **No significant drift detected** - accuracy is stable")
            lines.append("")
            if drift.recommendation:
                lines.append(f"**Recommendation:** {drift.recommendation}")
                lines.append("")

        return lines

    def generate_extended(
        self,
        results: List[ScenarioResult],
        extended_metrics: ExtendedSimulationMetrics = None,
        title: str = None
    ) -> str:
        """
        Generate comprehensive report with Phase 6 extended metrics.

        Args:
            results: List of ScenarioResults
            extended_metrics: Optional aggregated extended metrics
            title: Optional custom title

        Returns:
            Markdown formatted report with all Phase 6 sections
        """
        lines = []

        # Header
        report_title = title or "VibeMind Agent Simulation Report (Extended)"
        lines.extend([
            f"# {report_title}",
            "",
            f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Scenarios Run:** {len(results)}",
            f"**Total Duration:** {self._calc_total_duration(results):.1f}s",
            "",
        ])

        # Executive Summary
        lines.extend(self._generate_summary(results))

        # Phase 6: Extended Metrics Sections
        if extended_metrics:
            if extended_metrics.llm:
                lines.extend(self._generate_llm_section(extended_metrics.llm))

            if extended_metrics.tools:
                lines.extend(self._generate_tool_performance_section(extended_metrics.tools))

            if extended_metrics.context_sources:
                lines.extend(self._generate_context_analytics_section(extended_metrics.context_sources))

            if extended_metrics.intent_analytics:
                lines.extend(self._generate_intent_analytics_section(extended_metrics.intent_analytics))

        # Per-Scenario Results
        lines.extend(self._generate_scenario_details(results))

        # Failure Analysis
        lines.extend(self._generate_failure_analysis(results))

        # Recommendations
        lines.extend(self._generate_recommendations(results))

        return "\n".join(lines)

    def generate_console_summary(self, results: List[ScenarioResult]) -> str:
        """Generate a concise console-friendly summary."""
        lines = []

        lines.append("=" * 60)
        lines.append("   SIMULATION RESULTS")
        lines.append("=" * 60)

        if not results:
            lines.append("No results.")
            return "\n".join(lines)

        # Aggregate metrics
        all_metrics = [r.metrics for r in results]
        avg_accuracy = statistics.mean(m.intent_accuracy for m in all_metrics)
        avg_success = statistics.mean(m.tool_success_rate for m in all_metrics)
        avg_context = statistics.mean(m.context_retention_rate for m in all_metrics)
        avg_latency = statistics.mean(m.latency_avg_ms for m in all_metrics)

        lines.append("")
        lines.append(f"Intent Accuracy:     {avg_accuracy*100:.1f}%")
        lines.append(f"Tool Success Rate:   {avg_success*100:.1f}%")
        lines.append(f"Context Retention:   {avg_context*100:.1f}%")
        lines.append(f"Avg Latency:         {avg_latency:.0f}ms")

        # Per scenario
        lines.append("")
        lines.append("Per Scenario:")
        for result in results:
            status = "PASS" if result.success else "FAIL"
            emoji = "+" if result.success else "x"
            lines.append(f"  [{emoji}] {result.scenario.name}: {status}")

        # Issues found
        total_errors = sum(m.error_count for m in all_metrics)
        total_failures = sum(
            1 for r in results for t in r.turn_results
            if not t.intent_match and t.expected_intent
        )

        if total_errors or total_failures:
            lines.append("")
            lines.append("Issues Found:")
            if total_failures:
                lines.append(f"  - Intent mismatches: {total_failures}")
            if total_errors:
                lines.append(f"  - Errors: {total_errors}")

        lines.append("")
        lines.append("=" * 60)

        return "\n".join(lines)


__all__ = [
    "SimulationReportGenerator",
]
