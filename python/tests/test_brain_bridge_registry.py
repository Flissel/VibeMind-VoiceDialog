"""FIX-4 + ABSORB-7 + ABSORB-9 (Phase 0) — bridge dispatch is registry-derived.

RED (verified live before the fixes):
- ABSORB-7: LEGACY_SPACE_AGENT_MAP was a hand-maintained literal that had
  already drifted (bubbles='vibemind' vs YAML 'brain-bubbles'; the REG-3
  agentfarm drift was the same failure mode).
- FIX-4: bindings emitted 'rowboat'/'autogen' -> space_to_agent()==None ->
  silent dispatch death (fixed by FIX-3; this pins the regression).
- ABSORB-9: voice_manager imported the non-existent
  spaces.minibook.tools.collaboration_tools (ModuleNotFoundError trap).

Expectations are read FROM the registry — no agent name is hardcoded
(the REG-3 rule: no test may freeze the agentfarm agent).
"""
from pathlib import Path

from swarm.routing.brain_openfang_bridge import (
    BrainOpenFangBridge,
    LEGACY_SPACE_AGENT_MAP,
)
from swarm.routing.space_agent_registry import SpaceAgentRegistry

REPO_ROOT = Path(__file__).resolve().parents[3]
YAML_PATH = REPO_ROOT / "config" / "space_agent_registry.yml"


class TestLegacyMapDerivedFromRegistry:
    def test_keys_match_canonical_spaces(self):
        reg = SpaceAgentRegistry.load(YAML_PATH)
        assert set(LEGACY_SPACE_AGENT_MAP.keys()) == reg.canonical_spaces()

    def test_every_value_matches_yaml_agent(self):
        reg = SpaceAgentRegistry.load(YAML_PATH)
        drift = {
            space: (LEGACY_SPACE_AGENT_MAP.get(space), meta.get("agent"))
            for space, meta in reg.all_spaces().items()
            if LEGACY_SPACE_AGENT_MAP.get(space) != meta.get("agent")
        }
        assert not drift, (
            f"space->agent drift between bridge map and registry: {drift}"
        )


class TestDispatchResolvesCanonicalSpaces:
    """FIX-4: the two formerly-broken spaces resolve E2E, expectations
    registry-derived (no hardcoded agent names)."""

    def test_dispatch_roarboot_and_agentfarm_resolve(self):
        bridge = BrainOpenFangBridge()
        reg = SpaceAgentRegistry.load(YAML_PATH)
        for space in ("roarboot", "agentfarm"):
            expected = reg.space_meta(space)["agent"]
            got = bridge.space_to_agent(space)
            assert got == expected and got is not None, (
                f"space_to_agent({space!r}) = {got!r}, registry says {expected!r}"
            )

    def test_alias_spaces_do_not_resolve(self):
        # the un-canonical aliases must stay dead — resurrection would
        # mean a second name for the same space (drift by construction)
        bridge = BrainOpenFangBridge()
        assert bridge.space_to_agent("rowboat") is None
        assert bridge.space_to_agent("autogen") is None


class TestNoMinibookRouterImports:
    """ABSORB-9: no source/test imports the non-existent minibook routers."""

    def test_dead_minibook_refs_are_gone(self):
        targets = [
            REPO_ROOT / "voice" / "python" / "ipc" / "voice_manager.py",
            REPO_ROOT / "voice" / "python" / "tests" / "test_flowzen_integration.py",
        ]
        offenders = []
        for f in targets:
            src = f.read_text(encoding="utf-8", errors="replace")
            if "collaboration_tools import SPACE_AGENT_REGISTRY" in src:
                offenders.append(f"{f.name}: collaboration_tools")
            if "space_router import EVENT_TYPE_TO_SPACE" in src:
                offenders.append(f"{f.name}: space_router")
        assert not offenders, f"dead minibook router imports: {offenders}"
