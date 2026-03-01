"""
Arch-Team → Rowboat publisher (dual-write).

After mining, writes:
  1. JSON to re_ideas/{service}.json  (direct input for RE pipeline)
  2. Manifest to ~/.rowboat/vibemind/arch-team/{slug}.json
  3. Knowledge note to ~/.rowboat/knowledge/Projects/{Name}.md
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base_publisher import BasePublisher, _slugify
from .knowledge_note_builder import build_project_note

logger = logging.getLogger(__name__)


class ArchTeamPublisher(BasePublisher):

    space_name = "arch-team"

    def publish_requirements(
        self,
        project_name: str,
        requirements: List[Dict[str, Any]],
        source_type: str = "upload",
        validation_stats: Optional[Dict[str, Any]] = None,
        re_ideas_dir: Optional[str] = None,
    ):
        """Publish requirement set metadata with dual-write.

        Args:
            project_name: Project/service name
            requirements: List of requirement dicts
            source_type: How requirements were sourced (upload, api, etc.)
            validation_stats: Optional validation results
            re_ideas_dir: Path to re_ideas/ directory for dual-write
        """
        slug = _slugify(project_name)

        # Count by tag
        by_tag: Dict[str, int] = {}
        for req in requirements:
            tags = req.get("tags", [])
            if isinstance(tags, list):
                for tag in tags:
                    by_tag[tag] = by_tag.get(tag, 0) + 1
            elif isinstance(tags, str):
                by_tag[tags] = by_tag.get(tags, 0) + 1

        # Dual-write: copy to re_ideas/ if path provided
        re_ideas_path = None
        if re_ideas_dir:
            re_ideas_root = Path(re_ideas_dir)
            re_ideas_root.mkdir(parents=True, exist_ok=True)
            re_ideas_file = re_ideas_root / f"{slug}.json"
            re_ideas_file.write_text(
                json.dumps(requirements, indent=2, ensure_ascii=False, default=str),
                encoding="utf-8",
            )
            re_ideas_path = str(re_ideas_file)
            logger.debug(f"[ArchTeamPublisher] Dual-write to {re_ideas_file}")

        # Build manifest
        manifest = {
            "schema_version": "1.0",
            "space": "arch_team",
            "type": "requirement_set",
            "published_at": datetime.now().isoformat(),
            "project": {
                "name": project_name,
                "source_type": source_type,
            },
            "requirements_summary": {
                "total_count": len(requirements),
                "by_tag": by_tag,
            },
            "artifact_ref": {
                "type": "api",
                "base_url": "http://localhost:8000",
            },
        }

        if validation_stats:
            manifest["requirements_summary"]["validation_stats"] = validation_stats

        if re_ideas_path:
            manifest["re_ideas_path"] = re_ideas_path

        self._write_manifest(f"arch-team/{slug}.json", manifest)

        # Build knowledge note
        key_facts = [
            f"{len(requirements)} requirements mined",
        ]
        if by_tag:
            tag_summary = ", ".join(f"{k}: {v}" for k, v in sorted(by_tag.items(), key=lambda x: -x[1])[:5])
            key_facts.append(f"By category: {tag_summary}")
        if validation_stats:
            passed = validation_stats.get("passed", 0)
            total = validation_stats.get("validated", len(requirements))
            if total > 0:
                key_facts.append(f"Validation: {passed}/{total} passed ({100*passed//total}%)")
        if re_ideas_path:
            key_facts.append(f"RE pipeline input: {re_ideas_path}")

        knowledge_md = build_project_note(
            title=project_name,
            project_type="requirements-analysis",
            status="completed",
            summary=f"Requirements extracted from {source_type} for {project_name}.",
            key_facts=key_facts,
            related_topics=["Requirements Engineering"],
            source_space="Arch-Team",
        )
        self._write_knowledge_note("Projects", project_name, knowledge_md)

        self._update_index(self._count_manifests())
        logger.debug(f"[ArchTeamPublisher] Published requirements for '{project_name}'")
