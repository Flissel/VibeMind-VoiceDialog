"""Pins the 2026-09-17 fix: drain_outbox() must not mark an outbox row applied
unless its bubble actually published.

Incident this guards against: _republish_bubbles() already computed which
bubbles succeeded, but drain_outbox() discarded that return value and marked
EVERY fetched idea_ids/canvas_ids row applied unconditionally. On 2026-09-16
that silently marked 53 outbox rows (3 canvas + 50 ideas) as synced while
every single publish_bubble() call had failed with a network timeout — zero
files were actually written to the vault. See
docs/operations/2026-09-16-bubble-sync-dauerbetrieb.md for the incident.

This test simulates one bubble whose publish succeeds and one whose publish
raises, each contributing rows to BOTH outbox tables, and asserts on the
exact row-ids passed to mark_ideas_outbox_applied / mark_canvas_outbox_applied
— not merely that drain_outbox() returned without error. Against the
unfixed code this test fails, because the old code marks every row
(including the failed bubble's) applied regardless.
"""
import re
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
import types

# voice/python — parent of publishing/ — so `from publishing... import ...`
# resolves regardless of the directory pytest is invoked from.
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from publishing.bubble_sync import worker_db_to_fs as wa  # noqa: E402


def _uuids_in_call(call_args) -> set[str]:
    """Extract the quoted id literals from a `SELECT public.mark_*_applied(
    ARRAY['id1'::uuid, 'id2'::uuid])` SQL string passed to execute_via_docker."""
    sql = call_args.args[0]
    return set(re.findall(r"'([^']+)'::uuid", sql))


def test_failed_bubble_publish_leaves_its_outbox_rows_unmarked(monkeypatch):
    idea_rows = [
        {"id": "idea-good-1", "idea_id": "i1", "bubble_id": "good-bubble", "operation": "UPDATE"},
        {"id": "idea-bad-1", "idea_id": "i2", "bubble_id": "bad-bubble", "operation": "UPDATE"},
    ]
    canvas_rows = [
        {"id": "canvas-bad-1", "node_id": "n1", "bubble_id": "bad-bubble", "operation": "INSERT"},
    ]

    query_responses = iter([idea_rows, canvas_rows])
    monkeypatch.setattr(wa._db, "query_via_docker",
                         MagicMock(side_effect=lambda *a, **k: next(query_responses)))

    executed_calls = []
    monkeypatch.setattr(
        wa._db, "execute_via_docker",
        MagicMock(side_effect=lambda *a, **k: executed_calls.append(
            types.SimpleNamespace(args=a, kwargs=k)) or "OK"),
    )

    # _republish_bubbles never touches the filesystem in this test.
    monkeypatch.setattr(wa, "_record_folder_hashes", lambda *a, **k: 0)
    monkeypatch.setattr(wa, "_save_hash_store", lambda *a, **k: None)

    # Stub `data.IdeasRepository` and `publishing.ideas_publisher.IdeasPublisher`
    # via sys.modules so _republish_bubbles's lazy `from X import Y` picks up
    # fakes instead of executing the real, network-touching modules.
    fake_bubble = types.SimpleNamespace(title="Some Bubble")

    class FakeRepo:
        def get(self, bubble_id):
            return fake_bubble

    class FakePublisher:
        def publish_bubble(self, bubble_id):
            if bubble_id == "bad-bubble":
                raise RuntimeError("<urlopen error timed out>")
            return None

    fake_data_module = types.ModuleType("data")
    fake_data_module.IdeasRepository = FakeRepo
    fake_publisher_module = types.ModuleType("publishing.ideas_publisher")
    fake_publisher_module.IdeasPublisher = FakePublisher

    with patch.dict(sys.modules, {
        "data": fake_data_module,
        "publishing.ideas_publisher": fake_publisher_module,
    }):
        applied_count = wa.drain_outbox(container="fake-container", hash_store={})

    # ── The pin: only the successful bubble's rows may be marked applied ──
    assert applied_count == 1, (
        f"expected exactly 1 row marked applied (the good bubble's), got {applied_count}"
    )

    ideas_calls = [c for c in executed_calls if "mark_ideas_outbox_applied" in c.args[0]]
    canvas_calls = [c for c in executed_calls if "mark_canvas_outbox_applied" in c.args[0]]

    assert len(ideas_calls) == 1, f"expected exactly one mark_ideas_outbox_applied call, got {len(ideas_calls)}"
    ideas_marked = _uuids_in_call(ideas_calls[0])
    assert ideas_marked == {"idea-good-1"}, (
        f"mark_ideas_outbox_applied must cover ONLY the successful bubble's row, "
        f"got {ideas_marked} (bug: the failed bubble's 'idea-bad-1' must NOT appear here)"
    )

    # bad-bubble's canvas row is the ONLY canvas row fetched, and its publish
    # failed -> applied_canvas_ids is empty -> mark_canvas_outbox_applied must
    # not be called at all.
    assert len(canvas_calls) == 0, (
        f"mark_canvas_outbox_applied must not be called when every canvas row's "
        f"bubble failed to publish, but it was called with {[_uuids_in_call(c) for c in canvas_calls]}"
    )


def test_all_bubbles_succeed_marks_all_rows(monkeypatch):
    """Sanity companion: when every bubble publishes cleanly, every row IS
    marked applied (guards against an over-correction that marks nothing)."""
    idea_rows = [
        {"id": "idea-1", "idea_id": "i1", "bubble_id": "b1", "operation": "UPDATE"},
    ]
    canvas_rows = [
        {"id": "canvas-1", "node_id": "n1", "bubble_id": "b1", "operation": "INSERT"},
    ]
    query_responses = iter([idea_rows, canvas_rows])
    monkeypatch.setattr(wa._db, "query_via_docker",
                         MagicMock(side_effect=lambda *a, **k: next(query_responses)))
    executed_calls = []
    monkeypatch.setattr(
        wa._db, "execute_via_docker",
        MagicMock(side_effect=lambda *a, **k: executed_calls.append(
            types.SimpleNamespace(args=a, kwargs=k)) or "OK"),
    )
    monkeypatch.setattr(wa, "_record_folder_hashes", lambda *a, **k: 0)
    monkeypatch.setattr(wa, "_save_hash_store", lambda *a, **k: None)

    fake_bubble = types.SimpleNamespace(title="B1")

    class FakeRepo:
        def get(self, bubble_id):
            return fake_bubble

    class FakePublisher:
        def publish_bubble(self, bubble_id):
            return None

    fake_data_module = types.ModuleType("data")
    fake_data_module.IdeasRepository = FakeRepo
    fake_publisher_module = types.ModuleType("publishing.ideas_publisher")
    fake_publisher_module.IdeasPublisher = FakePublisher

    with patch.dict(sys.modules, {
        "data": fake_data_module,
        "publishing.ideas_publisher": fake_publisher_module,
    }):
        applied_count = wa.drain_outbox(container="fake-container", hash_store={})

    assert applied_count == 2
    ideas_calls = [c for c in executed_calls if "mark_ideas_outbox_applied" in c.args[0]]
    canvas_calls = [c for c in executed_calls if "mark_canvas_outbox_applied" in c.args[0]]
    assert _uuids_in_call(ideas_calls[0]) == {"idea-1"}
    assert _uuids_in_call(canvas_calls[0]) == {"canvas-1"}
