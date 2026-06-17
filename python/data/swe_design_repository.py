"""SWE Design Repository — CRUD for RE pipeline runs and their artifacts.

Persists the output of the Requirements Engineer pipeline
(vibemind-os/spaces/shuttles/swe_desgine/) to Supabase. The filesystem
under enterprise_output/ remains pipeline scratch (checkpoints / resume);
Supabase is the source of truth for run structure + artifact content.

Schema: see vibemind-os/supabase/migrations/20260521_swe_design.sql
  swe_design_runs      — one row per pipeline run
  swe_design_artifacts — one row per generated artifact
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from .supabase_database import Database, get_database
from .repository_utils import generate_id

logger = logging.getLogger(__name__)


class SweDesignRepository:
    """Repository for SWE Design pipeline runs and artifacts."""

    def __init__(self, db: Optional[Database] = None):
        self.db = db or get_database()

    # ------------------------------------------------------------------
    # Runs
    # ------------------------------------------------------------------

    def create_run(
        self,
        project_name: str,
        slug: str,
        *,
        pipeline_id: str = "",
        status: str = "in_progress",
        domain: str = "custom",
        total_stages: int = 0,
        completed_stages: int = 0,
        total_cost_usd: float = 0.0,
        total_tokens: int = 0,
        total_llm_calls: int = 0,
        project_id: Optional[str] = None,
        shuttle_id: Optional[str] = None,
        output_dir: Optional[str] = None,
        manifest: Optional[Dict[str, Any]] = None,
        completed_at: Optional[datetime] = None,
    ) -> str:
        """Insert a pipeline run. Returns the new run id."""
        run_id = generate_id()
        self.db.execute(
            """
            INSERT INTO swe_design_runs (
                id, pipeline_id, project_name, slug, status, domain,
                total_stages, completed_stages, total_cost_usd, total_tokens,
                total_llm_calls, project_id, shuttle_id, output_dir,
                manifest, created_at, completed_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                pipeline_id,
                project_name,
                slug,
                status,
                domain,
                total_stages,
                completed_stages,
                total_cost_usd,
                total_tokens,
                total_llm_calls,
                project_id,
                shuttle_id,
                output_dir,
                json.dumps(manifest or {}, ensure_ascii=False, default=str),
                datetime.now().isoformat(),
                completed_at.isoformat() if completed_at else None,
            ),
        )
        logger.debug("[SweDesignRepo] Created run %s for '%s'", run_id, project_name)
        return run_id

    def get_run_by_slug(self, slug: str) -> Optional[Dict[str, Any]]:
        """Return the most recent run for a slug, or None."""
        row = self.db.fetch_one(
            "SELECT * FROM swe_design_runs WHERE slug = ? "
            "ORDER BY created_at DESC LIMIT 1",
            (slug,),
        )
        return dict(row) if row else None

    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        row = self.db.fetch_one(
            "SELECT * FROM swe_design_runs WHERE id = ?", (run_id,)
        )
        return dict(row) if row else None

    def list_runs(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        rows = self.db.fetch_all(
            "SELECT * FROM swe_design_runs ORDER BY created_at DESC "
            "LIMIT ? OFFSET ?",
            (limit, offset),
        )
        return [dict(r) for r in rows]

    def update_run_status(
        self,
        run_id: str,
        status: str,
        *,
        completed_stages: Optional[int] = None,
        completed_at: Optional[datetime] = None,
    ) -> None:
        sets = ["status = ?"]
        params: List[Any] = [status]
        if completed_stages is not None:
            sets.append("completed_stages = ?")
            params.append(completed_stages)
        if completed_at is not None:
            sets.append("completed_at = ?")
            params.append(completed_at.isoformat())
        params.append(run_id)
        self.db.execute(
            f"UPDATE swe_design_runs SET {', '.join(sets)} WHERE id = ?",
            tuple(params),
        )

    def link_to_project(self, run_id: str, project_id: str) -> None:
        """Attach a code-generation project to this run."""
        self.db.execute(
            "UPDATE swe_design_runs SET project_id = ? WHERE id = ?",
            (project_id, run_id),
        )

    def set_gitea_ref(self, run_id: str, repo: str, commit_sha: str) -> None:
        """Record the Gitea commit that holds this run's artifact content.

        Called by the (future) Gitea artifact sync. NULL until then.
        """
        self.db.execute(
            "UPDATE swe_design_runs SET gitea_repo = ?, gitea_commit_sha = ? "
            "WHERE id = ?",
            (repo, commit_sha, run_id),
        )

    def delete_run(self, run_id: str) -> None:
        """Delete a run; artifacts cascade via FK ON DELETE CASCADE."""
        self.db.execute("DELETE FROM swe_design_runs WHERE id = ?", (run_id,))

    # ------------------------------------------------------------------
    # Artifacts
    # ------------------------------------------------------------------

    def add_artifact(
        self,
        run_id: str,
        artifact_type: str,
        name: str,
        *,
        rel_path: Optional[str] = None,
        fmt: str = "text",
        content_text: Optional[str] = None,
        content_json: Optional[Any] = None,
        item_count: int = 0,
    ) -> str:
        """Insert one artifact row. Returns the artifact id.

        rel_path defaults to name when not given; it is the UNIQUE key per
        run, so re-syncing the same artifact replaces rather than duplicates.
        """
        artifact_id = generate_id()
        rel_path = rel_path or name
        self.db.execute(
            """
            INSERT INTO swe_design_artifacts (
                id, run_id, artifact_type, name, rel_path, format,
                content_text, content_json, item_count, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                artifact_id,
                run_id,
                artifact_type,
                name,
                rel_path,
                fmt,
                content_text,
                json.dumps(content_json, ensure_ascii=False, default=str)
                if content_json is not None
                else None,
                item_count,
                datetime.now().isoformat(),
            ),
        )
        return artifact_id

    def list_artifacts(
        self, run_id: str, artifact_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        if artifact_type:
            rows = self.db.fetch_all(
                "SELECT * FROM swe_design_artifacts WHERE run_id = ? "
                "AND artifact_type = ? ORDER BY artifact_type, name",
                (run_id, artifact_type),
            )
        else:
            rows = self.db.fetch_all(
                "SELECT * FROM swe_design_artifacts WHERE run_id = ? "
                "ORDER BY artifact_type, name",
                (run_id,),
            )
        return [dict(r) for r in rows]

    def clear_artifacts(self, run_id: str) -> None:
        """Drop all artifacts for a run (used before a re-sync)."""
        self.db.execute(
            "DELETE FROM swe_design_artifacts WHERE run_id = ?", (run_id,)
        )

    def get_run_with_artifacts(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Return a run dict with an 'artifacts' list attached."""
        run = self.get_run(run_id)
        if not run:
            return None
        run["artifacts"] = self.list_artifacts(run_id)
        return run
