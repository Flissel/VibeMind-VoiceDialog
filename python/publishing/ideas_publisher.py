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
from .knowledge_note_builder import (
    build_project_note,
    build_requirements_note,
    build_stakeholders_note,
    build_constraints_note,
    build_techstack_note,
    build_mirofish_eval_note,
)

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

        # Source 2: Canvas nodes linked to this bubble.
        # Prefer content_json (structured: specs/SWOT/flowchart/etc.) over the
        # plain `node.content` so Rowboat/Obsidian sees actual formatted
        # content rather than just titles. Falls back to plain content/summary.
        all_nodes = canvas_repo.list_nodes(limit=2000)
        bubble_nodes = [n for n in all_nodes if n.linked_idea_id == bubble_id]
        for node in bubble_nodes:
            title = node.title or ""
            if not title or title in seen_titles:
                continue
            seen_titles.add(title)
            cj = getattr(node, "content_json", None)
            has_cj = isinstance(cj, dict) and bool(cj)
            reformat_pending = bool(getattr(node, "reformat_pending", False))
            # ANTI-FLICKER (canvas bidi-sync): while a content edit awaits its
            # content_json regeneration (reformat_pending), render the FRESH plain
            # `content` and SKIP the lossy content_json flatten — so a forced
            # re-render shows the user's edited text, not the stale structure.
            rendered_content = ""
            if has_cj and not reformat_pending:
                try:
                    from spaces.mirofish.tools.mirofish_tools import _flatten_content_json
                    fmt_type = cj.get("type") or node.node_type
                    rendered_content = f"_Format: {fmt_type}_\n\n" + _flatten_content_json(cj, max_chars=3000)
                except Exception:
                    import json as _json
                    rendered_content = "```json\n" + _json.dumps(cj, ensure_ascii=False, indent=2)[:3000] + "\n```"
            if not rendered_content:
                rendered_content = node.content or node.summary or ""
            notes.append({
                "id": node.id,
                "title": title,
                "content": rendered_content,
                "tags": [],
                "node_type": node.node_type or "note",
                # canvas-sync frontmatter drivers (consumed by render_canvas_note)
                "is_canvas": True,
                "has_content_json": has_cj,
                "reformat_pending": reformat_pending,
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

        # ── JSON manifest (schema 1.1: + eval, score, status) ──
        # Include eval-history + last MiroFish readiness scores so Rowboat/
        # Obsidian readers see the project maturity without hitting the DB.
        bubble_meta = bubble.metadata if isinstance(bubble.metadata, dict) else {}
        manifest = {
            "schema_version": "1.1",
            "space": "ideas",
            "type": "bubble",
            "published_at": datetime.now().isoformat(),
            "bubble": {
                "id": bubble.id,
                "title": bubble.title or "",
                "description": bubble.description or "",
                "status": bubble.status or "",
                "score": getattr(bubble, "score", None),
                "created_at": str(bubble.created_at) if bubble.created_at else None,
                "updated_at": str(getattr(bubble, 'updated_at', None)) if getattr(bubble, 'updated_at', None) else None,
            },
            "eval": {
                "last_eval": bubble_meta.get("last_eval"),
                "history": bubble_meta.get("eval_history") or [],
                "dimensions": {
                    "feasibility": getattr(bubble, "feasibility", None),
                    "impact": getattr(bubble, "impact", None),
                    "novelty": getattr(bubble, "novelty", None),
                    "urgency": getattr(bubble, "urgency", None),
                },
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

        # _overview.md — bubble metadata + MiroFish eval summary
        key_facts = [f"{len(notes)} ideas/notes"]
        if edges:
            key_facts.append(f"{len(edges)} connections")
        last_eval = bubble_meta.get("last_eval") or {}
        if last_eval.get("total_score") is not None:
            key_facts.append(f"MiroFish readiness: {last_eval['total_score']}/100 — {last_eval.get('prediction','')}")
        history = bubble_meta.get("eval_history") or []
        if history:
            key_facts.append(f"{len(history)} eval-runs tracked")
        if bubble.description:
            key_facts.append(bubble.description[:300])

        # Build eval summary appendix for the overview
        eval_appendix = ""
        if last_eval:
            from datetime import datetime as _dt
            ts = last_eval.get("ts")
            ts_str = _dt.fromtimestamp(ts).isoformat() if ts else "?"
            eval_appendix = "\n\n## MiroFish Evaluation\n\n"
            eval_appendix += f"- **Last run:** {ts_str}\n"
            eval_appendix += f"- **Score:** {last_eval.get('total_score', '?')}/100\n"
            eval_appendix += f"- **Prediction:** {last_eval.get('prediction', '?')}\n"
            per_agent = last_eval.get("per_agent_full") or {}
            if per_agent:
                eval_appendix += "\n### Per-Agent Breakdown\n\n"
                for agent, data in per_agent.items():
                    if isinstance(data, dict):
                        sc = data.get("score", 0)
                        eval_appendix += f"- **{agent}** [{sc}/25]: {data.get('assessment', '')[:200]}\n"
            missing = last_eval.get("missing_items") or []
            if missing:
                eval_appendix += f"\n### Top Missing Items ({len(missing)} total)\n\n"
                for m in missing[:15]:
                    eval_appendix += f"- {m}\n"
            if len(history) > 1:
                eval_appendix += "\n### Score History\n\n"
                for h in history[-10:]:
                    h_ts = _dt.fromtimestamp(h.get("ts", 0)).isoformat() if h.get("ts") else "?"
                    eval_appendix += f"- {h_ts}: {h.get('total_score', '?')}/100 ({h.get('prediction', '?')})\n"

        overview_md = build_project_note(
            title=f"VibeMind - {bubble_title}",
            project_type="idea-bubble",
            status=bubble.status or "active",
            summary=bubble.description or f"Idea bubble with {len(notes)} notes.",
            started=str(bubble.created_at)[:10] if bubble.created_at else "",
            last_activity=str(getattr(bubble, 'updated_at', None))[:10] if getattr(bubble, 'updated_at', None) else "",
            key_facts=key_facts,
            source_space="Ideas",
        )
        from .bubble_sync.render_md import render_overview
        _ov_path = bubble_dir / "_overview.md"
        _ov_existing = _ov_path.read_text(encoding="utf-8") if _ov_path.exists() else None
        _ov_path.write_text(
            render_overview(
                bubble_id=bubble.id,
                overview_body=(overview_md + eval_appendix),
                existing=_ov_existing,
            ),
            encoding="utf-8",
        )

        # Track which files we write so we can prune stale ones
        written_files = {"_overview.md"}

        # Individual idea files — now with stable frontmatter (idea_id/bubble_id)
        # + a user-editable fence, via bubble_sync.render_md. The DB-rendered
        # body is unchanged; this makes the files identifiable + round-trippable
        # for the bidirectional sync (see publishing/bubble_sync/).
        from .bubble_sync.render_md import render_idea_note, render_canvas_note
        for n in notes:
            idea_title = n["title"] or "Untitled"
            filename = f"{_safe_filename(idea_title)}.md"
            written_files.add(filename)

            idea_path = bubble_dir / filename
            existing = idea_path.read_text(encoding="utf-8") if idea_path.exists() else None
            # Canvas nodes get the canvas frontmatter (canvas_node_id + writeback
            # drivers) so Worker B can sync edits back to public.canvas_nodes;
            # child ideas keep the idea frontmatter.
            if n.get("is_canvas"):
                md = render_canvas_note(
                    n, bubble_id=bubble.id, folder_name=folder_name, existing=existing,
                )
            else:
                md = render_idea_note(
                    n, bubble_id=bubble.id, folder_name=folder_name, existing=existing,
                )
            idea_path.write_text(md, encoding="utf-8")

        # Prune ideas that were deleted (files in folder but not in current notes)
        # Skip _-prefixed files (wizard outputs like _requirements.md)
        for existing in bubble_dir.iterdir():
            if (existing.name not in written_files
                    and existing.suffix == ".md"
                    and not existing.name.startswith("_")):
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

    def cleanup_orphaned_project_dirs(
        self,
        live_titles,
        dry_run: bool = True,
        max_delete: Optional[int] = 200,
        skip_substrings=("VibeMind - TODO ",),
    ) -> Dict[str, Any]:
        """Filesystem reverse-sync: delete knowledge/Projects/'VibeMind - {title}'/
        folders whose {title} is NOT a live bubble. ONLY touches 'VibeMind - *'
        dirs — Agents/Diary/People/Bewerbung/Topics/Videos/etc. are never scanned.

        ``skip_substrings``: folder names containing any of these are PRESERVED
        even if orphaned. Default protects 'VibeMind - TODO ' dirs — those are the
        split-out E-Ticketing requirement bubbles (API spec, GDPR, Tariflogik…),
        which belong to the real project and must not be wiped as test junk.

        Mirrors cleanup_orphaned_sources (MongoDB) on the .md vault side. Same
        safety guards: empty live_titles -> abort; > max_delete -> abort;
        dry_run default report-only. Deletion reuses shutil.rmtree (same as
        remove_bubble).
        """
        projects_dir = self.knowledge_dir / "Projects"
        report: Dict[str, Any] = {
            "success": True, "dry_run": dry_run, "checked": 0,
            "orphaned": [], "deleted": 0, "aborted": None,
        }

        # GUARD 1: refuse to wipe on an empty/broken bubble set.
        live = set(live_titles or set())
        if not live:
            report["success"] = False
            report["aborted"] = "no live bubbles — refusing to delete project dirs"
            logger.warning("[IdeasPublisher] cleanup aborted: 0 live bubbles")
            return report

        if not projects_dir.is_dir():
            report["aborted"] = f"Projects dir not found: {projects_dir}"
            return report

        live_folders = {f"VibeMind - {_safe_filename(t)}" for t in live}
        # Only consider 'VibeMind - *' dirs (bubble-published); skip everything else.
        candidates = [
            p for p in projects_dir.iterdir()
            if p.is_dir() and p.name.startswith("VibeMind - ")
        ]
        report["checked"] = len(candidates)
        skips = tuple(skip_substrings or ())
        orphans = [
            p for p in candidates
            if p.name not in live_folders
            and not any(s in p.name for s in skips)
        ]
        report["orphaned"] = [p.name for p in orphans]
        report["protected"] = len([
            p for p in candidates
            if p.name not in live_folders and any(s in p.name for s in skips)
        ])

        # GUARD 2: refuse an unexpectedly large deletion.
        if max_delete is not None and len(orphans) > max_delete:
            report["success"] = False
            report["aborted"] = (
                f"{len(orphans)} orphan dirs exceed max_delete={max_delete} — aborting"
            )
            logger.warning("[IdeasPublisher] cleanup aborted: %s orphans > max_delete %s",
                           len(orphans), max_delete)
            return report

        if dry_run:
            logger.info("[IdeasPublisher] FS cleanup DRY-RUN: %s orphaned of %s checked",
                        len(orphans), len(candidates))
            return report

        for p in orphans:
            try:
                shutil.rmtree(p)
                report["deleted"] += 1
                logger.info("[IdeasPublisher] cleanup deleted orphan dir '%s'", p.name)
            except Exception as e:  # noqa: BLE001 — one bad dir must not abort the rest
                logger.warning("[IdeasPublisher] cleanup failed for '%s': %s", p.name, e)
        if not dry_run:
            self._update_index(self._count_manifests())
        return report

    def publish_wizard_results(
        self,
        bubble_id: str,
        wizard_state: Dict[str, Any],
        mirofish_result: Optional[Dict[str, Any]] = None,
    ):
        """Publish wizard + MiroFish outputs as _-prefixed .md files.

        Called after wizard finalize (full state) or after init_from_bubble
        (only mirofish_result available, wizard fields may be empty).

        Files written into existing knowledge/Projects/VibeMind - {Title}/ folder:
          _requirements.md, _stakeholders.md, _constraints.md,
          _techstack.md, _mirofish_eval.md, and enriched _overview.md.
        """
        from data import IdeasRepository

        bubble = IdeasRepository().get(bubble_id)
        if not bubble:
            logger.warning(f"[IdeasPublisher] publish_wizard_results: bubble {bubble_id} not found")
            return

        bubble_title = bubble.title or "Untitled"
        folder_name = f"VibeMind - {_safe_filename(bubble_title)}"
        bubble_dir = self.knowledge_dir / "Projects" / folder_name
        bubble_dir.mkdir(parents=True, exist_ok=True)

        # Requirements
        reqs = wizard_state.get("requirements", [])
        md = build_requirements_note(bubble_title, reqs)
        (bubble_dir / "_requirements.md").write_text(md, encoding="utf-8")

        # Stakeholders
        shs = wizard_state.get("stakeholders", [])
        md = build_stakeholders_note(bubble_title, shs)
        (bubble_dir / "_stakeholders.md").write_text(md, encoding="utf-8")

        # Constraints
        cons = wizard_state.get("constraints", {})
        md = build_constraints_note(bubble_title, cons)
        (bubble_dir / "_constraints.md").write_text(md, encoding="utf-8")

        # Tech Stack
        tech = wizard_state.get("techstack", {})
        wd = wizard_state.get("work_division", "")
        md = build_techstack_note(bubble_title, tech, wd)
        (bubble_dir / "_techstack.md").write_text(md, encoding="utf-8")

        # MiroFish Eval (optional)
        if mirofish_result:
            md = build_mirofish_eval_note(bubble_title, mirofish_result)
            (bubble_dir / "_mirofish_eval.md").write_text(md, encoding="utf-8")

        # Enrich _overview.md with wizard summary
        key_facts = []
        if reqs:
            key_facts.append(f"{len(reqs)} requirements")
        if shs:
            key_facts.append(f"{len(shs)} stakeholders")
        if mirofish_result:
            score = mirofish_result.get("total_score", "?")
            pred = mirofish_result.get("prediction", "?")
            key_facts.append(f"MiroFish Score: {score}/100 ({pred})")

        # Determine status based on wizard completeness
        has_wizard_data = bool(reqs or shs or cons)
        overview_md = build_project_note(
            title=f"VibeMind - {bubble_title}",
            project_type="swe-project" if has_wizard_data else "idea-bubble",
            status="wizard-complete" if has_wizard_data else "active",
            summary=wizard_state.get("project", {}).get("description", bubble.description or ""),
            started=str(bubble.created_at)[:10] if bubble.created_at else "",
            key_facts=key_facts or None,
            source_space="SWE Design",
        )
        (bubble_dir / "_overview.md").write_text(overview_md, encoding="utf-8")

        logger.info(
            f"[IdeasPublisher] Published wizard results for '{bubble_title}' "
            f"({len(reqs)} reqs, {len(shs)} stakeholders, mirofish={'yes' if mirofish_result else 'no'})"
        )

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
