"""
Ideas Space → Rowboat publisher.

Publishes bubble metadata and per-idea knowledge notes so the
Graph Builder indexes each idea as its own node.

Structure:
  knowledge/Projects/VibeMind - {Bubble}/
    _overview.md          ← Bubble metadata + summary
    {Idea Title}.md       ← Full idea content (one file per idea)
"""

import logging
import re
import shutil
from datetime import datetime
from typing import Any, Dict, List, Optional

from .base_publisher import BasePublisher, _slugify
from .knowledge_note_builder import build_project_note

logger = logging.getLogger(__name__)


def _safe_filename(title: str) -> str:
    """Sanitize a title for use as filename (keeps spaces, removes illegal chars)."""
    name = re.sub(r'[<>:"/\\|?*]', "", title).strip()
    return name or "Untitled"


class IdeasPublisher(BasePublisher):

    space_name = "ideas"

    def publish_bubble(self, bubble_id: str):
        """Publish a bubble as a folder with one .md per idea.

        Writes:
        - vibemind/ideas/bubble--{slug}.json          (manifest)
        - knowledge/Projects/VibeMind - {Title}/
            _overview.md                               (bubble summary)
            {Idea1}.md                                 (full content)
            {Idea2}.md                                 (full content)
        """
        from data import IdeasRepository, CanvasRepository

        ideas_repo = IdeasRepository()
        canvas_repo = CanvasRepository()

        bubble = ideas_repo.get(bubble_id)
        if not bubble:
            logger.debug(f"[IdeasPublisher] Bubble {bubble_id} not found, skipping")
            return

        # Collect notes from TWO sources:
        # 1. Child ideas (parent_id = bubble_id)
        # 2. Canvas nodes (linked_idea_id = bubble_id)
        notes = []
        seen_titles = set()

        # Source 1: Child ideas in ideas table
        from data.models import Idea
        child_rows = ideas_repo.db.fetch_all(
            "SELECT * FROM ideas WHERE parent_id = ?", (bubble_id,)
        )
        for r in child_rows:
            child = Idea.from_dict(dict(r))
            title = child.title or ""
            if title and title not in seen_titles:
                seen_titles.add(title)
                notes.append({
                    "id": child.id,
                    "title": title,
                    "content": child.description or "",
                    "tags": child.tags if child.tags else [],
                    "node_type": "idea",
                })

        # Source 2: Canvas nodes linked to this bubble
        all_nodes = canvas_repo.list_nodes(limit=2000)
        bubble_nodes = [n for n in all_nodes if n.linked_idea_id == bubble_id]
        for node in bubble_nodes:
            title = node.title or ""
            if not title or title in seen_titles:
                continue
            seen_titles.add(title)
            notes.append({
                "id": node.id,
                "title": title,
                "content": node.content or "",
                "tags": [],
                "node_type": node.node_type or "note",
            })

        # Get edges between this bubble's canvas nodes
        edges = []
        node_ids = {n.id for n in bubble_nodes}
        if node_ids:
            for node in bubble_nodes:
                for edge in canvas_repo.get_edges_for_node(node.id):
                    if edge.from_node_id in node_ids and edge.to_node_id in node_ids:
                        edges.append({
                            "from": edge.from_node_id,
                            "to": edge.to_node_id,
                            "type": edge.edge_type or "reference",
                        })

        slug = _slugify(bubble.title or "untitled")

        # ── JSON manifest (unchanged) ──
        manifest = {
            "schema_version": "1.0",
            "space": "ideas",
            "type": "bubble",
            "published_at": datetime.now().isoformat(),
            "bubble": {
                "id": bubble.id,
                "title": bubble.title or "",
                "description": bubble.description or "",
                "created_at": str(bubble.created_at) if bubble.created_at else None,
                "updated_at": str(getattr(bubble, 'updated_at', None)) if getattr(bubble, 'updated_at', None) else None,
            },
            "notes": notes,
            "edges": edges,
            "stats": {
                "note_count": len(notes),
                "edge_count": len(edges),
            },
            "artifact_ref": {
                "type": "sqlite",
                "db": "python/vibemind.db",
            },
        }
        self._write_manifest(f"ideas/bubble--{slug}.json", manifest)

        # ── Knowledge folder: one .md per idea ──
        bubble_title = bubble.title or "Untitled"
        folder_name = f"VibeMind - {_safe_filename(bubble_title)}"
        bubble_dir = self.knowledge_dir / "Projects" / folder_name
        bubble_dir.mkdir(parents=True, exist_ok=True)

        # Remove old flat file if it exists (migration from v1 layout)
        old_flat = self.knowledge_dir / "Projects" / f"{folder_name}.md"
        if old_flat.exists():
            old_flat.unlink()

        # _overview.md — bubble metadata
        key_facts = [f"{len(notes)} ideas/notes"]
        if edges:
            key_facts.append(f"{len(edges)} connections")
        if bubble.description:
            key_facts.append(bubble.description[:300])

        overview_md = build_project_note(
            title=f"VibeMind - {bubble_title}",
            project_type="idea-bubble",
            status="active",
            summary=bubble.description or f"Idea bubble with {len(notes)} notes.",
            started=str(bubble.created_at)[:10] if bubble.created_at else "",
            last_activity=str(getattr(bubble, 'updated_at', None))[:10] if getattr(bubble, 'updated_at', None) else "",
            key_facts=key_facts,
            source_space="Ideas",
        )
        (bubble_dir / "_overview.md").write_text(overview_md, encoding="utf-8")

        # Track which files we write so we can prune stale ones
        written_files = {"_overview.md"}

        # Individual idea files
        for n in notes:
            idea_title = n["title"] or "Untitled"
            filename = f"{_safe_filename(idea_title)}.md"
            written_files.add(filename)

            lines = [f"# {idea_title}", ""]
            if n["content"]:
                lines.append(n["content"])
                lines.append("")
            if n["tags"]:
                lines.append(f"**Tags:** {', '.join(n['tags'])}")
                lines.append("")
            if n.get("node_type") and n["node_type"] != "note":
                lines.append(f"**Type:** {n['node_type']}")
                lines.append("")
            lines.append(f"**Bubble:** [[Projects/{folder_name}/_overview]]")
            lines.append("")
            lines.append("---")
            lines.append(f"*Auto-published by VibeMind on {datetime.now().strftime('%Y-%m-%d %H:%M')}*")
            lines.append("")

            (bubble_dir / filename).write_text("\n".join(lines), encoding="utf-8")

        # Prune ideas that were deleted (files in folder but not in current notes)
        for existing in bubble_dir.iterdir():
            if existing.name not in written_files and existing.suffix == ".md":
                existing.unlink()
                logger.debug(f"[IdeasPublisher] Pruned stale note: {existing.name}")

        # ── Sync source for Graph Builder (runtime indexing) ──
        sync_lines = [f"# {bubble_title}", ""]
        if bubble.description:
            sync_lines.append(bubble.description)
            sync_lines.append("")
        for n in notes:
            sync_lines.append(f"## {n['title']}")
            if n["content"]:
                sync_lines.append(n["content"])
            if n["tags"]:
                sync_lines.append(f"Tags: {', '.join(n['tags'])}")
            sync_lines.append("")
        self._write_sync_source(f"bubble--{slug}.md", "\n".join(sync_lines))

        # Update index
        self._update_index(self._count_manifests())
        logger.debug(
            f"[IdeasPublisher] Published bubble '{bubble_title}' "
            f"({len(notes)} idea files)"
        )

    def remove_bubble(self, title: str):
        """Remove manifest and knowledge folder when a bubble is deleted."""
        slug = _slugify(title)
        manifest_path = self.vibemind_dir / "ideas" / f"bubble--{slug}.json"
        folder_name = f"VibeMind - {_safe_filename(title)}"
        folder_path = self.knowledge_dir / "Projects" / folder_name

        if manifest_path.exists():
            manifest_path.unlink()

        # Remove entire folder (overview + all idea files)
        if folder_path.exists() and folder_path.is_dir():
            shutil.rmtree(folder_path)

        # Also remove old flat file if it exists
        old_flat = self.knowledge_dir / "Projects" / f"{folder_name}.md"
        if old_flat.exists():
            old_flat.unlink()

        # Remove sync source so Graph Builder drops the entry
        self._remove_sync_source(f"bubble--{slug}.md")

        self._update_index(self._count_manifests())
        logger.debug(f"[IdeasPublisher] Removed bubble '{title}'")

    def sync_all(self):
        """Publish all existing bubbles (initial sync on startup)."""
        from data import IdeasRepository
        from data.models import Idea

        ideas_repo = IdeasRepository()
        rows = ideas_repo.db.fetch_all(
            "SELECT * FROM ideas WHERE parent_id IS NULL"
        )
        bubbles = [Idea.from_dict(dict(r)) for r in rows]

        published = 0
        for bubble in bubbles:
            try:
                self.publish_bubble(bubble_id=bubble.id)
                published += 1
            except Exception as e:
                logger.debug(f"[IdeasPublisher] sync_all: skip {bubble.title}: {e}")

        logger.info(f"[IdeasPublisher] Initial sync: {published}/{len(bubbles)} bubbles published")
