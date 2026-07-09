"""REG-1 (Phase 0) — registry_version stamp on SpaceAgentRegistry.

RED against today's tree: `SpaceAgentRegistry` reads `version` locally in
`load()` (space_agent_registry.py:62) but never stores it — the instance has
no `version`/`registry_version` accessor -> AttributeError.

GREEN after REG-1: `load().version == 1` (from config/space_agent_registry.yml
`version: 1`), empty registry defaults to 0.
"""
from pathlib import Path

from swarm.routing.space_agent_registry import SpaceAgentRegistry

# tests -> python -> voice -> vibemind-os
REPO_ROOT = Path(__file__).resolve().parents[3]
YAML_PATH = REPO_ROOT / "config" / "space_agent_registry.yml"


class TestRegistryVersionStamp:
    def test_yaml_exists_precondition(self):
        assert YAML_PATH.exists(), f"registry YAML missing: {YAML_PATH}"

    def test_registry_version_stamp(self):
        reg = SpaceAgentRegistry.load(YAML_PATH)
        assert reg.version == 1
        # alias used by learning-side consumers (trajectory stamping)
        assert reg.registry_version == 1

    def test_version_defaults_to_zero_for_empty_registry(self):
        assert SpaceAgentRegistry(data={}).version == 0

    def test_version_read_from_injected_data(self):
        assert SpaceAgentRegistry(data={"version": 7}).version == 7


# REG-2 (Phase 0) — canonical_spaces() as the ONE space-name authority.
# RED today: SpaceAgentRegistry has no canonical_spaces/space_exists ->
# AttributeError. GREEN: the 13 YAML keys, canonical names only
# (roarboot NOT rowboat, agentfarm NOT autogen).
CANONICAL_SPACES = {
    "agentfarm", "bubbles", "coding", "desktop", "flowzen", "ideas",
    "minibook", "mirofish", "n8n", "research", "roarboot", "schedule",
    "video",
}


class TestCanonicalSpaces:
    def test_canonical_spaces_matches_yaml_keys(self):
        reg = SpaceAgentRegistry.load(YAML_PATH)
        spaces = reg.canonical_spaces()
        assert spaces == CANONICAL_SPACES
        # the two drift-prone names: canonical form in, alias out
        assert "roarboot" in spaces and "rowboat" not in spaces
        assert "agentfarm" in spaces and "autogen" not in spaces

    def test_space_exists(self):
        reg = SpaceAgentRegistry.load(YAML_PATH)
        assert reg.space_exists("ideas")
        assert reg.space_exists("roarboot")
        assert not reg.space_exists("rowboat")
        assert not reg.space_exists("autogen")
        assert not reg.space_exists("")

    def test_canonical_spaces_empty_registry(self):
        assert SpaceAgentRegistry(data={}).canonical_spaces() == set()


class TestBootConsistencyAssertion:
    """ASSERT-10 (Phase 0) — boot gate against silent dispatch death.
    RED was: no assert_consistent; a binding emitting 'autogen'/'rowboat'
    produced no error until space_to_agent returned None at dispatch."""

    def _reg(self):
        return SpaceAgentRegistry(data={
            "version": 1,
            "spaces": {"ideas": {"agent": "a"}, "coding": {"agent": "b"}},
        })

    def test_aligned_sets_pass(self):
        assert self._reg().assert_consistent({"ideas", "coding"}) == []

    def test_offenders_warn_by_default(self):
        offenders = self._reg().assert_consistent({"ideas", "autogen", "rowboat"})
        assert offenders == ["autogen", "rowboat"]

    def test_strict_mode_raises(self):
        from swarm.routing.space_agent_registry import RegistryConsistencyError
        import pytest as _pytest
        with _pytest.raises(RegistryConsistencyError):
            self._reg().assert_consistent({"rowboat"}, strict=True)

    def test_empty_registry_is_noop(self):
        assert SpaceAgentRegistry(data={}).assert_consistent({"whatever"}) == []

    def test_live_bindings_are_consistent(self):
        # the real E2E gate: current binding layer vs current YAML
        from swarm.routing.bindings_registry import (
            build_keyword_bindings,
            build_prefix_bindings,
        )
        reg = SpaceAgentRegistry.load(YAML_PATH)
        spaces = {b.space for b in build_prefix_bindings().values() if b.agent}
        spaces |= {b.space for b in build_keyword_bindings().values()}
        assert reg.assert_consistent(spaces, strict=True) == []


class TestAgentfarmCanonicalization:
    """REG-3 (Phase 0) — YAML and LEGACY_SPACE_AGENT_MAP must agree on the
    agentfarm agent. RED proved the live drift: YAML said
    `brain-orchestrator`, the bridge dispatched `vibemind`.

    Decision (2026-07-02, against the LIVE OpenFang agent list, 71 agents):
    `brain-orchestrator` is NOT deployed; `vibemind` IS
    (openrouter/llama-3.3-70b) -> YAML canonicalized to `vibemind`.
    From here the registry is the single truth — NO test hardcodes the
    agentfarm agent name; both sides are compared against each other.
    """

    def test_agentfarm_agent_consistent(self):
        from swarm.routing.brain_openfang_bridge import LEGACY_SPACE_AGENT_MAP
        reg = SpaceAgentRegistry.load(YAML_PATH)
        yaml_agent = reg.lookup("agentfarm", "agentfarm.run").agent
        bridge_agent = LEGACY_SPACE_AGENT_MAP["agentfarm"]
        assert yaml_agent == bridge_agent, (
            f"agentfarm drift: YAML says {yaml_agent!r}, bridge dispatches "
            f"{bridge_agent!r} — registry must be the single truth (REG-3)"
        )
