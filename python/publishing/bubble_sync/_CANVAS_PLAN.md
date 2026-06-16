This is the decisive architectural finding. The `supabase_database.Database.execute()` is **NOT a real SQL connection** — it parses SQL with regexes and translates to **PostgREST API calls** (`_api`, `_do_update`). It cannot run `set_config('vibemind.sync_origin','fs',true)` in the same transaction (PostgREST = one call = one tx; DDL is no-op'd at line 372-374). This confirms the recon gotcha: **the reformat drainer CANNOT use `canvas_repo.update_node()` for a GUC-fenced write** — it would echo through the trigger. The drainer must write the `content_json` via `_db.execute_via_docker()` raw psql with the GUC, exactly like Worker B.

I now have everything load-bearing verified. I'll write the build spec.

I have verified all load-bearing claims against the actual source. Here is the final build spec.

---

# Build Spec — Rowboat Canvas-Node `.md` Edits Sync Back to `public.canvas_nodes` (FULL scope, with async LLM re-format)

## 0. Verified ground-truth corrections to the recon (read first — they change the design)

These were checked against source and **override** two assumptions implicit in the recon:

1. **`canvas_repo.update_node()` does NOT do a real SQL write.** `CanvasRepository` is constructed with `get_database()` → `supabase_database.Database` (`canvas_repository.py:6,17`). Its `.execute()` (`supabase_database.py:352-382`) **regex-parses the SQL and dispatches to PostgREST** (`_do_update`), and **no-ops all DDL** (`supabase_database.py:372-374`). Consequence: it is **one PostgREST call = one transaction**, so it **cannot** carry `SELECT set_config('vibemind.sync_origin','fs',true)` in the same tx. **Therefore `convert_format()`/`update_node()` are unusable for any fenced writeback** — they would trip the AFTER trigger and echo back to FS. Every fenced write (Worker B content write AND the reformat drainer's `content_json` write) MUST go through `_db.execute_via_docker()` raw psql (`_db.py:92-102`), exactly like Worker B's `update_idea_in_db` (`worker_fs_to_db.py:100-130`).

2. **`convert_format()` cannot be reused even with side-effects suppressed**, for the reason above plus its hardcoded `source_content` fallback (`format_dispatcher.py:870`) and its inline Electron/NotificationQueue calls (`:906`, `:909-918`). We reuse only the **pure parts**: the `FORMAT_AGENTS` registry (`:745-764`), `get_format_schema()` (`:899`), and the validation+note-fallback block (`:880-892`). A new headless function wraps these.

Everything else in the recon (outbox/trigger/GUC templates, worker patterns, detached-spawn pattern, `_record_folder_hashes` echo coverage) is confirmed accurate.

---

## 1. Architecture decision — re-format MUST be decoupled from the watchdog hot path

**Mechanism: a DB-backed reformat-jobs queue table + a dedicated debounced drainer daemon.** Chosen over a file-queue because (a) the canvas sync already runs entirely over docker-exec psql, so a table reuses the same transport with zero new infra; (b) it survives restarts (file-queue in a temp dir does not); (c) it lets us coalesce by `node_id` in SQL.

**Why decouple (grounded):** the recon's core gotcha — *"Do NOT run LLM re-format synchronously inside watchdog on_modified: the event handler blocks if the callback takes >500ms, starving the observer thread"* — and Worker B's handler is exactly such a synchronous watchdog callback (`worker_fs_to_db.py:224-226`). The LLM call is a blocking network call with 3× exponential-backoff retry (`format_dispatcher.py:44-77`, `max_tokens=3000`, `temperature=0.3`). Running it in `on_modified` would freeze the observer for seconds per edit.

**Dispatch pattern:** Worker B, after the content write, does **not** spawn a detached process per edit. Instead it INSERTs a row into `public.canvas_reformat_jobs` (cheap, fenced is not required — see below). A **separate long-lived daemon** (`worker_canvas_reformat.py`) drains that table. This mirrors the recon's preferred solution verbatim: *"enqueue job to outbox, drainer thread pulls + runs LLM, writes result back."* The daemon is launched as a `threading.Thread(daemon=True)` from `electron_backend.py` alongside Worker A/B (`electron_backend.py:537-541` pattern), **and** can be run standalone via `python -m publishing.bubble_sync.worker_canvas_reformat` for dry-run testing — same dual-mode as the existing workers.

(The detached-subprocess pattern from `openclaw_brain_dispatch_mcp.py:139-169` / `openfang_som_execute_wrapper.py:89-99` is the fallback if we ever need per-job isolation, but a single drainer thread with a wall-clock guard is simpler and matches how the bubble workers already run. We adopt the **hard self-kill timer idea** — `openclaw_brain_dispatch_worker.py:45-51` — but applied per-job: each LLM call runs under a `concurrent.futures` timeout, not `os._exit`, so one hung job can't wedge the drainer.)

**Debounce / coalescing (N rapid 500ms saves → 1 reformat):**
- The jobs table has a partial unique-ish dedup: before INSERT, Worker B runs `INSERT ... ON CONFLICT (node_id) WHERE status='pending' DO UPDATE SET enqueued_at = now(), content_hash = excluded.content_hash`. So rapid re-saves of the same node collapse onto **one pending row** with the latest hash.
- The drainer applies a **debounce window** `CANVAS_REFORMAT_DEBOUNCE_SEC` (default 3s): it only picks a pending job whose `enqueued_at < now() - debounce`. A node still being hammered with saves keeps bumping `enqueued_at`, so it's not picked until the user pauses ≥3s. This is the table analogue of the recon's "no 500ms debounce at watchdog level" warning — we debounce at the drainer, not the observer.
- The drainer reads the node **fresh** at execution time (`canvas_repo.get_node` / direct SELECT), so it always formats the latest committed `content`, never a stale enqueued snapshot.

**previous_content_json so undo survives (the trickiest part — recon Gotcha #3/#4):**
The danger: `convert_format` sets `previous_content_json = source_content` where `source_content` is the *current* `content_json` (`format_dispatcher.py:895`). But in our flow, by the time the reformat runs, the user has edited the **content** field; the **original structured `content_json` must be captured BEFORE Worker B touches the row.** Therefore:
- **Worker B**, at the moment it writes the edited `content`, also copies the node's existing `content_json` into the jobs row: `prev_content_json` column = the node's `content_json` as it was *before* this edit (read in the same handler, before the UPDATE). This is the "store node.content_json BEFORE worker modifies content field" instruction (recon Gotcha #3).
- **The drainer**, after the LLM produces `new_content`, writes `previous_content_json = jobs.prev_content_json` (the captured original), **not** the edited plaintext, **not** `source_content`. So "revert" restores the last good structured form. The schema undo limitation (recon Gotcha #5 — `format_schema` overwrite, no schema-undo) is accepted as-is; it matches existing behavior.

**Suppressing `_send_format_update_to_electron` / `NotificationQueue` in headless mode:**
We do **not** call `convert_format()` at all, so neither side-effect fires. The new headless function (`apply_format_to_node_headless`, §7) calls only the pure agent + validate + the raw-psql write. As belt-and-suspenders, gate any optional notify behind `CANVAS_REFORMAT_HEADLESS=1` (default on in the drainer) and wrap the NotificationQueue import in try/except per recon Gotcha #6 (`from swarm.orchestrator.notification_queue import ...` raises `ImportError` outside swarm context). The Electron stdout IPC (`format_dispatcher.py:927-942`) is simply never invoked.

---

## 2. The `content_json`-staleness coupling & the flicker window

**Sequence of states for a structured (content_json-set) node edit:**

| t | `content` | `content_json` | reformat_status | What Worker A would render |
|---|-----------|----------------|-----------------|----------------------------|
| t0 (before edit) | old text | structured (valid) | n/a | flattened structured |
| t1 (Worker B writes content, fenced) | **new edited text** | **still old structured (stale)** | `pending` | ⚠ flatten of STALE content_json |
| t2 (drainer runs LLM, fenced write) | new edited text | **new structured (regenerated)** | `done` | flatten of NEW content_json |

**The flicker problem:** between t1 and t2, `content_json` is stale. If anything triggered a DB→FS re-render in that window, Worker A's canvas renderer (which prefers `content_json` over `content` — `ideas_publisher.py:99-116`, `_flatten_content_json`) would re-emit the *pre-edit* structured body, momentarily reverting the user's visible edit on disk = flicker.

**Why it does NOT normally fire, and the guard anyway:**
- Worker B's content write is **GUC-fenced** (`sync_origin='fs'`), so the AFTER trigger skips the outbox emit (`triggers.sql:48-83`). So t1's write does **not** enqueue a DB→FS render. Good — no flicker source from the edit itself.
- But a *concurrent* DB-side change to the same node in the t1–t2 window (e.g. the app moves the node, or the drainer's own t2 write) emits to the canvas outbox and Worker A re-renders. The drainer's t2 write is also GUC-fenced, so it does not self-emit. A genuine concurrent app edit is the only real trigger — and that's the LWW conflict case we already handle.

**The `reformat_pending` marker (define it — needed):** add a column `canvas_nodes.reformat_pending boolean DEFAULT false`. Worker B sets it `true` in the **same fenced UPDATE** that writes `content` (for structured nodes only). The drainer clears it `false` in its fenced UPDATE at t2. **Worker A's `render_canvas_note` (§5) checks this flag: if `reformat_pending` is true, it renders from `content` (the fresh edited text) and SKIPS `_flatten_content_json`** — so even if a re-render is forced in the window, it shows the user's edited text, not the stale structure. No flicker. Once the drainer clears the flag, the next render uses the regenerated `content_json`. (Setting `reformat_pending` in the fenced write does not self-emit, so it doesn't cause its own render.)

This is the minimal correct intermediate-state contract: **`reformat_pending=true` means "content is authoritative, content_json is stale, render from content."**

---

## 3. Frontmatter design (canvas `.md`)

Confirmed enablers: Tiptap preserves frontmatter across split/join (given); `parse_frontmatter` already reads arbitrary keys (`worker_fs_to_db.py:42`). We extend the closed `SCHEMA_GROUPS` (`_frontmatter.py:24-28`) with a **canvas group** and **bump `SYNC_VERSION` 1→2** (recon: schema is CLOSED, bump on change).

New `SCHEMA_GROUPS` entry (added alongside existing `sync-meta`/`idea`):
```
("canvas", ["canvas_node_id", "has_content_json"]),
```
Full canvas-`.md` frontmatter fields:
- `idea_id` — **reused as the bubble id** (= `linked_idea_id`). Keeping the key name `idea_id` means Worker A/B's existing `bubble_id` grouping (`worker_db_to_fs.py:116`) and `_db_updated_at` keying need no rename; for canvas rows it carries the bubble. *(Document this overload clearly in code comments.)*
- `canvas_node_id` — the real `public.canvas_nodes.id`; **this is the row Worker B writes back to.**
- `node_type` — the canvas node_type (`note`, `swot`, `flowchart`, …). **READ-ONLY** on writeback. It is the discriminator Worker B uses to know this is a canvas file (`node_type != 'idea'`), replacing the old "ignore it" guard.
- `title` — **READ-ONLY** on writeback (user decision). Rendered for display only; Worker B never writes it.
- `has_content_json` — boolean. **The marker that selects Worker B's path:** `false` → 147 plain nodes → direct-content write only; `true` → 92 structured nodes → content write + enqueue reformat. (Recon: "keep a content_json-presence marker so Worker B knows whether to take the direct-content path or the content+reformat path.")
- `last_synced_at` — drives LWW (same role as ideas, `worker_fs_to_db.py:197-205`).
- `content_hash` — body hash, same as ideas.

No `writeback`/read-only flag is needed (all nodes writable, per decision). `title`/`node_type`/`content_json`-direct read-only-ness is enforced in code (Worker B only ever writes `content`), not via frontmatter.

---

## 4. DB plumbing — migration DDL skeletons (forked from the ideas templates)

Three migrations, named to sort after the ideas ones. All grounded in `20260610_ideas_sync_*.sql`.

### 4a. `20260611_canvas_sync_columns.sql` — fork of `20260610_ideas_sync_columns.sql:22-59`
```sql
BEGIN;

ALTER TABLE public.canvas_nodes
    ADD COLUMN IF NOT EXISTS updated_at       timestamptz DEFAULT now(),
    ADD COLUMN IF NOT EXISTS last_synced_at   timestamptz,
    ADD COLUMN IF NOT EXISTS reformat_pending boolean DEFAULT false;

UPDATE public.canvas_nodes
    SET updated_at = COALESCE(updated_at, last_formatted, now())
    WHERE updated_at IS NULL;

CREATE OR REPLACE FUNCTION public.canvas_touch_updated_at() RETURNS trigger AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_canvas_touch_updated_at ON public.canvas_nodes;
CREATE TRIGGER trg_canvas_touch_updated_at
    BEFORE UPDATE ON public.canvas_nodes
    FOR EACH ROW EXECUTE FUNCTION public.canvas_touch_updated_at();

COMMIT;
```
(REPLICA IDENTITY FULL already set — given. No need to re-issue.)

### 4b. `20260611_canvas_sync_triggers.sql` — fork of `20260610_ideas_sync_triggers.sql:26-103`
```sql
BEGIN;

-- Outbox (identical shape to ideas_sync_outbox)
CREATE TABLE IF NOT EXISTS public.canvas_sync_outbox (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    node_id     text NOT NULL,                 -- public.canvas_nodes.id
    bubble_id   text,                           -- = linked_idea_id
    operation   text NOT NULL CHECK (operation IN ('INSERT','UPDATE','DELETE')),
    payload     jsonb NOT NULL,
    origin      text NOT NULL DEFAULT 'db',
    emitted_at  timestamptz DEFAULT now(),
    applied_at  timestamptz
);
CREATE INDEX IF NOT EXISTS idx_canvas_outbox_unapplied ON public.canvas_sync_outbox(emitted_at)
    WHERE applied_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_canvas_outbox_node ON public.canvas_sync_outbox(node_id);

CREATE OR REPLACE FUNCTION public.emit_canvas_sync_event() RETURNS trigger AS $$
DECLARE
    origin_tag   text;
    payload_json jsonb;
    v_node_id    text;
    v_bubble_id  text;
BEGIN
    BEGIN
        origin_tag := current_setting('vibemind.sync_origin', true);
    EXCEPTION WHEN OTHERS THEN
        origin_tag := NULL;
    END;
    IF origin_tag = 'fs' THEN                  -- loop prevention (FS-applied write)
        RETURN COALESCE(NEW, OLD);
    END IF;

    IF TG_OP = 'DELETE' THEN
        payload_json := to_jsonb(OLD);
    ELSE
        payload_json := to_jsonb(NEW);
    END IF;

    v_bubble_id := payload_json->>'linked_idea_id';
    -- SCOPE: nodes with linked_idea_id NULL are NOT published (out of scope).
    IF v_bubble_id IS NULL THEN
        RETURN COALESCE(NEW, OLD);
    END IF;

    v_node_id := payload_json->>'id';
    INSERT INTO public.canvas_sync_outbox
        (node_id, bubble_id, operation, payload, origin)
    VALUES (v_node_id, v_bubble_id, TG_OP, payload_json, 'db');

    PERFORM pg_notify('vibemind_canvas_sync', '');
    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_emit_canvas_sync ON public.canvas_nodes;
CREATE TRIGGER trg_emit_canvas_sync
    AFTER INSERT OR UPDATE OR DELETE ON public.canvas_nodes
    FOR EACH ROW EXECUTE FUNCTION public.emit_canvas_sync_event();

CREATE OR REPLACE FUNCTION public.mark_canvas_outbox_applied(p_ids uuid[])
RETURNS integer AS $$
DECLARE n integer;
BEGIN
    UPDATE public.canvas_sync_outbox SET applied_at = now()
    WHERE id = ANY(p_ids) AND applied_at IS NULL;
    GET DIAGNOSTICS n = ROW_COUNT;
    RETURN n;
END;
$$ LANGUAGE plpgsql;

COMMIT;
```
**Double-fire note (see Risk §9):** `reformat_pending` and `updated_at` are columns ON `canvas_nodes`, so the drainer's fenced write touches the same table — but it's GUC-fenced, so no self-emit. The BEFORE-touch trigger bumps `updated_at` even on FS writes (harmless, same rationale as ideas columns migration comment).

### 4c. `20260611_canvas_reformat_jobs.sql` — new (no ideas analogue)
```sql
BEGIN;

CREATE TABLE IF NOT EXISTS public.canvas_reformat_jobs (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    node_id           text NOT NULL,
    bubble_id         text,
    target_format     text NOT NULL,            -- node_type at enqueue time
    prev_content_json jsonb,                    -- ORIGINAL content_json, captured BEFORE edit (undo source)
    content_hash      text,                     -- hash of the edited content that triggered this
    status            text NOT NULL DEFAULT 'pending'
                          CHECK (status IN ('pending','running','done','failed')),
    attempts          int NOT NULL DEFAULT 0,
    last_error        text,
    enqueued_at       timestamptz DEFAULT now(),
    started_at        timestamptz,
    finished_at       timestamptz
);
-- one live pending job per node (debounce/coalesce key)
CREATE UNIQUE INDEX IF NOT EXISTS uq_canvas_reformat_pending
    ON public.canvas_reformat_jobs(node_id) WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS idx_canvas_reformat_pickable
    ON public.canvas_reformat_jobs(enqueued_at) WHERE status = 'pending';

COMMIT;
```

---

## 5. Worker A changes (`worker_db_to_fs.py`)

1. **Merge canvas outbox into the drain.** Extend `drain_outbox` (`worker_db_to_fs.py:100-141`) — or add a parallel `drain_canvas_outbox` called in the same loop iteration — to also `SELECT id, node_id, bubble_id, operation FROM public.canvas_sync_outbox WHERE applied_at IS NULL ORDER BY emitted_at LIMIT {BATCH}`, collapse to unique `bubble_id`, and call the existing `pub.publish_bubble(bubble_id)` once per bubble. **Per recon: `publish_bubble` already renders BOTH ideas and canvas nodes** (`ideas_publisher.py:86-116`) and `_record_folder_hashes` (`worker_db_to_fs.py:143-160`) already hashes every `.md` including canvas — so echo protection is free (given fact). Mark applied via the new `mark_canvas_outbox_applied`.
2. **LISTEN the canvas channel.** Where `listen_forever` (`:142-160`) polls, also drive on `vibemind_canvas_sync` NOTIFY (or just poll both outboxes every `POLL_FALLBACK_SEC` — the existing loop already polls; cheapest is to call both drains in the loop body).
3. **`render_canvas_note`** — a new renderer (forked from `render_md.render_idea_note`, `render_md.py:54-106`). `publish_bubble` currently renders canvas nodes through `ideas_publisher.py:99-116`. Update that path so each canvas node's `.md` gets the canvas frontmatter (§3): emit `canvas_node_id`, `node_type`, `has_content_json` (= `bool(node.content_json)`), `idea_id=linked_idea_id`, plus `last_synced_at`/`content_hash`. **Flicker guard:** when building the body, `if node.reformat_pending: body = node.content` (skip `_flatten_content_json`); else keep the existing structured-flatten (`ideas_publisher.py:101-110`). Bump `sync_version` to 2.

---

## 6. Worker B changes (`worker_fs_to_db.py`)

Replace the blanket read-only guard (`worker_fs_to_db.py:187-192`) with canvas-aware handling:

1. **`parse_canvas_md`** (new, in `validate.py`, forked from `parse_idea_md` `validate.py:38-75`): when frontmatter has `canvas_node_id`, extract `{canvas_node_id, bubble_id(=idea_id), node_type, has_content_json, content(=body via _body_description), last_synced_at}`. **Never extract `title`** (read-only). Reject if no `canvas_node_id`.
2. **Dispatch in `_handle_event`:** after `parse_frontmatter`, branch on presence of `canvas_node_id`:
   - has `canvas_node_id` → canvas path (below).
   - else → existing idea path unchanged.
   The old `node_type != 'idea' → READ-ONLY skip` block is **removed** for canvas files (it stays only as the final catch-all for files that are neither idea nor canvas).
3. **LWW for canvas** — fork `_db_updated_at` into `_canvas_db_updated_at(canvas_node_id)` querying `public.canvas_nodes.updated_at` via `_db.query_via_docker` (now that the column exists, §4a). Same compare as `worker_fs_to_db.py:197-205`: if `db_updated > file_synced` → DB wins, skip.
4. **`update_canvas_in_db`** (new, forked from `update_idea_in_db` `worker_fs_to_db.py:100-130`) — writes **ONLY `content`** (NOT title, NOT node_type, NOT content_json), GUC-fenced in one psql tx:
```python
sql = ("BEGIN; "
       "SELECT set_config('vibemind.sync_origin','fs',true); "
       f"UPDATE public.canvas_nodes SET content = {_db._sql_literal(fields['content'])}"
       + (", reformat_pending = true" if fields['has_content_json'] else "")
       + f" WHERE id = {_db._sql_literal(fields['canvas_node_id'])}; "
       "COMMIT;")
```
   - **Plain nodes (`has_content_json=false`, the 147):** content-only write. Done.
   - **Structured nodes (`has_content_json=true`, the 92):** same write **plus** `reformat_pending=true`, then **enqueue a reformat job** with the captured original `content_json`:
```python
# read the node's CURRENT content_json BEFORE we relied on the edit (it's still the pre-edit structure
# because Worker B only wrote `content`): capture it for the undo chain.
prev_cj = _db.query_one(
    f"SELECT content_json, node_type FROM public.canvas_nodes WHERE id = {_db._sql_literal(nid)}")
enqueue_sql = (
    "INSERT INTO public.canvas_reformat_jobs (node_id, bubble_id, target_format, prev_content_json, content_hash) "
    f"VALUES ({_db._sql_literal(nid)}, {_db._sql_literal(bubble_id)}, "
    f"{_db._sql_literal(prev_cj['node_type'])}, "
    f"{_db._sql_literal(json.dumps(prev_cj['content_json']))}::jsonb, {_db._sql_literal(observed_hash)}) "
    "ON CONFLICT (node_id) WHERE status='pending' "
    "DO UPDATE SET enqueued_at = now(), content_hash = excluded.content_hash;")
```
   *(Capture `prev_content_json` from the row read **before** the content UPDATE in the handler — recon Gotcha #3. The enqueue is NOT fenced; the jobs table has no sync trigger.)*
5. Update hash store on every applied/skipped path exactly as the idea path does (`worker_fs_to_db.py:208-210`).

---

## 7. Reformat drainer (`worker_canvas_reformat.py` — new)

Lives in `vibemind-os/voice/python/publishing/bubble_sync/`. Dual-mode (thread from `electron_backend` + standalone CLI), same skeleton as Worker B (signal handlers, `ENABLED`/`DRY_RUN` env gates `worker_fs_to_db.py:62-75`).

**New headless formatter — add to `format_dispatcher.py`:**
```python
def apply_format_to_node_headless(node_id, target_format, source_text, prev_content_json):
    """Worker-safe re-format. NO electron/notification side-effects, NO content_json fallback.
    Reuses FORMAT_AGENTS + validation + note-fallback from convert_format, but:
      - source is FORCED to the edited plaintext (recon Gotcha #2),
      - returns (new_content, format_schema) — caller does the fenced DB write."""
    agent = FORMAT_AGENTS.get(target_format) or FORMAT_AGENTS["note"]
    source_content = {"type": "note", "text": source_text or ""}     # FORCE edited content
    new_content = agent(source_content, "")                           # title read-only -> ""
    is_valid, err = validate_format_schema(new_content, target_format)  # :880-892
    if not is_valid:
        new_content = FORMAT_AGENTS["note"](source_content, "")       # note fallback
        target_format = "note"
    return new_content, get_format_schema(target_format)              # :899
```
This forks the pure core of `convert_format` (`:872-899`) and **drops** lines `:906`/`:909-918` (Electron + NotificationQueue) and the `:870` stale-`content_json` fallback. Per recon Gotcha #7, the `FORMAT_AGENTS` functions are **sync/blocking**, so the drainer runs them on its own thread (not inside any async loop) under a `concurrent.futures.ThreadPoolExecutor` with a per-job timeout (e.g. 45s) so a hung LLM can't wedge the drain.

**Drainer loop:**
```
while not _shutdown:
    sleep(min(POLL_FALLBACK_SEC, 2))
    # pick ONE debounced pending job, claim it atomically (running)
    job = SELECT ... FROM canvas_reformat_jobs
          WHERE status='pending' AND enqueued_at < now() - interval 'DEBOUNCE s'
          ORDER BY enqueued_at LIMIT 1;
    if not job: continue
    UPDATE ... SET status='running', started_at=now(), attempts=attempts+1 WHERE id=job.id AND status='pending';  # claim
    node = SELECT content, content_json, node_type FROM canvas_nodes WHERE id=job.node_id;  # FRESH read
    new_content, schema = apply_format_to_node_headless(job.node_id, job.target_format, node.content, job.prev_content_json)
    if DRY_RUN:
        print(f"[reformat] DRY-RUN would format node={job.node_id} as {job.target_format}; "
              f"LLM produced type={new_content.get('type')}; NOT writing"); 
        # in dry-run we DO call the LLM (to verify it works) but skip the write — see Phase E
        mark job done(dry); continue
    # FENCED write via raw psql — NOT canvas_repo.update_node (PostgREST can't fence)
    sql = ("BEGIN; SELECT set_config('vibemind.sync_origin','fs',true); "
           f"UPDATE public.canvas_nodes SET content_json={lit(json.dumps(new_content))}::jsonb, "
           f"format_schema={lit(json.dumps(schema))}::jsonb, "
           f"previous_content_json={lit(json.dumps(job.prev_content_json))}::jsonb, "  # undo = ORIGINAL, recon G#3/4
           f"last_formatted=now(), reformat_pending=false "
           f"WHERE id={lit(job.node_id)}; COMMIT;")
    _db.execute_via_docker(sql)
    mark job done
```
- **Fenced write** ⇒ no echo to FS (the regenerated `content_json` is the DB's truth; Worker A would render it on the *next* genuine DB change). Clearing `reformat_pending=false` ends the flicker window (§2).
- **`previous_content_json = job.prev_content_json`** (the captured original) ⇒ "revert" works correctly even though content was edited via FS.
- **Failure** (`format_idea_content`/agent raises after retries `:44-77`): set `status='failed'`, `last_error`, leave `reformat_pending=true` so Worker A keeps rendering from `content` (no broken structure leaks to FS). Note-fallback inside the headless fn already covers validation failures (recon: "validation fallback to note").
- Headless side-effects off by construction (no Electron, no NotificationQueue).
- Model/provider via `get_model("format_dispatcher")` (`llm_config.py:166-195`) — unchanged.

---

## 8. Phased build plan A–F (each with dry-run/live verification mirroring ideas-sync)

**Phase A — DB plumbing.** Apply 4a/4b/4c migrations.
*Verify (fence smoke-test, mirrors the GUC smoke test in `20260610_ideas_sync_triggers.sql`):*
```sql
-- (1) normal UPDATE emits:
UPDATE public.canvas_nodes SET content='x' WHERE id='<node>'; 
SELECT count(*) FROM public.canvas_sync_outbox WHERE node_id='<node>' AND applied_at IS NULL; -- expect 1
-- (2) fenced UPDATE does NOT emit:
BEGIN; SELECT set_config('vibemind.sync_origin','fs',true); UPDATE public.canvas_nodes SET content='y' WHERE id='<node>'; COMMIT;
SELECT count(*) ...; -- expect still 1 (no new row)
-- (3) NULL linked_idea_id is skipped:
UPDATE public.canvas_nodes SET content='z' WHERE id='<orphan-node-with-null-linked_idea_id>';
SELECT count(*) FROM canvas_sync_outbox WHERE node_id='<orphan>'; -- expect 0
```

**Phase B — Worker A canvas render (DB→FS).** Add `render_canvas_note` + canvas frontmatter + outbox drain.
*Verify:* run Worker A live (it's already DB-authoritative/safe), edit a canvas node in the app, confirm `Projects/VibeMind - <bubble>/<node>.md` gets correct frontmatter (`canvas_node_id`, `node_type`, `has_content_json`, `idea_id`) and that `_record_folder_hashes` recorded its hash (no Worker B echo). Confirm `reformat_pending`-false nodes still flatten structured content as before (no regression on the 92).

**Phase C — Worker B canvas writeback, DRY_RUN.** Implement `parse_canvas_md`, `_canvas_db_updated_at`, `update_canvas_in_db`, the enqueue, the dispatch branch — all behind `VIBEMIND_BUBBLE_SYNC_DRY_RUN=1`.
*Verify (mirrors how ideas Worker B was dry-run'd, `worker_fs_to_db.py:117-119`):* edit a **plain** canvas `.md` body → log shows the exact GUC-fenced content-only UPDATE, executes nothing. Edit a **structured** `.md` → log shows the content UPDATE **+** `reformat_pending=true` **+** the `INSERT ... ON CONFLICT` enqueue SQL. Confirm title/node_type never appear in any SET clause. Confirm a non-canvas, non-idea file still hits the catch-all skip.

**Phase D — Worker B live (content only).** Set `DRY_RUN=0`, keep the reformat drainer OFF.
*Verify:* edit a plain node's body → `public.canvas_nodes.content` updates, **no** outbox row (fence works), Worker A re-render is a no-op (hash echo). Edit a structured node → `content` updates, `reformat_pending=true`, a `pending` row appears in `canvas_reformat_jobs`. Hammer the same node 5× in <3s → exactly **one** pending row (ON CONFLICT coalesce). `content_json` still stale (drainer off) but Worker A renders from `content` (flag guard) — confirm no flicker.

**Phase E — Reformat drainer, DRY_RUN (LLM called, write skipped).** Run `worker_canvas_reformat` with `VIBEMIND_CANVAS_REFORMAT_DRY_RUN=1`.
*Verify:* picks the debounced pending job (only after 3s quiet), **actually calls the LLM** (`apply_format_to_node_headless` → `FORMAT_AGENTS[...]` → `_call_format_agent_sync` `:44-77`), logs the produced `content_json.type` and validation result, and **skips the DB write**. Confirms model/provider wiring (`get_model("format_dispatcher")`), retry/timeout behavior, and note-fallback on a deliberately-bad format — without mutating the DB. This is the analogue of "dry-run reformat logging the LLM call without executing."

**Phase F — Arm end-to-end.** `DRY_RUN=0` on both Worker B and the drainer; launch the drainer thread from `electron_backend` (`:537-541` pattern).
*Verify full round-trip on a structured node:* edit body in Rowboat → `content` updates (fenced) + job enqueued + `reformat_pending=true` → drainer reformats → `content_json` regenerated (fenced), `reformat_pending=false`, `previous_content_json`=original → Worker A renders the new structured body to `.md` on the next genuine change. Then test **undo**: trigger the app's revert path and confirm it restores the pre-edit structure from `previous_content_json`. Confirm no oscillation (the fenced reformat write does not bounce back to FS; Worker B sees no new event because the only thing that changed structurally is `content_json`, which Worker B ignores).

---

## 9. Risk register (each mitigation grounded in recon/verified source)

| # | Risk | Mitigation |
|---|------|------------|
| R1 | **LLM non-determinism / oscillation** — repeated reformats of the same content drift, or a reformat→render→re-parse loop. | The reformat write is **GUC-fenced** (`triggers.sql:48-83`) so it never emits to FS; Worker B only writes `content` and **ignores `content_json`**, so a regenerated structure cannot re-trigger Worker B. The loop is structurally broken. Debounce (3s, §1) plus per-node single-pending job (unique index 4c) prevent rapid re-fires. |
| R2 | **Cost** — every structured-node body edit = one 3000-token LLM call (`format_dispatcher.py:44-77`). | Coalescing collapses N saves→1 job (ON CONFLICT, §6); 3s debounce ensures only the final paused state is formatted. Only the 92 `has_content_json=true` nodes ever enqueue; the 147 plain nodes never call the LLM. Optional: skip enqueue if `content_hash` matches the last `done` job for that node. |
| R3 | **Reformat failure / invalid LLM output** | `apply_format_to_node_headless` reuses the existing validate + **note-fallback** (`format_dispatcher.py:880-892`): invalid structured output downgrades to a valid `note`. Hard agent failure after 3× retry → job `status='failed'`, `reformat_pending` stays `true`, Worker A keeps rendering from `content` — no broken structure ever reaches `.md`. Per-job `ThreadPoolExecutor` timeout prevents a hung call wedging the drainer. |
| R4 | **Flicker window** (content_json stale t1→t2, §2) | `reformat_pending` column + Worker A render guard (§5): while pending, render from `content`, skip `_flatten_content_json`. Both the t1 (Worker B) and t2 (drainer) writes are fenced, so neither forces a render in the window. |
| R5 | **Tiptap round-trip on structured bodies** — user edits a *flattened* structured body; the flatten is lossy (`ideas_publisher.py:99-116`, recon "lossy flatten"). | We never write the edited body back into `content_json` directly. We write it to `content` (lossless plain) and **regenerate** `content_json` from that plain text via the LLM. Frontmatter (incl. `canvas_node_id`) survives Tiptap split/join (given). The user's structural intent is reconstructed by the formatter, not parsed from the flatten. |
| R6 | **Double-fire between ideas & canvas outbox** — a node linked to a bubble that also has an idea could publish twice. | Both outboxes collapse to the **same `bubble_id`** and call `publish_bubble(bubble_id)` **once** (`worker_db_to_fs.py:116`, `:122`). `publish_bubble` already renders ideas+canvas together (`ideas_publisher.py:86-116`). Draining both outboxes in one loop iteration and de-duping bubble_ids before publish means at most one publish per bubble per cycle. |
| R7 | **Wrong write path re-introduces echo** — using `canvas_repo.update_node()` (PostgREST, can't fence) anywhere in writeback. | **Hard rule, documented in code:** all canvas writeback (Worker B content write, drainer content_json write) goes through `_db.execute_via_docker` raw psql with the GUC (`_db.py:92-102`). `canvas_repo.update_node` (`canvas_repository.py:91-130` → `supabase_database.py:352-382` PostgREST) is forbidden in the sync path. (Verified: that adapter no-ops DDL and is one-call-one-tx.) |
| R8 | **`prev_content_json` capture race** — if Worker B reads `content_json` *after* its own write, it gets the (unchanged) original anyway, but a concurrent app reformat could change it. | Capture `content_json` in the **same `_handle_event` invocation, before** the content UPDATE, and store it in the job row (§6). LWW guard (R-aligned, `worker_fs_to_db.py:197-205` fork) already rejects the edit entirely if the DB changed after the file's `last_synced_at`, so a concurrent app reformat causes a skip, not a corrupt undo. |

---

## 10. Concrete file/function list (create / modify) with fork-source `file:line`

**New migrations** (`vibemind-os/supabase/migrations/`)
- `20260611_canvas_sync_columns.sql` — fork `20260610_ideas_sync_columns.sql:22-59`; add `updated_at`, `last_synced_at`, `reformat_pending`, touch trigger.
- `20260611_canvas_sync_triggers.sql` — fork `20260610_ideas_sync_triggers.sql:26-103`; `canvas_sync_outbox`, `emit_canvas_sync_event` (bubble = `linked_idea_id`, skip NULL), `mark_canvas_outbox_applied`, NOTIFY `vibemind_canvas_sync`.
- `20260611_canvas_reformat_jobs.sql` — new; jobs table + `uq_canvas_reformat_pending` partial unique index.

**Modify**
- `vibemind-os/voice/python/publishing/bubble_sync/_frontmatter.py` — add `("canvas", ["canvas_node_id","has_content_json"])` to `SCHEMA_GROUPS` (`:24-28`); bump `SYNC_VERSION` 1→2.
- `vibemind-os/voice/python/publishing/bubble_sync/validate.py` — new `parse_canvas_md` (fork `parse_idea_md` `:38-75`); reuse `_body_description` (`:78-103`) for canvas body; never extract `title`.
- `vibemind-os/voice/python/publishing/bubble_sync/render_md.py` — new `render_canvas_note` (fork `render_idea_note` `:54-106`); canvas frontmatter; `reformat_pending` flicker guard.
- `vibemind-os/voice/python/publishing/ideas_publisher.py` — canvas-node render block (`:86-116`) emits via `render_canvas_note` with canvas frontmatter + `has_content_json`; honor `reformat_pending` (render `content` not flatten).
- `vibemind-os/voice/python/publishing/bubble_sync/worker_fs_to_db.py` — replace guard `:187-192`; add canvas dispatch in `_handle_event` (`:155-210`); new `_canvas_db_updated_at` (fork `_db_updated_at` `:132-144`), `update_canvas_in_db` + enqueue (fork `update_idea_in_db` `:100-130`).
- `vibemind-os/voice/python/publishing/bubble_sync/worker_db_to_fs.py` — `drain_canvas_outbox` (fork `drain_outbox` `:100-141`); call it + ideas drain in `listen_forever` (`:142-160`); LISTEN/poll `vibemind_canvas_sync`.
- `vibemind-os/spaces/ideas/tools/format_dispatcher.py` — new `apply_format_to_node_headless` (fork pure core of `convert_format` `:872-899`; reuse `FORMAT_AGENTS` `:745-764`, validation+note-fallback `:880-892`, `get_format_schema` `:899`; **drop** Electron `:906`/`:927-942` + NotificationQueue `:909-918` + stale-`content_json` fallback `:870`).
- `vibemind-os/voice/python/electron_backend.py` — launch reformat drainer thread (fork worker-A/B launch `:537-541`).

**New worker**
- `vibemind-os/voice/python/publishing/bubble_sync/worker_canvas_reformat.py` — drainer daemon (skeleton fork of `worker_fs_to_db.py` env/signal `:52-75`; per-job `ThreadPoolExecutor` timeout idea from hard-kill `openclaw_brain_dispatch_worker.py:45-51`; fenced raw-psql write via `_db.execute_via_docker` `_db.py:92-102`).

**Env / kill-switches** (new, mirroring `worker_fs_to_db.py:62-63`): `VIBEMIND_CANVAS_SYNC_ENABLED`, `VIBEMIND_CANVAS_REFORMAT_ENABLED`, `VIBEMIND_CANVAS_REFORMAT_DRY_RUN`, `CANVAS_REFORMAT_DEBOUNCE_SEC` (default 3).

**Critical reminder for the implementer:** never write canvas data through `canvas_repo.update_node()` in the sync path — it routes to PostgREST (`supabase_database.py:352-382`), cannot set the `vibemind.sync_origin` GUC in-tx, and will echo. All fenced writes use `_db.execute_via_docker` raw psql.