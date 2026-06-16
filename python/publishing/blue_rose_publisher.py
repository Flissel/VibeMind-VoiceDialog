"""
Blue Rose (Flowzen) → Rowboat publisher.

Reads diary entries, check-ins and activity from the Flowzen data layer
(Supabase via FlowzenRepository) and publishes their metadata into the
VibeMind workspace so Rowboat's rag-worker can index them.

Triggered on demand / at startup sync.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from .base_publisher import BasePublisher, _slugify
from .knowledge_note_builder import build_project_note

logger = logging.getLogger(__name__)


class BlueRosePublisher(BasePublisher):

    space_name = "blue-rose"

    def publish_diary_snapshot(self, limit: int = 30) -> int:
        """Publish a snapshot of recent Flowzen diary entries.

        Writes one manifest (snapshot index) plus a knowledge note that
        bundles the recent entries. Returns the number of entries included.
        """
        try:
            from data import FlowzenRepository
        except ImportError as e:
            logger.warning(f"[BlueRosePublisher] FlowzenRepository unavailable: {e}")
            return 0

        repo = FlowzenRepository()
        try:
            entries = repo.get_recent_diary_entries(limit=limit)
            checkins = repo.get_recent_checkins(limit=limit)
        except Exception as e:
            logger.warning(f"[BlueRosePublisher] Flowzen read failed: {e}")
            return 0

        manifest = {
            "schema_version": "1.0",
            "space": "blue-rose",
            "type": "flowzen_snapshot",
            "published_at": datetime.now().isoformat(),
            "snapshot": {
                "diary_entry_count": len(entries),
                "checkin_count": len(checkins),
            },
        }
        self._write_manifest("blue-rose/diary_snapshot.json", manifest)

        # Bundle recent entries into a single knowledge note.
        lines: List[str] = []
        for entry in entries:
            ts = getattr(entry, "created_at", None)
            ts_str = ts.isoformat() if hasattr(ts, "isoformat") else str(ts or "")
            mood = getattr(entry, "mood", "")
            energy = getattr(entry, "energy", "")
            text = getattr(entry, "entry_text", "")
            lines.append(f"## {ts_str} — {mood} (energy {energy})")
            lines.append(text or "")
            lines.append("")

        key_facts = [
            f"{len(entries)} recent diary entries",
            f"{len(checkins)} recent check-ins",
        ]
        knowledge_md = build_project_note(
            title="Blue Rose Diary",
            project_type="flowzen-diary",
            status="active",
            summary="Recent Flowzen diary entries and check-ins.",
            key_facts=key_facts,
            related_topics=["Blue Rose", "Flowzen", "Diary"],
            source_space="Blue Rose",
        )
        # Append the bundled entries below the generated note.
        if lines:
            knowledge_md = knowledge_md + "\n\n## Entries\n\n" + "\n".join(lines)
        self._write_knowledge_note("Diary", "Blue Rose Diary", knowledge_md)

        self._update_index(self._count_manifests())
        logger.info(
            f"[BlueRosePublisher] Published diary snapshot "
            f"({len(entries)} entries, {len(checkins)} check-ins)"
        )
        return len(entries)

    def mirror(self, limit: int = 30) -> int:
        """Mirror the current Flowzen state into the workspace folder.

        Clears the blue-rose/ folder, then writes a fresh diary snapshot —
        the single snapshot file always reflects the latest state.
        """
        self.mirror_clean()
        return self.publish_diary_snapshot(limit=limit)
