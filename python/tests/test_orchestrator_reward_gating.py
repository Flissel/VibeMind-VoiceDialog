"""ORCH-4 (Phase 0) — orchestrator learning sinks derive from the outcome
gate, never from hardcoded success=True.

The four fake sinks (verified live before the fix, this session):
- Phase -1 bridge success  -> _brain_event_shadow.reward(success=True)
- BrainEvent+OpenFang path -> _brain_event_shadow.reward(success=True)
- Tier1-4 tool path        -> _brain_shadow.observe(success=True)
                              + _brain_event_shadow.reward(success=True)
Plus TWO unconditional LLM label posts (_brain_event_shadow.observe) that
trained /api/cortex/classify/train even when execution then failed.

GREEN: sinks carry gate-derived signals (None for free-text/unverified,
False for failed tools), label posts run through
_fire_event_label_if_verified (fire only on sig True), and no
success=True literal reaches a shadow sink (callsite-pattern regression
guard — the NOFAKE-6 approach scoped to this file, never line numbers).
"""
import asyncio
import re
from pathlib import Path

import pytest

ORCH_PATH = (
    Path(__file__).resolve().parents[1]
    / "swarm" / "orchestrator" / "intent_orchestrator.py"
)


# ── Regression guard: callsite pattern scan ──────────────────────────

SINK_RE = re.compile(
    r"(_brain_shadow\.observe\(|_brain_event_shadow\.reward\(|"
    r"_brain_event_shadow\.observe\()"
)


class TestNoHardcodedSuccessSinks:
    def test_no_shadow_sink_carries_success_true(self):
        src = ORCH_PATH.read_text(encoding="utf-8")
        offenders = []
        for m in SINK_RE.finditer(src):
            window = src[m.start(): m.start() + 400]
            if "success=True" in window:
                line_no = src[: m.start()].count("\n") + 1
                offenders.append(f"line {line_no}: {m.group(1)}")
        assert not offenders, (
            f"hardcoded success=True still reaches shadow sinks: {offenders}"
        )

    def test_unconditional_event_label_posts_are_gone(self):
        """The classify-time observe() label posts must run through the
        gate helper, not fire directly via create_task."""
        src = ORCH_PATH.read_text(encoding="utf-8")
        direct = re.findall(
            r"create_task\(self\._brain_event_shadow\.observe\(", src
        )
        # exactly ONE direct call site is allowed: inside the gate helper
        assert len(direct) == 1, (
            f"{len(direct)} direct event-label posts found — all label "
            "posts must go through _fire_event_label_if_verified"
        )
        assert "_fire_event_label_if_verified" in src


# ── Behavioral: the gate helper itself ───────────────────────────────

class _SpyShadow:
    def __init__(self):
        self.observed = []

    async def observe(self, user_text, actual_event_type, user_id=None):
        self.observed.append((user_text, actual_event_type, user_id))


def _bare_orchestrator():
    """Instance without running the heavy __init__ — the helper only
    touches _brain_event_shadow and a lazy counter."""
    from swarm.orchestrator.intent_orchestrator import IntentOrchestrator
    orch = object.__new__(IntentOrchestrator)
    orch._brain_event_shadow = _SpyShadow()
    return orch


class TestFireEventLabelIfVerified:
    def test_sig_none_skips_and_counts(self):
        orch = _bare_orchestrator()

        async def _run():
            orch._fire_event_label_if_verified(None, "text", "idea.create")

        asyncio.run(_run())
        assert orch._brain_event_shadow.observed == []
        assert orch._skipped_event_labels == 1

    def test_sig_false_skips_and_counts(self):
        orch = _bare_orchestrator()

        async def _run():
            orch._fire_event_label_if_verified(False, "text", "idea.create")

        asyncio.run(_run())
        assert orch._brain_event_shadow.observed == []
        assert orch._skipped_event_labels == 1

    def test_sig_true_fires_label(self):
        orch = _bare_orchestrator()

        async def _run():
            orch._fire_event_label_if_verified(True, "text", "idea.create", "u1")
            # let the created task run
            await asyncio.sleep(0)

        asyncio.run(_run())
        assert orch._brain_event_shadow.observed == [
            ("text", "idea.create", "u1")
        ]
