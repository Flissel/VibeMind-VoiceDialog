"""task-openfang-0002 — cognitive voice routing must fail closed.

These regressions pin the execution authority boundary: a cognitive intent
either completes through Brain -> OpenFang -> an already registered canonical
agent, or reports a caller-visible failure.  It must never spawn an agent or
continue into a local routing/execution path.
"""
import asyncio
import inspect
from pathlib import Path

from swarm.orchestrator.result_formatter import OrchestrationResult
from swarm.routing.brain_openfang_bridge import BrainOpenFangBridge
from swarm.routing.space_agent_registry import RoutingRecipe


async def _brain_route(*_args, space: str = "ideas"):
    return {
        "space": space,
        "confidence": 1.0,
        "routing_id": "route-1",
    }


def _canonical_recipe(space: str = "ideas") -> RoutingRecipe:
    return RoutingRecipe(
        space=space,
        event_type="idea.create",
        agent="brain-ideas",
    )


class _Registry:
    def __init__(self, recipe):
        self.recipe = recipe

    def lookup(self, _space, _event_type):
        return self.recipe


class TestBrainOpenFangBridgeFailClosed:
    def test_brain_unavailable_is_a_caller_visible_failure(self, monkeypatch):
        bridge = BrainOpenFangBridge()

        async def brain_down(*_args):
            return None

        monkeypatch.setattr(bridge, "_route_via_brain", brain_down)

        result = asyncio.run(bridge.execute("notiere eine idee"))

        assert isinstance(result, OrchestrationResult)
        assert result.error == "brain_unavailable"

    def test_unknown_canonical_space_does_not_use_a_fallback_agent(self, monkeypatch):
        bridge = BrainOpenFangBridge()
        bridge._registry = _Registry(recipe=None)
        monkeypatch.setattr(bridge, "_route_via_brain", _brain_route)

        result = asyncio.run(bridge.execute("notiere eine idee"))

        assert isinstance(result, OrchestrationResult)
        assert result.error == "canonical_agent_unresolved"

    def test_missing_canonical_agent_is_a_caller_visible_failure(self, monkeypatch):
        bridge = BrainOpenFangBridge()
        bridge._registry = _Registry(_canonical_recipe())
        monkeypatch.setattr(bridge, "_route_via_brain", _brain_route)

        async def missing_agent(_agent_name):
            return None

        monkeypatch.setattr(bridge, "_ensure_agent", missing_agent)

        result = asyncio.run(bridge.execute("notiere eine idee"))

        assert isinstance(result, OrchestrationResult)
        assert result.error == "canonical_agent_unavailable"

    def test_openfang_timeout_is_a_failure_not_a_background_ack(self, monkeypatch):
        bridge = BrainOpenFangBridge(voice_timeout_s=0.001)
        bridge._registry = _Registry(_canonical_recipe())
        monkeypatch.setattr(bridge, "_route_via_brain", _brain_route)

        async def existing_agent(_agent_name):
            return "agent-1"

        async def timeout(*_args):
            await asyncio.sleep(0.01)
            return "late response"

        monkeypatch.setattr(bridge, "_ensure_agent", existing_agent)
        monkeypatch.setattr(bridge, "_send_to_openfang", timeout)

        result = asyncio.run(bridge.execute("notiere eine idee"))

        assert isinstance(result, OrchestrationResult)
        assert result.error == "openfang_timeout"
        assert result.response_hint != "Ich arbeite daran..."

    def test_bridge_never_spawns_an_agent(self):
        source = inspect.getsource(__import__(
            "swarm.routing.brain_openfang_bridge", fromlist=["*"]
        ))
        assert 'f"{self._openfang_url}/api/agents",' not in source


class TestIntentOrchestratorBridgeBoundary:
    def test_bridge_failure_returns_before_hybrid_or_sync_fallback(self):
        orchestrator_path = (
            Path(__file__).resolve().parents[1]
            / "swarm"
            / "orchestrator"
            / "intent_orchestrator.py"
        )
        source = orchestrator_path.read_text(encoding="utf-8")
        bridge_start = source.index("bridge_result = await self._brain_bridge.execute(")
        phase_zero = source.index("# PHASE 0: HYBRID ROUTER", bridge_start)
        bridge_block = source[bridge_start:phase_zero]

        assert "if bridge_result and bridge_result.error:" in bridge_block
        assert "return bridge_result" in bridge_block
