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
        logger.info(f"[Registry] Loaded {n_spaces} spaces from {p}")
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

    def all_spaces(self) -> dict[str, dict[str, Any]]:
        return dict(self._spaces)

    def space_meta(self, space: str) -> dict[str, Any] | None:
        return self._spaces.get(space)

    def defaults(self) -> dict[str, Any]:
        return dict(self._defaults)
