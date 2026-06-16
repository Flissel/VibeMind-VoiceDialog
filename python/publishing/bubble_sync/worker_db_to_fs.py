"""Worker A — DB to Filesystem sync for bubbles (public.ideas -> .md vault).

Drains public.ideas_sync_outbox (rows the trigger emitted on every ideas
change), and for each affected bubble re-publishes its .md folder via the
existing IdeasPublisher.publish_bubble (which already renders id-stamped
frontmatter + user fence — Phase 1). After writing, it records each file's
content-hash into the SHARED .bubble_sync_hashes.json so Worker B recognises
the write as an echo (no bounce-back).

Why reuse publish_bubble instead of a bespoke renderer: it is the single source
of truth for the .md layout (overview + per-idea files + pruning) and is already
deterministic/byte-stable (verified Phase 1). Worker A just makes it event-driven.

Loop/echo prevention: hash-store is shared with Worker B; Worker B skips a file
whose hash matches what Worker A just stored.

Kill-switch: VIBEMIND_BUBBLE_SYNC_ENABLED (default off).

CLI:  python -m publishing.bubble_sync.worker_db_to_fs [--once]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import signal
import sys
import time
from pathlib import Path

from . import _db

VAULT_DIR = Path(os.environ.get(
    "BUBBLE_VAULT_DIR",
    str(Path.home() / ".rowboat" / "knowledge" / "Projects"),
))
HASH_STORE = Path(os.environ.get(
    "BUBBLE_HASH_STORE",
    str(Path.home() / ".rowboat" / "knowledge" / ".bubble_sync_hashes.json"),
))
POLL_FALLBACK_SEC = int(os.environ.get("BUBBLE_DB_POLL_SEC", "5"))
ENABLED = os.environ.get("VIBEMIND_BUBBLE_SYNC_ENABLED", "0") in ("1", "true", "True")
BATCH = 50

_shutdown = False


def _on_sigterm(signum, frame):
    global _shutdown
    _shutdown = True
    print("[worker_a] received signal, will exit", flush=True)


signal.signal(signal.SIGINT, _on_sigterm)
signal.signal(signal.SIGTERM, _on_sigterm)


def _load_hash_store() -> dict:
    if HASH_STORE.exists():
        try:
            return json.loads(HASH_STORE.read_text())
        except Exception:
            pass
    return {}


def _save_hash_store(store: dict) -> None:
    HASH_STORE.parent.mkdir(parents=True, exist_ok=True)
    tmp = HASH_STORE.with_suffix(".tmp")
    tmp.write_text(json.dumps(store, indent=2, sort_keys=True))
    tmp.replace(HASH_STORE)


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _safe_filename(title: str) -> str:
    import re
    name = re.sub(r'[<>:"/\\|?*]', "", title or "").strip()
    return name or "Untitled"


def _record_folder_hashes(bubble_title: str, hash_store: dict) -> int:
    """After publish_bubble wrote the folder, store every .md's hash so Worker B
    sees them as echoes (= our own write, don't re-apply to DB)."""
    folder = VAULT_DIR / f"VibeMind - {_safe_filename(bubble_title)}"
    n = 0
    if folder.is_dir():
        for f in folder.glob("*.md"):
            try:
                hash_store[str(f)] = _content_hash(f.read_text(encoding="utf-8"))
                n += 1
            except Exception:
                pass
    return n


def _republish_bubbles(by_bubble: dict[str, list], container: str, hash_store: dict,
                       label: str) -> list:
    """Re-publish each unique bubble once (covers ALL its ideas AND canvas nodes —
    publish_bubble renders both into the one folder). Returns the flat list of
    outbox row-ids that were covered (caller marks them applied in their table).
    Shared by the ideas- and canvas-outbox drains so a bubble touched by both in
    one cycle is published only once (de-dup happens in the merged by_bubble map)."""
    from data import IdeasRepository
    from publishing.ideas_publisher import IdeasPublisher
    repo = IdeasRepository()
    pub = IdeasPublisher()

    applied_ids: list = []
    for bubble_id, ids in by_bubble.items():
        try:
            bub = repo.get(bubble_id)
            if bub:
                pub.publish_bubble(bubble_id)
                cnt = _record_folder_hashes(bub.title or "", hash_store)
                print(f"[worker_a] re-published bubble={bubble_id} ({cnt} .md hashed) [{label}]",
                      flush=True)
            else:
                print(f"[worker_a] bubble {bubble_id} not in DB (deleted) — skipping render", flush=True)
            applied_ids.extend(ids)
        except Exception as e:
            print(f"[worker_a] publish bubble={bubble_id} ERROR: {e}", flush=True)
    return applied_ids


def drain_outbox(container: str, hash_store: dict) -> int:
    """Drain BOTH the ideas- and canvas-sync outboxes in one pass, collapse to a
    SINGLE set of affected bubbles, and re-publish each bubble once. This is the
    de-dup that prevents a double render when a bubble has both an ideas change
    and a canvas change in the same cycle (Risk R6)."""
    idea_rows = _db.query_via_docker(
        "SELECT id, idea_id, bubble_id, operation FROM public.ideas_sync_outbox "
        f"WHERE applied_at IS NULL ORDER BY emitted_at LIMIT {BATCH}",
        container=container,
    )
    canvas_rows = _db.query_via_docker(
        "SELECT id, node_id, bubble_id, operation FROM public.canvas_sync_outbox "
        f"WHERE applied_at IS NULL ORDER BY emitted_at LIMIT {BATCH}",
        container=container,
    )
    if not idea_rows and not canvas_rows:
        return 0

    # Merge BOTH outboxes onto the bubble key (de-dup), tracking which table each
    # row-id came from so we mark them applied in the right table afterwards.
    by_bubble: dict[str, list] = {}
    idea_ids: list[str] = []
    canvas_ids: list[str] = []
    for r in idea_rows:
        by_bubble.setdefault(r["bubble_id"], [])
        idea_ids.append(r["id"])
    for r in canvas_rows:
        by_bubble.setdefault(r["bubble_id"], [])
        canvas_ids.append(r["id"])
    # value lists are only used for the count; the publish covers the whole bubble
    for b in by_bubble:
        by_bubble[b] = ["_"]

    _republish_bubbles(by_bubble, container, hash_store, label="ideas+canvas")
    if hash_store:
        _save_hash_store(hash_store)

    if idea_ids:
        id_array = ",".join(f"'{i}'::uuid" for i in idea_ids)
        _db.execute_via_docker(
            f"SELECT public.mark_ideas_outbox_applied(ARRAY[{id_array}])",
            container=container,
        )
    if canvas_ids:
        id_array = ",".join(f"'{i}'::uuid" for i in canvas_ids)
        _db.execute_via_docker(
            f"SELECT public.mark_canvas_outbox_applied(ARRAY[{id_array}])",
            container=container,
        )
    return len(idea_ids) + len(canvas_ids)


def listen_forever(container: str) -> None:
    hash_store = _load_hash_store()
    print(f"[worker_a] initial drain…", flush=True)
    try:
        n = drain_outbox(container, hash_store)
        print(f"[worker_a] initial drain applied {n} events", flush=True)
    except Exception as e:
        print(f"[worker_a] initial drain error: {e}", flush=True)
    while not _shutdown:
        time.sleep(min(POLL_FALLBACK_SEC, 5))
        if _shutdown:
            break
        try:
            drain_outbox(container, hash_store)
        except Exception as e:
            print(f"[worker_a] drain error: {e}", flush=True)


def _main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    p = argparse.ArgumentParser(description="Bubble DB->FS sync worker")
    p.add_argument("--once", action="store_true", help="drain once and exit")
    args = p.parse_args()

    if not ENABLED:
        print("[worker_a] VIBEMIND_BUBBLE_SYNC_ENABLED not set — exiting (kill-switch).",
              flush=True)
        return 0
    container = _db.find_supabase_container()
    print(f"[worker_a] container={container[:12]} vault={VAULT_DIR}", flush=True)
    if args.once:
        hs = _load_hash_store()
        n = drain_outbox(container, hs)
        print(f"[worker_a] drained {n} events", flush=True)
        return 0
    listen_forever(container)
    return 0


if __name__ == "__main__":
    sys.exit(_main())
