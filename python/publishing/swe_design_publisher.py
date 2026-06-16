"""
SWE Design Space → Rowboat / Supabase publisher.

Publishes RE pipeline output after pipeline completion.

Two methods:
  publish_pipeline()      — legacy: writes a metadata manifest + knowledge
                            note to the Rowboat filesystem (~/.rowboat/).
  publish_pipeline_full() — primary: persists the full run (manifest + every
                            artifact) to Supabase via SweDesignRepository.
                            Supabase becomes the source of truth; the
                            enterprise_output/ folder stays as scratch.

A future Gitea sync will own versioned artifact *content*; _sync_to_gitea()
is the placeholder hook for that — it returns None until Gitea ships.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .base_publisher import BasePublisher, _slugify
from .knowledge_note_builder import build_project_note

logger = logging.getLogger(__name__)

# Directories under output_dir that are pipeline scratch, never published.
_SCRATCH_DIRS = {"_checkpoints"}

# File extension → (artifact format, is_structured)
_TEXT_EXTS = {".md": "markdown", ".mmd": "mermaid", ".feature": "gherkin",
              ".txt": "text", ".yaml": "text", ".yml": "text"}
_JSON_EXTS = {".json": "json"}

# Map a file's parent-dir / name to an artifact_type bucket.
def _classify_artifact(rel_path: str) -> str:
    """Classify a file path into a coarse artifact_type bucket."""
    p = rel_path.replace("\\", "/").lower()
    if "diagram" in p or p.endswith(".mmd"):
        return "mermaid"
    if "user_stor" in p:
        return "epics" if "epic" in p else "user_stories"
    if "traceab" in p:
        return "traceability"
    if "data_dict" in p or p.startswith("data/"):
        return "data_dictionary"
    if "work_breakdown" in p or "task" in p:
        return "work_breakdown"
    if p.startswith("api/") or "api_doc" in p or "openapi" in p:
        return "api_documentation"
    if "state_machine" in p:
        return "state_machines"
    if "infra" in p or "config" in p:
        return "infrastructure"
    if "composition" in p or "ui_design" in p or "ux_design" in p:
        return "ui_compositions"
    if "test_fact" in p or p.startswith("testing/"):
        return "tests"
    if "architecture" in p:
        return "architecture"
    if "journal" in p:
        return "journal"
    if "manifest" in p:
        return "manifest"
    if "master_document" in p:
        return "master_document"
    if "requirements_specification" in p:
        return "requirements"
    if "report" in p or "quality" in p:
        return "reports"
    return "other"


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

    # ------------------------------------------------------------------
    # Supabase persistence (primary path)
    # ------------------------------------------------------------------

    def publish_pipeline_full(
        self,
        project_name: str,
        output_dir: str,
        manifest_data: Dict[str, Any],
        *,
        project_id: Optional[str] = None,
        shuttle_id: Optional[str] = None,
        max_artifact_bytes: int = 2_000_000,
    ) -> Optional[str]:
        """Persist a complete RE pipeline run to Supabase.

        Writes one swe_design_runs row + one swe_design_artifacts row per
        generated file. Re-publishing the same run replaces its artifacts
        (slug-keyed) rather than duplicating them.

        Args:
            project_name: Project name (e.g. 'whatsapp-messaging-service').
            output_dir: enterprise_output/{name}_{ts}/ directory.
            manifest_data: Dict from PipelineManifest.to_dict().
            project_id: Linked code-generation project, if any.
            shuttle_id: Linked shuttle, if any.
            max_artifact_bytes: Files larger than this are skipped (with a
                logged warning) to keep row sizes sane.

        Returns:
            The swe_design_runs id, or None if persistence failed.
        """
        try:
            from data.swe_design_repository import SweDesignRepository
        except ImportError as e:
            logger.warning(f"[SweDesignPublisher] SweDesignRepository unavailable: {e}")
            return None

        slug = _slugify(project_name)
        output_path = Path(output_dir)

        stages = manifest_data.get("stages", [])
        completed = sum(1 for s in stages if s.get("status") == "completed")
        total = len(stages)
        status = "completed" if total and completed == total else (
            "in_progress" if total else "completed"
        )

        # Aggregate cost / token telemetry from manifest stages.
        total_cost = sum(float(s.get("cost_usd", 0) or 0) for s in stages)
        total_calls = sum(int(s.get("llm_calls", 0) or 0) for s in stages)
        total_tokens = int(manifest_data.get("total_tokens", 0) or 0)

        repo = SweDesignRepository()

        # Replace an existing run for this slug (idempotent re-publish).
        existing = repo.get_run_by_slug(slug)
        if existing:
            repo.delete_run(existing["id"])  # artifacts cascade

        run_id = repo.create_run(
            project_name=project_name,
            slug=slug,
            pipeline_id=manifest_data.get("pipeline_id", ""),
            status=status,
            domain=manifest_data.get("domain", "custom"),
            total_stages=total,
            completed_stages=completed,
            total_cost_usd=total_cost,
            total_tokens=total_tokens,
            total_llm_calls=total_calls,
            project_id=project_id,
            shuttle_id=shuttle_id,
            output_dir=str(output_path),
            manifest=manifest_data,
            completed_at=datetime.now() if status == "completed" else None,
        )

        artifact_count = 0
        for rel_path, abs_path, fmt, is_json in self._walk_artifacts(output_path):
            try:
                size = abs_path.stat().st_size
                if size > max_artifact_bytes:
                    logger.warning(
                        f"[SweDesignPublisher] Skipping oversized artifact "
                        f"{rel_path} ({size} bytes)"
                    )
                    continue
                raw = abs_path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as e:
                logger.debug(f"[SweDesignPublisher] Skip {rel_path}: {e}")
                continue

            content_json = None
            content_text = None
            item_count = 0
            if is_json:
                try:
                    content_json = json.loads(raw)
                    if isinstance(content_json, list):
                        item_count = len(content_json)
                    elif isinstance(content_json, dict):
                        item_count = len(content_json.get("nodes", content_json))
                except json.JSONDecodeError:
                    content_text = raw  # malformed JSON → keep as text
            else:
                content_text = raw

            repo.add_artifact(
                run_id,
                artifact_type=_classify_artifact(rel_path),
                name=abs_path.name,
                rel_path=rel_path,
                fmt=fmt,
                content_text=content_text,
                content_json=content_json,
                item_count=item_count,
            )
            artifact_count += 1

        # Gitea handoff — no-op until the Gitea artifact sync ships.
        gitea_ref = self._sync_to_gitea(output_path, slug)
        if gitea_ref:
            repo.set_gitea_ref(run_id, gitea_ref[0], gitea_ref[1])

        logger.info(
            f"[SweDesignPublisher] Persisted run '{project_name}' to Supabase "
            f"(run_id={run_id}, {artifact_count} artifacts)"
        )
        return run_id

    def _walk_artifacts(
        self, output_path: Path
    ) -> List[Tuple[str, Path, str, bool]]:
        """Yield (rel_path, abs_path, format, is_json) for publishable files.

        Skips scratch directories (_checkpoints) and unknown extensions.
        """
        results: List[Tuple[str, Path, str, bool]] = []
        if not output_path.exists():
            return results

        for abs_path in output_path.rglob("*"):
            if not abs_path.is_file():
                continue
            rel = abs_path.relative_to(output_path)
            parts = set(p.lower() for p in rel.parts)
            if parts & _SCRATCH_DIRS:
                continue
            ext = abs_path.suffix.lower()
            if ext in _JSON_EXTS:
                results.append((str(rel), abs_path, "json", True))
            elif ext in _TEXT_EXTS:
                results.append((str(rel), abs_path, _TEXT_EXTS[ext], False))
            # other extensions (images, binaries) are not published
        return results

    def _sync_to_gitea(
        self, output_path: Path, slug: str
    ) -> Optional[Tuple[str, str]]:
        """Push artifact content to Gitea; return (repo, commit_sha).

        TODO(gitea): once Gitea is available, commit the artifact files in
        `output_path` to a per-project repo and return its (repo, commit_sha)
        so the run's gitea_commit_sha column points at versioned content.
        Until then this is a deliberate no-op — Supabase holds the content.
        """
        return None
