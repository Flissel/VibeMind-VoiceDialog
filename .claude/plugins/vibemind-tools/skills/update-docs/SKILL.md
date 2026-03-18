---
name: update-docs
description: This skill should be used when the user asks to "update docs", "update documentation", "sync docs", "refresh docs", "check doc drift", "docs outdated", "documentation audit", "are docs up to date", "update CLAUDE.md", "update README", "regenerate docs", or mentions keeping documentation in sync with the codebase.
---

# Update Documentation from Codebase

Detect and fix documentation drift by scanning the VibeMind codebase for current state and comparing against existing docs.

## Safety Rules

- **Never delete documentation** without confirming the code source was actually removed
- **Preserve bilingual content** — German docs (`docs/0X_*.md`) stay German, English docs stay English
- **Do not rewrite working docs** — only update sections with confirmed drift
- **Back up before bulk edits** — for files with >5 changes, read the full file first

## Workflow

### 1. Run the Drift Scanner

Execute the scanner to get a structured drift report:

```bash
python .claude/plugins/vibemind-tools/skills/update-docs/scripts/doc_drift_scanner.py --root .
```

For JSON output (machine-readable):

```bash
python .claude/plugins/vibemind-tools/skills/update-docs/scripts/doc_drift_scanner.py --root . --json
```

To scan specific sections only:

```bash
# Available sections: spaces, events, tools, db, ipc, agents
python .claude/plugins/vibemind-tools/skills/update-docs/scripts/doc_drift_scanner.py --root . --section spaces,events
```

### 2. Analyze the Drift Report

The scanner outputs three drift types:

| Type | Icon | Meaning | Action |
|------|------|---------|--------|
| `missing_in_docs` | `+` | Code exists, docs don't mention it | Add to docs |
| `extra_in_docs` | `-` | Docs mention it, code doesn't have it | Verify removal, then update docs |
| `missing_doc_file` | `!` | Expected doc file doesn't exist | Create from template |

### 3. Prioritize Updates

Follow this priority order:

1. **CLAUDE.md** — most-read file, update first
2. **API reference docs** (`docs/api/`) — event-types, tool-functions, database-schema, ipc-messages
3. **Space READMEs** (`docs/python/spaces/*/README.md`) — per-space docs
4. **Architecture docs** (`docs/architecture/`) — system design
5. **German docs** (`docs/0X_*.md`) — numbered system docs

### 4. Update Documentation

For each drift item, follow the update pattern for its section:

#### Spaces Drift

When a new space is detected:
1. Read `python/spaces/{name}/` to understand agents, tools, README
2. Add row to CLAUDE.md "Eight Spaces" table
3. Add section to `docs/03_spaces.md`
4. Create `docs/python/spaces/{name}/README.md` if missing
5. Update `docs/python/spaces/README.md` overview

#### Event Types Drift

When new event types are detected:
1. Read `python/swarm/event_team/event_router.py` STREAM_MAPPING
2. Determine which stream/domain the event belongs to
3. Add to `docs/api/event-types.md` under the correct domain section
4. If the event represents a new category, add examples to CLAUDE.md "Intent Classification"

#### Tool Functions Drift

When new tool functions are detected:
1. Read the source file to get function signature and docstring
2. Add to `docs/api/tool-functions.md` under the correct section
3. Update space README if it's a space-specific tool

#### Database Schema Drift

When new tables or columns are detected:
1. Read `python/data/database.py` and relevant migration files
2. Add table/column to `docs/api/database-schema.md`
3. Update the ER diagram if new relationships exist
4. Update CLAUDE.md schema summary table

#### IPC Messages Drift

When new message types are detected:
1. Grep for the message type to find broadcast calls and handlers
2. Add to `docs/api/ipc-messages.md` with purpose and payload
3. Update CLAUDE.md IPC table if it's a major message type

#### Backend Agents Drift

When new agents are detected:
1. Read the agent class for stream, TOOL_MAP, and PARAM_MAPPING
2. Add to CLAUDE.md backend agent table
3. Update `docs/python/swarm/backend-agents/README.md`
4. Update `docs/04_swarm_layer.md` (German)

### 5. Verify Updates

After making changes, re-run the scanner to confirm zero drift:

```bash
python .claude/plugins/vibemind-tools/skills/update-docs/scripts/doc_drift_scanner.py --root .
```

### 6. Cross-Reference Check

After updating individual docs, verify cross-references stay consistent. These sections must match across files — consult `references/doc-structure.md` for the full cross-reference map:

- **Space count**: CLAUDE.md, `docs/03_spaces.md`, `docs/python/spaces/README.md`
- **Event types**: CLAUDE.md examples, `docs/api/event-types.md`, `event_router.py`
- **Agent table**: CLAUDE.md, `docs/04_swarm_layer.md`, agent registry
- **DB schema**: CLAUDE.md summary, `docs/api/database-schema.md`, `database.py`

## Doc File Templates

### New Space README Template

```markdown
# {Space Name} Space

{One-paragraph description of what this space does.}

## Architecture

{Mermaid diagram or flow description}

## Backend Agent

- **Class:** `{ClassName}` in `python/spaces/{name}/agents/{file}.py`
- **Stream:** `events:tasks:{stream}`
- **Event Prefix:** `{prefix}.*`

## Tools

| Tool | File | Description |
|------|------|-------------|
| `function_name` | `tools/{file}.py` | What it does |

## Event Types

| Event | Parameters | Description |
|-------|-----------|-------------|
| `prefix.action` | `{param}` | What happens |
```

## Additional Resources

### Reference Files

- **`references/doc-structure.md`** — Complete mapping of every doc file to its code source of truth, update priority matrix, and cross-reference map

### Scripts

- **`scripts/doc_drift_scanner.py`** — Standalone Python scanner (no dependencies). Supports `--json`, `--section` flags