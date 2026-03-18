---
name: inject-debug-logs
description: This skill should be used when the user asks to "add debug logs", "inject logging", "add space logging", "check missing logs", "scan for unlogged functions", "improve observability", "add colored logs", or mentions debug logging coverage for VibeMind spaces.
---

# Inject Debug Logs

Scan the VibeMind Python codebase for files and functions missing debug logging, then inject space-aware colored log statements using the SpaceLogger system.

## When to Use

- Adding debug logs to files that lack them
- Ensuring all tool functions, event handlers, and public methods have entry/exit logging
- Converting remaining `print()` statements to proper logger calls
- Improving observability for a specific space (e.g., "add debug logs to the coding space")

## Space Color Reference

| Space | Tag | ANSI Color | Module Prefix |
|-------|-----|------------|---------------|
| bubbles | `[BUBBLES]` | Bright Cyan | `spaces.ideas.agents.bubbles` |
| ideas | `[IDEAS]` | Bright Green | `spaces.ideas` |
| coding | `[CODING]` | Bright Yellow | `spaces.coding` |
| desktop | `[DESKTOP]` | Bright Magenta | `spaces.desktop` |
| rowboat | `[ROWBOAT]` | Blue | `spaces.rowboat` |
| research | `[RESEARCH]` | Red | `spaces.research` |
| minibook | `[MINIBOOK]` | White Bold | `spaces.minibook` |
| schedule | `[SCHEDULE]` | Cyan | `spaces.schedule` |
| voice | `[VOICE]` | Dark Yellow | `voice` |
| orchestrator | `[ORCH]` | Dark Magenta | `swarm.orchestrator` |
| brain | `[BRAIN]` | Dark Green | `brain` |
| system | `[SYSTEM]` | Dim | everything else |

Colors are auto-assigned by SpaceLogger based on the module path (`__name__`). No manual color setup needed.

## Workflow

### Step 1: Scan for Missing Logs

Run the scanner script to identify files and functions without logging:

```bash
cd python
python ../.claude/plugins/vibemind-tools/skills/inject-debug-logs/scripts/scan_missing_logs.py .
```

The script outputs a JSON report grouped by space with:
- **Issues**: Missing logger setup, bare print() calls
- **Suggestions**: Functions that need entry/exit debug logs

### Step 2: Fix Logger Setup

For files missing logger setup, add at module top (after imports):

```python
import logging

logger = logging.getLogger(__name__)
```

No additional configuration needed. SpaceLogger auto-detects the space from `__name__` and applies the correct color.

### Step 3: Inject Debug Logs

Follow these placement rules based on function type:

**Tool functions** (functions that execute user-visible actions):
```python
def create_bubble(title: str, description: str = "") -> dict:
    logger.debug("create_bubble called: title=%s", title)
    # ... implementation ...
    logger.debug("create_bubble result: id=%s", result.get("id"))
    return result
```

**Event handlers** (functions that process events/messages):
```python
async def _handle_intent(self, event_type: str, payload: dict):
    logger.debug("_handle_intent: event_type=%s payload_keys=%s", event_type, list(payload.keys()))
    # ... implementation ...
```

**Public methods** (8+ lines, entry-only):
```python
def initialize(self):
    logger.debug("initialize: starting %s", self.__class__.__name__)
    # ... implementation ...
```

**Error paths** (catch blocks with meaningful context):
```python
except Exception as e:
    logger.error("Failed to process %s: %s", item_id, e)
```

### Step 4: Validate

After injection, verify by scanning again:

```bash
python ../.claude/plugins/vibemind-tools/skills/inject-debug-logs/scripts/scan_missing_logs.py .
```

The "total_issues" and "total_suggestions" counts should decrease.

## Logging Rules

1. **Use `logger.debug()` for operational flow** — entry/exit of functions, parameter values, decision points
2. **Use `logger.info()` for significant events** — creation of resources, state changes, initialization
3. **Use `logger.warning()` for recoverable issues** — missing optional config, fallback behavior
4. **Use `logger.error()` for failures** — exceptions, failed operations, broken invariants
5. **Never use `print()` to stderr** — always use the logger
6. **Use `%s` formatting, not f-strings** — `logger.debug("x=%s", x)` is more efficient than `logger.debug(f"x={x}")`
7. **Include identifying context** — function name, key parameters, result IDs
8. **Keep messages concise** — no full object dumps, just identifying fields

## Scope Control

- **Single space**: "Add debug logs to the coding space" — only scan/modify `python/spaces/coding/`
- **Single file**: "Add logging to intent_classifier.py" — just that file
- **Full scan**: "Check all missing logs" — run scanner on entire codebase
- **Incremental**: After any code change, re-scan the modified files

## Key Files

| File | Purpose |
|------|---------|
| `python/swarm/logging/space_logger.py` | SpaceLogger system (colors, formatters, JSON output) |
| `python/electron_backend.py` | Entry point that calls `setup_space_logging()` |
| `python/debug/electron_debug_agent.py` | Debug terminal color rendering |

## Script

**`scripts/scan_missing_logs.py`** — AST-based scanner that checks every Python file for:
- Missing `import logging` / `logging.getLogger(__name__)`
- Bare `print(..., file=sys.stderr)` calls
- Tool functions (5+ lines) without any log call
- Event handlers without entry logging
- Public methods (8+ lines) without logging

Run with optional path argument: `python scan_missing_logs.py [python_root]`
