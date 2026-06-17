"""Format validation for bubble/idea .md files — both sync directions.

validate_idea_md: DB->FS guard — Worker A refuses to write a malformed render.
parse_idea_md:    FS->DB guard (Phase 2) — extract editable fields from an
                  edited file, rejecting anything that doesn't parse to a valid
                  idea (so a broken file never corrupts public.ideas).
"""
from __future__ import annotations

from ._frontmatter import parse_frontmatter
from .render_md import USER_FENCE

VALID_STATUS = {"raw", "scored", "promoted", "archived", "active"}
_REQUIRED_FM = ("idea_id", "bubble_id", "sync_version")


def validate_idea_md(text: str) -> tuple[bool, list[str]]:
    """DB->FS: is this a well-formed idea .md we're allowed to write?
    Returns (ok, errors)."""
    errors: list[str] = []
    fm = parse_frontmatter(text)
    if fm is None:
        return False, ["no frontmatter block"]
    for k in _REQUIRED_FM:
        if not fm.get(k):
            errors.append(f"missing/empty frontmatter field: {k}")
    if not text.lstrip().startswith("---"):
        errors.append("does not start with frontmatter")
    if USER_FENCE not in text:
        errors.append("user fence missing")
    # exactly one H1
    h1s = [ln for ln in text.splitlines() if ln.startswith("# ")]
    if len(h1s) != 1:
        errors.append(f"expected exactly one H1, found {len(h1s)}")
    return (not errors), errors


def parse_idea_md(text: str) -> tuple[bool, dict, list[str]]:
    """FS->DB (Phase 2): extract editable fields from an edited file.
    Returns (ok, fields, errors). fields keys: idea_id, title, status, tags,
    description. Rejects malformed input — caller must NOT apply on ok=False."""
    errors: list[str] = []
    fm = parse_frontmatter(text)
    if fm is None:
        return False, {}, ["no frontmatter"]
    idea_id = fm.get("idea_id")
    if not idea_id:
        return False, {}, ["no idea_id — cannot match to a row"]

    title = (fm.get("title") or "").strip()
    if not title:
        errors.append("empty title")
    status = (fm.get("status") or "").strip() or "raw"
    if status not in VALID_STATUS:
        errors.append(f"invalid status: {status!r}")
    tags = fm.get("tags") or []
    if not isinstance(tags, list):
        errors.append("tags is not a list")
        tags = []

    description = _body_description(text)

    fields = {
        "idea_id": idea_id,
        "title": title,
        "status": status,
        "tags": tags,
        "description": description,
        # node_type drives Worker B's read-only guard: canvas-node-sourced .md
        # (node_type != 'idea') are a lossy flatten of content_json and must NOT
        # be written back to public.ideas. last_synced_at drives conflict-LWW.
        "node_type": (fm.get("node_type") or "idea"),
        "last_synced_at": fm.get("last_synced_at"),
    }
    return (not errors), fields, errors


def parse_canvas_md(text: str) -> tuple[bool, dict, list[str]]:
    """FS->DB for CANVAS nodes: extract the writable field (content body) from an
    edited canvas .md. Returns (ok, fields, errors). fields keys: canvas_node_id,
    bubble_id, node_type, has_content_json, reformat_pending, content, last_synced_at.

    Canvas writeback rules (differ from ideas):
      - The ONLY field written back is `content` (the body). title, node_type and
        content_json-direct are READ-ONLY (title per user decision; content_json is
        a lossy flatten that can't be reconstructed — it's regenerated via reformat).
      - Identity key is `canvas_node_id` (NOT idea_id, which carries the bubble id
        on canvas files). Reject if absent — never guess.
    """
    errors: list[str] = []
    fm = parse_frontmatter(text)
    if fm is None:
        return False, {}, ["no frontmatter"]
    canvas_node_id = fm.get("canvas_node_id")
    if not canvas_node_id:
        return False, {}, ["no canvas_node_id — not a canvas-writeback file"]

    content = _body_description(text)

    fields = {
        "canvas_node_id": canvas_node_id,
        "bubble_id": fm.get("idea_id"),          # canvas files carry the bubble id under idea_id
        "node_type": fm.get("node_type") or "note",
        "has_content_json": bool(fm.get("has_content_json")),
        "reformat_pending": bool(fm.get("reformat_pending")),
        "content": content,
        "last_synced_at": fm.get("last_synced_at"),  # drives conflict-LWW
    }
    return (not errors), fields, errors


def _body_description(text: str) -> str:
    """Extract the idea body (between the H1 and the first decoration/fence) as
    the description. Stops at **Tags:** / **Type:** / **Bubble:** / the fence /
    the '---' footer."""
    # strip frontmatter
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end >= 0:
            text = text[end + 5:]
    lines = text.splitlines()
    # find H1
    start = 0
    for i, ln in enumerate(lines):
        if ln.startswith("# "):
            start = i + 1
            break
    out: list[str] = []
    for ln in lines[start:]:
        s = ln.strip()
        if (s.startswith("**Tags:**") or s.startswith("**Type:**")
                or s.startswith("**Bubble:**") or s == "---"
                or ln.startswith("<!-- ")):
            break
        out.append(ln)
    return "\n".join(out).strip()
