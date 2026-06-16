"""Worker B — Filesystem to DB sync for bubbles (FS -> public.ideas).

Watches ~/.rowboat/knowledge/Projects/ RECURSIVELY for edits to the bubble .md
files (Rowboat Knowledge tab writes them directly). On a user edit:

  - parse the idea_id + editable fields (title/status/tags/description) from the
    file's frontmatter+body (bubble_sync.validate.parse_idea_md),
  - apply a GUC-fenced UPDATE to public.ideas via docker-exec psql.

Echo prevention: the file's content-hash is compared to the hash Worker A wrote
into the SHARED .bubble_sync_hashes.json. Same hash == our own echo -> skip.

Loop prevention: every DB write runs
    BEGIN; SELECT set_config('vibemind.sync_origin','fs',true); UPDATE ...; COMMIT;
in ONE psql invocation (= one tx), so the AFTER trigger sees origin='fs' and
skips the outbox emit -> no bounce back to FS. (PostgREST can't do this — each
call is its own tx — which is why Worker B uses direct docker-exec psql.)

SAFETY — NO FS-DELETE -> DB-DELETE: a deleted/renamed file does NOT delete the
bubble. The DB stays authoritative for deletions (a stray editor/rename must
never wipe a real bubble). Deletes are logged only. Bubble deletion happens via
the app, which Worker A then propagates DB->FS.

Kill-switches:
  VIBEMIND_BUBBLE_SYNC_ENABLED  (default off — worker exits unless '1')
  VIBEMIND_BUBBLE_SYNC_DRY_RUN  (logs the UPDATE SQL, executes nothing)

CLI:  python -m publishing.bubble_sync.worker_fs_to_db [--force-polling]
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
from ._frontmatter import parse_frontmatter
from .validate import parse_idea_md, parse_canvas_md

try:
    from watchdog.events import FileSystemEventHandler
    from watchdog.observers import Observer
    HAS_WATCHDOG = True
except ImportError:
    HAS_WATCHDOG = False

# ─── config ─────────────────────────────────────────────────────────────
VAULT_DIR = Path(os.environ.get(
    "BUBBLE_VAULT_DIR",
    str(Path.home() / ".rowboat" / "knowledge" / "Projects"),
))
HASH_STORE = Path(os.environ.get(
    "BUBBLE_HASH_STORE",
    str(Path.home() / ".rowboat" / "knowledge" / ".bubble_sync_hashes.json"),
))
POLL_INTERVAL = int(os.environ.get("BUBBLE_FS_POLL_SEC", "5"))
ENABLED = os.environ.get("VIBEMIND_BUBBLE_SYNC_ENABLED", "0") in ("1", "true", "True")
DRY_RUN = os.environ.get("VIBEMIND_BUBBLE_SYNC_DRY_RUN", "0") in ("1", "true", "True")

_shutdown = False


def _on_sigterm(signum, frame):
    global _shutdown
    _shutdown = True
    print("[worker_b] received signal, will exit", flush=True)


signal.signal(signal.SIGINT, _on_sigterm)
signal.signal(signal.SIGTERM, _on_sigterm)


# ─── hash store (shared with Worker A) — reused verbatim from marketing ──
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


# ─── DB writeback: GUC-fenced UPDATE (extends marketing's DELETE pattern) ─
def update_idea_in_db(fields: dict, container: str) -> bool:
    """Apply an FS edit back to public.ideas. fields from parse_idea_md:
    idea_id, title, status, tags(list), description. GUC-fenced so the trigger
    skips the outbox emit (no loop). All values via _db._sql_literal (no manual
    escaping). tags -> jsonb."""
    iid = fields["idea_id"]
    set_clauses = [
        f"title = {_db._sql_literal(fields['title'])}",
        f"description = {_db._sql_literal(fields['description'])}",
        f"status = {_db._sql_literal(fields['status'])}",
        f"tags = {_db._sql_literal(json.dumps(fields.get('tags') or []))}::jsonb",
    ]
    sql = (
        "BEGIN; "
        "SELECT set_config('vibemind.sync_origin', 'fs', true); "
        f"UPDATE public.ideas SET {', '.join(set_clauses)} "
        f"WHERE id = {_db._sql_literal(iid)}; "
        "COMMIT;"
    )
    if DRY_RUN:
        print(f"[worker_b] DRY-RUN would apply:\n  {sql}", flush=True)
        return True
    try:
        out = _db.execute_via_docker(sql, container=container)
        print(f"[worker_b] UPDATE idea={iid} title={fields['title'][:40]!r} -> {out.strip()[:60]}",
              flush=True)
        return True
    except Exception as e:
        print(f"[worker_b] UPDATE idea={iid} ERROR: {e}", flush=True)
        return False


def update_canvas_in_db(fields: dict, container: str, observed_hash: str) -> bool:
    """Apply a canvas .md body edit back to public.canvas_nodes. Writes ONLY the
    `content` column (title/node_type/content_json stay read-only), GUC-fenced so
    the AFTER trigger skips the outbox emit (no loop). For STRUCTURED nodes
    (has_content_json) it also sets reformat_pending=true (anti-flicker) and
    ENQUEUES a reformat job carrying the node's ORIGINAL content_json (captured
    BEFORE this write) as the undo source — the drainer regenerates content_json.

    NEVER use canvas_repo.update_node here: it routes through PostgREST, which is
    one-call-one-tx and cannot carry the sync_origin GUC → it would echo. All
    fenced writes go through raw psql (_db.execute_via_docker)."""
    nid = fields["canvas_node_id"]

    # Capture the node's CURRENT content_json + node_type BEFORE the content write.
    # Worker B only writes `content`, so this read still sees the pre-edit structure
    # — the correct undo source for the reformat job (recon Gotcha #3).
    prev = None
    if fields["has_content_json"]:
        prev = _db.query_one(
            f"SELECT content_json, node_type FROM public.canvas_nodes "
            f"WHERE id = {_db._sql_literal(nid)}",
            container=container,
        )

    set_clauses = [f"content = {_db._sql_literal(fields['content'])}"]
    if fields["has_content_json"]:
        set_clauses.append("reformat_pending = true")
    sql = (
        "BEGIN; "
        "SELECT set_config('vibemind.sync_origin', 'fs', true); "
        f"UPDATE public.canvas_nodes SET {', '.join(set_clauses)} "
        f"WHERE id = {_db._sql_literal(nid)}; "
        "COMMIT;"
    )

    enqueue_sql = None
    if fields["has_content_json"] and prev is not None:
        target_format = prev.get("node_type") or fields["node_type"] or "note"
        prev_cj = json.dumps(prev.get("content_json"))
        enqueue_sql = (
            "INSERT INTO public.canvas_reformat_jobs "
            "(node_id, bubble_id, target_format, prev_content_json, content_hash) "
            f"VALUES ({_db._sql_literal(nid)}, {_db._sql_literal(fields.get('bubble_id'))}, "
            f"{_db._sql_literal(target_format)}, {_db._sql_literal(prev_cj)}::jsonb, "
            f"{_db._sql_literal(observed_hash)}) "
            "ON CONFLICT (node_id) WHERE status = 'pending' "
            "DO UPDATE SET enqueued_at = now(), content_hash = excluded.content_hash"
        )

    if DRY_RUN:
        print(f"[worker_b] DRY-RUN would apply (canvas):\n  {sql}", flush=True)
        if enqueue_sql:
            print(f"[worker_b] DRY-RUN would enqueue reformat:\n  {enqueue_sql}", flush=True)
        return True
    try:
        out = _db.execute_via_docker(sql, container=container)
        print(f"[worker_b] UPDATE canvas={nid} content[{len(fields['content'])}c]"
              f"{' +reformat_pending' if fields['has_content_json'] else ''} -> {out.strip()[:40]}",
              flush=True)
        if enqueue_sql:
            _db.execute_via_docker(enqueue_sql, container=container)
            print(f"[worker_b] enqueued reformat job node={nid} fmt={prev.get('node_type')}", flush=True)
        return True
    except Exception as e:
        print(f"[worker_b] UPDATE canvas={nid} ERROR: {e}", flush=True)
        return False


def _canvas_db_updated_at(canvas_node_id: str, container: str) -> str | None:
    """Read public.canvas_nodes.updated_at for conflict-LWW, via direct SQL.
    Returns the ISO string or None if the row is gone."""
    try:
        rows = _db.query_via_docker(
            f"SELECT updated_at FROM public.canvas_nodes WHERE id = {_db._sql_literal(canvas_node_id)}",
            container=container,
        )
        return rows[0]["updated_at"] if rows else None
    except Exception as e:
        print(f"[worker_b] _canvas_db_updated_at({canvas_node_id}) error: {e}", flush=True)
        return None


def _db_updated_at(idea_id: str, container: str) -> str | None:
    """Read public.ideas.updated_at for conflict-LWW, via direct SQL (NOT
    PostgREST, which lags the new column behind its schema cache). Returns the
    ISO string or None if the row is gone."""
    try:
        rows = _db.query_via_docker(
            f"SELECT updated_at FROM public.ideas WHERE id = {_db._sql_literal(idea_id)}",
            container=container,
        )
        return rows[0]["updated_at"] if rows else None
    except Exception as e:
        print(f"[worker_b] _db_updated_at({idea_id}) error: {e}", flush=True)
        return None


# ─── event handler ───────────────────────────────────────────────────────
def _handle_event(path: Path, kind: str, container: str, hash_store: dict) -> None:
    if path.suffix != ".md" or path.name.startswith("."):
        return

    if kind == "deleted":
        # SAFETY: never delete a bubble from a vanished file. DB is authoritative
        # for deletions; the app deletes bubbles, Worker A then removes the file.
        hash_store.pop(str(path), None)
        _save_hash_store(hash_store)
        print(f"[worker_b] file deleted (NOT propagated to DB by design): {path.name}", flush=True)
        return

    if kind not in ("created", "modified"):
        return
    if not path.exists():
        return  # race: deleted between event and read
    try:
        text = path.read_text(encoding="utf-8")
    except Exception as e:
        print(f"[worker_b] cannot read {path}: {e}", flush=True)
        return

    observed_hash = _content_hash(text)
    if observed_hash == hash_store.get(str(path)):
        return  # same content Worker A last wrote — own echo, ignore

    # ── Route by frontmatter: canvas .md (carries canvas_node_id) take the
    # canvas writeback path; everything else takes the idea path. ──
    fm = parse_frontmatter(text)
    is_canvas = bool(fm and fm.get("canvas_node_id"))

    if is_canvas:
        _handle_canvas_event(path, text, observed_hash, container, hash_store)
        return

    # Real user edit (idea). Parse + validate before applying.
    ok, fields, errors = parse_idea_md(text)
    if not ok:
        print(f"[worker_b] WARN unparseable/invalid, NOT applying: {path.name} errs={errors}",
              flush=True)
        # refresh hash so we don't re-warn on identical content
        hash_store[str(path)] = observed_hash
        _save_hash_store(hash_store)
        return

    # CATCH-ALL: a non-idea, non-canvas file (e.g. legacy canvas .md without a
    # canvas_node_id, or an overview) is READ-ONLY — DB authoritative.
    if fields.get("node_type") != "idea":
        print(f"[worker_b] non-idea/non-canvas node_type={fields.get('node_type')!r} READ-ONLY, "
              f"ignoring edit: {path.name}", flush=True)
        hash_store[str(path)] = observed_hash
        _save_hash_store(hash_store)
        return

    # CONFLICT (LWW): if the DB row changed AFTER Worker A last rendered this file
    # (file frontmatter last_synced_at), a concurrent app edit wins — DB is
    # authoritative for the rendered fields. Don't apply; Worker A re-renders.
    db_updated = _db_updated_at(fields["idea_id"], container)
    file_synced = fields.get("last_synced_at")
    if db_updated and file_synced and db_updated > file_synced:
        print(f"[worker_b] CONFLICT idea={fields['idea_id']} db_updated={db_updated} "
              f"> file_synced={file_synced} — DB wins, NOT applying (Worker A will re-render)",
              flush=True)
        hash_store[str(path)] = observed_hash
        _save_hash_store(hash_store)
        return

    if update_idea_in_db(fields, container):
        # store the new hash so the DB->FS re-render (Worker A) isn't re-applied
        hash_store[str(path)] = observed_hash
        _save_hash_store(hash_store)


def _handle_canvas_event(path: Path, text: str, observed_hash: str,
                         container: str, hash_store: dict) -> None:
    """Canvas .md writeback: parse, LWW-check, then write ONLY `content` back to
    public.canvas_nodes (and enqueue a reformat job for structured nodes). Title,
    node_type and content_json-direct are never written (read-only)."""
    ok, fields, errors = parse_canvas_md(text)
    if not ok:
        print(f"[worker_b] WARN canvas .md invalid, NOT applying: {path.name} errs={errors}",
              flush=True)
        hash_store[str(path)] = observed_hash
        _save_hash_store(hash_store)
        return

    # CONFLICT (LWW): DB wins if the canvas row changed after this file was rendered.
    db_updated = _canvas_db_updated_at(fields["canvas_node_id"], container)
    file_synced = fields.get("last_synced_at")
    if db_updated and file_synced and db_updated > file_synced:
        print(f"[worker_b] CONFLICT canvas={fields['canvas_node_id']} db_updated={db_updated} "
              f"> file_synced={file_synced} — DB wins, NOT applying (Worker A will re-render)",
              flush=True)
        hash_store[str(path)] = observed_hash
        _save_hash_store(hash_store)
        return

    if update_canvas_in_db(fields, container, observed_hash):
        hash_store[str(path)] = observed_hash
        _save_hash_store(hash_store)


# ─── watchdog mode (RECURSIVE — nested Projects/VibeMind - */*.md) ────────
if HAS_WATCHDOG:
    class BubbleVaultHandler(FileSystemEventHandler):
        def __init__(self, container: str, hash_store: dict):
            self.container = container
            self.hash_store = hash_store

        def on_deleted(self, event):
            if not event.is_directory:
                _handle_event(Path(event.src_path), "deleted", self.container, self.hash_store)

        def on_modified(self, event):
            if not event.is_directory:
                _handle_event(Path(event.src_path), "modified", self.container, self.hash_store)

        def on_created(self, event):
            if not event.is_directory:
                _handle_event(Path(event.src_path), "created", self.container, self.hash_store)


def _run_watchdog(container: str) -> None:
    if not HAS_WATCHDOG:
        raise RuntimeError("watchdog not installed — pip install watchdog")
    hash_store = _load_hash_store()
    VAULT_DIR.mkdir(parents=True, exist_ok=True)
    handler = BubbleVaultHandler(container, hash_store)
    observer = Observer()
    observer.schedule(handler, str(VAULT_DIR), recursive=True)  # nested vault
    observer.start()
    print(f"[worker_b] watching (recursive) {VAULT_DIR}", flush=True)
    try:
        while not _shutdown:
            time.sleep(1)
    finally:
        observer.stop()
        observer.join()


# ─── polling fallback (recursive glob) ───────────────────────────────────
def _run_polling(container: str) -> None:
    hash_store = _load_hash_store()
    VAULT_DIR.mkdir(parents=True, exist_ok=True)
    seen: dict[str, str] = {}
    for p in VAULT_DIR.rglob("*.md"):
        try:
            seen[str(p)] = _content_hash(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    print(f"[worker_b] polling interval={POLL_INTERVAL}s, recursive {VAULT_DIR}, "
          f"tracking {len(seen)} files", flush=True)
    while not _shutdown:
        time.sleep(POLL_INTERVAL)
        if _shutdown:
            break
        try:
            current = set()
            for p in VAULT_DIR.rglob("*.md"):
                sp = str(p)
                current.add(sp)
                try:
                    h = _content_hash(p.read_text(encoding="utf-8"))
                except Exception:
                    continue
                if sp not in seen:
                    _handle_event(p, "created", container, hash_store); seen[sp] = h
                elif h != seen[sp]:
                    _handle_event(p, "modified", container, hash_store); seen[sp] = h
            for sp in list(seen.keys()):
                if sp not in current:
                    _handle_event(Path(sp), "deleted", container, hash_store); del seen[sp]
        except Exception as e:
            print(f"[worker_b] poll loop error: {e}", flush=True)


def _main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    p = argparse.ArgumentParser(description="Bubble FS->DB sync worker")
    p.add_argument("--force-polling", action="store_true")
    args = p.parse_args()

    if not ENABLED:
        print("[worker_b] VIBEMIND_BUBBLE_SYNC_ENABLED not set — exiting (kill-switch).",
              flush=True)
        return 0
    container = _db.find_supabase_container()
    print(f"[worker_b] container={container[:12]} vault={VAULT_DIR} "
          f"watchdog={HAS_WATCHDOG} dry_run={DRY_RUN}", flush=True)
    if HAS_WATCHDOG and not args.force_polling:
        _run_watchdog(container)
    else:
        _run_polling(container)
    return 0


if __name__ == "__main__":
    sys.exit(_main())
