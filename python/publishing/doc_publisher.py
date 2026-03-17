"""
Project Documentation Publisher.

Writes LLM-synthesized project documentation as Markdown files
to ~/.rowboat/docs/{bubble-slug}/.

This is the user-facing export path — unlike IdeasPublisher which
writes for the internal Graph Builder, DocPublisher produces
shareable project documents.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from .base_publisher import BasePublisher, _slugify

logger = logging.getLogger(__name__)


class DocPublisher(BasePublisher):
    """Publisher for project documentation Markdown files."""

    space_name = "docs"

    def publish_doc(
        self,
        bubble_slug: str,
        title: str,
        markdown_content: str,
    ) -> Optional[Path]:
        """Write project documentation as a Markdown file.

        Args:
            bubble_slug: Filesystem-safe bubble identifier.
            title: Human-readable document title.
            markdown_content: Full Markdown content to write.

        Returns:
            Path to the written file, or None on failure.
        """
        try:
            docs_dir = self.rowboat_root / "docs" / bubble_slug
            docs_dir.mkdir(parents=True, exist_ok=True)

            filename = f"projektdoku-{bubble_slug}.md"
            path = docs_dir / filename
            path.write_text(markdown_content, encoding="utf-8")

            # Also write a JSON manifest for discoverability
            self._write_manifest(f"docs/doc--{bubble_slug}.json", {
                "schema_version": "1.0",
                "space": "docs",
                "type": "projektdoku",
                "published_at": datetime.now().isoformat(),
                "document": {
                    "title": title,
                    "slug": bubble_slug,
                    "path": str(path),
                    "size_bytes": len(markdown_content.encode("utf-8")),
                },
            })

            self._update_index(self._count_manifests())
            logger.info(
                f"[DocPublisher] Published '{title}' → {path} "
                f"({len(markdown_content)} chars)"
            )
            return path

        except Exception as e:
            logger.error(f"[DocPublisher] Failed to publish '{title}': {e}")
            return None

    def remove_doc(self, bubble_slug: str):
        """Remove a previously published document."""
        doc_path = self.rowboat_root / "docs" / bubble_slug
        manifest_path = self.vibemind_dir / "docs" / f"doc--{bubble_slug}.json"

        if manifest_path.exists():
            manifest_path.unlink()

        if doc_path.exists() and doc_path.is_dir():
            import shutil
            shutil.rmtree(doc_path)

        self._update_index(self._count_manifests())
        logger.debug(f"[DocPublisher] Removed doc '{bubble_slug}'")
