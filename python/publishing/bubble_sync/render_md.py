"""Render a bubble/idea row to a .md file with stable frontmatter + user fence.

Phase 1 (DB->FS foundation). The BODY is byte-identical to what
ideas_publisher.publish_bubble built before (so re-publishing is a clean
migration), but now PREPENDED with id-bearing frontmatter and APPENDED with a
user-editable fence (everything below is user-owned, never overwritten).

We render from the `note` dicts the publisher already assembles
({id,title,content,tags,node_type}) — NOT a separate DB query — to keep one
source of truth and avoid the PostgREST/SQL split in Phase 1. Phase 2's
worker_db_to_fs may switch to _queries.py for the event-driven path.

The user fence + content_hash are reused conceptually from the marketing sync.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from ._frontmatter import render_frontmatter, parse_frontmatter, SYNC_VERSION

# Everything BELOW this fence is user-owned and preserved across re-renders.
USER_FENCE = (
    "<!-- ─────────────────────────────────────────────────────────────── -->\n"
    "<!-- Custom notes below this line.                                     -->\n"
    "<!-- Everything BELOW this fence is owned by the user and will NOT be  -->\n"
    "<!-- overwritten by the sync. Frontmatter + sections ABOVE this fence  -->\n"
    "<!-- are DB-rendered and regenerated on every sync.                    -->\n"
    "<!-- ─────────────────────────────────────────────────────────────── -->"
)


def content_hash(body: str) -> str:
    """SHA256-16 of the DB-rendered region (above the fence) — echo detection."""
    return hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")


def user_content_below_fence(existing: str | None) -> str:
    """Extract the user-owned section (everything after the fence) from an
    existing file, so a re-render preserves it. Returns '' if none."""
    if not existing:
        return ""
    idx = existing.find(USER_FENCE)
    if idx < 0:
        return ""
    after = existing[idx + len(USER_FENCE):]
    return after if after.strip() else ""


def _idea_body(note: dict, folder_name: str) -> str:
    """The DB-rendered body — byte-identical to the legacy publisher block
    (ideas_publisher.py:247-261) MINUS the timestamp footer (the timestamp
    lives in frontmatter last_synced_at now, so the body stays stable for
    hashing/diffing)."""
    lines = [f"# {note['title'] or 'Untitled'}", ""]
    if note.get("content"):
        lines.append(note["content"])
        lines.append("")
    if note.get("tags"):
        lines.append(f"**Tags:** {', '.join(note['tags'])}")
        lines.append("")
    if note.get("node_type") and note["node_type"] != "note":
        lines.append(f"**Type:** {note['node_type']}")
        lines.append("")
    lines.append(f"**Bubble:** [[Projects/{folder_name}/_overview]]")
    lines.append("")
    return "\n".join(lines)


def render_idea_note(
    note: dict,
    *,
    bubble_id: str,
    folder_name: str,
    existing: str | None = None,
    now_iso: str | None = None,
) -> str:
    """Render one idea note to a full .md (frontmatter + body + preserved user
    section). `note` = {id,title,content,tags,node_type}. `existing` = current
    file content (to preserve below-fence). Deterministic given inputs."""
    body = _idea_body(note, folder_name)
    fm = {
        "idea_id": note["id"],
        "bubble_id": bubble_id,
        "sync_version": SYNC_VERSION,
        "sync_source": "supabase",
        "sync_path": f"ideas/{note['id']}",
        "last_synced_at": now_iso or _now_iso(),
        "content_hash": content_hash(body),
        "title": note.get("title") or "Untitled",
        "status": note.get("status") or "raw",
        "tags": list(note.get("tags") or []),
        "score": note.get("score"),
        "node_type": note.get("node_type") or "idea",
    }
    preserved = user_content_below_fence(existing)
    out = render_frontmatter(fm) + "\n\n" + body.rstrip() + "\n\n" + USER_FENCE
    if preserved:
        out = out + preserved.rstrip("\n") + "\n"
    else:
        out = out + "\n"
    return out


def render_canvas_note(
    note: dict,
    *,
    bubble_id: str,
    folder_name: str,
    existing: str | None = None,
    now_iso: str | None = None,
) -> str:
    """Render one CANVAS node to a full .md, with the canvas frontmatter group so
    Worker B can write edits back to public.canvas_nodes.

    `note` = {id, title, content, tags, node_type, has_content_json,
    reformat_pending}. The `content` passed in is ALREADY the body the publisher
    chose: the content_json flatten for structured nodes, OR plain content for
    plain nodes / when reformat_pending (the anti-flicker decision is made in the
    publisher; this renderer just lays it out + stamps frontmatter).

    Frontmatter differences vs render_idea_note:
      - idea_id carries the BUBBLE id (so bubble_id grouping/LWW keying is reused),
      - canvas_node_id carries the real node id (the FS->DB match key),
      - has_content_json / reformat_pending drive Worker B's path + the flicker guard,
      - title is rendered for display but is READ-ONLY on writeback (Worker B never
        writes it).
    Deterministic given inputs."""
    body = _idea_body(note, folder_name)
    fm = {
        "idea_id": bubble_id,            # bubble id (reuse grouping/LWW key)
        "bubble_id": bubble_id,
        "sync_version": SYNC_VERSION,
        "sync_source": "supabase",
        "sync_path": f"canvas/{note['id']}",
        "last_synced_at": now_iso or _now_iso(),
        "content_hash": content_hash(body),
        "title": note.get("title") or "Untitled",
        "status": None,                  # canvas nodes have no idea-status
        "tags": list(note.get("tags") or []),
        "score": None,
        "node_type": note.get("node_type") or "note",
        "canvas_node_id": note["id"],    # the real canvas_nodes.id — FS->DB match key
        "has_content_json": bool(note.get("has_content_json")),
        "reformat_pending": bool(note.get("reformat_pending")),
    }
    preserved = user_content_below_fence(existing)
    out = render_frontmatter(fm) + "\n\n" + body.rstrip() + "\n\n" + USER_FENCE
    if preserved:
        out = out + preserved.rstrip("\n") + "\n"
    else:
        out = out + "\n"
    return out


def render_overview(
    *,
    bubble_id: str,
    overview_body: str,
    existing: str | None = None,
    now_iso: str | None = None,
) -> str:
    """Wrap the legacy _overview.md body (from build_project_note + eval) with
    id-bearing frontmatter + user fence. overview_body = the already-built
    overview markdown (we don't change its content)."""
    fm = {
        "idea_id": bubble_id,            # the bubble's own id
        "bubble_id": bubble_id,
        "sync_version": SYNC_VERSION,
        "sync_source": "supabase",
        "sync_path": f"ideas/{bubble_id}",
        "last_synced_at": now_iso or _now_iso(),
        "content_hash": content_hash(overview_body),
        "title": None,
        "status": None,
        "tags": [],
        "score": None,
        "node_type": "overview",
    }
    preserved = user_content_below_fence(existing)
    out = render_frontmatter(fm) + "\n\n" + overview_body.rstrip() + "\n\n" + USER_FENCE
    out = out + (preserved.rstrip("\n") + "\n" if preserved else "\n")
    return out


# ── Dry-run CLI: render one idea by id to stdout (no write) ──────────────────
def _main(argv: list[str]) -> int:
    import argparse, sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    p = argparse.ArgumentParser(description="Dry-run render an idea/bubble to .md (stdout)")
    p.add_argument("--idea", help="idea_id to render", required=False)
    p.add_argument("--bubble", help="bubble_id (for overview)", required=False)
    args = p.parse_args(argv)
    from data import IdeasRepository
    repo = IdeasRepository()
    if args.idea:
        idea = repo.get(args.idea)
        if not idea:
            print(f"idea {args.idea} not found", file=sys.stderr); return 1
        note = {"id": idea.id, "title": idea.title, "content": idea.description or "",
                "tags": idea.tags or [], "node_type": "idea",
                "status": idea.status, "score": idea.score}
        print(render_idea_note(note, bubble_id=idea.parent_id or idea.id,
                               folder_name="VibeMind - <bubble>"))
        return 0
    print("pass --idea <id>", file=sys.stderr)
    return 2


if __name__ == "__main__":
    import sys
    raise SystemExit(_main(sys.argv[1:]))
