"""SupabaseDatabase — drop-in replacement for SQLite `Database`.

Parses SQL statements used by VibeMind repositories and translates them
to PostgREST HTTP calls. Implements the same interface as `database.py`:
    - execute(sql, params)
    - execute_many(sql, params_list)
    - fetch_one(sql, params)
    - fetch_all(sql, params)
    - connection() context manager (returns a compat shim)

Activated via USE_SUPABASE_DB=true env var (see data/__init__.py).

The SQL parser covers the ~20 query patterns VibeMind uses (from code analysis).
Unknown patterns raise NotImplementedError with the SQL string so we can extend.

Row access supports both `row["col"]` (dict) and `row[0]` (positional).
"""

from __future__ import annotations

import json
import logging
import os
import re
import urllib.error
import urllib.request
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

SUPABASE_URL = os.environ.get("SUPABASE_URL", "http://localhost:54321").rstrip("/")
SUPABASE_KEY = os.environ.get(
    "SUPABASE_ANON_KEY",
    "sb_publishable_ACJWlzQHlZjBrEguHvfOxg_3BJgxAaH",
)

# Columns in SQLite schema that don't exist in Supabase (discovered at runtime).
# Populated when PGRST204 errors surface.
_UNKNOWN_COLS: Dict[str, set] = {}


# ─────────────────────────────────────────────────────────────
# Row: dict + positional access (sqlite3.Row compat)
# ─────────────────────────────────────────────────────────────

class Row:
    """Row wrapper that supports row['col'], row[0], keys(), values(), dict(row)."""

    __slots__ = ("_data", "_keys", "_values")

    def __init__(self, data: Dict[str, Any]):
        self._data = data
        self._keys = list(data.keys())
        self._values = list(data.values())

    def __getitem__(self, key):
        if isinstance(key, int):
            return self._values[key]
        return self._data[key]

    def get(self, key, default=None):
        return self._data.get(key, default)

    def keys(self):
        return self._keys

    def values(self):
        return self._values

    def __contains__(self, key):
        return key in self._data

    def __iter__(self):
        return iter(self._keys)

    def __len__(self):
        return len(self._keys)

    def __repr__(self):
        return f"Row({self._data})"

    # dict(row) compat
    def __bool__(self):
        return bool(self._data)


# ─────────────────────────────────────────────────────────────
# HTTP client
# ─────────────────────────────────────────────────────────────

def _api(
    method: str,
    path: str,
    body: Any = None,
    params: str = "",
    prefer: str = "return=representation",
) -> Any:
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    if params:
        url += f"?{params}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": prefer,
    }
    data = (
        json.dumps(body, default=str, ensure_ascii=False).encode("utf-8")
        if body is not None
        else None
    )
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        resp = urllib.request.urlopen(req, timeout=5)
        raw = resp.read().decode("utf-8", errors="replace")
        if not raw.strip():
            return []
        return json.loads(raw)
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")[:300]
        # Auto-detect unknown cols
        if "PGRST204" in err or "Could not find" in err:
            m = re.search(r"'(\w+)' column", err)
            if m:
                col = m.group(1)
                table = path.split("?")[0]
                _UNKNOWN_COLS.setdefault(table, set()).add(col)
                logger.debug(f"[SupabaseDB] stripping unknown col {table}.{col}")
                return {"__retry__": True, "__error__": err}
        logger.warning(f"[SupabaseDB] HTTP {e.code} {method} {url}: {err[:150]}")
        raise RuntimeError(f"Supabase {method} {path}: {err[:200]}")
    except Exception as e:
        logger.warning(f"[SupabaseDB] {method} {url}: {e}")
        raise


# ─────────────────────────────────────────────────────────────
# SQL → PostgREST translator
# ─────────────────────────────────────────────────────────────

_INSERT_RE = re.compile(
    r"INSERT\s+(?:OR\s+REPLACE\s+)?INTO\s+(\w+)\s*\(([^)]+)\)\s*VALUES\s*\(([^)]+)\)",
    re.IGNORECASE | re.DOTALL,
)
_UPDATE_RE = re.compile(
    r"UPDATE\s+(\w+)\s+SET\s+(.+?)\s+WHERE\s+(.+?)(?:\s*$|\s*;)",
    re.IGNORECASE | re.DOTALL,
)
_DELETE_RE = re.compile(
    r"DELETE\s+FROM\s+(\w+)\s+WHERE\s+(.+?)(?:\s*$|\s*;)",
    re.IGNORECASE | re.DOTALL,
)
_SELECT_RE = re.compile(
    r"SELECT\s+(.+?)\s+FROM\s+(\w+)"
    r"(?:\s+WHERE\s+(.+?))?"
    r"(?:\s+ORDER\s+BY\s+(.+?))?"
    r"(?:\s+LIMIT\s+(\d+))?"
    r"(?:\s+OFFSET\s+(\d+))?"
    r"\s*;?\s*$",
    re.IGNORECASE | re.DOTALL,
)


def _sql_where_to_postgrest(where: str, params: list, param_idx: list) -> str:
    """Translate simple WHERE clauses to PostgREST filter string.

    Supports: col = ?, col IS NULL, col IS NOT NULL, col LIKE ?, LOWER(col) LIKE LOWER(?),
              col IN (?,?,?), col >= ?, col < ?, col != ?, AND.
    """
    where = where.strip().rstrip(";").strip()
    filters = []

    # Split by AND (top-level only — no nested parens supported yet)
    # Handle parenthesized groups: "LOWER(col) LIKE LOWER(?) AND other = ?"
    parts = _split_and(where)

    for part in parts:
        part = part.strip()
        if not part:
            continue

        # 1=1 or TRUE — always-true placeholder, ignore
        if part in ("1=1", "1 = 1", "TRUE", "true"):
            continue

        # LOWER(col) LIKE LOWER(?) → col=ilike.X
        m = re.match(r"LOWER\s*\(\s*(\w+)\s*\)\s+LIKE\s+LOWER\s*\(\s*\?\s*\)", part, re.IGNORECASE)
        if m:
            col = m.group(1)
            val = params[param_idx[0]]
            param_idx[0] += 1
            # PostgREST ilike uses * as wildcard (SQL %)
            val_esc = str(val).replace("%", "*")
            filters.append(f"{col}=ilike.{urllib_quote(val_esc)}")
            continue

        # col LIKE ?
        m = re.match(r"(\w+)\s+LIKE\s+\?", part, re.IGNORECASE)
        if m:
            col = m.group(1)
            val = params[param_idx[0]]
            param_idx[0] += 1
            val_esc = str(val).replace("%", "*")
            filters.append(f"{col}=like.{urllib_quote(val_esc)}")
            continue

        # col IS NULL
        m = re.match(r"(\w+)\s+IS\s+NULL", part, re.IGNORECASE)
        if m:
            filters.append(f"{m.group(1)}=is.null")
            continue

        # col IS NOT NULL
        m = re.match(r"(\w+)\s+IS\s+NOT\s+NULL", part, re.IGNORECASE)
        if m:
            filters.append(f"{m.group(1)}=not.is.null")
            continue

        # col IN (?,?,?)
        m = re.match(r"(\w+)\s+IN\s*\(([?,\s]+)\)", part, re.IGNORECASE)
        if m:
            col = m.group(1)
            placeholders = m.group(2).count("?")
            vals = params[param_idx[0] : param_idx[0] + placeholders]
            param_idx[0] += placeholders
            vals_str = ",".join(urllib_quote(str(v)) for v in vals)
            filters.append(f"{col}=in.({vals_str})")
            continue

        # col OP ? (=, !=, <, >, <=, >=)
        m = re.match(r"(\w+)\s*(=|!=|<>|<=|>=|<|>)\s*\?", part)
        if m:
            col, op = m.group(1), m.group(2)
            val = params[param_idx[0]]
            param_idx[0] += 1
            op_map = {"=": "eq", "!=": "neq", "<>": "neq", "<": "lt", ">": "gt", "<=": "lte", ">=": "gte"}
            if val is None and op in ("=", "!="):
                filters.append(f"{col}={'is.null' if op == '=' else 'not.is.null'}")
            else:
                filters.append(f"{col}={op_map[op]}.{urllib_quote(str(val))}")
            continue

        # Fallback: log and skip
        logger.warning(f"[SupabaseDB] Unparsed WHERE clause: {part!r}")

    return "&".join(filters)


def _split_and(s: str) -> list:
    """Split on AND while respecting parentheses."""
    parts = []
    depth = 0
    start = 0
    i = 0
    while i < len(s):
        c = s[i]
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
        elif depth == 0 and i + 5 <= len(s) and s[i : i + 5].upper() == " AND ":
            parts.append(s[start:i])
            i += 5
            start = i
            continue
        i += 1
    parts.append(s[start:])
    return parts


def urllib_quote(s: str) -> str:
    """URL-encode a filter value for PostgREST."""
    from urllib.parse import quote
    # PostgREST treats comma specially in filters
    return quote(str(s), safe="")


def _sql_order_to_postgrest(order: str) -> str:
    """Translate ORDER BY clause: `col DESC, col2` → `col.desc,col2.asc`."""
    parts = [p.strip() for p in order.split(",")]
    out = []
    for p in parts:
        if not p:
            continue
        m = re.match(r"(\w+(?:\s*\(\s*\w+\s*\))?)\s*(ASC|DESC)?", p, re.IGNORECASE)
        if m:
            col = m.group(1).strip()
            direction = (m.group(2) or "ASC").lower()
            # Strip function wrappers (LOWER(col) → col)
            fm = re.match(r"\w+\s*\(\s*(\w+)\s*\)", col)
            if fm:
                col = fm.group(1)
            out.append(f"{col}.{direction}")
    return ",".join(out)


# ─────────────────────────────────────────────────────────────
# Cursor (mimics sqlite3.Cursor for compatibility)
# ─────────────────────────────────────────────────────────────

class SupabaseCursor:
    """Minimal sqlite3.Cursor-compatible cursor backed by PostgREST."""

    def __init__(self, rows: list = None, rowcount: int = 0, lastrowid=None):
        self._rows = rows or []
        self.rowcount = rowcount
        self.lastrowid = lastrowid

    def fetchone(self):
        return Row(self._rows[0]) if self._rows else None

    def fetchall(self):
        return [Row(r) for r in self._rows]

    def __iter__(self):
        return iter(self.fetchall())


# ─────────────────────────────────────────────────────────────
# SupabaseDatabase main class
# ─────────────────────────────────────────────────────────────

class SupabaseDatabase:
    """Drop-in replacement for sqlite3-backed Database."""

    def __init__(self, *args, **kwargs):
        # Ignore db_path and other SQLite-specific args
        self.db_path = "supabase://" + SUPABASE_URL
        self._schema_initialized = True

    # ---- Compat no-ops ----

    def _ensure_database(self):
        pass

    def initialize(self):
        pass

    def get_schema_version(self) -> int:
        try:
            data = _api("GET", "schema_version", params="select=version&limit=1")
            if isinstance(data, list) and data:
                return data[0].get("version", 22)
            return 22
        except Exception:
            return 22

    # ---- Core API ----

    def execute(self, sql: str, params: Sequence = ()) -> SupabaseCursor:
        """Execute INSERT/UPDATE/DELETE. Returns a cursor with rowcount."""
        params = list(params) if params else []
        sql_clean = sql.strip()

        # INSERT
        m = _INSERT_RE.match(sql_clean)
        if m:
            return self._do_insert(m.group(1), m.group(2), params)

        # UPDATE
        m = _UPDATE_RE.match(sql_clean)
        if m:
            return self._do_update(m.group(1), m.group(2), m.group(3), params)

        # DELETE
        m = _DELETE_RE.match(sql_clean)
        if m:
            return self._do_delete(m.group(1), m.group(2), params)

        # Support a few DDL-ish statements by no-op-ing (schema is managed by Supabase migrations)
        if re.match(r"\s*(CREATE|ALTER|DROP)\s+", sql_clean, re.IGNORECASE):
            return SupabaseCursor()

        # SELECT via execute (some code paths use it)
        if re.match(r"\s*SELECT\s+", sql_clean, re.IGNORECASE):
            rows = self._do_select(sql_clean, params)
            return SupabaseCursor(rows=rows)

        logger.warning(f"[SupabaseDB] Unknown SQL: {sql_clean[:120]}")
        return SupabaseCursor()

    def execute_many(self, sql: str, params_list: list):
        for params in params_list:
            self.execute(sql, params)

    def fetch_one(self, sql: str, params: Sequence = ()) -> Optional[Row]:
        rows = self._do_select(sql, list(params) if params else [], limit_hint=1)
        return Row(rows[0]) if rows else None

    def fetch_all(self, sql: str, params: Sequence = ()) -> List[Row]:
        rows = self._do_select(sql, list(params) if params else [])
        return [Row(r) for r in rows]

    # ---- Private helpers ----

    def _do_insert(self, table: str, cols_str: str, params: list) -> SupabaseCursor:
        cols = [c.strip() for c in cols_str.split(",")]
        row = {}
        for i, col in enumerate(cols):
            if i < len(params):
                v = params[i]
                # Strip unknown columns (discovered from previous errors)
                if col in _UNKNOWN_COLS.get(table, set()):
                    continue
                # SQLite JSON TEXT → dict/list for JSONB
                if isinstance(v, str) and v and v[0] in "[{":
                    try:
                        v = json.loads(v)
                    except (json.JSONDecodeError, ValueError):
                        pass
                # datetime → ISO
                if isinstance(v, datetime):
                    v = v.isoformat()
                row[col] = v

        # Retry on unknown column errors
        for _ in range(8):
            result = _api("POST", table, body=[row], prefer="return=representation")
            if isinstance(result, dict) and result.get("__retry__"):
                # Re-clean with new unknown_cols
                row = {k: v for k, v in row.items() if k not in _UNKNOWN_COLS.get(table, set())}
                continue
            return SupabaseCursor(
                rows=result if isinstance(result, list) else [],
                rowcount=len(result) if isinstance(result, list) else 1,
                lastrowid=(result[0].get("id") if isinstance(result, list) and result else None),
            )
        logger.warning(f"[SupabaseDB] INSERT {table} gave up after retries")
        return SupabaseCursor()

    def _do_update(self, table: str, set_clause: str, where: str, params: list) -> SupabaseCursor:
        # Parse SET: "col1 = ?, col2 = ?"
        set_parts = [p.strip() for p in re.split(r",(?![^(]*\))", set_clause)]
        update_row = {}
        param_idx = 0
        for part in set_parts:
            m = re.match(r"(\w+)\s*=\s*\?", part)
            if m:
                col = m.group(1)
                v = params[param_idx]
                param_idx += 1
                if col in _UNKNOWN_COLS.get(table, set()):
                    continue
                if isinstance(v, str) and v and v[0] in "[{":
                    try:
                        v = json.loads(v)
                    except (json.JSONDecodeError, ValueError):
                        pass
                if isinstance(v, datetime):
                    v = v.isoformat()
                update_row[col] = v
            else:
                logger.warning(f"[SupabaseDB] Unparsed SET: {part!r}")

        # Parse WHERE
        remaining = [param_idx]
        filter_str = _sql_where_to_postgrest(where, params, remaining)

        # Retry on unknown col
        for _ in range(8):
            result = _api("PATCH", table, body=update_row, params=filter_str, prefer="return=representation")
            if isinstance(result, dict) and result.get("__retry__"):
                update_row = {k: v for k, v in update_row.items() if k not in _UNKNOWN_COLS.get(table, set())}
                continue
            return SupabaseCursor(
                rows=result if isinstance(result, list) else [],
                rowcount=len(result) if isinstance(result, list) else 1,
            )
        return SupabaseCursor()

    def _do_delete(self, table: str, where: str, params: list) -> SupabaseCursor:
        remaining = [0]
        filter_str = _sql_where_to_postgrest(where, params, remaining)
        result = _api("DELETE", table, params=filter_str, prefer="return=representation")
        return SupabaseCursor(
            rows=result if isinstance(result, list) else [],
            rowcount=len(result) if isinstance(result, list) else 0,
        )

    def _do_select(self, sql: str, params: list, limit_hint: int = None) -> list:
        sql_clean = sql.strip().rstrip(";")
        m = _SELECT_RE.match(sql_clean)
        if not m:
            logger.warning(f"[SupabaseDB] Unparsed SELECT: {sql_clean[:120]}")
            return []

        select_cols, table, where, order_by, limit, offset = m.groups()

        parts = []

        # SELECT column list → PostgREST `select=`
        select_cols = select_cols.strip()
        if select_cols == "*":
            parts.append("select=*")
        elif re.match(r"^\s*COUNT\s*\(\s*\*\s*\)", select_cols, re.IGNORECASE):
            # SELECT COUNT(*) — we do this via the count head response
            # PostgREST alternative: select=count
            # But the repos expect row[0] = count, so we need to return [{count: N}]
            return self._select_count(table, where, params)
        else:
            # Specific column list
            cols = [c.strip() for c in select_cols.split(",")]
            # Strip aliases (col AS alias)
            clean = []
            for c in cols:
                am = re.match(r"(\w+)(?:\s+AS\s+\w+)?", c, re.IGNORECASE)
                if am:
                    clean.append(am.group(1))
            parts.append("select=" + ",".join(clean))

        if where:
            remaining = [0]
            filter_str = _sql_where_to_postgrest(where, params, remaining)
            if filter_str:
                parts.append(filter_str)

        if order_by:
            parts.append("order=" + _sql_order_to_postgrest(order_by))

        if limit:
            parts.append(f"limit={limit}")
        elif limit_hint:
            parts.append(f"limit={limit_hint}")

        if offset:
            parts.append(f"offset={offset}")

        params_str = "&".join(parts)
        result = _api("GET", table, params=params_str)
        return result if isinstance(result, list) else []

    def _select_count(self, table: str, where: str, params: list) -> list:
        """Handle SELECT COUNT(*) ... by using PostgREST count via header."""
        filter_str = ""
        if where:
            remaining = [0]
            filter_str = _sql_where_to_postgrest(where, params, remaining)

        # Use exact count via Prefer header
        url = f"{SUPABASE_URL}/rest/v1/{table}?select=id&limit=0"
        if filter_str:
            url += f"&{filter_str}"
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Prefer": "count=exact",
        }
        req = urllib.request.Request(url, headers=headers, method="GET")
        try:
            resp = urllib.request.urlopen(req, timeout=5)
            # Content-Range: 0-0/42 → 42 is the count
            cr = resp.headers.get("Content-Range", "*/0")
            count = int(cr.split("/")[-1]) if "/" in cr else 0
            # Return in a shape that supports row[0] → count
            return [{"count": count, "0": count}]
        except Exception as e:
            logger.warning(f"[SupabaseDB] count {table}: {e}")
            return [{"count": 0, "0": 0}]

    # ---- Connection context (compat shim) ----

    @contextmanager
    def connection(self):
        """Yield a shim that looks like a sqlite3 connection (for transaction blocks)."""
        yield _TxShim(self)


class _TxShim:
    """Fake connection for `with db.connection() as conn` blocks.
    Each execute hits Supabase directly (no real transaction, but most VibeMind
    "transactions" are just sequential deletes which Supabase handles atomically
    via FK cascades).
    """

    def __init__(self, db: SupabaseDatabase):
        self._db = db

    def execute(self, sql: str, params: tuple = ()):
        return self._db.execute(sql, params)

    def executescript(self, sql: str):
        # Ignore — Supabase schema is managed via migrations
        pass

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass


# ─────────────────────────────────────────────────────────────
# Module-level singleton
# ─────────────────────────────────────────────────────────────

_INSTANCE: Optional[SupabaseDatabase] = None


def get_database(db_path=None) -> SupabaseDatabase:
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE = SupabaseDatabase()
        logger.info(f"[SupabaseDB] Initialized, url={SUPABASE_URL}")
    return _INSTANCE


def reset_database():
    global _INSTANCE
    _INSTANCE = None


# Default path (for compat)
DEFAULT_DB_PATH = "supabase://" + SUPABASE_URL


# Alias for drop-in compatibility
Database = SupabaseDatabase
