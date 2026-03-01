"""
Base publisher for writing metadata to Rowboat's workspace.

All publishing is fire-and-forget — a failed publish never blocks
the primary operation.
"""

import json
import re
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)


def _slugify(text: str) -> str:
    """Convert text to a filesystem-safe slug."""
    text = text.lower().strip()
    text = re.sub(r"[äÄ]", "ae", text)
    text = re.sub(r"[öÖ]", "oe", text)
    text = re.sub(r"[üÜ]", "ue", text)
    text = re.sub(r"ß", "ss", text)
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text or "untitled"


class BasePublisher(ABC):
    """Abstract base for space-to-Rowboat metadata publishers."""

    def __init__(self):
        self.rowboat_root = Path.home() / ".rowboat"
        self.vibemind_dir = self.rowboat_root / "vibemind"
        self.knowledge_dir = self.rowboat_root / "knowledge"

    @property
    @abstractmethod
    def space_name(self) -> str:
        """Return the space identifier (e.g. 'ideas', 'swe-design')."""
        ...

    def _write_manifest(self, rel_path: str, data: Dict[str, Any]) -> Path:
        """Write JSON manifest to vibemind/ directory.

        Args:
            rel_path: Relative path under vibemind/ (e.g. 'ideas/bubble--marketing.json')
            data: Dict to serialize as JSON

        Returns:
            The full path written to.
        """
        full_path = self.vibemind_dir / rel_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        logger.debug(f"[Publishing] Wrote manifest: {full_path}")
        return full_path

    def _write_knowledge_note(self, category: str, title: str, content: str) -> Path:
        """Write markdown note to knowledge/ directory.

        The Rowboat Graph Builder watches this directory and
        auto-indexes new/changed notes.

        Args:
            category: Subdirectory (e.g. 'Projects', 'Topics')
            title: Note title (will be sanitized for filesystem)
            content: Markdown content

        Returns:
            The full path written to.
        """
        safe_title = re.sub(r'[<>:"/\\|?*]', "", title).strip()
        if not safe_title:
            safe_title = "Untitled"
        note_path = self.knowledge_dir / category / f"{safe_title}.md"
        note_path.parent.mkdir(parents=True, exist_ok=True)
        note_path.write_text(content, encoding="utf-8")
        logger.debug(f"[Publishing] Wrote knowledge note: {note_path}")
        return note_path

    def _write_sync_source(self, filename: str, content: str) -> Path:
        """Write a source file to vibemind_sync/ for Graph Builder processing.

        The Graph Builder watches this folder and processes new/changed files
        every 30 seconds, integrating them into the knowledge graph.
        """
        sync_dir = self.rowboat_root / "vibemind_sync"
        sync_dir.mkdir(parents=True, exist_ok=True)
        path = sync_dir / filename
        path.write_text(content, encoding="utf-8")
        logger.debug(f"[Publishing] Wrote sync source: {path}")
        return path

    def _remove_sync_source(self, filename: str):
        """Remove a sync source file."""
        path = self.rowboat_root / "vibemind_sync" / filename
        if path.exists():
            path.unlink()

    def _update_index(self, manifest_count: int):
        """Update this space's entry in vibemind/index.json."""
        index_path = self.vibemind_dir / "index.json"
        index_path.parent.mkdir(parents=True, exist_ok=True)

        # Read existing or create new
        if index_path.exists():
            try:
                index = json.loads(index_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                index = {"version": "1.0", "spaces": {}}
        else:
            index = {"version": "1.0", "spaces": {}}

        now = datetime.now().isoformat()
        index["updated_at"] = now
        index.setdefault("spaces", {})[self.space_name] = {
            "enabled": True,
            "manifest_count": manifest_count,
            "last_published": now,
        }

        index_path.write_text(
            json.dumps(index, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def _count_manifests(self) -> int:
        """Count JSON manifest files for this space."""
        space_dir = self.vibemind_dir / self.space_name
        if not space_dir.exists():
            return 0
        return len(list(space_dir.glob("*.json")))
