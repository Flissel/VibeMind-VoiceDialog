"""Saving an idea keeps its score; the old block of open points does not come back.

1. IdeasRepository.update used to recompute ideas.score from the four old axes on
   every save and so overwrote every other evaluation. Saving now writes the score
   as it is; only the explicit scoring tool computes from the axes.
2. The file-to-database sync must not write the machine-written block
   "--- MiroFish Evaluation: Offene Punkte ---" back into the description.
Invented ideas only; no database is touched.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from data.ideas_repository import IdeasRepository  # noqa: E402
from data.models import Idea  # noqa: E402
from publishing.bubble_sync.render_md import render_idea_note  # noqa: E402
from publishing.bubble_sync.validate import OPEN_POINTS_MARKER, parse_idea_md  # noqa: E402


class FakeDb:
    def __init__(self):
        self.calls = []

    def execute(self, sql, params=()):
        self.calls.append((sql, params))


def _saved_score_and_status(db):
    sql, params = db.calls[-1]
    assert "UPDATE ideas SET" in sql
    # order in the UPDATE: title, description, source, score, status, ...
    return params[3], params[4]


def test_saving_keeps_the_score_of_an_evaluation():
    db = FakeDb()
    idea = Idea(id="idee-1", title="Beispielidee", score=80.0, status="scored",
                feasibility=5, impact=4, novelty=4, urgency=6)
    saved = IdeasRepository(db=db).update(idea)
    assert saved.score == 80.0, "not the 46.5 of the four old axes"
    assert _saved_score_and_status(db) == (80.0, "scored")


def test_saving_changes_neither_score_nor_status_of_a_promoted_idea():
    db = FakeDb()
    idea = Idea(id="idee-2", title="Beispielidee", score=0.0, status="promoted",
                feasibility=8, impact=9, novelty=7, urgency=6)
    IdeasRepository(db=db).update(idea)
    assert _saved_score_and_status(db) == (0.0, "promoted")


def test_the_scoring_tool_still_computes_from_the_axes():
    from tools import workspace_tools as wt

    db = FakeDb()
    stored = Idea(id="idee-3", title="Beispielidee", status="raw")

    class Repo(IdeasRepository):
        def __init__(self):
            super().__init__(db=db)

        def get(self, idea_id):
            return stored

    original = wt.IdeasRepository
    wt.IdeasRepository = Repo
    try:
        text = wt.score_idea({"id": "idee-3", "feasibility": 5, "impact": 4, "novelty": 4, "urgency": 6})
    finally:
        wt.IdeasRepository = original
    assert "scored 46 out of 100" in text, text
    assert _saved_score_and_status(db) == (46.5, "scored")


def _file_with(description):
    return render_idea_note(
        {"id": "idee-4", "title": "Beispielidee", "content": description, "tags": [], "node_type": "idea"},
        bubble_id="bubble-4", folder_name="Beispiel", now_iso="2026-01-01T00:00:00+00:00",
    )


def test_an_old_file_does_not_bring_the_open_points_back():
    old = "Kurze Beschreibung.\n\n" + OPEN_POINTS_MARKER + "\n- Punkt eins\n- Punkt zwei"
    text = _file_with(old)
    assert OPEN_POINTS_MARKER in text, "the render carries the block (precondition)"
    ok, fields, errors = parse_idea_md(text)
    assert ok, errors
    assert fields["description"] == "Kurze Beschreibung."


def test_a_description_without_the_block_is_written_back_unchanged():
    ok, fields, errors = parse_idea_md(_file_with("Erste Zeile.\n\nZweite Zeile mit --- Strichen."))
    assert ok, errors
    assert fields["description"] == "Erste Zeile.\n\nZweite Zeile mit --- Strichen."
