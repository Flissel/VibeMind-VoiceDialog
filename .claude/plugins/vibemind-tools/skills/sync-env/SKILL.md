---
name: sync-env
description: This skill should be used when the user asks to "sync env", "update .env.example", "check env vars", "find missing env variables", "audit environment config", or mentions keeping .env.example up to date. Scans the codebase for os.getenv() calls and compares against .env.example to find undocumented variables.
---

# Sync Environment Variables

Scan the VibeMind codebase for all `os.getenv()`, `os.environ.get()`, and `process.env.*` references, then compare against `.env.example` to find missing or undocumented variables.

## Safety Rules

**CRITICAL: Never modify `.env` directly.** The `.env` file contains live secrets and API keys. Only `.env.example` may be edited. The scan script is read-only and makes no file changes.

## Workflow

### 1. Run the Scanner

Execute the scan script to get a diff report:

```bash
cd python && python ../.claude/plugins/vibemind-tools/skills/sync-env/scripts/scan_env_vars.py --root .. --json
```

The script outputs grouped by domain:
- **missing_by_domain**: Vars grouped by Space/Application (Ideas, Coding, Electron, etc.)
- **unused**: Vars in `.env.example` but not found in code
- **Domain Overview**: Summary table showing documentation coverage per domain

### 2. Analyze Results

The output groups vars by domain (Ideas, Coding, Desktop, Electron, Voice, etc.) so you immediately know where each var belongs in `.env.example`.

For each **missing** variable:
- The domain tells you which `.env.example` section it belongs to
- Check the file location to understand its purpose
- Find the default value from the `os.getenv("VAR", "default")` call

For each **unused** variable:
- Verify it's truly unused (might be in Docker, CI, or shell scripts not scanned)
- If confirmed unused, consider removing from `.env.example`

### 3. Update `.env.example` Only

Add missing variables to `.env.example`, grouped by their domain:

```bash
# Section Header (matching the domain from scan output)
# =============================================================================

# Description of what this variable does
VARIABLE_NAME=default_value
```

### 4. Verify

Run the scanner again to confirm zero missing variables:

```bash
cd python && python ../.claude/plugins/vibemind-tools/skills/sync-env/scripts/scan_env_vars.py --root ..
```

## What the Script Scans

| Pattern | Language | Example |
|---------|----------|---------|
| `os.getenv("VAR")` | Python | `os.getenv("SPACE_LOG_LEVEL", "INFO")` |
| `os.environ.get("VAR")` | Python | `os.environ.get("REDIS_URL")` |
| `os.environ["VAR"]` | Python | `os.environ["OPENAI_API_KEY"]` |
| `process.env.VAR` | JavaScript | `process.env.NODE_ENV` |

### Excluded Directories

The scanner skips: `__pycache__`, `node_modules`, `.git`, `.venv`, `Coding_engine`, `Automation_ui`, `swe_desgine`, `rowboat` (external submodules).

## Scripts

- **`scripts/scan_env_vars.py`** — Standalone scanner, no dependencies. Run with `--json` for machine-readable output or without for a human-readable report.
