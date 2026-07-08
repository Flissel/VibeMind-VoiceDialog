"""GATE-1 (Phase 0) — semantics of the shared outcome gate.

RED against today's tree: `swarm/routing/outcome_gate.py` does not exist,
so this module fails at collection with ImportError — that IS the gap proof.

GREEN after GATE-1: the truth-table below holds. Learning semantics are
deliberately STRICTER than execution gating (`core/contract_gate.py:84-90`
falls back to `ok` when verified is None): for LEARNING, UNVERIFIED must
never become a positive signal — it maps to None (= caller does not reward).
"""
import pytest

from swarm.routing.outcome_gate import (
    contract_pass_from_verdict,
    contract_pass_from_executed,
)


class TestContractPassFromVerdict:
    def test_verified_true_ok_true_is_true(self):
        assert contract_pass_from_verdict({"verified": True}, True) is True

    def test_verified_false_ok_true_is_false(self):
        assert contract_pass_from_verdict({"verified": False}, True) is False

    def test_verified_none_ok_true_is_none(self):
        assert contract_pass_from_verdict({"verified": None}, True) is None

    def test_verdict_none_ok_true_is_none(self):
        assert contract_pass_from_verdict(None, True) is None

    def test_verified_true_ok_false_is_false(self):
        # executor said not-ok — a verdict cannot rescue a failed hop
        assert contract_pass_from_verdict({"verified": True}, False) is False

    def test_empty_verdict_dict_is_none(self):
        # verdict present but carries no `verified` key -> unobserved
        assert contract_pass_from_verdict({}, True) is None

    def test_verdict_without_verified_key_is_none(self):
        assert contract_pass_from_verdict({"valid": True, "reason": "x"}, True) is None


class TestContractPassFromExecuted:
    def test_all_hops_ok_and_verified_is_true(self):
        executed = {
            "hop_0": {"ok": True, "validator_verdict": {"verified": True}},
            "hop_1": {"ok": True, "validator_verdict": {"verified": True}},
        }
        assert contract_pass_from_executed(executed) is True

    def test_single_verified_hop_is_true(self):
        executed = {"hop_0": {"ok": True, "validator_verdict": {"verified": True}}}
        assert contract_pass_from_executed(executed) is True

    def test_empty_executed_is_none(self):
        # no hops -> no evidence -> never a positive signal
        assert contract_pass_from_executed({}) is None
        assert contract_pass_from_executed(None) is None

    def test_empty_hop_dict_is_not_true(self):
        # a hop `{}` carries no ok -> treated as not-ok (ORCH-4 rule:
        # None/empty-dict/error-key -> ok=False) -> gate False
        assert contract_pass_from_executed({"hop_0": {}}) is False

    def test_one_refuted_hop_poisons_the_run(self):
        executed = {
            "hop_0": {"ok": True, "validator_verdict": {"verified": True}},
            "hop_1": {"ok": True, "validator_verdict": {"verified": False}},
        }
        assert contract_pass_from_executed(executed) is False

    def test_one_failed_hop_poisons_the_run(self):
        executed = {
            "hop_0": {"ok": True, "validator_verdict": {"verified": True}},
            "hop_1": {"ok": False},
        }
        assert contract_pass_from_executed(executed) is False

    def test_ok_hop_without_verdict_is_none(self):
        # ran fine but nobody re-queried ground truth -> UNVERIFIED -> None,
        # NOT True (the anti-"did-not-throw" invariant)
        executed = {"hop_0": {"ok": True}}
        assert contract_pass_from_executed(executed) is None

    def test_mixed_verified_and_unverified_is_none(self):
        executed = {
            "hop_0": {"ok": True, "validator_verdict": {"verified": True}},
            "hop_1": {"ok": True},
        }
        assert contract_pass_from_executed(executed) is None

    def test_false_beats_none(self):
        # one refuted hop -> False even when others are unverified
        executed = {
            "hop_0": {"ok": True},
            "hop_1": {"ok": True, "validator_verdict": {"verified": False}},
        }
        assert contract_pass_from_executed(executed) is False
