"""task-openfang-0002 — cognitive voice routing must fail closed.

These regressions pin the execution authority boundary: a cognitive intent
either completes through Brain -> OpenFang -> an already registered canonical
agent, or reports a caller-visible failure.  It must never spawn an agent or
continue into a local routing/execution path.
"""
import asyncio
from types import SimpleNamespace

import swarm.routing.brain_openfang_bridge as bridge_mod
import swarm.orchestrator.intent_orchestrator as orchestrator_mod
from swarm.orchestrator.result_formatter import OrchestrationResult
from swarm.orchestrator.intent_orchestrator import IntentOrchestrator
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


class _FakeResponse:
    def __init__(self, status, payload):
        self.status = status
        self._payload = payload

    async def json(self):
        return self._payload


class _FakeRequest:
    def __init__(self, response):
        self._response = response

    async def __aenter__(self):
        return self._response

    async def __aexit__(self, *_args):
        return False


class _RecordingAgentSession:
    agents = []
    calls = []

    def __init__(self, *_args, **_kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return False

    def get(self, url, **_kwargs):
        self.calls.append(("GET", url))
        return _FakeRequest(_FakeResponse(200, self.agents))

    def post(self, url, **_kwargs):
        self.calls.append(("POST", url))
        raise AssertionError("agent lookup must never create an agent")


class _FailClosedBridge:
    def __init__(self, result):
        self.result = result
        self.calls = 0

    async def execute(self, **_kwargs):
        self.calls += 1
        return self.result


class _ActiveBrainEventShadow:
    brain_active = True

    async def classify_via_brain(self, *_args, **_kwargs):
        return {
            "event_type": "idea.create",
            "confidence": 1.0,
            "routing_id": "",
        }


class _ForbiddenHybridRouter:
    def __init__(self):
        self.calls = 0

    async def resolve(self, *_args, **_kwargs):
        self.calls += 1
        raise AssertionError("HybridRouter must not run after a bridge failure")


class _ForbiddenSyncExecutor:
    def __init__(self):
        self.calls = 0

    async def process_sync(self, *_args, **_kwargs):
        self.calls += 1
        raise AssertionError("SyncExecutor must not run after a bridge failure")

    async def process_multi_step(self, *_args, **_kwargs):
        self.calls += 1
        raise AssertionError("SyncExecutor must not run after a bridge failure")


class _ForbiddenLegacyClassifier:
    def __init__(self):
        self.calls = 0

    async def classify(self, *_args, **_kwargs):
        self.calls += 1
        raise AssertionError("legacy classifier must not run after a bridge failure")


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

    def test_existing_agent_is_resolved_by_get_without_post(self, monkeypatch):
        bridge = BrainOpenFangBridge(openfang_url="http://openfang.test")
        _RecordingAgentSession.agents = [{"name": "brain-ideas", "id": "agent-42"}]
        _RecordingAgentSession.calls = []
        monkeypatch.setattr(
            bridge_mod.aiohttp, "ClientSession", _RecordingAgentSession
        )

        agent_id = asyncio.run(bridge._ensure_agent("brain-ideas"))

        assert agent_id == "agent-42"
        assert _RecordingAgentSession.calls == [
            ("GET", "http://openfang.test/api/agents")
        ]

    def test_missing_agent_never_posts_or_creates(self, monkeypatch):
        bridge = BrainOpenFangBridge(openfang_url="http://openfang.test")
        _RecordingAgentSession.agents = []
        _RecordingAgentSession.calls = []
        monkeypatch.setattr(
            bridge_mod.aiohttp, "ClientSession", _RecordingAgentSession
        )

        agent_id = asyncio.run(bridge._ensure_agent("brain-ideas"))

        assert agent_id is None
        assert bridge._last_agent_lookup_error == "canonical_agent_unavailable"
        assert _RecordingAgentSession.calls == [
            ("GET", "http://openfang.test/api/agents")
        ]


class TestIntentOrchestratorBridgeBoundary:
    def test_bridge_failure_returns_without_hybrid_sync_or_legacy_execution(
        self, monkeypatch
    ):
        expected = OrchestrationResult(
            job_id="brain-openfang-failed",
            event_type="idea.create",
            stream="ideas",
            response_hint="OpenFang unavailable",
            error="openfang_unavailable",
        )
        bridge = _FailClosedBridge(expected)
        hybrid = _ForbiddenHybridRouter()
        sync = _ForbiddenSyncExecutor()
        legacy = _ForbiddenLegacyClassifier()
        orchestrator = object.__new__(IntentOrchestrator)
        orchestrator._last_brain_classify = {}
        orchestrator._brain_event_shadow = _ActiveBrainEventShadow()
        orchestrator._brain_event_force_active = False
        orchestrator._BRAIN_EVENT_MIN_CONFIDENCE = 0.0
        orchestrator._multihop_bridge = None
        orchestrator._brain_bridge = bridge
        orchestrator._brain_shadow = SimpleNamespace(_active=True)
        orchestrator._hybrid_router = hybrid
        orchestrator._sync_executor = sync
        orchestrator.classifier = legacy
        monkeypatch.setattr(orchestrator_mod, "HAS_SESSION_CONTEXT", False)

        result = asyncio.run(
            orchestrator.process_intent(
                "notiere eine idee",
                context=SimpleNamespace(user_input="", session_id="s1", user_id="u1"),
            )
        )

        assert result is expected
        assert bridge.calls == 1
        assert hybrid.calls == 0
        assert sync.calls == 0
        assert legacy.calls == 0
