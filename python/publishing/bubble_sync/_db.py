"""Thin DB access layer for the marketing sync workers.

We support two ways to reach supabase-db:
  1) DIRECT: via TCP to localhost — needs a SUPABASE_DB_URL env (Phase 2+,
     for the sync worker running on the host).
  2) DOCKER-EXEC: via `docker exec <container> psql ...` — works without
     direct postgres-port-exposure. Slower (process spawn per query) but
     zero extra setup.

For renderer testing (Phase 2) we use docker-exec — the sync worker
(Phase 4+) will prefer a long-lived psycopg connection.

Both expose the same `query(sql, params) -> list[dict]` interface.
"""
from __future__ import annotations

import json
import os
import subprocess
from typing import Any


def find_supabase_container() -> str:
    """Locate the running supabase-db container ID."""
    res = subprocess.run(
        ["docker", "ps", "-qf", "name=vibemind_supabase-db"],
        capture_output=True, text=True, encoding="utf-8", check=True,
    )
    cid = res.stdout.strip().split("\n")[0] if res.stdout.strip() else ""
    if not cid:
        raise RuntimeError("vibemind_supabase-db container not running")
    return cid


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
    cmd = ["docker", "exec", container, "psql", "-U", "supabase_admin", "-d", "postgres",
           "-tAc", json_sql]
    # encoding="utf-8" is REQUIRED: psql emits UTF-8, but text=True defaults to the
    # Windows locale codepage (cp1252) here → double-decode mojibake (geprüft→geprÃ¼ft)
    # in any non-ASCII content_json / description. (Verified: locale=cp1252.)
    res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", check=False)
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
    """Run a write/DDL statement via docker-exec, return stdout."""
    if container is None:
        container = find_supabase_container()
    res = subprocess.run(
        ["docker", "exec", container, "psql", "-U", "supabase_admin", "-d", "postgres", "-tAc", sql],
        capture_output=True, text=True, encoding="utf-8", check=False,
    )
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
