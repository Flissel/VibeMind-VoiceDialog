"""
MiroFish → Rowboat publisher.

Reads project + simulation metadata from the MiroFish HTTP API and
publishes it into the VibeMind workspace so Rowboat's rag-worker can
index it for semantic search.

Source of truth remains MiroFish itself (Neo4j graph + HTTP API on
:5001) — this only publishes derived read-only metadata. Triggered on
demand / by the periodic sync_all_spaces loop.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from .base_publisher import BasePublisher, _slugify
from .knowledge_note_builder import build_project_note

logger = logging.getLogger(__name__)


class MiroFishPublisher(BasePublisher):

    space_name = "mirofish"

    def _list_projects(self) -> Optional[List[Dict[str, Any]]]:
        """Fetch MiroFish projects via the tool layer.

        Returns the list, or None if the backend is unreachable / disabled
        (distinct from an empty list, which means 'zero projects').
        """
        try:
            from spaces.mirofish.tools.mirofish_tools import list_projects
        except ImportError as e:
            logger.debug(f"[MiroFishPublisher] tools unavailable: {e}")
            return None
        try:
            result = list_projects()
        except Exception as e:
            logger.warning(f"[MiroFishPublisher] list_projects failed: {e}")
            return None
        if not isinstance(result, dict) or not result.get("success"):
            return None
        return result.get("projects", [])

    def _fetch_status(self) -> Optional[Dict[str, Any]]:
        """Fetch the MiroFish service status snapshot."""
        try:
            from spaces.mirofish.tools.mirofish_tools import get_status
        except ImportError:
            return None
        try:
            result = get_status()
            return result if isinstance(result, dict) else None
        except Exception as e:
            logger.debug(f"[MiroFishPublisher] get_status failed: {e}")
            return None

    def publish_project(self, project: Dict[str, Any]) -> None:
        """Publish a single MiroFish project's metadata."""
        name = project.get("name") or project.get("id") or "Unnamed"
        slug = _slugify(str(name))

        manifest = {
            "schema_version": "1.0",
            "space": self.space_name,
            "type": "mirofish_project",
            "published_at": datetime.now().isoformat(),
            "project": {
                "id": project.get("id", ""),
                "name": name,
                "node_count": project.get("node_count", 0),
                "edge_count": project.get("edge_count", 0),
                "status": project.get("status", ""),
                "score": project.get("score"),
            },
        }
        self._write_manifest(f"{self.space_name}/{slug}.json", manifest)

        key_facts = []
        if project.get("node_count"):
            key_facts.append(f"{project['node_count']} nodes")
        if project.get("edge_count"):
            key_facts.append(f"{project['edge_count']} edges")
        if project.get("status"):
            key_facts.append(f"Status: {project['status']}")
        if project.get("score") is not None:
            key_facts.append(f"Score: {project['score']}")

        knowledge_md = build_project_note(
            title=f"MiroFish Project: {name}",
            project_type="mirofish-simulation",
            status=project.get("status", "active"),
            summary=f"MiroFish knowledge-graph project '{name}'.",
            key_facts=key_facts,
            related_topics=["MiroFish", "Knowledge Graph"],
            source_space="MiroFish",
        )
        self._write_knowledge_note("Simulations", str(name), knowledge_md)

    def publish_status_snapshot(self) -> None:
        """Write a single status snapshot manifest for the MiroFish service."""
        status = self._fetch_status() or {}
        manifest = {
            "schema_version": "1.0",
            "space": self.space_name,
            "type": "mirofish_status",
            "published_at": datetime.now().isoformat(),
            "status": status,
        }
        self._write_manifest(f"{self.space_name}/status_snapshot.json", manifest)

    def publish_all_projects(self) -> int:
        """Publish every MiroFish project. Returns the count published."""
        projects = self._list_projects()
        if projects is None:
            logger.debug("[MiroFishPublisher] backend unreachable — skipping")
            return 0
        published = 0
        for project in projects:
            try:
                self.publish_project(project)
                published += 1
            except Exception as e:
                logger.debug(
                    f"[MiroFishPublisher] skip {project.get('id', '?')}: {e}"
                )
        logger.info(f"[MiroFishPublisher] Published {published} projects")
        return published

    def mirror(self) -> int:
        """Mirror the MiroFish project list + status into the workspace.

        Fetches first; only clears + rewrites the mirofish/ folder once the
        backend responded. A transient outage leaves the existing mirror
        intact — a stale mirror beats an empty one.
        """
        projects = self._list_projects()
        if projects is None:
            logger.debug("[MiroFishPublisher] mirror skipped — backend unreachable")
            return 0
        self.mirror_clean()
        published = 0
        for project in projects:
            try:
                self.publish_project(project)
                published += 1
            except Exception as e:
                logger.debug(
                    f"[MiroFishPublisher] skip {project.get('id', '?')}: {e}"
                )
        # Always include a status snapshot alongside the per-project manifests.
        try:
            self.publish_status_snapshot()
        except Exception as e:
            logger.debug(f"[MiroFishPublisher] status snapshot skipped: {e}")
        logger.info(f"[MiroFishPublisher] Mirrored {published} projects")
        return published
