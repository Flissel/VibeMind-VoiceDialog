"""
Plugin Manager - Core discovery, validation, loading, and state management.

Scans builtin/ and community/ directories for plugin.json manifests,
manages user accept/reject state, and dynamically loads agents via importlib.
"""

import importlib
import logging
import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from plugins.plugin_manifest import PluginManifest
from plugins.plugin_state import PluginStateRepository

logger = logging.getLogger(__name__)

_PLUGINS_DIR = Path(__file__).resolve().parent
_BUILTIN_DIR = _PLUGINS_DIR / "builtin"
_COMMUNITY_DIR = _PLUGINS_DIR / "community"


class PluginManager:
    """Discovers, validates, and manages the plugin lifecycle."""

    def __init__(self, db_path: Optional[Path] = None):
        self._state = PluginStateRepository(db_path)
        self._manifests: Dict[str, PluginManifest] = {}
        self._agents: Dict[str, Any] = {}  # Loaded agent singletons
        self._discovered = False

    # ── Discovery ──────────────────────────────────────────────

    def discover_plugins(self) -> List[PluginManifest]:
        """Scan builtin/ and community/ dirs for plugin.json files."""
        self._manifests.clear()

        for directory, label in [(_BUILTIN_DIR, "builtin"), (_COMMUNITY_DIR, "community")]:
            if not directory.exists():
                continue
            for plugin_json in sorted(directory.rglob("plugin.json")):
                # Only load direct children: builtin/<name>/plugin.json
                if plugin_json.parent.parent != directory:
                    continue
                manifest = PluginManifest.from_json(plugin_json)
                if manifest:
                    if label == "builtin":
                        manifest.builtin = True
                    self._manifests[manifest.id] = manifest
                    logger.debug(f"Discovered {label} plugin: {manifest.id} v{manifest.version}")

        self._discovered = True
        logger.info(f"PluginManager: discovered {len(self._manifests)} plugins "
                     f"({sum(1 for m in self._manifests.values() if m.builtin)} builtin, "
                     f"{sum(1 for m in self._manifests.values() if not m.builtin)} community)")
        return list(self._manifests.values())

    def _ensure_discovered(self):
        if not self._discovered:
            self.discover_plugins()

    # ── Queries ────────────────────────────────────────────────

    def get_manifest(self, plugin_id: str) -> Optional[PluginManifest]:
        self._ensure_discovered()
        return self._manifests.get(plugin_id)

    def get_all_manifests(self) -> List[PluginManifest]:
        self._ensure_discovered()
        return list(self._manifests.values())

    def is_enabled(self, plugin_id: str) -> bool:
        """Check if a plugin should be loaded.

        Builtin plugins are always enabled.
        Community plugins respect env_flag and user state.
        """
        self._ensure_discovered()
        manifest = self._manifests.get(plugin_id)
        if not manifest:
            return False

        if manifest.builtin:
            return True

        # Check env_flag (backward compat: MINIBOOK_ENABLED, etc.)
        if manifest.env_flag:
            env_val = os.getenv(manifest.env_flag, "").lower()
            if env_val == "false":
                return False

        return self._state.is_enabled(plugin_id)

    def get_enabled_plugins(self) -> List[PluginManifest]:
        """All plugins that should be loaded (builtin + user-accepted)."""
        self._ensure_discovered()
        return [m for m in self._manifests.values() if self.is_enabled(m.id)]

    def get_new_plugins(self) -> List[PluginManifest]:
        """Plugins the user hasn't seen yet (no state entry)."""
        self._ensure_discovered()
        return [
            m for m in self._manifests.values()
            if not m.builtin and not self._state.has_state(m.id)
        ]

    def get_updated_plugins(self) -> List[PluginManifest]:
        """Plugins where manifest version > version_seen."""
        self._ensure_discovered()
        result = []
        for m in self._manifests.values():
            if m.builtin:
                continue
            seen = self._state.get_version_seen(m.id)
            if seen and seen != m.version:
                result.append(m)
        return result

    # ── State Changes ──────────────────────────────────────────

    def accept_plugin(self, plugin_id: str) -> bool:
        manifest = self._manifests.get(plugin_id)
        if not manifest:
            return False
        return self._state.accept(plugin_id, manifest.version)

    def reject_plugin(self, plugin_id: str) -> bool:
        manifest = self._manifests.get(plugin_id)
        if not manifest:
            return False
        return self._state.reject(plugin_id, manifest.version)

    def toggle_plugin(self, plugin_id: str, enabled: bool) -> bool:
        manifest = self._manifests.get(plugin_id)
        if not manifest or manifest.builtin:
            return False
        return self._state.toggle(plugin_id, enabled)

    # ── Agent Loading ──────────────────────────────────────────

    def load_agent(self, manifest: PluginManifest) -> Any:
        """Dynamically import and instantiate the agent from a manifest.

        Uses the singleton factory function if available.
        """
        if manifest.id in self._agents:
            return self._agents[manifest.id]

        if not manifest.agent_module or not manifest.agent_factory:
            logger.warning(f"Plugin '{manifest.id}' has no agent_module/agent_factory")
            return None

        try:
            module = importlib.import_module(manifest.agent_module)
            factory: Callable = getattr(module, manifest.agent_factory)
            agent = factory()
            self._agents[manifest.id] = agent
            logger.info(f"Loaded agent for plugin '{manifest.id}': {manifest.agent_class}")
            return agent
        except (ImportError, AttributeError) as e:
            logger.error(f"Failed to load agent for plugin '{manifest.id}': {e}")
            return None

    def get_loaded_agent(self, plugin_id: str) -> Any:
        """Get a previously loaded agent (does not trigger import)."""
        return self._agents.get(plugin_id)

    # ── Route Aggregation ──────────────────────────────────────

    def get_event_routes(self) -> Dict[str, str]:
        """Aggregate event_routes from all enabled plugins."""
        routes: Dict[str, str] = {}
        for manifest in self.get_enabled_plugins():
            routes.update(manifest.event_routes)
        return routes

    # ── Classifier Context ─────────────────────────────────────

    def get_classifier_context(self) -> str:
        """Build classifier prompt additions from enabled plugin hints."""
        parts = []
        for manifest in self.get_enabled_plugins():
            hints = manifest.classifier_hints
            if not hints:
                continue

            lines = [f"### {manifest.name} (prefix: {manifest.id}.*)"]

            keywords = hints.get("keywords_de", []) + hints.get("keywords_en", [])
            if keywords:
                lines.append(f"Keywords: {', '.join(keywords)}")

            examples = hints.get("example_utterances", [])
            for ex in examples:
                lines.append(f'  "{ex.get("text", "")}" -> {ex.get("event_type", "")}')

            parts.append("\n".join(lines))

        return "\n\n".join(parts)

    # ── UI Info ────────────────────────────────────────────────

    def get_all_plugin_info(self) -> List[Dict[str, Any]]:
        """Return plugin info dicts for the dashboard UI."""
        self._ensure_discovered()
        states = self._state.get_all_states()
        result = []

        for m in self._manifests.values():
            state = states.get(m.id, {})
            version_seen = state.get("version_seen")

            is_new = not m.builtin and not self._state.has_state(m.id)
            is_updated = (not m.builtin and version_seen is not None
                          and version_seen != m.version)

            info = m.to_dict()
            info["enabled"] = self.is_enabled(m.id)
            info["is_new"] = is_new
            info["is_updated"] = is_updated
            result.append(info)

        return result


# ── Singleton ──────────────────────────────────────────────────

_plugin_manager: Optional[PluginManager] = None


def get_plugin_manager(db_path: Optional[Path] = None) -> PluginManager:
    """Get or create the PluginManager singleton."""
    global _plugin_manager
    if _plugin_manager is None:
        _plugin_manager = PluginManager(db_path)
    return _plugin_manager
