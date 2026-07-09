"""SpaceAgentRegistry — YAML-driven Intent → Space → Agent → Tools mapping.

Loads `config/space_agent_registry.yml` and provides O(1) lookup from
(space, event_type) to a RoutingRecipe used by BrainOpenFangBridge.

Fallback: when YAML missing or lookup fails, uses the legacy SPACE_AGENT_MAP
dict passed in at load time. Controlled by env VIBEMIND_ROUTING_REGISTRY.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


class RegistryConsistencyError(RuntimeError):
    """ASSERT-10: binding layer emits space names the registry doesn't know."""


@dataclass
class RoutingRecipe:
    """Structured routing decision for an intent."""
    space: str
    event_type: str
    agent: str
    mcp_scope: list[str] = field(default_factory=list)
    tool_hint: str = ""
    required_params: list[str] = field(default_factory=list)
    context_fields: list[str] = field(default_factory=list)
    system_prompt_hint: str = ""
    is_fallback: bool = False


_DEFAULT_PATH = (
    Path(__file__).resolve().parents[4] / "config" / "space_agent_registry.yml"
)


class SpaceAgentRegistry:
    """YAML-backed registry with legacy-dict fallback."""

    def __init__(
        self,
        data: dict[str, Any] | None = None,
        legacy_map: dict[str, str] | None = None,
    ):
        self._data = data or {}
        self._legacy = legacy_map or {}
        self._defaults = self._data.get("defaults", {}) if self._data else {}
        self._spaces = self._data.get("spaces", {}) if self._data else {}
        try:
            self._version = int(self._data.get("version", 0) or 0)
        except (TypeError, ValueError):
            self._version = 0

    @classmethod
    def load(cls, path: str | Path | None = None) -> "SpaceAgentRegistry":
        p = Path(path) if path else _DEFAULT_PATH
        if not p.exists():
            logger.warning(f"[Registry] YAML not found at {p}, registry empty")
            return cls(data={})
        with open(p, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        version = data.get("version", 0)
        if version != 1:
            logger.warning(f"[Registry] Unknown version {version}, expected 1")
        n_spaces = len(data.get("spaces", {}))
        logger.info(
            f"[Registry] Loaded {n_spaces} spaces from {p} "
            f"(registry_version={version})"
        )
        return cls(data=data)

    @classmethod
    def load_or_legacy(
        cls,
        legacy: dict[str, str],
        path: str | Path | None = None,
    ) -> "SpaceAgentRegistry":
        """Load YAML; if absent, use legacy dict as minimal registry."""
        reg = cls.load(path)
        reg._legacy = dict(legacy)
        return reg

    @property
    def mode(self) -> str:
        return os.getenv("VIBEMIND_ROUTING_REGISTRY", "shadow").lower()

    @property
    def version(self) -> int:
        """Registry content version from the YAML `version:` stamp (0 = empty
        or unversioned). REG-1 (Phase 0): learned-routing trajectories are
        stamped with this so distilled (state, agent_id) pairs from an older
        registry generation can be quarantined."""
        return self._version

    @property
    def registry_version(self) -> int:
        """Alias of `version` — the name trajectory rows use (CASCADE §2.3)."""
        return self._version

    def lookup(self, space: str, event_type: str) -> RoutingRecipe | None:
        """Return a RoutingRecipe for (space, event_type), or None if unknown."""
        sp = self._spaces.get(space)
        if not sp or not sp.get("enabled", True):
            return None
        events = sp.get("events") or {}
        ev = events.get(event_type)
        if ev is None:
            # Space known but event not registered — partial recipe with agent only
            return RoutingRecipe(
                space=space,
                event_type=event_type,
                agent=sp.get("agent", ""),
                mcp_scope=list(sp.get("mcp_servers") or []),
                context_fields=list(sp.get("default_context") or []),
                system_prompt_hint=sp.get("system_prompt_hint", ""),
            )
        return RoutingRecipe(
            space=space,
            event_type=event_type,
            agent=sp.get("agent", ""),
            mcp_scope=list(sp.get("mcp_servers") or []),
            tool_hint=ev.get("tool", ""),
            required_params=list(ev.get("required_params") or []),
            context_fields=list(
                ev.get("context_fields") or sp.get("default_context") or []
            ),
            system_prompt_hint=sp.get("system_prompt_hint", ""),
        )

    def fallback(self, space: str) -> RoutingRecipe:
        """Return a fallback recipe — uses legacy dict or defaults.fallback_agent."""
        legacy_agent = self._legacy.get(space)
        fb_agent = legacy_agent or self._defaults.get("fallback_agent", "brain-fallback")
        return RoutingRecipe(
            space=space,
            event_type="",
            agent=fb_agent,
            mcp_scope=[],
            context_fields=list(
                self._defaults.get("default_context_fields") or []
            ),
            is_fallback=True,
        )

    def legacy_agent(self, space: str) -> str:
        return self._legacy.get(space, "vibemind")

    def assert_consistent(
        self,
        binding_spaces: set[str],
        *,
        strict: bool | None = None,
    ) -> list[str]:
        """ASSERT-10 (Phase 0): boot-time consistency gate — every space the
        binding layer can emit must be a canonical registry key, otherwise
        dispatch dies silently (`space_to_agent -> None`, the FIX-3 bug
        class). Returns the offender list.

        strict=None reads env VIBEMIND_REGISTRY_STRICT (default off =
        warn-only for the first rollout; set to 1 to fail-fast at boot).
        Empty registry => no-op (registry-less boot stays possible).

        Note: the plan also wants Brain's SPACE_NAMES compared; Brain is a
        separate service not importable from the voice venv — callers that
        HAVE the brain space set can pass it as part of binding_spaces."""
        canonical = self.canonical_spaces()
        if not canonical:
            return []
        offenders = sorted(s for s in binding_spaces if s not in canonical)
        if offenders:
            msg = (
                f"non-canonical binding spaces {offenders} "
                f"(registry_version={self.version}, canonical={sorted(canonical)})"
            )
            if strict is None:
                strict = os.getenv(
                    "VIBEMIND_REGISTRY_STRICT", "0"
                ).lower() in ("1", "true")
            if strict:
                raise RegistryConsistencyError(msg)
            logger.warning(f"[Registry] ASSERT-10: {msg}")
        return offenders

    def canonical_spaces(self) -> set[str]:
        """REG-2 (Phase 0): the ONE authority for space names = the YAML
        `spaces:` keys. Every other map (bindings, legacy dict, logger
        colors) must validate against this set — canonical forms only
        (`roarboot` not `rowboat`, `agentfarm` not `autogen`)."""
        return set(self._spaces.keys())

    def space_exists(self, space: str) -> bool:
        return space in self._spaces

    def all_spaces(self) -> dict[str, dict[str, Any]]:
        return dict(self._spaces)

    def space_meta(self, space: str) -> dict[str, Any] | None:
        return self._spaces.get(space)

    def defaults(self) -> dict[str, Any]:
        return dict(self._defaults)
