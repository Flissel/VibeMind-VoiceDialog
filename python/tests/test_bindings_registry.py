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


class TestPrefixBindingsFromRegistry:
    """ABSORB-5 (Phase 0): prefix bindings derive from YAML `prefixes:` —
    a new prefix in the registry is picked up WITHOUT code changes.
    RED was: build_registry_prefix_bindings did not exist; bindings were
    18 hardcoded entries independent of the YAML."""

    def test_injected_registry_prefix_is_picked_up(self):
        from swarm.routing.bindings_registry import build_registry_prefix_bindings
        reg = SpaceAgentRegistry(data={
            "version": 1,
            "spaces": {
                "testspace": {"agent": "test-agent", "prefixes": ["testpfx."]},
            },
        })
        b = build_registry_prefix_bindings(registry=reg)
        assert b["testpfx."].space == "testspace"
        assert b["testpfx."].agent == "test-agent"
        assert b["testpfx."].stream == "events:tasks:testspace"

    def test_default_prefix_bindings_agree_with_yaml(self):
        from swarm.routing.bindings_registry import build_prefix_bindings
        merged = build_prefix_bindings()
        reg = SpaceAgentRegistry.load(YAML_PATH)
        for space, meta in reg.all_spaces().items():
            for pfx in meta.get("prefixes") or []:
                assert pfx in merged, f"registry prefix {pfx!r} missing"
                assert merged[pfx].space == space, (
                    f"{pfx!r} -> {merged[pfx].space!r}, registry says {space!r}"
                )

    def test_infra_pseudo_bindings_survive(self):
        # conversation./evaluation. (agent=None) are code-only infra —
        # the registry merge must not drop them
        from swarm.routing.bindings_registry import build_prefix_bindings
        merged = build_prefix_bindings()
        assert "conversation." in merged and "evaluation." in merged


class TestKeywordBindingsFromRegistry:
    """ABSORB-6 (Phase 0): keyword regexes derive from YAML `keywords:`;
    static dict only as registry-less fallback."""

    def test_injected_registry_keyword_is_picked_up(self):
        from swarm.routing.bindings_registry import build_keyword_bindings
        reg = SpaceAgentRegistry(data={
            "version": 1,
            "spaces": {"ks": {"agent": "a1", "keywords": ["zebra|yak"]}},
        })
        kb = build_keyword_bindings(registry=reg)
        assert list(kb.keys()) == ["zebra|yak"]
        assert kb["zebra|yak"].space == "ks"

    def test_registry_without_keywords_falls_back_to_static(self):
        from swarm.routing.bindings_registry import build_keyword_bindings
        reg = SpaceAgentRegistry(data={
            "version": 1,
            "spaces": {"ks": {"agent": "a1"}},  # no keywords anywhere
        })
        kb = build_keyword_bindings(registry=reg)
        assert kb == KEYWORD_BINDINGS

    def test_default_keywords_agree_with_yaml(self):
        from swarm.routing.bindings_registry import build_keyword_bindings
        kb = build_keyword_bindings()
        reg = SpaceAgentRegistry.load(YAML_PATH)
        yaml_patterns = {
            pat: space
            for space, meta in reg.all_spaces().items()
            for pat in (meta.get("keywords") or [])
        }
        assert yaml_patterns, "YAML carries no keywords — injection missing?"
        for pat, space in yaml_patterns.items():
            assert pat in kb and kb[pat].space == space
