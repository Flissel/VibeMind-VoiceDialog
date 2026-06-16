"""Deterministic YAML frontmatter serializer for bubble/idea .md files.

Hand-rolled (not PyYAML) for exact control over field ordering, quoting, null
representation and list formatting — diff-friendly + round-trippable. The schema
is CLOSED: a known set of fields in a known order. Adapted verbatim from
spaces/marketing/sync/_frontmatter.py; only SCHEMA_GROUPS differs.

Schema groups (in this order):
  1. sync-meta: idea_id, bubble_id, sync_version, sync_source, sync_path,
                last_synced_at, content_hash
  2. idea:      title, status, tags, score, node_type
  3. canvas:    canvas_node_id, has_content_json, reformat_pending

sync-meta is sync-authoritative (do NOT edit by hand). The `idea` group are the
editable mirrors that FS->DB reads back. `idea_id` = the public.ideas PK (stable
UUID) — the deterministic match key for FS->DB. Bump sync_version on schema change.

The `canvas` group is emitted ONLY for canvas-node .md (render_canvas_note); for
idea/overview notes these fields render as `null` and are ignored by parse_idea_md.
  - canvas_node_id   = public.canvas_nodes.id — the FS->DB match key for canvas.
                       Its presence is what makes Worker B take the canvas path.
  - has_content_json = true for the 91 structured nodes (content+reformat path),
                       false for the 6 plain nodes (direct-content path).
  - reformat_pending = true while content was FS-edited but content_json not yet
                       regenerated (anti-flicker: render from content, not flatten).
NOTE for canvas .md: `idea_id` carries the BUBBLE id (= linked_idea_id), so the
existing bubble_id grouping / LWW keying need no rename; the real node id lives in
canvas_node_id.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

SYNC_VERSION = 2

SCHEMA_GROUPS: list[tuple[str, list[str]]] = [
    ("sync-meta", ["idea_id", "bubble_id", "sync_version", "sync_source",
                   "sync_path", "last_synced_at", "content_hash"]),
    ("idea",      ["title", "status", "tags", "score", "node_type"]),
    ("canvas",    ["canvas_node_id", "has_content_json", "reformat_pending"]),
]

# Flat ordered list of every field name.
SCHEMA_FIELDS: list[str] = [f for _, fields in SCHEMA_GROUPS for f in fields]


def _scalar(value: Any) -> str:
    """Serialise a YAML scalar with safe quoting."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")
    if isinstance(value, str):
        if not value:
            return '""'
        reserved = {"null", "true", "false", "yes", "no", "on", "off", "~"}
        bare_safe = (
            value not in reserved
            and value[0] not in ' \t-?[{!&*|>"\'%@`#,'
            and value[-1] not in " \t"
            and not any(c in value for c in ":#\n\r\t\"\\")
            and not value.replace(".", "").replace("-", "").isdigit()
        )
        if bare_safe:
            return value
        escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\t", "\\t")
        return f'"{escaped}"'
    raise TypeError(f"Unhandled YAML scalar type: {type(value).__name__}")


def _emit_list(key: str, items: list[Any], indent: int = 0) -> list[str]:
    """Emit a list — block style (`- item`) so each line diffs cleanly."""
    prefix = " " * indent
    if not items:
        return [f"{prefix}{key}: []"]
    out = [f"{prefix}{key}:"]
    for item in items:
        if isinstance(item, dict):
            keys = list(item.keys())
            first_key = keys[0]
            out.append(f"{prefix}  - {first_key}: {_scalar(item[first_key])}")
            for k in keys[1:]:
                out.append(f"{prefix}    {k}: {_scalar(item[k])}")
        else:
            out.append(f"{prefix}  - {_scalar(item)}")
    return out


def render_frontmatter(data: dict) -> str:
    """Render a frontmatter dict to canonical YAML. Unknown fields dropped
    (closed schema); missing fields appear as `key: null`."""
    lines: list[str] = ["---"]
    for group_name, fields in SCHEMA_GROUPS:
        if group_name != "sync-meta":
            lines.append("")
        for field in fields:
            value = data.get(field)
            if isinstance(value, list):
                lines.extend(_emit_list(field, value))
            else:
                lines.append(f"{field}: {_scalar(value)}")
    lines.append("---")
    return "\n".join(lines)


def parse_frontmatter(md_text: str) -> dict | None:
    """Tiny frontmatter parser for round-trip diffing + FS->DB identity.
    Only handles what we emit. Returns None if no frontmatter block found."""
    if not md_text.startswith("---\n"):
        return None
    end = md_text.find("\n---\n", 4)
    if end < 0:
        return None
    fm_block = md_text[4:end]

    out: dict[str, Any] = {}
    current_list_key: str | None = None
    current_list_items: list = []
    current_dict_item: dict | None = None
    for raw_line in fm_block.split("\n"):
        line = raw_line.rstrip()
        if not line or line.startswith("#"):
            continue
        if current_list_key is not None:
            stripped = line.lstrip()
            indent = len(line) - len(stripped)
            if indent >= 2 and stripped.startswith("- "):
                if current_dict_item is not None:
                    current_list_items.append(current_dict_item)
                    current_dict_item = None
                item_text = stripped[2:].strip()
                if ":" in item_text:
                    k, _, v = item_text.partition(":")
                    current_dict_item = {k.strip(): _parse_scalar(v.strip())}
                else:
                    current_list_items.append(_parse_scalar(item_text))
                continue
            if indent >= 4 and current_dict_item is not None and ":" in stripped:
                k, _, v = stripped.partition(":")
                current_dict_item[k.strip()] = _parse_scalar(v.strip())
                continue
            if current_dict_item is not None:
                current_list_items.append(current_dict_item)
                current_dict_item = None
            out[current_list_key] = current_list_items
            current_list_key = None
            current_list_items = []

        if ":" in line:
            key, _, val = line.partition(":")
            key = key.strip()
            val = val.strip()
            if val == "" or val == "[]":
                if val == "[]":
                    out[key] = []
                else:
                    current_list_key = key
                    current_list_items = []
                    current_dict_item = None
            else:
                out[key] = _parse_scalar(val)

    if current_list_key is not None:
        if current_dict_item is not None:
            current_list_items.append(current_dict_item)
        out[current_list_key] = current_list_items

    return out


def _parse_scalar(text: str) -> Any:
    """Inverse of _scalar — minimal."""
    if text == "null":
        return None
    if text == "true":
        return True
    if text == "false":
        return False
    if text.startswith('"') and text.endswith('"'):
        return text[1:-1].replace('\\n', '\n').replace('\\t', '\t').replace('\\"', '"').replace('\\\\', '\\')
    try:
        if "." in text:
            return float(text)
        return int(text)
    except ValueError:
        return text
