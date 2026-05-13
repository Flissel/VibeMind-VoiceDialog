"""Video Project Repository — CRUD for video production projects + pipeline tracking."""

import json
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

from .supabase_database import Database, get_database
from .repository_utils import generate_id

logger = logging.getLogger(__name__)

# All pipeline steps in execution order
PIPELINE_STEPS = [
    "raw", "analyze", "voice_clone", "transcript",
    "tts", "lipsync", "background", "composite",
    "build", "final",
]

# Steps that are per-person (vs. group steps)
PER_PERSON_STEPS = {"raw", "analyze", "voice_clone", "transcript", "tts", "lipsync", "background", "composite"}
GROUP_STEPS = {"build", "final"}

# Step metadata for the UI
STEP_INFO = {
    "raw": {
        "label": "Raw",
        "description": "Rohvideo hochladen",
        "input": ".mp4 Video",
        "output": "data/<Name>.mp4",
        "api": None,
    },
    "analyze": {
        "label": "Analyze",
        "description": "Whisper Transkription + Silence Detection",
        "input": "raw video",
        "output": "analysis.json",
        "api": None,
    },
    "voice_clone": {
        "label": "Voice Clone",
        "description": "Reference-Audio extrahieren fuer Chatterbox (lokal)",
        "input": "raw video audio",
        "output": "voice_references/<Name>_ref.wav",
        "api": "Chatterbox (lokal)",
    },
    "transcript": {
        "label": "Transcript",
        "description": "Transkript exportieren / bearbeiten",
        "input": "analysis segments",
        "output": "transcripts/<Name>.txt",
        "api": None,
    },
    "tts": {
        "label": "TTS",
        "description": "Text-to-Speech Voiceover generieren (Chatterbox)",
        "input": "transcript + reference audio",
        "output": "tts/<Name>.wav",
        "api": "Chatterbox (lokal)",
    },
    "lipsync": {
        "label": "Lipsync",
        "description": "MuseTalk Lippensynchronisation",
        "input": "raw video + TTS audio",
        "output": "lip_sync/<Name>.mp4",
        "api": None,
    },
    "background": {
        "label": "Background",
        "description": "Sora AI Hintergrund generieren",
        "input": "Rolle / Prompt",
        "output": "backgrounds/<Name>.mp4",
        "api": "Sora AI",
    },
    "composite": {
        "label": "Composite",
        "description": "Person auf Hintergrund compositen (rembg)",
        "input": "lipsync + background video",
        "output": "composited/<Name>.mp4",
        "api": None,
    },
    "build": {
        "label": "Build",
        "description": "Portrait-Videos + Team-Shot zusammenbauen",
        "input": "alle composited videos",
        "output": "team_video.mp4 + team_shot.mp4",
        "api": None,
    },
    "final": {
        "label": "Final",
        "description": "Einzelclips + Team-Shot Outro zusammenf\u00fcgen",
        "input": "build + split output",
        "output": "team_final_video.mp4",
        "api": None,
    },
}


class VideoProjectRepository:
    """Repository for Video Project CRUD and pipeline step tracking."""

    def __init__(self, db: Optional[Database] = None):
        self.db = db or get_database()

    # ── Project CRUD ──────────────────────────────────────────

    def create_project(self, name: str, description: str = "") -> Dict[str, Any]:
        """Create a new video project."""
        project_id = generate_id()
        now = datetime.now().isoformat()
        self.db.execute(
            """INSERT INTO video_projects (id, name, description, status, created_at, updated_at)
               VALUES (?, ?, ?, 'draft', ?, ?)""",
            (project_id, name, description, now, now),
        )
        return {"id": project_id, "name": name, "status": "draft"}

    def get_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        """Get project with persons."""
        row = self.db.fetch_one("SELECT * FROM video_projects WHERE id = ?", (project_id,))
        if not row:
            return None
        project = dict(row)
        project["persons"] = self._get_persons(project_id)
        return project

    def list_projects(self) -> List[Dict[str, Any]]:
        """List all projects with person counts."""
        rows = self.db.fetch_all(
            "SELECT * FROM video_projects ORDER BY created_at DESC"
        )
        projects = []
        for r in rows:
            p = dict(r)
            p["person_count"] = self.db.fetch_one(
                "SELECT COUNT(*) FROM video_project_persons WHERE project_id = ?",
                (p["id"],),
            )[0]
            projects.append(p)
        return projects

    def update_project_status(self, project_id: str, status: str) -> None:
        """Update project status."""
        now = datetime.now().isoformat()
        self.db.execute(
            "UPDATE video_projects SET status = ?, updated_at = ? WHERE id = ?",
            (status, now, project_id),
        )

    # ── Persons ───────────────────────────────────────────────

    def add_person(
        self,
        project_id: str,
        name: str,
        role: str = "",
        raw_video_path: str = "",
        voice_id: str = "",
    ) -> Dict[str, Any]:
        """Add a person to a project and initialize their pipeline steps."""
        person_id = generate_id()
        self.db.execute(
            """INSERT OR IGNORE INTO video_project_persons
               (id, project_id, name, role, raw_video_path, voice_id)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (person_id, project_id, name, role, raw_video_path, voice_id),
        )

        # Initialize pipeline steps for this person
        for step in PIPELINE_STEPS:
            step_id = generate_id()
            # If raw video is provided, mark raw step as completed
            status = "completed" if step == "raw" and raw_video_path else "pending"
            output_path = raw_video_path if step == "raw" and raw_video_path else ""
            self.db.execute(
                """INSERT OR IGNORE INTO video_pipeline_steps
                   (id, project_id, person_name, step_name, status, output_path)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (step_id, project_id, name, step, status, output_path),
            )

        return {"id": person_id, "name": name, "role": role}

    def _get_persons(self, project_id: str) -> List[Dict[str, Any]]:
        """Get all persons for a project."""
        rows = self.db.fetch_all(
            "SELECT * FROM video_project_persons WHERE project_id = ? ORDER BY name",
            (project_id,),
        )
        return [dict(r) for r in rows]

    # ── Pipeline Steps ────────────────────────────────────────

    def update_step(
        self,
        project_id: str,
        person_name: str,
        step_name: str,
        status: str,
        output_path: str = "",
        output_video_id: str = "",
        error_message: str = "",
    ) -> None:
        """Update a pipeline step's status."""
        now = datetime.now().isoformat()
        started = now if status == "running" else None
        completed = now if status in ("completed", "failed", "skipped") else None

        self.db.execute(
            """UPDATE video_pipeline_steps SET
                status = ?, output_path = ?, output_video_id = ?,
                started_at = COALESCE(?, started_at),
                completed_at = COALESCE(?, completed_at),
                error_message = ?
               WHERE project_id = ? AND person_name = ? AND step_name = ?""",
            (
                status, output_path, output_video_id,
                started, completed, error_message,
                project_id, person_name, step_name,
            ),
        )

    def get_pipeline_matrix(self, project_id: str) -> Dict[str, Any]:
        """
        Get the full pipeline matrix for a project.

        Returns:
            {
                "persons": ["Felix", "Lisa", ...],
                "steps": ["raw", "analyze", ...],
                "step_info": {step_name: {label, description, input, output, api}},
                "matrix": {
                    "Felix": {
                        "raw": {"status": "completed", "output_path": "...", "video_id": "..."},
                        "analyze": {"status": "pending", ...},
                        ...
                    }
                }
            }
        """
        persons = self._get_persons(project_id)
        person_names = [p["name"] for p in persons]

        rows = self.db.fetch_all(
            "SELECT * FROM video_pipeline_steps WHERE project_id = ? ORDER BY person_name, step_name",
            (project_id,),
        )

        matrix = {}
        for row in rows:
            r = dict(row)
            pn = r["person_name"]
            sn = r["step_name"]
            if pn not in matrix:
                matrix[pn] = {}
            matrix[pn][sn] = {
                "status": r["status"],
                "output_path": r["output_path"],
                "video_id": r["output_video_id"],
            }

        return {
            "persons": person_names,
            "steps": PIPELINE_STEPS,
            "step_info": STEP_INFO,
            "matrix": matrix,
        }

    def get_reference_pipeline(self, person_name: str = "Surya") -> Dict[str, Any]:
        """
        Get reference pipeline for a specific person (default: Surya).
        Returns step_info enriched with the person's actual video assets.
        """
        # Find the project containing this person
        row = self.db.fetch_one(
            "SELECT project_id FROM video_project_persons WHERE name = ? LIMIT 1",
            (person_name,),
        )
        if not row:
            return {"person": person_name, "steps": PIPELINE_STEPS, "step_info": STEP_INFO, "assets": {}}

        project_id = row["project_id"]
        steps = self.db.fetch_all(
            "SELECT * FROM video_pipeline_steps WHERE project_id = ? AND person_name = ?",
            (project_id, person_name),
        )

        assets = {}
        for s in steps:
            d = dict(s)
            assets[d["step_name"]] = {
                "status": d["status"],
                "output_path": d["output_path"],
                "video_id": d["output_video_id"],
            }

        return {
            "person": person_name,
            "project_id": project_id,
            "steps": PIPELINE_STEPS,
            "step_info": STEP_INFO,
            "assets": assets,
        }
