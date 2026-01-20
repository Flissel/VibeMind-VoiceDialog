"""
Learning Plugin - Adaptive Agent Capabilities

Plugin that enables agents to learn from interactions and adapt behavior.
"""

import asyncio
import logging
from typing import Dict, Any, Set
from collections import defaultdict
import statistics

from swarm.backend_agents.enhanced_base_agent import AgentPlugin, AgentCapability, EnhancedBaseAgent

logger = logging.getLogger(__name__)


class LearningPlugin(AgentPlugin):
    """
    Plugin that enables agents to learn from task performance and adapt behavior.

    Features:
    - Performance tracking per task type
    - Adaptive confidence thresholds
    - Pattern recognition for optimization
    - Predictive task routing
    """

    def __init__(self):
        self._agent: EnhancedBaseAgent = None
        self._task_performance: Dict[str, list] = defaultdict(list)
        self._adaptive_thresholds: Dict[str, float] = {}
        self._pattern_cache: Dict[str, Dict[str, Any]] = {}

    @property
    def name(self) -> str:
        return "learning"

    @property
    def capabilities(self) -> Set[AgentCapability]:
        return {AgentCapability.LEARNING, AgentCapability.TASK_EXECUTION}

    async def initialize(self, agent: EnhancedBaseAgent) -> None:
        """Initialize learning plugin."""
        self._agent = agent

        # Set up learning hooks
        agent._adaptation_rules.update({
            "confidence_threshold": self._adapt_confidence_threshold,
            "task_routing": self._optimize_task_routing,
            "resource_allocation": self._predict_resource_needs
        })

        logger.info("Learning plugin initialized")

    async def execute(self, task_type: str, payload: Dict[str, Any]) -> Any:
        """Execute task with learning-based optimization."""
        if task_type == "learning.analyze_performance":
            return await self._analyze_performance(payload)
        elif task_type == "learning.predict_success":
            return self._predict_task_success(payload)
        elif task_type == "learning.optimize_workflow":
            return await self._optimize_workflow(payload)

        return None  # Not handled by this plugin

    async def cleanup(self) -> None:
        """Cleanup learning resources."""
        self._task_performance.clear()
        self._adaptive_thresholds.clear()
        self._pattern_cache.clear()
        logger.info("Learning plugin cleaned up")

    async def record_task_result(
        self,
        task_type: str,
        success: bool,
        response_time: float,
        context: Dict[str, Any]
    ) -> None:
        """Record task execution result for learning."""
        performance_data = {
            "success": success,
            "response_time": response_time,
            "context": context,
            "timestamp": asyncio.get_event_loop().time()
        }

        self._task_performance[task_type].append(performance_data)

        # Keep only recent data (last 1000 executions)
        if len(self._task_performance[task_type]) > 1000:
            self._task_performance[task_type] = self._task_performance[task_type][-500:]

        # Update adaptive thresholds
        await self._update_adaptive_thresholds(task_type)

    async def _update_adaptive_thresholds(self, task_type: str) -> None:
        """Update adaptive confidence thresholds based on performance."""
        performances = self._task_performance[task_type][-100:]  # Last 100

        if len(performances) < 10:
            return  # Need minimum data

        success_rate = sum(1 for p in performances if p["success"]) / len(performances)
        avg_response_time = statistics.mean(p["response_time"] for p in performances)

        # Adaptive threshold: higher success rate = lower threshold
        base_threshold = 0.6
        success_bonus = (success_rate - 0.5) * 0.4  # Max ±0.2 adjustment
        time_penalty = min(avg_response_time / 10.0, 0.2)  # Penalty for slow responses

        self._adaptive_thresholds[task_type] = max(0.3, min(0.9, base_threshold + success_bonus - time_penalty))

    def get_adaptive_threshold(self, task_type: str) -> float:
        """Get adaptive confidence threshold for task type."""
        return self._adaptive_thresholds.get(task_type, 0.6)  # Default 60%

    async def _analyze_performance(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze performance patterns."""
        task_type = payload.get("task_type")
        if not task_type or task_type not in self._task_performance:
            return {"error": "No performance data available"}

        performances = self._task_performance[task_type]

        response_times = [p["response_time"] for p in performances]
        success_count = sum(1 for p in performances if p["success"])

        return {
            "task_type": task_type,
            "total_executions": len(performances),
            "success_rate": success_count / len(performances),
            "avg_response_time": statistics.mean(response_times),
            "median_response_time": statistics.median(response_times),
            "min_response_time": min(response_times),
            "max_response_time": max(response_times),
            "adaptive_threshold": self.get_adaptive_threshold(task_type)
        }

    def _predict_task_success(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Predict success probability for a task."""
        task_type = payload.get("task_type")
        context = payload.get("context", {})

        if task_type not in self._task_performance:
            return {"prediction": 0.5, "confidence": 0.0}  # Neutral prediction

        performances = self._task_performance[task_type][-50:]  # Recent performances

        # Simple prediction based on recent success rate
        recent_success_rate = sum(1 for p in performances if p["success"]) / len(performances)

        # Context-based adjustments
        context_bonus = 0.0
        if context.get("high_priority"):
            context_bonus += 0.1
        if context.get("similar_recent_tasks"):
            context_bonus += 0.05

        prediction = min(0.95, recent_success_rate + context_bonus)
        confidence = min(1.0, len(performances) / 50.0)  # Higher confidence with more data

        return {
            "prediction": prediction,
            "confidence": confidence,
            "based_on_executions": len(performances)
        }

    async def _optimize_workflow(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Optimize workflow based on learned patterns."""
        workflow_steps = payload.get("steps", [])

        optimizations = []

        for step in workflow_steps:
            task_type = step.get("task_type")
            if task_type in self._task_performance:
                perf_data = await self._analyze_performance({"task_type": task_type})

                # Suggest optimizations based on performance
                if perf_data.get("success_rate", 0) < 0.8:
                    optimizations.append({
                        "step": step.get("id"),
                        "suggestion": "Consider retry logic or alternative implementation",
                        "current_success_rate": perf_data["success_rate"]
                    })

                if perf_data.get("avg_response_time", 0) > 5.0:
                    optimizations.append({
                        "step": step.get("id"),
                        "suggestion": "Consider parallel execution or optimization",
                        "current_avg_time": perf_data["avg_response_time"]
                    })

        return {
            "optimizations": optimizations,
            "total_suggestions": len(optimizations)
        }

    async def health_check(self) -> bool:
        """Plugin health check."""
        try:
            # Basic health checks
            assert self._agent is not None
            assert isinstance(self._task_performance, dict)
            assert isinstance(self._adaptive_thresholds, dict)
            return True
        except Exception:
            return False