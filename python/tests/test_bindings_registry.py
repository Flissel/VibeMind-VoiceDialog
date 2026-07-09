"""FIX-3 (Phase 0) — bindings emit CANONICAL space names.

RED against today's tree: KEYWORD_BINDINGS routes agent-farm intents to
space `autogen` (bindings_registry.py:23) and the static prefix map keys
`roarboot.` to space `rowboat` (:116) / `agentfarm.` to `autogen` (:122) —
neither is a key in the registry YAML or LEGACY_SPACE_AGENT_MAP, so the
bridge's space->agent lookup returns None and dispatch dies silently.

GREEN after FIX-3: every dispatchable binding's space is in
SpaceAgentRegistry.canonical_spaces(). Infra pseudo-bindings with
agent=None (conversation./evaluation.) are exempt — they never dispatch.

NOTE: lands in the SAME commit as ABSORB-8 (space_logger) so router and
logger never disagree transiently (plan file-conflict rule).
"""
from pathlib import Path

from swarm.routing.bindings_registry import (
    KEYWORD_BINDINGS,
    _get_static_fallback,
    match_keyword,
)
from swarm.routing.space_agent_registry import SpaceAgentRegistry

REPO_ROOT = Path(__file__).resolve().parents[3]
YAML_PATH = REPO_ROOT / "config" / "space_agent_registry.yml"


def _canonical() -> set:
    return SpaceAgentRegistry.load(YAML_PATH).canonical_spaces()


class TestBindingSpacesAreCanonical:
    def test_static_prefix_spaces_are_canonical(self):
        canonical = _canonical()
        offenders = {
            prefix: b.space
            for prefix, b in _get_static_fallback().items()
            if b.agent is not None and b.space not in canonical
        }
        assert not offenders, (
            f"static prefix bindings emit non-canonical spaces: {offenders}"
        )

    def test_keyword_spaces_are_canonical(self):
        canonical = _canonical()
        offenders = {
            pat: b.space
            for pat, b in KEYWORD_BINDINGS.items()
            if b.space not in canonical
        }
        assert not offenders, (
            f"keyword bindings emit non-canonical spaces: {offenders}"
        )

    def test_agentfarm_keyword_routes_canonical(self):
        b = match_keyword("starte agent farm pipeline")
        assert b is not None
        assert b.space == "agentfarm", (
            f"agent-farm keyword routes to {b.space!r} — no such key in the "
            "registry, bridge dispatch returns None"
        )

    def test_roarboot_prefix_routes_canonical(self):
        b = _get_static_fallback()["roarboot."]
        assert b.space == "roarboot", (
            f"roarboot. prefix routes to {b.space!r} — no such key in the "
            "registry, bridge dispatch returns None"
        )
