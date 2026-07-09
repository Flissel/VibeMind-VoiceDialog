"""OF-3 (Phase 0) — no fake positive reward from brain_openfang_bridge.

RED against today's tree (SINKS #5/#6 of the fake-signal inventory):
`execute()` (:188) and `_background_execute()` (:380) fire
`_reward_brain(routing_id, success=True)` on mere non-throw —
`_send_to_openfang` returns FREE TEXT with no ground-truth verdict, so
"didn't crash" trains the SpaceRoutingHead as "routing was correct".

GREEN after OF-3: non-verified responses reward None (no-op POST-wise,
REWARD-2 semantics), exception paths keep their honest success=False,
and `_reward_brain(rid, None)` sends zero POSTs.
"""
import asyncio

import pytest

import swarm.routing.brain_openfang_bridge as bridge_mod
from swarm.routing.brain_openfang_bridge import BrainOpenFangBridge


class _FakeResp:
    status = 200

    async def json(self):
        return {}


class _FakePostResult:
    def __init__(self, recorder, url, payload):
        recorder.append((url, payload))

    async def __aenter__(self):
        return _FakeResp()

    async def __aexit__(self, *exc):
        return False

    def __await__(self):
        async def _coro():
            return _FakeResp()
        return _coro().__await__()


class _FakeSession:
    recorded: list = []

    def __init__(self, *a, **kw):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def post(self, url, json=None, **kw):
        return _FakePostResult(_FakeSession.recorded, url, json)


@pytest.fixture()
def posts(monkeypatch):
    _FakeSession.recorded = []
    monkeypatch.setattr(bridge_mod.aiohttp, "ClientSession", _FakeSession)
    return _FakeSession.recorded


class TestRewardBrainNoneGating:
    def test_reward_brain_none_is_noop(self, posts):
        bridge = BrainOpenFangBridge()
        asyncio.run(bridge._reward_brain("rid-1", None))
        assert posts == [], f"None must not POST, got: {posts}"

    def test_reward_brain_true_and_false_still_post(self, posts):
        # control: fake session works, True/False shapes unchanged
        bridge = BrainOpenFangBridge()
        asyncio.run(bridge._reward_brain("rid-1", True))
        asyncio.run(bridge._reward_brain("rid-1", False))
        payloads = [p for _, p in posts]
        assert payloads == [
            {"routing_id": "rid-1", "success": True},
            {"routing_id": "rid-1", "success": False},
        ]


class TestNoFakePositiveOnFreeText:
    def test_background_execute_unverified_rewards_none(self, posts):
        """A free-text OpenFang response carries NO ground truth — the
        background path must not reward success=True for it."""
        bridge = BrainOpenFangBridge()
        rewards = []

        async def _fake_send(agent_id, message):
            return "some free text answer"

        async def _spy_reward(routing_id, success):
            rewards.append((routing_id, success))

        bridge._send_to_openfang = _fake_send
        bridge._reward_brain = _spy_reward
        asyncio.run(
            bridge._background_execute("aid", "msg", "rid-1", "ideas", "idea.create")
        )
        assert rewards, "background path stopped rewarding entirely"
        assert rewards[0] == ("rid-1", None), (
            f"free-text response must reward None (unverified), got "
            f"{rewards[0]} — success=True here is the did-not-throw fake signal"
        )

    def test_background_execute_exception_rewards_false(self, posts):
        bridge = BrainOpenFangBridge()
        rewards = []

        async def _fake_send(agent_id, message):
            raise RuntimeError("openfang down")

        async def _spy_reward(routing_id, success):
            rewards.append((routing_id, success))

        bridge._send_to_openfang = _fake_send
        bridge._reward_brain = _spy_reward
        asyncio.run(
            bridge._background_execute("aid", "msg", "rid-1", "ideas", "idea.create")
        )
        assert rewards == [("rid-1", False)], (
            "exception path must keep its honest success=False"
        )


class TestNoHardcodedTrueSinkSurvives:
    def test_no_reward_brain_success_true_callsite(self):
        """Pattern-match on callsites (not line numbers): no
        `_reward_brain(..., success=True)` literal may survive OF-3."""
        import inspect
        src = inspect.getsource(bridge_mod)
        assert "_reward_brain(routing_id, success=True)" not in src, (
            "hardcoded success=True still reaches _reward_brain "
            "(did-not-throw fake signal, OF-3)"
        )
