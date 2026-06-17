"""
n8n → Rowboat publisher.

Fetches workflow definitions from the n8n REST API and publishes their
metadata into the VibeMind workspace so Rowboat's rag-worker can index
them for semantic search.

Reads the n8n URL from N8N_API_URL (the repo-wide convention), falling
back to N8N_BASE_URL. N8N_API_KEY is optional — local Docker n8n runs
with auth disabled. Triggered on demand / at startup sync.
"""

import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from .base_publisher import BasePublisher, _slugify
from .knowledge_note_builder import build_project_note

logger = logging.getLogger(__name__)


class N8nPublisher(BasePublisher):

    space_name = "n8n"

    def _base_url(self) -> str:
        """n8n instance URL — N8N_API_URL (repo convention) or N8N_BASE_URL."""
        url = os.getenv("N8N_API_URL") or os.getenv("N8N_BASE_URL", "")
        return url.rstrip("/")

    def publish_workflow(
        self, workflow_name: str, workflow_data: Dict[str, Any]
    ) -> None:
        """Publish a single n8n workflow's metadata.

        Args:
            workflow_name: Workflow name.
            workflow_data: Raw workflow dict from the n8n API.
        """
        slug = _slugify(workflow_name)
        nodes = workflow_data.get("nodes", [])
        active = workflow_data.get("active", False)
        node_types = sorted({
            n.get("type", "?") for n in nodes if isinstance(n, dict)
        }) if isinstance(nodes, list) else []

        manifest = {
            "schema_version": "1.0",
            "space": "n8n",
            "type": "workflow",
            "published_at": datetime.now().isoformat(),
            "workflow": {
                "name": workflow_name,
                "id": workflow_data.get("id", ""),
                "active": bool(active),
                "node_count": len(nodes) if isinstance(nodes, list) else 0,
                "node_types": node_types,
            },
        }
        self._write_manifest(f"n8n/{slug}.json", manifest)

        key_facts = [
            f"Status: {'active' if active else 'inactive'}",
            f"{len(nodes) if isinstance(nodes, list) else 0} nodes",
        ]
        if node_types:
            key_facts.append(f"Node types: {', '.join(node_types[:8])}")

        knowledge_md = build_project_note(
            title=f"n8n Workflow: {workflow_name}",
            project_type="n8n-workflow",
            status="active" if active else "inactive",
            summary=f"n8n automation workflow '{workflow_name}'.",
            key_facts=key_facts,
            related_topics=["n8n", "Automation"],
            source_space="n8n",
        )
        self._write_knowledge_note("Workflows", workflow_name, knowledge_md)

        self._update_index(self._count_manifests())
        logger.debug(f"[N8nPublisher] Published workflow '{workflow_name}'")

    def _fetch_workflows(self) -> Optional[List[Dict[str, Any]]]:
        """Fetch the workflow list from the n8n API.

        Returns the list, or None if the API is unreachable / unconfigured
        (distinct from an empty list, which means 'zero workflows').
        """
        base_url = self._base_url()
        if not base_url:
            logger.debug("[N8nPublisher] N8N_BASE_URL not set — skipping")
            return None
        try:
            import httpx
        except ImportError:
            logger.warning("[N8nPublisher] httpx not installed — skipping")
            return None
        try:
            resp = httpx.get(
                f"{base_url}/api/v1/workflows",
                headers={"X-N8N-API-KEY": os.getenv("N8N_API_KEY", "")},
                timeout=10,
            )
            resp.raise_for_status()
            return resp.json().get("data", [])
        except Exception as e:
            logger.warning(f"[N8nPublisher] n8n API unreachable: {e}")
            return None

    def _publish_workflow_list(self, workflows: List[Dict[str, Any]]) -> int:
        """Publish a list of workflow dicts. Returns the count published."""
        published = 0
        for wf in workflows:
            try:
                self.publish_workflow(wf.get("name", "Unnamed"), wf)
                published += 1
            except Exception as e:
                logger.debug(f"[N8nPublisher] skip '{wf.get('name')}': {e}")
        return published

    def publish_all_workflows(self) -> int:
        """Fetch all workflows from the n8n API and publish them.

        Returns the number published, or 0 if the API is unreachable /
        not configured.
        """
        workflows = self._fetch_workflows()
        if workflows is None:
            return 0
        published = self._publish_workflow_list(workflows)
        logger.info(f"[N8nPublisher] Published {published} workflows")
        return published

    def mirror(self) -> int:
        """Mirror the n8n API workflow list into the workspace folder.

        Fetches first; only clears + rewrites the n8n/ folder once the API
        responded. A transient outage leaves the existing mirror intact —
        a stale mirror beats an empty one.
        """
        workflows = self._fetch_workflows()
        if workflows is None:
            logger.debug("[N8nPublisher] mirror skipped — API unreachable")
            return 0
        self.mirror_clean()
        published = self._publish_workflow_list(workflows)
        logger.info(f"[N8nPublisher] Mirrored {published} workflows")
        return published
