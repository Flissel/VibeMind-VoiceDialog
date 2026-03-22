---
name: refactor
description: >
  Analyze and refactor large monolithic files. Scans Python (AST) and JS/TS files,
  computes complexity scores, identifies classes/functions/sections, maps dependencies.
  Two modes: Analyse (scan + suggestions) and Execute (split files with import updates).
  Use when asked to "refactor", "split large file", "find monoliths", "complexity scan",
  "refactor scan", "which files are too big", "welche Dateien splitten".
---

# refactor — Monolith Analyzer & Splitter

Two-mode skill: **Analyse** (default) scans for large files and suggests splits.
**Execute** (on user confirmation) performs the actual file splits.

## Scanner Script

`scripts/refactor_scanner.py` — Deterministic Python script, no LLM dependency.

```bash
# Console report (default threshold: 300 lines)
python .claude/plugins/vibemind-tools/skills/refactor/scripts/refactor_scanner.py --root .

# Lower threshold
python ... --threshold 200

# JSON output (for programmatic use)
python ... --json

# YAML report file
python ... --yaml REFACTOR_REPORT.yml

# Include git submodules (Coding_engine, Automation_ui, etc.)
python ... --include-submodules
```

### What it measures per file

| Metric | Python | JS/TS |
|--------|--------|-------|
| Line count | exact | exact |
| Functions/methods | AST (FunctionDef, AsyncFunctionDef) | Regex (function, =>, class methods) |
| Classes | AST (ClassDef) | Regex (class X { }) |
| Internal imports | AST (ImportFrom with project modules) | Regex (import from './...') |
| Comment sections | `# --- Name ---` pattern | `// --- Name ---` pattern |
| Complexity score | lines/50 + funcs×0.3 + maxFunc/20 + classes×2 | same formula |

### Complexity Score

`score = lines/50 + func_count×0.3 + (max_func_lines/20 if >50) + class_count×2`

Higher score = more urgent. Files are ranked by score descending.

## Instructions for Claude

### Analyse Mode (default)

When the user triggers this skill:

1. Run the scanner:
   ```bash
   python .claude/plugins/vibemind-tools/skills/refactor/scripts/refactor_scanner.py --root .
   ```

2. Present the top candidates sorted by complexity score.

3. For each top candidate, provide a **semantic split recommendation**:
   - Read the file
   - Identify logical groups of functions (by domain, responsibility, or existing comment sections)
   - Suggest target modules with rationale
   - List which imports would need updating

4. Format as a refactor plan table:
   ```
   Source File → Proposed Module → Functions/Classes → Rationale
   ```

### Execute Mode (user confirms)

When the user says "ja", "mach das", "split it", "refactor it":

1. Read the target file completely
2. Create new module files with extracted functions/classes
3. Add proper imports to each new module
4. Convert the original file to a re-export shim (for backwards compatibility)
5. Update all files that import from the original
6. Verify: no broken imports, no circular dependencies

**Safety rules:**
- Never split more than one file at a time
- Show `git diff` summary before and after
- Remind user: all changes are uncommitted, `git checkout .` to rollback
- Preserve ALL existing import paths via re-export shims

## Key Patterns

### Re-Export Shim
```python
# original_module.py (was 2000+ lines, now ~30)
"""Backwards-compatible re-export shim."""
from .new_module_a import ClassA, helper_a
from .new_module_b import ClassB, helper_b
```

### Handler Extraction (for large classes)
```python
# New handler module
class CanvasManager:
    def __init__(self, backend):
        self.backend = backend
    def handle_get_bubbles(self, message): ...

# Original file composes
self._canvas_mgr = CanvasManager(self)
self._dispatch = {"get_bubbles": self._canvas_mgr.handle_get_bubbles}
```