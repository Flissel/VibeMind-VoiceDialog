"""NOFAKE-6 (Phase 0) — regression guard: no hardcoded success=True reaches
ANY shadow learning sink in voice/python/swarm.

RED (verified live before Waves B/C): 6 sinks — intent_orchestrator (4)
and brain_openfang_bridge (2) — trained hardcoded success into
/api/cortex/route/train, /route/reward and /classify/reward.

Matching is on CALLSITE PATTERNS (receiver name + success=True literal in
the statement window), NEVER on line numbers — the sinks move when files
are edited. Legitimate non-learning `success=True` flags (tool results,
telemetry, status envelopes) are out of scope: only the learning-sink
receivers below are scanned.
"""
import re
from pathlib import Path

SWARM_ROOT = Path(__file__).resolve().parents[1] / "swarm"

# learning-sink receivers: anything that feeds a Brain train/reward endpoint
SINK_RE = re.compile(
    r"(_brain_shadow\.observe\(|"
    r"_brain_event_shadow\.reward\(|"
    r"_brain_event_shadow\.observe\(|"
    r"_reward_brain\(|"
    r"_reward_multihop\()"
)
WINDOW = 400  # chars after the callsite opening — covers multi-line calls


def test_no_hardcoded_success_true_in_shadow_sinks():
    offenders = []
    for f in sorted(SWARM_ROOT.rglob("*.py")):
        src = f.read_text(encoding="utf-8", errors="replace")
        for m in SINK_RE.finditer(src):
            window = src[m.start(): m.start() + WINDOW]
            if "success=True" in window:
                line_no = src[: m.start()].count("\n") + 1
                offenders.append(
                    f"{f.relative_to(SWARM_ROOT)}:{line_no} {m.group(1)}"
                )
    assert not offenders, (
        "hardcoded success=True reaches learning sinks (did-not-throw "
        f"fake signal): {offenders}"
    )
