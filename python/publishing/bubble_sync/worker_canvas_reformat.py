"""Reformat drainer — regenerate canvas_nodes.content_json from FS-edited content.

Worker B writes a structured canvas node's edited prose to `content` and enqueues
a row in public.canvas_reformat_jobs. THIS daemon drains that queue, OUT of the
watchdog hot path, so the blocking LLM call never starves the file observer.

Per job:
  1. pick ONE debounced pending job (enqueued_at older than DEBOUNCE — so a node
     still being typed into is not formatted until the user pauses),
  2. claim it (status=running),
  3. read the node FRESH (latest committed content),
  4. generate_format_content(content, target_format) via the LLM (under a per-job
     timeout so a hung call can't wedge the drain),
  5. write content_json + format_schema + previous_content_json(=the ORIGINAL
     captured at enqueue, the undo source) + last_formatted + reformat_pending=false,
     GUC-FENCED via raw psql (NOT PostgREST — which can't carry the sync_origin GUC
     in-tx and would echo back to FS),
  6. mark the job done (or failed; on failure reformat_pending stays true so
     Worker A keeps rendering from `content` — no broken structure leaks to FS).

Loop safety: the fenced content_json write does not emit to the canvas outbox,
and Worker B ignores content_json (only writes `content`), so a regenerated
structure cannot re-trigger the FS->DB path. The loop is structurally broken.

Kill-switches:
  VIBEMIND_CANVAS_REFORMAT_ENABLED   (default off — worker exits unless '1')
  VIBEMIND_CANVAS_REFORMAT_DRY_RUN   (calls the LLM, logs result, writes NOTHING)
  CANVAS_REFORMAT_DEBOUNCE_SEC       (default 3)
  CANVAS_REFORMAT_TIMEOUT_SEC        (default 45 — per-job LLM wall-clock)

CLI:  python -m publishing.bubble_sync.worker_canvas_reformat
"""
from __future__ import annotations

import json
import os
import signal
import sys
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout

from . import _db
from .format_engine import generate_format_content, FormatError

ENABLED = os.environ.get("VIBEMIND_CANVAS_REFORMAT_ENABLED", "0") in ("1", "true", "True")
DRY_RUN = os.environ.get("VIBEMIND_CANVAS_REFORMAT_DRY_RUN", "0") in ("1", "true", "True")
DEBOUNCE_SEC = int(os.environ.get("CANVAS_REFORMAT_DEBOUNCE_SEC", "3"))
TIMEOUT_SEC = int(os.environ.get("CANVAS_REFORMAT_TIMEOUT_SEC", "45"))
POLL_SEC = int(os.environ.get("CANVAS_REFORMAT_POLL_SEC", "2"))
MAX_ATTEMPTS = 3

_shutdown = False
_pool = ThreadPoolExecutor(max_workers=1)


def _on_sigterm(signum, frame):
    global _shutdown
    _shutdown = True
    print("[reformat] received signal, will exit", flush=True)


signal.signal(signal.SIGINT, _on_sigterm)
signal.signal(signal.SIGTERM, _on_sigterm)


def _claim_one(container: str) -> dict | None:
    """Atomically pick + claim the oldest debounced pending job. Returns the job
    row, or None if none ready. The UPDATE...WHERE status='pending' guards against
    two drainers racing (only one wins the row)."""
    rows = _db.query_via_docker(
        "SELECT id, node_id, bubble_id, target_format, prev_content_json, attempts "
        "FROM public.canvas_reformat_jobs "
        f"WHERE status = 'pending' AND enqueued_at < now() - interval '{DEBOUNCE_SEC} seconds' "
        "ORDER BY enqueued_at LIMIT 1",
        container=container,
    )
    if not rows:
        return None
    job = rows[0]
    claimed = _db.execute_via_docker(
        "UPDATE public.canvas_reformat_jobs "
        "SET status = 'running', started_at = now(), attempts = attempts + 1 "
        f"WHERE id = {_db._sql_literal(job['id'])}::uuid AND status = 'pending' "
        "RETURNING id",
        container=container,
    )
    if not claimed.strip():
        return None  # lost the race
    return job


def _finish(container: str, job_id: str, status: str, error: str | None = None) -> None:
    set_err = f", last_error = {_db._sql_literal(error[:500])}" if error else ""
    _db.execute_via_docker(
        f"UPDATE public.canvas_reformat_jobs SET status = {_db._sql_literal(status)}, "
        f"finished_at = now(){set_err} WHERE id = {_db._sql_literal(job_id)}::uuid",
        container=container,
    )


def _process_job(job: dict, container: str) -> None:
    nid = job["node_id"]
    # Fresh read — always format the latest committed content, not a stale snapshot.
    node = _db.query_one(
        f"SELECT content, content_json, node_type, title FROM public.canvas_nodes "
        f"WHERE id = {_db._sql_literal(nid)}",
        container=container,
    )
    if not node:
        print(f"[reformat] node {nid} gone — marking job failed", flush=True)
        _finish(container, job["id"], "failed", "node not found")
        return

    target_format = job.get("target_format") or node.get("node_type") or "note"
    content = node.get("content") or ""
    title = node.get("title") or ""

    # LLM under a wall-clock timeout so a hung call can't wedge the drainer.
    try:
        fut = _pool.submit(generate_format_content, content, target_format, title)
        content_json, format_schema = fut.result(timeout=TIMEOUT_SEC)
    except FutureTimeout:
        attempts = int(job.get("attempts") or 0)
        status = "failed" if attempts >= MAX_ATTEMPTS else "pending"
        print(f"[reformat] node={nid} LLM TIMEOUT (attempt {attempts}) -> {status}", flush=True)
        # leave reformat_pending=true; re-queue by resetting to pending if under cap
        if status == "pending":
            _db.execute_via_docker(
                "UPDATE public.canvas_reformat_jobs SET status='pending', enqueued_at=now() "
                f"WHERE id = {_db._sql_literal(job['id'])}::uuid",
                container=container,
            )
        else:
            _finish(container, job["id"], "failed", "LLM timeout")
        return
    except (FormatError, Exception) as e:
        print(f"[reformat] node={nid} generate ERROR: {e}", flush=True)
        _finish(container, job["id"], "failed", str(e))
        return

    # previous_content_json = the ORIGINAL structure captured at enqueue (undo
    # source), NOT the edited plaintext — so the app's revert restores the last
    # good structured form (recon Gotcha #3).
    prev_cj = job.get("prev_content_json")

    write_sql = (
        "BEGIN; "
        "SELECT set_config('vibemind.sync_origin', 'fs', true); "
        "UPDATE public.canvas_nodes SET "
        f"content_json = {_db._sql_literal(json.dumps(content_json))}::jsonb, "
        f"format_schema = {_db._sql_literal(json.dumps(format_schema))}::jsonb, "
        f"previous_content_json = {_db._sql_literal(json.dumps(prev_cj))}::jsonb, "
        "last_formatted = now(), reformat_pending = false "
        f"WHERE id = {_db._sql_literal(nid)}; "
        "COMMIT;"
    )

    if DRY_RUN:
        print(f"[reformat] DRY-RUN node={nid} fmt={target_format} -> "
              f"content_json.type={content_json.get('type')} keys={list(content_json.keys())}; "
              f"NOT writing", flush=True)
        _finish(container, job["id"], "done")
        return

    try:
        _db.execute_via_docker(write_sql, container=container)
        print(f"[reformat] node={nid} reformatted as {target_format} "
              f"({len(content_json)} keys), reformat_pending cleared", flush=True)
        _finish(container, job["id"], "done")
    except Exception as e:
        print(f"[reformat] node={nid} WRITE ERROR: {e}", flush=True)
        _finish(container, job["id"], "failed", str(e))


def drain_forever(container: str) -> None:
    print(f"[reformat] draining (debounce={DEBOUNCE_SEC}s timeout={TIMEOUT_SEC}s "
          f"dry_run={DRY_RUN})", flush=True)
    while not _shutdown:
        try:
            job = _claim_one(container)
            if job:
                _process_job(job, container)
                continue  # immediately look for the next
        except Exception as e:
            print(f"[reformat] drain loop error: {e}", flush=True)
        for _ in range(POLL_SEC):
            if _shutdown:
                break
            time.sleep(1)


def _main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    if not ENABLED:
        print("[reformat] VIBEMIND_CANVAS_REFORMAT_ENABLED not set — exiting (kill-switch).",
              flush=True)
        return 0
    container = _db.find_supabase_container()
    print(f"[reformat] container={container[:12]}", flush=True)
    drain_forever(container)
    return 0


if __name__ == "__main__":
    sys.exit(_main())
