"""ABSORB-8 (Phase 0) — space_logger fully canonical, validated against the
registry.

RED against today's tree (5 non-canonical spots): MODULE_TO_SPACE values
`spaces.rowboat`->rowboat (:71) and `publishing`->rowboat (:88), color-dict
key `rowboat` (:107), badge-dict key `rowboat` (:123) — plus flowzen/
mirofish/video have NO color/badge at all (canonical spaces silently lose
their color).

GREEN after ABSORB-8: every non-infra MODULE_TO_SPACE value is canonical,
color+badge dicts key every canonical space, no `rowboat` key survives.
Module-path KEYS like `spaces.rowboat` stay — they match real module dirs
on disk; only the emitted SPACE NAMES are canonicalized.

Lands in the SAME commit as FIX-3 (plan file-conflict rule).
"""
from pathlib import Path

from swarm.logging.space_logger import (
    MODULE_TO_SPACE,
    SPACE_TO_COLOR,
    SPACE_TO_TAG,
)
from swarm.routing.space_agent_registry import SpaceAgentRegistry

REPO_ROOT = Path(__file__).resolve().parents[3]
YAML_PATH = REPO_ROOT / "config" / "space_agent_registry.yml"

# infra pseudo-spaces: log routing targets that are not dispatchable spaces
INFRA = {"voice", "orchestrator", "brain", "conversation"}


def _canonical() -> set:
    return SpaceAgentRegistry.load(YAML_PATH).canonical_spaces()


class TestSpaceLoggerFullyCanonical:
    def test_module_to_space_values_canonical(self):
        canonical = _canonical()
        offenders = {
            key: space
            for key, space in MODULE_TO_SPACE.items()
            if space not in INFRA and space not in canonical
        }
        assert not offenders, (
            f"MODULE_TO_SPACE emits non-canonical space names: {offenders}"
        )

    def test_color_dict_keys_canonical(self):
        canonical = _canonical()
        offenders = [
            s for s in SPACE_TO_COLOR if s not in INFRA and s not in canonical
        ]
        assert not offenders, f"non-canonical color keys: {offenders}"

    def test_tag_dict_keys_canonical(self):
        canonical = _canonical()
        offenders = [
            s for s in SPACE_TO_TAG if s not in INFRA and s not in canonical
        ]
        assert not offenders, f"non-canonical badge keys: {offenders}"

    def test_every_canonical_space_has_color_and_tag(self):
        canonical = _canonical()
        missing_color = sorted(canonical - set(SPACE_TO_COLOR))
        missing_tag = sorted(canonical - set(SPACE_TO_TAG))
        assert not missing_color, (
            f"canonical spaces silently without color: {missing_color}"
        )
        assert not missing_tag, (
            f"canonical spaces silently without badge: {missing_tag}"
        )

    def test_no_rowboat_alias_survives(self):
        assert "rowboat" not in SPACE_TO_COLOR
        assert "rowboat" not in SPACE_TO_TAG
        assert "rowboat" not in MODULE_TO_SPACE.values()
