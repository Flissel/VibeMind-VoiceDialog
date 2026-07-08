"""Outcome gate — the ONE learning-signal gate (GATE-1, Phase 0).

Every shadow learning sink (`_brain_shadow.observe`, `_brain_event_shadow
.reward`/`.observe`, `_reward_brain`) must derive its success signal from
these functions instead of hardcoding `success=True`. The gate maps a hop's
independently observed ground truth (the `truth:` validator verdict produced
by `capability_validator` -> `world_observer`) onto a tri-state:

    True   -> hop/run PROVEN ok against ground truth  => may train positive
    False  -> hop failed or ground truth REFUTED it   => may train negative
    None   -> no independent evidence (UNVERIFIED)    => train NOTHING

Deliberately STRICTER than execution gating: `core/contract_gate.py:84-90`
falls back to `ok` when verified is None (fail-open so plans don't stall).
For LEARNING that fallback would resurrect the did-not-throw fake signal, so
UNVERIFIED maps to None here — never to a positive. Do NOT align the two.

Pure functions, no I/O, no brain-package imports (runs in the voice venv).
"""
from __future__ import annotations

from typing import Any, Mapping, Optional

__all__ = ["contract_pass_from_verdict", "contract_pass_from_executed"]


def contract_pass_from_verdict(
    verdict: Optional[Mapping[str, Any]],
    ok: bool,
) -> Optional[bool]:
    """Tri-state contract signal for a single hop.

    Args:
        verdict: the hop's `validator_verdict` dict (expects a `verified` key
            as written by the truth: validator), or None when no validator ran.
        ok: the executor-level ok flag for the hop.

    Returns:
        True only for `ok and verified is True`; False when the hop failed
        (`ok` falsy) or ground truth refuted it (`verified is False`); None
        when there is no independent evidence (no verdict / no `verified`
        key / `verified is None`).
    """
    if not ok:
        return False
    if not isinstance(verdict, Mapping):
        return None
    verified = verdict.get("verified")
    if verified is True:
        return True
    if verified is False:
        return False
    return None


def contract_pass_from_executed(
    executed: Optional[Mapping[str, Any]],
) -> Optional[bool]:
    """AND the per-hop contract signals of a multihop `executed` map.

    Args:
        executed: `{step_id: {ok, validator_verdict, ...}}` as returned by
            `/api/multihop/execute` (HopResult-shaped dicts).

    Returns:
        True only when EVERY hop is ok AND ground-truth verified; False as
        soon as any hop failed or was refuted (False beats None); None when
        the map is empty/missing or at least one ok-hop lacks independent
        evidence. An empty hop dict counts as failed (ORCH-4 rule:
        None/empty/error -> ok=False), never as unverified.
    """
    if not executed:
        return None
    saw_unverified = False
    for hop in executed.values():
        if not isinstance(hop, Mapping):
            return False
        if not hop.get("ok"):
            return False
        hop_pass = contract_pass_from_verdict(hop.get("validator_verdict"), True)
        if hop_pass is False:
            return False
        if hop_pass is None:
            saw_unverified = True
    return None if saw_unverified else True
