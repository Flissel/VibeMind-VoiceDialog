"""
Tests for the Plugin Manager system.

Tests manifest loading, plugin discovery, state persistence,
and dynamic agent loading.
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from plugins.plugin_manifest import PluginManifest
from plugins.plugin_state import PluginStateRepository
from plugins.plugin_manager import PluginManager


class TestPluginManifest(unittest.TestCase):
    """Test plugin.json loading and validation."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())

    def _write_manifest(self, data: dict, name: str = "test") -> Path:
        plugin_dir = self.tmpdir / name
        plugin_dir.mkdir(exist_ok=True)
        path = plugin_dir / "plugin.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def test_valid_manifest(self):
        path = self._write_manifest({
            "id": "test",
            "version": "1.0.0",
            "name": "Test Plugin",
            "description": "A test plugin",
            "agent_module": "spaces.test.agents.test_agent",
            "agent_class": "TestAgent",
            "agent_factory": "get_test_agent",
            "stream": "events:tasks:test",
            "event_routes": {"test.hello": "events:tasks:test"},
        })
        m = PluginManifest.from_json(path)
        self.assertIsNotNone(m)
        self.assertEqual(m.id, "test")
        self.assertEqual(m.version, "1.0.0")
        self.assertEqual(m.event_routes, {"test.hello": "events:tasks:test"})
        self.assertEqual(m.plugin_dir, str(path.parent))

    def test_missing_required_fields(self):
        path = self._write_manifest({
            "id": "incomplete",
            "version": "1.0.0",
            # Missing: name, description, agent_module, etc.
        })
        m = PluginManifest.from_json(path)
        self.assertIsNone(m)

    def test_invalid_json(self):
        plugin_dir = self.tmpdir / "bad"
        plugin_dir.mkdir()
        path = plugin_dir / "plugin.json"
        path.write_text("not json", encoding="utf-8")
        m = PluginManifest.from_json(path)
        self.assertIsNone(m)

    def test_nonexistent_file(self):
        m = PluginManifest.from_json(self.tmpdir / "nope" / "plugin.json")
        self.assertIsNone(m)

    def test_to_dict(self):
        path = self._write_manifest({
            "id": "x",
            "version": "2.0.0",
            "name": "X Plugin",
            "description": "Desc",
            "agent_module": "m",
            "agent_class": "C",
            "agent_factory": "f",
            "stream": "s",
            "event_routes": {"x.a": "s", "x.b": "s"},
            "builtin": True,
        })
        m = PluginManifest.from_json(path)
        d = m.to_dict()
        self.assertEqual(d["id"], "x")
        self.assertEqual(d["event_count"], 2)
        self.assertTrue(d["builtin"])

    def test_optional_fields_default(self):
        path = self._write_manifest({
            "id": "minimal",
            "version": "1.0.0",
            "name": "Minimal",
            "description": "Min",
            "agent_module": "m",
            "agent_class": "C",
            "agent_factory": "f",
            "stream": "s",
            "event_routes": {},
        })
        m = PluginManifest.from_json(path)
        self.assertEqual(m.author, "VibeMind Team")
        self.assertEqual(m.category, "general")
        self.assertFalse(m.builtin)
        self.assertIsNone(m.env_flag)
        self.assertEqual(m.dependencies, [])
        self.assertEqual(m.classifier_hints, {})


class TestPluginState(unittest.TestCase):
    """Test SQLite state persistence."""

    def setUp(self):
        self.db_path = Path(tempfile.mktemp(suffix=".db"))
        self.repo = PluginStateRepository(db_path=self.db_path)

    def tearDown(self):
        if self.db_path.exists():
            self.db_path.unlink()

    def test_no_state_initially(self):
        self.assertFalse(self.repo.has_state("test"))
        self.assertFalse(self.repo.is_enabled("test"))
        self.assertIsNone(self.repo.get_version_seen("test"))

    def test_accept(self):
        self.repo.accept("test", "1.0.0")
        self.assertTrue(self.repo.has_state("test"))
        self.assertTrue(self.repo.is_enabled("test"))
        self.assertEqual(self.repo.get_version_seen("test"), "1.0.0")

    def test_reject(self):
        self.repo.reject("test", "1.0.0")
        self.assertTrue(self.repo.has_state("test"))
        self.assertFalse(self.repo.is_enabled("test"))
        self.assertEqual(self.repo.get_version_seen("test"), "1.0.0")

    def test_toggle(self):
        self.repo.accept("test", "1.0.0")
        self.assertTrue(self.repo.is_enabled("test"))
        self.repo.toggle("test", False)
        self.assertFalse(self.repo.is_enabled("test"))
        self.repo.toggle("test", True)
        self.assertTrue(self.repo.is_enabled("test"))

    def test_accept_overwrites_reject(self):
        self.repo.reject("test", "1.0.0")
        self.assertFalse(self.repo.is_enabled("test"))
        self.repo.accept("test", "2.0.0")
        self.assertTrue(self.repo.is_enabled("test"))
        self.assertEqual(self.repo.get_version_seen("test"), "2.0.0")

    def test_get_all_states(self):
        self.repo.accept("a", "1.0")
        self.repo.reject("b", "2.0")
        states = self.repo.get_all_states()
        self.assertIn("a", states)
        self.assertIn("b", states)
        self.assertTrue(states["a"]["enabled"])
        self.assertFalse(states["b"]["enabled"])


class TestPluginManager(unittest.TestCase):
    """Test discovery, state management, and route aggregation."""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.db_path = Path(tempfile.mktemp(suffix=".db"))

        # Create builtin and community dirs
        self.builtin_dir = self.tmpdir / "builtin"
        self.community_dir = self.tmpdir / "community"
        self.builtin_dir.mkdir()
        self.community_dir.mkdir()

        # Patch the PluginManager dirs
        import plugins.plugin_manager as pm_mod
        self._orig_builtin = pm_mod._BUILTIN_DIR
        self._orig_community = pm_mod._COMMUNITY_DIR
        pm_mod._BUILTIN_DIR = self.builtin_dir
        pm_mod._COMMUNITY_DIR = self.community_dir

        self.manager = PluginManager(db_path=self.db_path)

    def tearDown(self):
        import plugins.plugin_manager as pm_mod
        pm_mod._BUILTIN_DIR = self._orig_builtin
        pm_mod._COMMUNITY_DIR = self._orig_community
        if self.db_path.exists():
            self.db_path.unlink()

    def _add_plugin(self, base_dir: Path, plugin_id: str, builtin: bool = False, **extra):
        d = base_dir / plugin_id
        d.mkdir(exist_ok=True)
        manifest = {
            "id": plugin_id,
            "version": extra.get("version", "1.0.0"),
            "name": extra.get("name", plugin_id.title()),
            "description": f"Test {plugin_id}",
            "agent_module": f"spaces.{plugin_id}.agents.{plugin_id}_agent",
            "agent_class": f"{plugin_id.title()}Agent",
            "agent_factory": f"get_{plugin_id}_agent",
            "stream": f"events:tasks:{plugin_id}",
            "event_routes": {f"{plugin_id}.test": f"events:tasks:{plugin_id}"},
            "builtin": builtin,
            **{k: v for k, v in extra.items() if k not in ("version", "name")},
        }
        (d / "plugin.json").write_text(json.dumps(manifest), encoding="utf-8")

    def test_discover_builtin(self):
        self._add_plugin(self.builtin_dir, "ideas", builtin=True)
        self._add_plugin(self.builtin_dir, "coding", builtin=True)
        plugins = self.manager.discover_plugins()
        self.assertEqual(len(plugins), 2)
        self.assertTrue(all(p.builtin for p in plugins))

    def test_discover_community(self):
        self._add_plugin(self.community_dir, "marketing")
        plugins = self.manager.discover_plugins()
        self.assertEqual(len(plugins), 1)
        self.assertFalse(plugins[0].builtin)

    def test_builtin_always_enabled(self):
        self._add_plugin(self.builtin_dir, "ideas", builtin=True)
        self.manager.discover_plugins()
        self.assertTrue(self.manager.is_enabled("ideas"))

    def test_community_disabled_by_default(self):
        self._add_plugin(self.community_dir, "marketing")
        self.manager.discover_plugins()
        self.assertFalse(self.manager.is_enabled("marketing"))

    def test_accept_enables_community(self):
        self._add_plugin(self.community_dir, "marketing")
        self.manager.discover_plugins()
        self.manager.accept_plugin("marketing")
        self.assertTrue(self.manager.is_enabled("marketing"))

    def test_reject_keeps_disabled(self):
        self._add_plugin(self.community_dir, "marketing")
        self.manager.discover_plugins()
        self.manager.reject_plugin("marketing")
        self.assertFalse(self.manager.is_enabled("marketing"))

    def test_toggle_community(self):
        self._add_plugin(self.community_dir, "marketing")
        self.manager.discover_plugins()
        self.manager.accept_plugin("marketing")
        self.assertTrue(self.manager.is_enabled("marketing"))
        self.manager.toggle_plugin("marketing", False)
        self.assertFalse(self.manager.is_enabled("marketing"))

    def test_cannot_toggle_builtin(self):
        self._add_plugin(self.builtin_dir, "ideas", builtin=True)
        self.manager.discover_plugins()
        result = self.manager.toggle_plugin("ideas", False)
        self.assertFalse(result)
        self.assertTrue(self.manager.is_enabled("ideas"))

    def test_get_new_plugins(self):
        self._add_plugin(self.builtin_dir, "ideas", builtin=True)
        self._add_plugin(self.community_dir, "marketing")
        self.manager.discover_plugins()
        new = self.manager.get_new_plugins()
        self.assertEqual(len(new), 1)
        self.assertEqual(new[0].id, "marketing")

    def test_get_new_plugins_after_accept(self):
        self._add_plugin(self.community_dir, "marketing")
        self.manager.discover_plugins()
        self.manager.accept_plugin("marketing")
        new = self.manager.get_new_plugins()
        self.assertEqual(len(new), 0)

    def test_get_updated_plugins(self):
        self._add_plugin(self.community_dir, "marketing", version="2.0.0")
        self.manager.discover_plugins()
        # Accept v2.0.0
        self.manager.accept_plugin("marketing")
        # Simulate version bump in manifest
        self._add_plugin(self.community_dir, "marketing", version="3.0.0")
        self.manager.discover_plugins()  # Re-discover
        updated = self.manager.get_updated_plugins()
        self.assertEqual(len(updated), 1)
        self.assertEqual(updated[0].version, "3.0.0")

    def test_get_event_routes(self):
        self._add_plugin(self.builtin_dir, "ideas", builtin=True)
        self._add_plugin(self.community_dir, "marketing")
        self.manager.discover_plugins()
        self.manager.accept_plugin("marketing")
        routes = self.manager.get_event_routes()
        self.assertIn("ideas.test", routes)
        self.assertIn("marketing.test", routes)

    def test_get_event_routes_excludes_disabled(self):
        self._add_plugin(self.community_dir, "marketing")
        self.manager.discover_plugins()
        # Not accepted = disabled
        routes = self.manager.get_event_routes()
        self.assertNotIn("marketing.test", routes)

    def test_get_all_plugin_info(self):
        self._add_plugin(self.builtin_dir, "ideas", builtin=True)
        self._add_plugin(self.community_dir, "marketing")
        self.manager.discover_plugins()
        info = self.manager.get_all_plugin_info()
        self.assertEqual(len(info), 2)
        ideas_info = next(p for p in info if p["id"] == "ideas")
        marketing_info = next(p for p in info if p["id"] == "marketing")
        self.assertTrue(ideas_info["enabled"])
        self.assertTrue(ideas_info["builtin"])
        self.assertFalse(marketing_info["enabled"])
        self.assertTrue(marketing_info["is_new"])

    def test_get_classifier_context(self):
        self._add_plugin(self.builtin_dir, "ideas", builtin=True,
                         classifier_hints={
                             "keywords_de": ["idee"],
                             "example_utterances": [
                                 {"text": "Neue Idee", "event_type": "ideas.test"}
                             ]
                         })
        self.manager.discover_plugins()
        ctx = self.manager.get_classifier_context()
        self.assertIn("Ideas", ctx)
        self.assertIn("idee", ctx)
        self.assertIn("Neue Idee", ctx)


class TestBuiltinManifests(unittest.TestCase):
    """Verify all 10 builtin plugin.json files are valid."""

    def test_all_builtin_manifests_load(self):
        builtin_dir = Path(__file__).resolve().parent.parent / "plugins" / "builtin"
        if not builtin_dir.exists():
            self.skipTest("Builtin dir not found")

        manifests = []
        for plugin_json in sorted(builtin_dir.rglob("plugin.json")):
            m = PluginManifest.from_json(plugin_json)
            self.assertIsNotNone(m, f"Failed to load {plugin_json}")
            manifests.append(m)

        # Expect 10 builtin plugins
        self.assertEqual(len(manifests), 10, f"Expected 10 builtin plugins, got {len(manifests)}")

        # All should be marked builtin
        for m in manifests:
            self.assertTrue(m.builtin, f"Plugin '{m.id}' should be builtin")

        # All IDs should be unique
        ids = [m.id for m in manifests]
        self.assertEqual(len(ids), len(set(ids)), f"Duplicate plugin IDs: {ids}")

    def test_event_routes_match_event_router(self):
        """Verify plugin event_routes cover the same events as the static EventRouter."""
        builtin_dir = Path(__file__).resolve().parent.parent / "plugins" / "builtin"
        if not builtin_dir.exists():
            self.skipTest("Builtin dir not found")

        # Aggregate all routes from plugin manifests
        plugin_routes = {}
        for plugin_json in builtin_dir.rglob("plugin.json"):
            m = PluginManifest.from_json(plugin_json)
            if m:
                plugin_routes.update(m.event_routes)

        # Load static routes from EventRouter (excluding status events)
        from swarm.event_team.event_router import EventRouter
        static_routes = {k: v for k, v in EventRouter.STREAM_MAPPING.items()
                         if not k.startswith("task.")}

        # All static routes should be covered by plugin manifests
        missing = set(static_routes.keys()) - set(plugin_routes.keys())
        self.assertEqual(missing, set(),
                         f"Static routes missing from plugin manifests: {missing}")


if __name__ == "__main__":
    unittest.main()
