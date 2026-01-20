"""
Scenario Runner for Agent Simulation.

Executes multi-turn conversation scenarios through the real swarm backend
and collects comprehensive metrics.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any

from swarm.simulation.metrics_collector import MetricsCollector, TurnResult, SimulationMetrics
from swarm.simulation.context_inspector import ContextInspector, ContextSnapshot

logger = logging.getLogger(__name__)


@dataclass
class ConversationTurn:
    """Single turn in a simulated conversation."""
    user_input: str
    expected_intent: Optional[str] = None
    expected_payload_contains: Dict[str, Any] = field(default_factory=dict)
    expected_success: bool = True
    expected_error: bool = False
    expected_result_contains: List[str] = field(default_factory=list)
    context_checks: List[str] = field(default_factory=list)
    delay_before_ms: int = 0


@dataclass
class SimulationScenario:
    """Multi-turn conversation scenario."""
    name: str
    description: str
    turns: List[ConversationTurn]
    setup: Optional[Callable] = None  # Pre-scenario setup (async)
    teardown: Optional[Callable] = None  # Post-scenario cleanup (async)
    tags: List[str] = field(default_factory=list)


@dataclass
class ScenarioResult:
    """Result of running a scenario."""
    scenario: SimulationScenario
    turn_results: List[TurnResult]
    metrics: SimulationMetrics
    started_at: float
    completed_at: float
    success: bool
    error: Optional[str] = None


class ScenarioRunner:
    """
    Runs simulation scenarios through the real swarm backend.

    Executes multi-turn conversations and collects:
    - Intent classification accuracy
    - Tool execution success/failure
    - Latency statistics
    - Context retention across turns
    """

    def __init__(self, orchestrator=None, verbose: bool = False):
        """
        Initialize scenario runner.

        Args:
            orchestrator: IntentOrchestrator instance (lazy-loaded if None)
            verbose: Print turn details during execution
        """
        self._orchestrator = orchestrator
        self.verbose = verbose
        self.metrics = MetricsCollector()
        self.context_inspector = ContextInspector()

    @property
    def orchestrator(self):
        """Lazy-load orchestrator."""
        if self._orchestrator is None:
            from swarm.orchestrator import get_orchestrator
            self._orchestrator = get_orchestrator()
        return self._orchestrator

    async def run_scenario(self, scenario: SimulationScenario) -> ScenarioResult:
        """
        Execute a full scenario and collect metrics.

        Args:
            scenario: The scenario to execute

        Returns:
            ScenarioResult with all turn results and aggregated metrics
        """
        started_at = time.time()
        results: List[TurnResult] = []
        self.metrics.reset()

        if self.verbose:
            print(f"\n{'='*60}")
            print(f"Scenario: {scenario.name}")
            print(f"Description: {scenario.description}")
            print(f"Turns: {len(scenario.turns)}")
            print(f"{'='*60}")

        # Setup
        if scenario.setup:
            try:
                if asyncio.iscoroutinefunction(scenario.setup):
                    await scenario.setup()
                else:
                    scenario.setup()
            except Exception as e:
                logger.error(f"Scenario setup failed: {e}")
                return ScenarioResult(
                    scenario=scenario,
                    turn_results=[],
                    metrics=self.metrics.summarize(),
                    started_at=started_at,
                    completed_at=time.time(),
                    success=False,
                    error=f"Setup failed: {e}"
                )

        # Execute turns
        error = None
        try:
            for i, turn in enumerate(scenario.turns):
                turn_result = await self._execute_turn(turn, i + 1, len(scenario.turns))
                results.append(turn_result)
                self.metrics.record_turn(turn_result)
        except Exception as e:
            error = str(e)
            logger.error(f"Scenario execution error: {e}")

        # Teardown
        if scenario.teardown:
            try:
                if asyncio.iscoroutinefunction(scenario.teardown):
                    await scenario.teardown()
                else:
                    scenario.teardown()
            except Exception as e:
                logger.warning(f"Scenario teardown error: {e}")

        completed_at = time.time()
        metrics = self.metrics.summarize()

        # Determine overall success
        success = (
            error is None and
            metrics.intent_accuracy >= 0.8 and
            metrics.tool_success_rate >= 0.9
        )

        if self.verbose:
            self._print_scenario_summary(scenario.name, metrics)

        return ScenarioResult(
            scenario=scenario,
            turn_results=results,
            metrics=metrics,
            started_at=started_at,
            completed_at=completed_at,
            success=success,
            error=error
        )

    def _check_context_sources(self, user_input: str):
        """
        Check all context sources and record hits/misses.

        Phase 7 Fix: Simulation showed 0% context retention because
        context sources weren't being checked before each turn.

        This method:
        1. Checks NotificationQueue for pending results
        2. Checks SystemContextStore for relevant recent events
        3. Checks ConversationMemory for conversation history
        """
        # 1. Check NotificationQueue
        notifications = self.context_inspector.get_pending_notifications()
        if notifications:
            self.metrics.record_context_hit("notification_queue")
            if self.verbose:
                print(f"      [Context] NotificationQueue: {len(notifications)} pending")
        else:
            self.metrics.record_context_miss("notification_queue")

        # 2. Check SystemContextStore
        relevant_events = self.context_inspector.check_context_contains(user_input)
        if relevant_events.get("system_context", False):
            self.metrics.record_context_hit("system_context")
            if self.verbose:
                print(f"      [Context] SystemContextStore: relevant events found")
        else:
            self.metrics.record_context_miss("system_context")

        # 3. Check ConversationMemory
        if relevant_events.get("conversation_memory", False):
            self.metrics.record_context_hit("conversation_memory")
            if self.verbose:
                print(f"      [Context] ConversationMemory: history available")
        else:
            self.metrics.record_context_miss("conversation_memory")

    async def _execute_turn(
        self,
        turn: ConversationTurn,
        turn_num: int,
        total_turns: int
    ) -> TurnResult:
        """Execute a single conversation turn."""
        # Optional delay
        if turn.delay_before_ms > 0:
            if self.verbose:
                print(f"\n  [Waiting {turn.delay_before_ms}ms...]")
            await asyncio.sleep(turn.delay_before_ms / 1000)

        if self.verbose:
            print(f"\n[{turn_num}/{total_turns}] \"{turn.user_input}\"")

        # Phase 7: Check all context sources BEFORE processing
        self._check_context_sources(turn.user_input)

        # Capture context state before
        context_before = self.context_inspector.snapshot()

        # Execute through orchestrator
        start = time.time()
        try:
            result = await self.orchestrator.process_intent(turn.user_input)
            latency = (time.time() - start) * 1000

            actual_intent = result.event_type
            response = result.response_hint
            error = result.error

        except Exception as e:
            latency = (time.time() - start) * 1000
            actual_intent = "error"
            response = str(e)
            error = str(e)

        # Check intent match
        intent_match = (
            turn.expected_intent is None or
            actual_intent == turn.expected_intent
        )

        # Capture context state after
        context_after = self.context_inspector.snapshot()

        # Run context checks
        context_check_results = {}
        for check in turn.context_checks:
            context_check_results[check] = self._run_context_check(check)

        # Record context source hits
        if context_after.notification_count > context_before.notification_count:
            self.metrics.record_context_hit("notification_queue")
        if context_after.system_context_count > context_before.system_context_count:
            self.metrics.record_context_hit("system_context")

        # Create turn result
        turn_result = TurnResult(
            input_text=turn.user_input,
            expected_intent=turn.expected_intent,
            actual_intent=actual_intent,
            response=response,
            latency_ms=latency,
            intent_match=intent_match,
            error=error,
            context_state=context_after,
            context_checks=context_check_results,
        )

        # Verbose output
        if self.verbose:
            self._print_turn_result(turn_result, turn)

        return turn_result

    def _run_context_check(self, check: str) -> bool:
        """
        Run a context check expression.

        Supported checks:
        - "current_bubble == 'Name'" - Check current bubble
        - "context_contains('text')" - Check if context has text
        - "notification_queue_has_results" - Check notification queue
        - "rachel_knows_about('topic')" - Check if any context has topic
        """
        check = check.strip()

        # current_bubble == 'Name'
        if check.startswith("current_bubble"):
            if "==" in check:
                expected = check.split("==")[1].strip().strip("'\"")
                return self.context_inspector.check_current_bubble(expected)
            return False

        # context_contains('text')
        if check.startswith("context_contains"):
            query = check.split("'")[1] if "'" in check else check.split('"')[1]
            results = self.context_inspector.check_context_contains(query)
            return any(results.values())

        # notification_queue_has_results
        if check == "notification_queue_has_results":
            notifications = self.context_inspector.get_pending_notifications()
            return len(notifications) > 0

        # rachel_knows_about('topic')
        if check.startswith("rachel_knows_about"):
            topic = check.split("'")[1] if "'" in check else check.split('"')[1]
            results = self.context_inspector.check_context_contains(topic)
            return any(results.values())

        logger.warning(f"Unknown context check: {check}")
        return False

    def _print_turn_result(self, result: TurnResult, turn: ConversationTurn):
        """Print verbose turn result."""
        intent_status = "OK" if result.intent_match else "FAIL"
        intent_emoji = "+" if result.intent_match else "x"

        print(f"      Intent: {result.actual_intent} [{intent_emoji} {intent_status}]")
        if turn.expected_intent and not result.intent_match:
            print(f"      (Expected: {turn.expected_intent})")
        print(f"      Latency: {result.latency_ms:.0f}ms")

        if result.error:
            print(f"      Error: {result.error}")

        # Context checks
        for check, passed in result.context_checks.items():
            status = "PASS" if passed else "FAIL"
            emoji = "+" if passed else "x"
            print(f"      Context: {check} [{emoji} {status}]")

    def _print_scenario_summary(self, name: str, metrics: SimulationMetrics):
        """Print scenario summary."""
        print(f"\n{'='*60}")
        print(f"Results: {name}")
        print(f"{'='*60}")
        print(f"  Intent Accuracy: {metrics.intent_accuracy*100:.1f}%")
        print(f"  Tool Success:    {metrics.tool_success_rate*100:.1f}%")
        print(f"  Context Retention: {metrics.context_retention_rate*100:.1f}%")
        print(f"  Avg Latency:     {metrics.latency_avg_ms:.0f}ms")
        print(f"  P95 Latency:     {metrics.latency_p95_ms:.0f}ms")
        if metrics.error_count > 0:
            print(f"  Errors:          {metrics.error_count}")
        if metrics.timeout_count > 0:
            print(f"  Timeouts:        {metrics.timeout_count}")

    async def run_all(
        self,
        scenarios: List[SimulationScenario]
    ) -> List[ScenarioResult]:
        """
        Run multiple scenarios sequentially.

        Args:
            scenarios: List of scenarios to execute

        Returns:
            List of ScenarioResults
        """
        results = []

        for scenario in scenarios:
            result = await self.run_scenario(scenario)
            results.append(result)

        return results


# Sync wrapper for convenience
def run_scenario_sync(scenario: SimulationScenario, verbose: bool = False) -> ScenarioResult:
    """Synchronous wrapper for running a single scenario."""
    runner = ScenarioRunner(verbose=verbose)
    return asyncio.run(runner.run_scenario(scenario))


__all__ = [
    "ScenarioRunner",
    "ConversationTurn",
    "SimulationScenario",
    "ScenarioResult",
    "run_scenario_sync",
]
