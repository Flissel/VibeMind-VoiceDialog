"""Thin DB access layer for the bubble-sync workers (originally verbatim from marketing).

Reaching supabase-db, selected at call time:

  A) REMOTE docker-exec over SSH: when SUPABASE_SSH_HOST is set, run
     `ssh <host> docker exec -i <SUPABASE_DB_CONTAINER> psql ...`. Since 2026-10-19 the mini-PC
     Supabase (offload-vm, container debian-supabase-db-1) is the only source of truth and the PC no
     longer runs vibemind_supabase-db; same mechanism as the marketing sync (spaces/marketing/sync/_db.py).
  B) LOCAL docker-exec: `docker exec` against the local container (SUPABASE_DB_CONTAINER, else the
     running vibemind_supabase-db). Active when SUPABASE_SSH_HOST is unset.

In both modes the SQL travels on stdin (`-f -`), never on a command line, and psql runs with
ON_ERROR_STOP so a failing statement raises instead of returning an empty result.

Both expose the same `query(sql, params) -> list[dict]` interface.
"""
from __future__ import annotations

import json
import os
import subprocess
from typing import Any


def find_supabase_container() -> str:
    """Name/ID of the supabase-db container to exec into (see module docstring for the modes)."""
    name = os.environ.get("SUPABASE_DB_CONTAINER", "").strip()
    if os.environ.get("SUPABASE_SSH_HOST", "").strip():
        if not name:
            raise RuntimeError("SUPABASE_SSH_HOST is set but SUPABASE_DB_CONTAINER is missing")
        return name
    if name:
        return name
    res = subprocess.run(
        ["docker", "ps", "-qf", "name=vibemind_supabase-db"],
        capture_output=True, text=True, encoding="utf-8", check=True,
    )
    cid = res.stdout.strip().split("\n")[0] if res.stdout.strip() else ""
    if not cid:
        raise RuntimeError("vibemind_supabase-db container not running")
    return cid


def _run_psql(sql: str, container: str) -> subprocess.CompletedProcess:
    """Run SQL through psql in the container, locally or over SSH; SQL goes on stdin."""
    inner = ["docker", "exec", "-i", container, "psql", "-U", "supabase_admin", "-d", "postgres",
             "-v", "ON_ERROR_STOP=1", "-tA", "-f", "-"]
    host = os.environ.get("SUPABASE_SSH_HOST", "").strip()
    # The fixed tokens contain no spaces, so joining them for the remote shell needs no quoting.
    argv = ["ssh", "-o", "BatchMode=yes", host, " ".join(inner)] if host else inner
    # encoding="utf-8" is REQUIRED: psql emits UTF-8, but text=True defaults to the Windows locale
    # codepage (cp1252) here -> mojibake (geprüft -> geprÃ¼ft) in non-ASCII content.
    return subprocess.run(argv, input=sql, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", check=False)


def query_via_docker(sql: str, params: dict | None = None, container: str | None = None) -> list[dict]:
    """Execute SQL via docker-exec psql, return rows as list[dict].

    Uses jsonb_agg + row_to_json to ship results as a single JSON array,
    avoiding shell parsing of psql tabular output.
    """
    if container is None:
        container = find_supabase_container()

    # Wrap the user SQL so psql returns a JSON array
    if params:
        # Use named-parameter substitution. Postgres doesn't support :name
        # directly, but psql's `\set` would require multiple statements.
        # We use prepared statements via a wrapper.
        keys = list(params.keys())
        placeholders = {k: f"${i+1}" for i, k in enumerate(keys)}
        # crude param-substitution: replace %(name)s with $1, $2, ...
        substituted_sql = sql
        for i, k in enumerate(keys):
            substituted_sql = substituted_sql.replace(f"%({k})s", f"${i+1}")
        # build PREPARE + EXECUTE
        types_unused = ["text"] * len(keys)  # supabase auto-casts; types_unused not used
        # Simpler: use a CTE wrapper with VALUES
        values_list = ", ".join(_sql_literal(params[k]) for k in keys)
        cte_cols = ", ".join(keys)
        # substitute %(k)s in original sql with p.k references via a CTE
        wrapped = sql
        for k in keys:
            wrapped = wrapped.replace(f"%({k})s", f"(SELECT {k} FROM _p)")
        full = f"WITH _p AS (SELECT {values_list} {('AS ' + cte_cols) if False else ''}) {wrapped}"
        # Actually CTE-with-named-columns is awkward; switch to a simpler
        # approach: build an inlined-SQL with safely-quoted params.
        full = sql
        for k in keys:
            full = full.replace(f"%({k})s", _sql_literal(params[k]))
    else:
        full = sql

    json_sql = (
        f"SELECT COALESCE(jsonb_agg(row_to_json(t)), '[]'::jsonb) AS rows FROM ({full}) t"
    )
    res = _run_psql(json_sql, container)
    if res.returncode != 0:
        raise RuntimeError(f"psql failed: {res.stderr.strip()[:500]}")
    out = res.stdout.strip()
    if not out:
        return []
    return json.loads(out)


def query_one(sql: str, params: dict | None = None, container: str | None = None) -> dict | None:
    rows = query_via_docker(sql, params, container)
    return rows[0] if rows else None


def execute_via_docker(sql: str, container: str | None = None) -> str:
    """Run a write/DDL statement, return stdout."""
    if container is None:
        container = find_supabase_container()
    res = _run_psql(sql, container)
    if res.returncode != 0:
        raise RuntimeError(f"psql exec failed: {res.stderr.strip()[:500]}")
    return res.stdout


def _sql_literal(value: Any) -> str:
    """Safely quote a value for direct SQL substitution.

    Only used for trusted query templates inside this file — not for
    user input. Conservative quoting.
    """
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return str(value)
    # string
    s = str(value).replace("'", "''")
    return f"'{s}'"
