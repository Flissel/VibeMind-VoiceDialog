"""MH-5 (Phase 0) — the multihop bridge feeds the REAL per-hop verdict back
as a reward, keyed on the top-level plan_id (MH-5a contract).

RED against pre-MH-5 code: `execute()` used `data["executed"]` only for the
voice summary (never a reward) — the spy below recorded nothing.

Fixture-payload rule (plan): the payload mirrors the REAL MH-5a response
schema — top-level {ok, trace_id, plan_id, plan, executed, state} exactly as
/api/multihop/execute now serializes it (pinned server-side by
brain/the_brain/tests/test_multihop_response_contract.py). A companion
assert checks the reward key used here IS the MH-5a top-level plan_id.
"""
import asyncio

import pytest

from swarm.routing.brain_multihop_bridge import BrainMultihopBridge


def _mh5a_payload(executed: dict) -> dict:
    """Response shaped exactly like the MH-5a envelope (top-level plan_id)."""
    return {
        "ok": True,
        "trace_id": "tr_test123",
        "plan_id": "plan_test123",
        "plan": {"plan_id": "plan_test123", "intent": "x", "hops": []},
        "executed": executed,
        "state": {},
        "final_text": "done",
        "elapsed_s": 0.1,
        "replans": 0,
    }


def _run_execute(payload):
    bridge = BrainMultihopBridge()
    rewards = []

    async def _fake_post(text):
        return payload

    async def _spy_reward(plan_id, success):
        rewards.append((plan_id, success))

    bridge._post_multihop = _fake_post
    bridge._reward_multihop = _spy_reward

    async def _main():
        result = await bridge.execute("do the thing")
        await asyncio.sleep(0)  # let fire-and-forget task run
        return result

    result = asyncio.run(_main())
    return result, rewards


class TestMultihopRewardsOnlyOnVerified:
    def test_all_hops_verified_rewards_true_on_plan_id(self):
        payload = _mh5a_payload({
            "s1": {"ok": True, "validator_verdict": {"verified": True}},
            "s2": {"ok": True, "validator_verdict": {"verified": True}},
        })
        # companion assert: reward key IS the MH-5a top-level plan_id
        assert "plan_id" in payload and payload["plan_id"] == "plan_test123"
        result, rewards = _run_execute(payload)
        assert result is not None
        assert rewards == [("plan_test123", True)]

    def test_refuted_hop_rewards_false(self):
        payload = _mh5a_payload({
            "s1": {"ok": True, "validator_verdict": {"verified": True}},
            "s2": {"ok": True, "validator_verdict": {"verified": False}},
        })
        _, rewards = _run_execute(payload)
        assert rewards == [("plan_test123", False)]

    def test_unverified_hops_reward_nothing(self):
        # hops ran ok but nobody re-queried ground truth -> sig None -> no POST
        payload = _mh5a_payload({
            "s1": {"ok": True},
            "s2": {"ok": True},
        })
        _, rewards = _run_execute(payload)
        assert rewards == [], (
            f"unverified hops must not reward, got {rewards} — "
            "that would be the did-not-throw fake signal"
        )

    def test_empty_executed_rewards_nothing(self):
        payload = _mh5a_payload({})
        _, rewards = _run_execute(payload)
        assert rewards == []

    def test_missing_plan_id_rewards_nothing(self):
        payload = _mh5a_payload({
            "s1": {"ok": True, "validator_verdict": {"verified": True}},
        })
        payload.pop("plan_id")
        _, rewards = _run_execute(payload)
        assert rewards == []
