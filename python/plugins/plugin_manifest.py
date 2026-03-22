"""
Plugin Manifest - Dataclass and JSON loader for plugin.json files.

Each space (builtin or community) has a plugin.json that describes
the agent, event routes, and metadata for the Plugin Manager.
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

REQUIRED_FIELDS = {"id", "version", "name", "description", "agent_module", "agent_class", "agent_factory", "stream", "event_routes"}


@dataclass
class PluginManifest:
    """Describes a VibeMind space plugin."""

    # Identity
    id: str
    version: str
    name: str
    description: str
    author: str = "VibeMind Team"
    category: str = "general"
    changelog: str = ""

    # Agent loading
    agent_module: str = ""       # e.g. "spaces.n8n.agents.n8n_agent"
    agent_class: str = ""        # e.g. "N8nBackendAgent"
    agent_factory: str = ""      # e.g. "get_n8n_agent"

    # Routing
    stream: str = ""             # e.g. "events:tasks:n8n"
    event_routes: Dict[str, str] = field(default_factory=dict)

    # Classifier integration
    classifier_hints: Dict[str, Any] = field(default_factory=dict)

    # Flags
    builtin: bool = False
    env_flag: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)

    # Resolved at load time
    plugin_dir: Optional[str] = None

    @classmethod
    def from_json(cls, path: Path) -> Optional["PluginManifest"]:
        """Load and validate a plugin.json file.

        Returns None if the file is missing or invalid.
        """
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            logger.warning(f"Could not load plugin manifest {path}: {e}")
            return None

        missing = REQUIRED_FIELDS - set(data.keys())
        if missing:
            logger.warning(f"Plugin manifest {path} missing fields: {missing}")
            return None

        try:
            manifest = cls(
                id=data["id"],
                version=data["version"],
                name=data["name"],
                description=data["description"],
                author=data.get("author", "VibeMind Team"),
                category=data.get("category", "general"),
                changelog=data.get("changelog", ""),
                agent_module=data.get("agent_module", ""),
                agent_class=data.get("agent_class", ""),
                agent_factory=data.get("agent_factory", ""),
                stream=data.get("stream", ""),
                event_routes=data.get("event_routes", {}),
                classifier_hints=data.get("classifier_hints", {}),
                builtin=data.get("builtin", False),
                env_flag=data.get("env_flag"),
                dependencies=data.get("dependencies", []),
                plugin_dir=str(path.parent),
            )
            return manifest
        except (TypeError, KeyError) as e:
            logger.warning(f"Invalid plugin manifest {path}: {e}")
            return None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for IPC / UI display."""
        return {
            "id": self.id,
            "version": self.version,
            "name": self.name,
            "description": self.description,
            "author": self.author,
            "category": self.category,
            "changelog": self.changelog,
            "stream": self.stream,
            "event_count": len(self.event_routes),
            "builtin": self.builtin,
            "env_flag": self.env_flag,
            "dependencies": self.dependencies,
        }
