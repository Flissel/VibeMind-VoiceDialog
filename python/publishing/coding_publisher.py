"""
Coding Engine → Rowboat publisher.

Publishes code project metadata on status transitions.
"""

import logging
from datetime import datetime
from typing import Any, Dict, Optional

from .base_publisher import BasePublisher, _slugify
from .knowledge_note_builder import build_project_note

logger = logging.getLogger(__name__)


class CodingPublisher(BasePublisher):

    space_name = "coding"

    def publish_project(
        self,
        project_name: str,
        tech_stack: str = "",
        status: str = "generating",
        progress: float = 0.0,
        data_dir: str = "",
    ):
        """Publish a coding project's metadata.

        Args:
            project_name: Project name
            tech_stack: Technology stack used
            status: Generation status (generating, completed, failed)
            progress: Progress percentage (0-100)
            data_dir: Path to Data/all_services/{name}/ directory
        """
        slug = _slugify(project_name)

        manifest = {
            "schema_version": "1.0",
            "space": "coding",
            "type": "code_project",
            "published_at": datetime.now().isoformat(),
            "project": {
                "name": project_name,
                "tech_stack": tech_stack,
                "status": status,
                "progress": progress,
            },
            "artifact_ref": {
                "type": "directory",
                "base_path": data_dir,
            },
        }

        self._write_manifest(f"coding/{slug}.json", manifest)

        # Build knowledge note
        key_facts = [
            f"Status: {status}",
            f"Progress: {progress:.0f}%",
        ]
        if tech_stack:
            key_facts.append(f"Tech stack: {tech_stack}")
        if data_dir:
            key_facts.append(f"Output: {data_dir}")

        knowledge_md = build_project_note(
            title=project_name,
            project_type="code-generation",
            status=status,
            summary=f"Code generation project using {tech_stack or 'auto-detected stack'}.",
            key_facts=key_facts,
            source_space="Coding Engine",
        )
        self._write_knowledge_note("Projects", project_name, knowledge_md)

        self._update_index(self._count_manifests())
        logger.debug(f"[CodingPublisher] Published project '{project_name}' ({status})")
