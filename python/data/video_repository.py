"""Video Repository — CRUD operations for video asset tracking."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from .supabase_database import Database, get_database
from .repository_utils import generate_id

logger = logging.getLogger(__name__)

# Known team members (auto-detected from filenames)
KNOWN_PERSONS = {"Felix", "Lisa", "Moritz", "Steffen", "Stefan", "Stephane", "Surya"}

# Pipeline stage detection from directory names
STAGE_MAP = {
    "data": "raw",
    "backgrounds": "background",
    "composited": "composited",
    "lip_sync": "lipsync",
    "lipsync": "lipsync",
    "musetalk": "lipsync",
    "output": "final",
    "vision": "vision",
    "sora": "vision",
    "tts": "tts",
    "voice": "voice_clone",
    "analysis_output": "analysis",
    "vibemind": "demo",
    "extracted": "demo",
    "product": "product",
    "demo_configs": "config",
    "pipeline": "pipeline",
    "transcripts": "transcript",
}

# Category detection from directory / filename
CATEGORY_MAP = {
    "data": "Team",
    "backgrounds": "Team",
    "composited": "Team",
    "lip_sync": "Lipsync",
    "lipsync": "Lipsync",
    "musetalk": "Lipsync",
    "output": "Final",
    "vision": "Vision",
    "sora": "Vision",
    "tts": "Voice",
    "voice": "Voice Clone",
    "analysis_output": "Analysis",
    "vibemind": "VibeMind Demo",
    "extracted": "VibeMind Demo",
    "product": "Product Demo",
}


def _detect_person(filepath: Path) -> str:
    """Detect person name from filename."""
    stem = filepath.stem
    for person in KNOWN_PERSONS:
        if person.lower() == stem.lower():
            return person
    return ""


def _detect_stage(filepath: Path) -> str:
    """Detect pipeline stage from directory structure."""
    parts = [p.lower() for p in filepath.parts]
    for part in reversed(parts[:-1]):  # skip filename
        if part in STAGE_MAP:
            return STAGE_MAP[part]
    return "raw"


def _detect_category(filepath: Path, source_root: Path) -> str:
    """Detect category from directory structure."""
    try:
        rel = filepath.relative_to(source_root)
    except ValueError:
        rel = filepath
    parts = [p.lower() for p in rel.parts]
    for part in parts[:-1]:  # skip filename
        if part in CATEGORY_MAP:
            return CATEGORY_MAP[part]
    # Fallback: check filename
    stem = filepath.stem.lower()
    if "team" in stem:
        return "Team"
    if "product" in stem or "demo" in stem:
        return "Product Demo"
    if "vision" in stem:
        return "Vision"
    if "overview" in stem:
        return "Final"
    return "Other"


def _human_size(size_bytes: int) -> str:
    """Format bytes as human-readable string."""
    for unit in ("B", "KB", "MB", "GB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def _make_title(filepath: Path, person: str, category: str, stage: str) -> str:
    """Generate a readable title from file metadata."""
    stem = filepath.stem
    # If the filename IS the person name, build a descriptive title
    if person and person.lower() == stem.lower():
        return f"{person} — {stage.replace('_', ' ').title()}"
    # Otherwise clean up the filename
    title = stem.replace("_", " ").replace("-", " ").strip()
    if person and person.lower() not in title.lower():
        title = f"{person} — {title}"
    return title


class VideoRepository:
    """Repository for Video asset CRUD operations."""

    def __init__(self, db: Optional[Database] = None):
        self.db = db or get_database()

    def create(
        self,
        file_path: str,
        filename: str = "",
        title: str = "",
        person: str = "",
        pipeline_stage: str = "raw",
        category: str = "Other",
        source_dir: str = "",
        size_bytes: int = 0,
        duration_secs: float = 0.0,
        width: int = 0,
        height: int = 0,
        tags: Optional[List[str]] = None,
        notes: str = "",
        file_modified: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a new video record."""
        video_id = generate_id()
        if not filename:
            filename = Path(file_path).name
        now = datetime.now().isoformat()

        self.db.execute(
            """
            INSERT OR IGNORE INTO videos (
                id, filename, file_path, title, person, pipeline_stage,
                category, source_dir, size_bytes, duration_secs,
                width, height, tags, notes, created_at, file_modified, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                video_id, filename, file_path, title, person, pipeline_stage,
                category, source_dir, size_bytes, duration_secs,
                width, height, json.dumps(tags or []), notes,
                now, file_modified, json.dumps(metadata or {}),
            ),
        )
        return {"id": video_id, "filename": filename, "file_path": file_path}

    def get(self, video_id: str) -> Optional[Dict[str, Any]]:
        """Get a video by ID."""
        row = self.db.fetch_one("SELECT * FROM videos WHERE id = ?", (video_id,))
        return dict(row) if row else None

    def get_by_path(self, file_path: str) -> Optional[Dict[str, Any]]:
        """Get a video by file path."""
        row = self.db.fetch_one("SELECT * FROM videos WHERE file_path = ?", (file_path,))
        return dict(row) if row else None

    def list_all(self, limit: int = 200, offset: int = 0) -> List[Dict[str, Any]]:
        """List all videos (newest first)."""
        rows = self.db.fetch_all(
            "SELECT * FROM videos ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        return [dict(r) for r in rows]

    def list_by_category(self, category: str) -> List[Dict[str, Any]]:
        """List videos filtered by category."""
        rows = self.db.fetch_all(
            "SELECT * FROM videos WHERE category = ? ORDER BY created_at DESC",
            (category,),
        )
        return [dict(r) for r in rows]

    def list_by_person(self, person: str) -> List[Dict[str, Any]]:
        """List videos filtered by person."""
        rows = self.db.fetch_all(
            "SELECT * FROM videos WHERE person = ? ORDER BY pipeline_stage, created_at DESC",
            (person,),
        )
        return [dict(r) for r in rows]

    def list_by_stage(self, stage: str) -> List[Dict[str, Any]]:
        """List videos filtered by pipeline stage."""
        rows = self.db.fetch_all(
            "SELECT * FROM videos WHERE pipeline_stage = ? ORDER BY created_at DESC",
            (stage,),
        )
        return [dict(r) for r in rows]

    def get_categories(self) -> List[Dict[str, Any]]:
        """Get distinct categories with counts."""
        rows = self.db.fetch_all(
            "SELECT category, COUNT(*) as count FROM videos GROUP BY category ORDER BY count DESC"
        )
        return [{"category": r["category"], "count": r["count"]} for r in rows]

    def get_persons(self) -> List[Dict[str, Any]]:
        """Get distinct persons with counts."""
        rows = self.db.fetch_all(
            "SELECT person, COUNT(*) as count FROM videos WHERE person != '' GROUP BY person ORDER BY count DESC"
        )
        return [{"person": r["person"], "count": r["count"]} for r in rows]

    def get_stages(self) -> List[Dict[str, Any]]:
        """Get distinct pipeline stages with counts."""
        rows = self.db.fetch_all(
            "SELECT pipeline_stage, COUNT(*) as count FROM videos GROUP BY pipeline_stage ORDER BY count DESC"
        )
        return [{"stage": r["pipeline_stage"], "count": r["count"]} for r in rows]

    def search(self, query: str) -> List[Dict[str, Any]]:
        """Search videos by title, filename, or person."""
        pattern = f"%{query}%"
        rows = self.db.fetch_all(
            """SELECT * FROM videos
               WHERE title LIKE ? OR filename LIKE ? OR person LIKE ? OR category LIKE ?
               ORDER BY created_at DESC""",
            (pattern, pattern, pattern, pattern),
        )
        return [dict(r) for r in rows]

    def update(self, video_id: str, **fields) -> Optional[Dict[str, Any]]:
        """Update video fields."""
        allowed = {
            "title", "person", "pipeline_stage", "category", "tags",
            "notes", "duration_secs", "width", "height", "metadata",
        }
        updates = {k: v for k, v in fields.items() if k in allowed}
        if not updates:
            return self.get(video_id)

        if "tags" in updates and isinstance(updates["tags"], list):
            updates["tags"] = json.dumps(updates["tags"])
        if "metadata" in updates and isinstance(updates["metadata"], dict):
            updates["metadata"] = json.dumps(updates["metadata"])

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [video_id]
        self.db.execute(f"UPDATE videos SET {set_clause} WHERE id = ?", tuple(values))
        return self.get(video_id)

    def delete(self, video_id: str) -> bool:
        """Delete a video record (does not delete the file)."""
        self.db.execute("DELETE FROM videos WHERE id = ?", (video_id,))
        return True

    def count(self, category: Optional[str] = None) -> int:
        """Count videos, optionally filtered by category."""
        if category:
            row = self.db.fetch_one(
                "SELECT COUNT(*) FROM videos WHERE category = ?", (category,),
            )
        else:
            row = self.db.fetch_one("SELECT COUNT(*) FROM videos")
        return row[0] if row else 0

    def import_directory(
        self,
        source_dir: str,
        extensions: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Scan a directory and import all video files into the database.

        Returns summary with counts of new, skipped (already exists), and errors.
        """
        source = Path(source_dir)
        if not source.exists():
            return {"success": False, "message": f"Directory not found: {source_dir}"}

        exts = extensions or [".mp4", ".mov", ".avi", ".mkv", ".webm"]
        new_count = 0
        skip_count = 0
        errors = []

        for ext in exts:
            for filepath in source.rglob(f"*{ext}"):
                if not filepath.is_file():
                    continue

                abs_path = str(filepath.resolve())

                # Skip if already in DB
                if self.get_by_path(abs_path):
                    skip_count += 1
                    continue

                try:
                    stat = filepath.stat()
                    person = _detect_person(filepath)
                    stage = _detect_stage(filepath)
                    category = _detect_category(filepath, source)
                    title = _make_title(filepath, person, category, stage)

                    self.create(
                        file_path=abs_path,
                        filename=filepath.name,
                        title=title,
                        person=person,
                        pipeline_stage=stage,
                        category=category,
                        source_dir=str(source),
                        size_bytes=stat.st_size,
                        file_modified=datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    )
                    new_count += 1
                except Exception as e:
                    errors.append({"file": str(filepath), "error": str(e)})

        return {
            "success": True,
            "message": f"Imported {new_count} videos ({skip_count} already existed)",
            "new": new_count,
            "skipped": skip_count,
            "errors": errors,
            "total": self.count(),
        }

    def to_gallery_format(self, videos: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
        """Convert DB records to the gallery format expected by the frontend."""
        if videos is None:
            videos = self.list_all()

        gallery = []
        for v in videos:
            gallery.append({
                "path": v["file_path"],
                "filename": v["filename"],
                "size_bytes": v["size_bytes"],
                "size_human": _human_size(v["size_bytes"]),
                "category": v["category"],
                "modified": v["file_modified"] or v["created_at"],
                "modified_iso": v["file_modified"] or v["created_at"],
                # Extra fields from DB
                "id": v["id"],
                "title": v["title"],
                "person": v["person"],
                "pipeline_stage": v["pipeline_stage"],
            })
        return gallery
