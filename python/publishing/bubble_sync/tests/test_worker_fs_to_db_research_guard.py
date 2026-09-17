"""Pins the 2026-09-17 fix: a research canvas node must never be written back
from the vault to the database.

Incident this guards against: `_body_description` (validate.py) stops
collecting a canvas node's body at the first line that is exactly `---`. A
deep-research report legitimately contains many such lines — the real one on
this machine has 20, the first at line 9 — so a single FS->DB writeback of a
research node would truncate a 57,454-byte `canvas_nodes.content` down to
364 bytes, silently: the write is GUC-fenced, so it emits no outbox event and
nothing downstream notices. The next render then carries the truncation into
the vault file too.

A research node is filed once by a deep-research run and never touched again
— vault->database is meaningless for it by construction, exactly like the
pre-existing non-idea/non-canvas read-only guard in the idea path
(worker_fs_to_db.py `_handle_event`, ~line 277). `_handle_canvas_event` now
applies the same shape for `node_type == "research"`: log read-only, record
the observed hash, return — BEFORE the LWW check and BEFORE
update_canvas_in_db.

Against the unguarded code, test_research_node_never_reaches_update_canvas_in_db
fails (update_canvas_in_db gets called), because nothing stops a research
node's edited body from being written straight through.
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock

# voice/python — parent of publishing/ — so `from publishing... import ...`
# resolves regardless of the directory pytest is invoked from.
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from publishing.bubble_sync import worker_fs_to_db as wb  # noqa: E402
from publishing.bubble_sync.render_md import render_canvas_note  # noqa: E402


def _research_report_body(n_dividers: int = 20) -> str:
    """A synthetic deep-research report body shaped like the real incident:
    many literal `---` lines mixed into prose, well before any trailing
    footer — the thing _body_description truncates at line 9 of 20 on the
    real file."""
    lines = ["## Executive Summary", "", "Some introductory analysis text.", ""]
    for i in range(n_dividers):
        lines.append(f"### Finding {i}")
        lines.append("Supporting detail for this finding.")
        lines.append("---")
    return "\n".join(lines)


def _canvas_md(node_type: str, node_id: str = "node-1", bubble_id: str = "bubble-1") -> str:
    """Build a real, well-formed canvas .md (via the actual renderer) for the
    given node_type, so parse_canvas_md sees exactly what Worker A would have
    written."""
    note = {
        "id": node_id,
        "title": "Deep Research: Something",
        "content": _research_report_body() if node_type == "research" else "Plain note body.",
        "tags": [],
        "node_type": node_type,
        "has_content_json": False,
        "reformat_pending": False,
    }
    return render_canvas_note(note, bubble_id=bubble_id, folder_name="TestProject")


def test_research_node_never_reaches_update_canvas_in_db(monkeypatch):
    """The write function itself must never be called for a research node —
    not merely 'nothing changed'."""
    text = _canvas_md("research")
    path = Path("Projects/TestProject/canvas/node-1.md")

    monkeypatch.setattr(wb, "update_canvas_in_db", MagicMock())
    # The guard must return BEFORE the LWW check ever touches the DB.
    monkeypatch.setattr(
        wb, "_canvas_db_updated_at",
        MagicMock(side_effect=AssertionError(
            "guard must return before the LWW check reaches the DB")),
    )
    monkeypatch.setattr(wb, "_save_hash_store", lambda store: None)

    hash_store: dict = {}
    wb._handle_canvas_event(path, text, "observed-hash-1", "fake-container", hash_store)

    wb.update_canvas_in_db.assert_not_called()


def test_non_research_canvas_node_still_writes(monkeypatch):
    """Guard against over-broad matching: an ordinary canvas node (node_type
    != 'research') must still take the normal writeback path."""
    text = _canvas_md("note")
    path = Path("Projects/TestProject/canvas/node-1.md")

    monkeypatch.setattr(wb, "update_canvas_in_db", MagicMock(return_value=True))
    monkeypatch.setattr(wb, "_canvas_db_updated_at", MagicMock(return_value=None))
    monkeypatch.setattr(wb, "_save_hash_store", lambda store: None)

    hash_store: dict = {}
    wb._handle_canvas_event(path, text, "observed-hash-2", "fake-container", hash_store)

    wb.update_canvas_in_db.assert_called_once()


def test_research_node_hash_recorded_on_skip(monkeypatch):
    """The skip path must still record the observed hash, so the poll loop
    doesn't reprocess (and re-log) the same file forever."""
    text = _canvas_md("research")
    path = Path("Projects/TestProject/canvas/node-1.md")

    monkeypatch.setattr(wb, "update_canvas_in_db", MagicMock())
    monkeypatch.setattr(
        wb, "_canvas_db_updated_at",
        MagicMock(side_effect=AssertionError(
            "guard must return before the LWW check reaches the DB")),
    )
    saved: dict = {}
    monkeypatch.setattr(wb, "_save_hash_store", lambda store: saved.update(store))

    hash_store: dict = {}
    wb._handle_canvas_event(path, text, "observed-hash-3", "fake-container", hash_store)

    assert hash_store[str(path)] == "observed-hash-3"
    assert saved.get(str(path)) == "observed-hash-3"
