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


# ─────────────────────────────────────────────────────────────────────
# Workspace space registry
#
# ~/.rowboat/vibemind/ is the VibeMind collection + distribution point.
# Every space publishes into its own subdirectory here so output stays
# sorted by origin (and separate from Rowboat's own agents/ projects/ ...).
#
# Keys are the canonical space slugs used as `space_name` on publishers
# and as the subdirectory name. Values are human-readable descriptions
# written into each folder's README.
# ─────────────────────────────────────────────────────────────────────
WORKSPACE_SPACES: Dict[str, str] = {
    "ideas":      "Ideas Universe — bubbles and ideas (synced via Graph Builder).",
    "swe-design": "SWE Design — Requirements Engineer pipeline runs and specs.",
    "projects":   "Coding — code-generation project metadata and quality reports.",
    "videos":     "Video Studio — rendered video projects and pipeline output.",
    "n8n":        "n8n — workflow definitions and automation metadata.",
    "openfang":   "OpenFang — agent definitions and execution metadata.",
    "blue-rose":  "Blue Rose / Flowzen — diary, check-ins and activity logs.",
    "mirofish":   "MiroFish — simulation and prediction output.",
}


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

    def mirror_clean(self) -> None:
        """Empty this space's workspace folder before a full re-sync.

        Deletes every file in vibemind/{space_name}/ except README.md, so a
        subsequent publish leaves the folder as an exact mirror of the
        source (orphaned manifests for deleted objects are removed).
        Knowledge notes are NOT touched here — they live under knowledge/.
        """
        space_dir = self.vibemind_dir / self.space_name
        if not space_dir.exists():
            return
        for entry in space_dir.iterdir():
            if entry.is_file() and entry.name != "README.md":
                try:
                    entry.unlink()
                except OSError as e:
                    logger.debug(f"[Publishing] mirror_clean skip {entry}: {e}")

    @staticmethod
    def ensure_space_dirs() -> Path:
        """Create the per-space subdirectories under ~/.rowboat/vibemind/.

        Idempotent: existing folders and READMEs are left untouched. This
        makes the workspace the collection + distribution point — every
        space has a guaranteed home folder. Returns the vibemind/ root.
        """
        vibemind_dir = Path.home() / ".rowboat" / "vibemind"
        vibemind_dir.mkdir(parents=True, exist_ok=True)
        for slug, description in WORKSPACE_SPACES.items():
            space_dir = vibemind_dir / slug
            space_dir.mkdir(parents=True, exist_ok=True)
            readme = space_dir / "README.md"
            if not readme.exists():
                readme.write_text(
                    f"# {slug}\n\n{description}\n\n"
                    f"_This folder is part of the VibeMind → Rowboat workspace. "
                    f"Files here are published by the `{slug}` space._\n",
                    encoding="utf-8",
                )
        return vibemind_dir
