"""Multi-space execution: pipeline, parallel, and mixed strategies."""

import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional

from .types import ExecutionStep, MultiSpaceStrategy

logger = logging.getLogger(__name__)

# Default timeout for entire multi-space operation
MULTI_SPACE_TIMEOUT = 120  # seconds


class MultiSpaceExecutor:
    """
    Executes multi-space requests with dependency-aware phasing.
    Replaces MinibookHub's ResultAggregator.track_multi() for pipeline/mixed.
    """

    def __init__(self, space_executor: Optional[Callable] = None):
        """
        Args:
            space_executor: async callable(space, payload) -> dict result.
                           Injected by IntentOrchestrator at init.
        """
        self._execute_fn = space_executor

    async def execute(
        self, strategy: MultiSpaceStrategy, payload: dict, timeout: float = MULTI_SPACE_TIMEOUT
    ) -> dict:
        """Execute multi-space strategy with phased coordination."""
        if not self._execute_fn:
            return {"success": False, "error": "No space executor configured"}

        results: Dict[str, Any] = {}
        phases = self._build_phases(strategy.steps)

        try:
            async with asyncio.timeout(timeout):
                for phase_idx, phase in enumerate(phases):
                    logger.info(
                        f"Multi-space phase {phase_idx + 1}/{len(phases)}: "
                        f"{[s.space for s in phase]}"
                    )
                    tasks = []
                    for step in phase:
                        enriched = self._inject_context(payload, step, results)
                        tasks.append(self._execute_step(step.space, enriched))

                    phase_results = await asyncio.gather(*tasks, return_exceptions=True)

                    for step, result in zip(phase, phase_results):
                        if isinstance(result, Exception):
                            logger.error(f"Space {step.space} failed: {result}")
                            results[step.space] = {
                                "success": False, "error": str(result)
                            }
                        else:
                            results[step.space] = result

        except asyncio.TimeoutError:
            logger.warning(f"Multi-space execution timed out after {timeout}s")
            results["_timeout"] = True

        return self._merge_results(results)

    async def _execute_step(self, space: str, payload: dict) -> dict:
        """Execute a single space step."""
        try:
            return await self._execute_fn(space, payload)
        except Exception as e:
            logger.error(f"Space {space} execution error: {e}")
            return {"success": False, "error": str(e), "space": space}

    def _build_phases(self, steps: List[ExecutionStep]) -> List[List[ExecutionStep]]:
        """
        Group steps into execution phases based on dependencies.
        Steps with no unresolved dependencies run in the same phase.
        """
        phases: List[List[ExecutionStep]] = []
        resolved: set = set()
        remaining = list(steps)

        while remaining:
            current_phase = []
            still_remaining = []

            for step in remaining:
                deps_met = all(dep in resolved for dep in step.depends_on)
                if deps_met:
                    current_phase.append(step)
                else:
                    still_remaining.append(step)

            if not current_phase:
                # Circular dependency or unresolvable -- force remaining into one phase
                logger.warning(f"Unresolvable dependencies: {[s.space for s in still_remaining]}")
                phases.append(still_remaining)
                break

            phases.append(current_phase)
            resolved.update(step.space for step in current_phase)
            remaining = still_remaining

        return phases

    def _inject_context(
        self, payload: dict, step: ExecutionStep, prior_results: Dict[str, Any]
    ) -> dict:
        """Enrich payload with results from dependent spaces."""
        enriched = {**payload}

        for dep_space in step.depends_on:
            dep_result = prior_results.get(dep_space)
            if not dep_result or not isinstance(dep_result, dict):
                continue

            for field_name in step.context_fields:
                if field_name in dep_result:
                    enriched[f"from_{dep_space}_{field_name}"] = dep_result[field_name]

            summary = dep_result.get("summary", dep_result.get("message", ""))
            if summary:
                enriched["prior_context"] = f"Ergebnis aus {dep_space}: {summary}"

        return enriched

    def _merge_results(self, results: Dict[str, Any]) -> dict:
        """Combine results from all spaces into a single response."""
        spaces = [k for k in results.keys() if not k.startswith("_")]
        success = all(
            results[s].get("success", False)
            for s in spaces
            if isinstance(results[s], dict)
        ) if spaces else False

        messages = []
        for space, result in results.items():
            if space.startswith("_"):
                continue
            if isinstance(result, dict):
                msg = result.get("message", result.get("summary", ""))
                if msg:
                    messages.append(f"[{space}] {msg}")

        return {
            "success": success,
            "multi_space": True,
            "spaces": spaces,
            "results": results,
            "message": " | ".join(messages) if messages else "Multi-space execution complete",
            "timed_out": results.get("_timeout", False),
        }
