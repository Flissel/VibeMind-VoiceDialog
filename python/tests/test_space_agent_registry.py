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
