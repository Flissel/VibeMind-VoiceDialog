"""Bubbles stay where they are stored.

At some starts every bubble jumped: the start thread "bubble-loader" and the renderer's
get_bubbles loaded at the same time, each bubble met its own copy in memory, counted that
as a collision, got a random new place and that place was written back to the database.
Now a stored position is never moved or written while loading, a bubble never collides
with itself, and only one load runs at a time. Invented ids and titles only.
"""
import threading
import time

from ipc.canvas_manager import CanvasManager


class _Idea:
    def __init__(self, idea_id, title, position=None):
        self.id = idea_id
        self.title = title
        self.description = ""
        self.score = 0
        self.status = ""
        self.metadata = {"position": dict(position)} if position else {}


class _Repo:
    """Hands out the ideas; the first list call can be held so a second load runs into it."""

    def __init__(self, ideas, hold_first=False):
        self.ideas = ideas
        self.updates = []
        self.lists = 0
        self.first_inside = threading.Event()
        self.release_first = threading.Event()
        if not hold_first:
            self.release_first.set()

    def list_top_level(self, limit=50, order_by=None):
        self.lists += 1
        if self.lists == 1:
            self.first_inside.set()
            self.release_first.wait(5)
        return list(self.ideas)

    def update(self, idea):
        self.updates.append((idea.id, dict(idea.metadata.get("position", {}))))


class _Backend:
    def __init__(self, repo):
        self.ideas_repo = repo
        self.bubbles = {}
        self.bubble_id_map = {}
        self.next_bubble_id = 1
        self.sent = []

    def send_message(self, message):
        self.sent.append(message)


def _ideas_close_together():
    # two stored places 0.5 apart: closer than the collision distance, still never moved
    return [
        _Idea("idee-0001", "Erfunden Eins", {"x": 1.0, "y": 0.0, "z": 0.0}),
        _Idea("idee-0002", "Erfunden Zwei", {"x": 1.5, "y": 0.0, "z": 0.0}),
        _Idea("idee-0003", "Erfunden Drei", {"x": -4.0, "y": 0.5, "z": 2.0}),
    ]


def _places(backend):
    return {b.db_id: dict(b.position) for b in backend.bubbles.values()}


def test_two_loads_at_the_same_time_write_nothing_and_move_nothing():
    ideas = _ideas_close_together()
    stored = {i.id: dict(i.metadata["position"]) for i in ideas}
    repo = _Repo(ideas, hold_first=True)
    backend = _Backend(repo)
    manager = CanvasManager(backend)

    start = threading.Thread(target=manager._load_bubbles_from_db, name="bubble-loader")
    start.start()
    assert repo.first_inside.wait(5)
    renderer = threading.Thread(target=manager.get_all_bubbles)
    renderer.start()
    time.sleep(0.2)                       # the renderer's load runs into the start load
    repo.release_first.set()
    start.join(5)
    renderer.join(5)

    assert repo.updates == []             # no update call
    assert repo.lists == 1                # the second load used the first one's result
    assert _places(backend) == stored     # every bubble at its stored place
    assert len(backend.bubbles) == 3      # one copy each
    assert sorted(m["node"]["id"] for m in backend.sent if m["type"] == "node_added") == sorted(stored)


def test_loading_again_after_the_first_load_keeps_the_places():
    ideas = _ideas_close_together()
    stored = {i.id: dict(i.metadata["position"]) for i in ideas}
    repo = _Repo(ideas)
    backend = _Backend(repo)
    manager = CanvasManager(backend)

    manager._load_bubbles_from_db()       # start thread
    manager._load_bubbles_from_db()       # a reload without clearing (enter of an unknown bubble)
    manager.get_all_bubbles()             # the renderer's reload with clearing

    assert repo.updates == []
    assert _places(backend) == stored
    assert len(backend.bubbles) == 3


def test_a_bubble_never_collides_with_itself():
    backend = _Backend(_Repo([]))
    manager = CanvasManager(backend)
    backend.ideas_repo = None
    from electron_backend import Bubble
    backend.bubbles[1] = Bubble(id=1, title="Erfunden", position={"x": 0, "y": 0, "z": 0}, db_id="idee-0001")
    assert manager._check_collision({"x": 0, "y": 0, "z": 0}, exclude_db_id="idee-0001") is False
    assert manager._check_collision({"x": 0, "y": 0, "z": 0}, exclude_db_id="idee-0002") is True
    assert manager._check_collision({"x": 0, "y": 0, "z": 0}) is True


def test_a_bubble_without_a_place_gets_one_written_once():
    fresh = _Idea("idee-0009", "Erfunden Neu")
    repo = _Repo([fresh])
    backend = _Backend(repo)
    manager = CanvasManager(backend)

    manager._load_bubbles_from_db()
    assert len(repo.updates) == 1
    written = repo.updates[0][1]
    assert _places(backend)["idee-0009"] == written

    # the database did not keep it (a failed write): loading again does not write again
    fresh.metadata = {}
    manager.get_all_bubbles()
    assert len(repo.updates) == 1
