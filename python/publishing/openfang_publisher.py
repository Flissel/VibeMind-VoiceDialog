"""
OpenFang → Rowboat publisher.

Reads agent definitions from OpenFang's live workspace (~/.openfang/agents/)
and publishes their metadata into the VibeMind workspace so Rowboat's
rag-worker can index them for semantic search.

Source of truth stays in ~/.openfang/ — this only publishes derived,
read-only metadata. Triggered on demand / at startup sync.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base_publisher import BasePublisher, _slugify
from .knowledge_note_builder import build_project_note

logger = logging.getLogger(__name__)

try:
    import tomllib  # Python 3.11+
    _HAS_TOML = True
except ImportError:  # pragma: no cover
    try:
        import tomli as tomllib  # type: ignore
        _HAS_TOML = True
    except ImportError:
        _HAS_TOML = False


class OpenFangPublisher(BasePublisher):

    space_name = "openfang"

    def _agents_dir(self) -> Path:
        """OpenFang's live agent directory."""
        return Path.home() / ".openfang" / "agents"

    def _read_agent_toml(self, agent_dir: Path) -> Optional[Dict[str, Any]]:
        """Parse an agent.toml file. Returns None if missing/unparseable."""
        toml_path = agent_dir / "agent.toml"
        if not toml_path.exists() or not _HAS_TOML:
            return None
        try:
            return tomllib.loads(toml_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            logger.debug(f"[OpenFangPublisher] skip {toml_path}: {e}")
            return None

    def publish_agent(self, agent_name: str) -> bool:
        """Publish a single OpenFang agent's metadata.

        Returns True on success, False if the agent could not be read.
        """
        agent_dir = self._agents_dir() / agent_name
        if not agent_dir.is_dir():
            logger.debug(f"[OpenFangPublisher] agent '{agent_name}' not found")
            return False

        config = self._read_agent_toml(agent_dir) or {}
        slug = _slugify(agent_name)

        # agent.toml top-level keys: name, version, description, module,
        # tags, [model], fallback_models, [resources], [capabilities].
        # Extract flat metadata only — never embed the system_prompt etc.
        description = config.get("description", "")
        version = config.get("version", "")
        module = config.get("module", "")
        tags = config.get("tags", [])

        model_cfg = config.get("model", {})
        if isinstance(model_cfg, dict):
            model = model_cfg.get("model", "")
            provider = model_cfg.get("provider", "")
        else:  # tolerate a plain-string model field
            model = str(model_cfg)
            provider = ""

        caps = config.get("capabilities", {})
        tools = caps.get("tools", []) if isinstance(caps, dict) else []
        tool_count = len(tools) if isinstance(tools, list) else 0

        manifest = {
            "schema_version": "1.0",
            "space": "openfang",
            "type": "agent",
            "published_at": datetime.now().isoformat(),
            "agent": {
                "name": agent_name,
                "version": version,
                "module": module,
                "provider": provider,
                "model": model,
                "description": description,
                "tags": tags if isinstance(tags, list) else [],
                "tool_count": tool_count,
            },
            "artifact_ref": {
                "type": "directory",
                "base_path": str(agent_dir),
            },
        }
        self._write_manifest(f"openfang/{slug}.json", manifest)

        key_facts = []
        if model:
            key_facts.append(
                f"Model: {provider + '/' if provider else ''}{model}"
            )
        if module:
            key_facts.append(f"Module: {module}")
        if tool_count:
            key_facts.append(f"{tool_count} tools")
        if isinstance(tags, list) and tags:
            key_facts.append(f"Tags: {', '.join(str(t) for t in tags)}")
        key_facts.append(f"Definition: {agent_dir / 'agent.toml'}")

        knowledge_md = build_project_note(
            title=f"OpenFang Agent: {agent_name}",
            project_type="openfang-agent",
            status="active",
            summary=description or f"OpenFang agent '{agent_name}'.",
            key_facts=key_facts,
            related_topics=["OpenFang", "Agents"],
            source_space="OpenFang",
        )
        self._write_knowledge_note("Agents", agent_name, knowledge_md)

        self._update_index(self._count_manifests())
        logger.debug(f"[OpenFangPublisher] Published agent '{agent_name}'")
        return True

    def publish_all_agents(self) -> int:
        """Publish every agent found in ~/.openfang/agents/. Returns count."""
        agents_dir = self._agents_dir()
        if not agents_dir.is_dir():
            logger.debug("[OpenFangPublisher] no ~/.openfang/agents/ directory")
            return 0

        published = 0
        for agent_dir in sorted(agents_dir.iterdir()):
            if agent_dir.is_dir() and self.publish_agent(agent_dir.name):
                published += 1
        logger.info(f"[OpenFangPublisher] Published {published} agents")
        return published

    def mirror(self) -> int:
        """Mirror ~/.openfang/agents/ into the workspace folder.

        Clears the openfang/ folder first, then republishes every agent,
        so removed agents drop out and the folder reflects the live state.
        """
        self.mirror_clean()
        return self.publish_all_agents()
