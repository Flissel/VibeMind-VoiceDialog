"""REWARD-2 (Phase 0) — None-signal is a NO-OP in BOTH shadow learning loops.

RED against today's tree: neither `BrainEventShadowObserver.reward`
(brain_event_shadow.py:183) nor `BrainShadowObserver.observe`
(brain_shadow.py:43) has a None branch — `reward(rid, None)` POSTs
`success: None` to /api/cortex/classify/reward, and `observe(..., None)`
POSTs to /api/cortex/route + /api/cortex/route/train regardless.

GREEN after REWARD-2: `success is None` -> zero POSTs (no fabricated
positive AND no fabricated negative — an unverified hop trains NOTHING),
True/False keep their exact POST shapes. Control tests for True/False
double as fake-session sanity checks (a broken fake would record 0 posts
and silently fake-pass the None case).
"""
import asyncio

import pytest

import swarm.routing.brain_event_shadow as bes_mod
import swarm.routing.brain_shadow as bs_mod
from swarm.routing.brain_event_shadow import BrainEventShadowObserver
from swarm.routing.brain_shadow import BrainShadowObserver


# ── aiohttp fake: records every POST; result is both awaitable and an
#    async context manager (aiohttp's _RequestContextManager duality) ──

class _FakeResp:
    status = 200

    async def json(self):
        return {"primary_space": "ideas", "routing_id": "r1"}


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
    # both modules share the aiohttp module object — patch its ClientSession
    monkeypatch.setattr(bes_mod.aiohttp, "ClientSession", _FakeSession)
    monkeypatch.setattr(bs_mod.aiohttp, "ClientSession", _FakeSession)
    return _FakeSession.recorded


# ── BrainEventShadowObserver.reward ──────────────────────────────────

class TestEventShadowRewardGating:
    def test_reward_none_is_noop(self, posts):
        shadow = BrainEventShadowObserver()
        asyncio.run(shadow.reward("rid-1", None))
        assert posts == [], f"None must not POST, got: {posts}"

    def test_reward_true_posts_success_true(self, posts):
        shadow = BrainEventShadowObserver()
        asyncio.run(shadow.reward("rid-1", True))
        assert len(posts) == 1
        url, payload = posts[0]
        assert url.endswith("/api/cortex/classify/reward")
        assert payload == {"routing_id": "rid-1", "success": True}

    def test_reward_false_posts_success_false(self, posts):
        shadow = BrainEventShadowObserver()
        asyncio.run(shadow.reward("rid-1", False))
        assert len(posts) == 1
        _, payload = posts[0]
        assert payload["success"] is False


# ── BrainShadowObserver.observe ──────────────────────────────────────

class TestBrainShadowObserveGating:
    def test_observe_none_is_noop(self, posts):
        shadow = BrainShadowObserver()
        asyncio.run(shadow.observe("do x", "idea.create", "ideas", None))
        assert posts == [], f"None must not POST at all, got: {posts}"

    def test_observe_true_posts_route_and_train(self, posts):
        shadow = BrainShadowObserver()
        asyncio.run(shadow.observe("do x", "idea.create", "ideas", True))
        urls = [u for u, _ in posts]
        assert any(u.endswith("/api/cortex/route") for u in urls)
        assert any(u.endswith("/api/cortex/route/train") for u in urls)
        train_payload = [p for u, p in posts if u.endswith("/route/train")][0]
        assert train_payload["success"] is True

    def test_observe_false_trains_success_false(self, posts):
        shadow = BrainShadowObserver()
        asyncio.run(shadow.observe("do x", "idea.create", "ideas", False))
        train_payload = [p for u, p in posts if u.endswith("/route/train")][0]
        assert train_payload["success"] is False
