"""Standalone launcher — runs Worker A (DB->FS) + Worker B (FS->DB) together.

Loads the repo .env into os.environ (skipping malformed var names like
GITHUB_PAT_VIBEMIND-LAB that bash can't export), forces the bubble-sync flags
on, then starts both workers as daemon threads in ONE process. This is the
"jetzt starten" path — the same wiring electron_backend._sync_to_rowboat uses,
but invokable directly so the workers run now without a backend restart.

The .env flags (VIBEMIND_BUBBLE_SYNC_ENABLED=1 / _DRY_RUN=1) already persist
this on the next backend start; this just brings it up immediately.

Usage:  python -m publishing.bubble_sync._run_both
        (Ctrl+C / SIGTERM stops both cleanly.)
"""
from __future__ import annotations

import os
import re
import sys
import threading
import time
from pathlib import Path

_VALID_ENV_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _load_dotenv(path: Path) -> int:
    """Minimal .env loader — KEY=VALUE lines, ignores comments/blank/malformed
    names. Does not overwrite vars already in the environment."""
    if not path.exists():
        return 0
    n = 0
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        if not _VALID_ENV_NAME.match(key):
            continue  # e.g. GITHUB_PAT_VIBEMIND-LAB — skip, never export
        val = val.strip().strip('"').strip("'")
        os.environ.setdefault(key, val)
        n += 1
    return n


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    # repo root = .../Vibemind_V1 ; .env lives there
    here = Path(__file__).resolve()
    repo_root = here.parents[5]  # bubble_sync/publishing/python/voice/vibemind-os/Vibemind_V1
    env_path = repo_root / ".env"
    loaded = _load_dotenv(env_path)
    # hard-force the sync flags on for this launcher (idempotent with .env)
    os.environ["VIBEMIND_BUBBLE_SYNC_ENABLED"] = os.environ.get(
        "VIBEMIND_BUBBLE_SYNC_ENABLED", "1") or "1"

    print(f"[run_both] loaded {loaded} env vars from {env_path}", flush=True)
    print(f"[run_both] ENABLED={os.environ.get('VIBEMIND_BUBBLE_SYNC_ENABLED')} "
          f"DRY_RUN={os.environ.get('VIBEMIND_BUBBLE_SYNC_DRY_RUN')}", flush=True)

    # import AFTER env is set (workers read flags at import time)
    sys.path.insert(0, str(here.parents[2]))  # .../voice/python
    from publishing.bubble_sync import _db
    from publishing.bubble_sync import worker_db_to_fs as wa
    from publishing.bubble_sync import worker_fs_to_db as wb

    if not wa.ENABLED:
        print("[run_both] ENABLED flag not picked up — abort", flush=True)
        return 1

    container = _db.find_supabase_container()
    print(f"[run_both] supabase container={container[:12]}", flush=True)

    def _run_a():
        try:
            wa.listen_forever(container)
        except Exception as e:
            print(f"[run_both] worker A crashed: {e}", flush=True)

    def _run_b():
        try:
            if wb.HAS_WATCHDOG:
                wb._run_watchdog(container)
            else:
                wb._run_polling(container)
        except Exception as e:
            print(f"[run_both] worker B crashed: {e}", flush=True)

    ta = threading.Thread(target=_run_a, name="worker-a", daemon=True)
    tb = threading.Thread(target=_run_b, name="worker-b", daemon=True)
    ta.start()
    tb.start()
    print("[run_both] both workers started; Ctrl+C to stop", flush=True)

    try:
        while ta.is_alive() or tb.is_alive():
            time.sleep(1)
    except KeyboardInterrupt:
        wa._shutdown = True
        wb._shutdown = True
        print("[run_both] shutdown requested", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
