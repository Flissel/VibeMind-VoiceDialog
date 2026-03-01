"""
SWE Design Space → Rowboat publisher.

Publishes RE pipeline metadata after pipeline completion.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from .base_publisher import BasePublisher, _slugify
from .knowledge_note_builder import build_project_note

logger = logging.getLogger(__name__)


class SweDesignPublisher(BasePublisher):

    space_name = "swe-design"

    def publish_pipeline(
        self,
        project_name: str,
        output_dir: str,
        manifest_data: Dict[str, Any],
    ):
        """Publish an RE pipeline's metadata after completion.

        Args:
            project_name: Project name (e.g. 'whatsapp-messaging-service')
            output_dir: Path to the enterprise_output/{name}_{ts}/ directory
            manifest_data: Dict from PipelineManifest.to_dict()
        """
        slug = _slugify(project_name)
        output_path = Path(output_dir)

        # Extract stage info
        stages = manifest_data.get("stages", [])
        completed = sum(1 for s in stages if s.get("status") == "completed")
        total = len(stages)

        # Count key outputs from the output directory
        key_outputs = {}
        if output_path.exists():
            us_file = output_path / "user_stories.json"
            if us_file.exists():
                try:
                    us_data = json.loads(us_file.read_text(encoding="utf-8"))
                    key_outputs["user_stories_count"] = len(us_data) if isinstance(us_data, list) else 0
                except (json.JSONDecodeError, OSError):
                    pass

            diagrams_dir = output_path / "diagrams"
            if diagrams_dir.exists():
                key_outputs["diagrams_count"] = len(list(diagrams_dir.glob("*.mmd")))

            key_outputs["has_master_document"] = (output_path / "MASTER_DOCUMENT.md").exists()

        # Build manifest
        manifest = {
            "schema_version": "1.0",
            "space": "swe_design",
            "type": "re_pipeline",
            "published_at": datetime.now().isoformat(),
            "project": {
                "name": project_name,
                "pipeline_id": manifest_data.get("pipeline_id", ""),
                "status": "completed" if completed == total else "in_progress",
                "total_stages": total,
                "completed_stages": completed,
            },
            "key_outputs": key_outputs,
            "artifact_ref": {
                "type": "directory",
                "base_path": str(output_path),
            },
        }

        self._write_manifest(f"swe-design/{slug}.json", manifest)

        # Build knowledge note
        key_facts = [
            f"{completed}/{total} pipeline stages completed",
        ]
        if key_outputs.get("user_stories_count"):
            key_facts.append(f"{key_outputs['user_stories_count']} user stories generated")
        if key_outputs.get("diagrams_count"):
            key_facts.append(f"{key_outputs['diagrams_count']} Mermaid diagrams")
        if key_outputs.get("has_master_document"):
            key_facts.append("Full MASTER_DOCUMENT.md available")
        key_facts.append(f"Output: {output_path}")

        knowledge_md = build_project_note(
            title=project_name,
            project_type="requirements-engineering",
            status="completed" if completed == total else "in-progress",
            summary=f"Requirements engineering pipeline for {project_name}.",
            key_facts=key_facts,
            related_topics=["Requirements Engineering"],
            source_space="SWE Design",
        )
        self._write_knowledge_note("Projects", project_name, knowledge_md)

        self._update_index(self._count_manifests())
        logger.debug(f"[SweDesignPublisher] Published pipeline '{project_name}'")
