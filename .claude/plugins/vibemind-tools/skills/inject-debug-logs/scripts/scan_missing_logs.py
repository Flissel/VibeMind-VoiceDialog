#!/usr/bin/env python3
"""
Scan VibeMind codebase for files missing debug logging.

Checks:
1. Python files without `logging.getLogger(__name__)`
2. Functions/methods that could benefit from entry/exit debug logs
3. Files with bare `print()` statements that should use the logger
4. Tool functions missing result logging
5. Agent event handlers missing logging

Output: JSON report with file paths, issues, and suggested log placements.
"""

import ast
import json
import sys
from pathlib import Path
from typing import Dict, List, Any

# Space detection from module path (mirrors space_logger.py MODULE_TO_SPACE)
MODULE_TO_SPACE = {
    "spaces.ideas.agents.bubbles": "bubbles",
    "spaces.ideas": "ideas",
    "spaces.coding": "coding",
    "spaces.desktop": "desktop",
    "spaces.rowboat": "rowboat",
    "spaces.research": "research",
    "spaces.minibook": "minibook",
    "spaces.schedule": "schedule",
    "spaces.n8n": "n8n",
    "spaces.brain": "brain",
    "voice": "voice",
    "swarm.orchestrator": "orchestrator",
    "swarm.listeners": "orchestrator",
    "swarm.event_team": "orchestrator",
    "swarm.backend_agents": "system",
    "swarm.monitoring": "system",
    "swarm.logging": "system",
    "data": "system",
    "tools": "system",
    "workers": "system",
    "publishing": "system",
    "memory": "system",
    "debug": "system",
}

SPACE_COLORS = {
    "bubbles": "Bright Cyan",
    "ideas": "Bright Green",
    "coding": "Bright Yellow",
    "desktop": "Bright Magenta",
    "rowboat": "Blue",
    "research": "Red",
    "minibook": "White Bold",
    "schedule": "Cyan",
    "n8n": "Cyan",
    "voice": "Dark Yellow",
    "orchestrator": "Dark Magenta",
    "brain": "Dark Green",
    "system": "Dim",
}


def detect_space(filepath: Path, python_root: Path) -> str:
    """Detect which space a file belongs to based on its path."""
    try:
        rel = filepath.relative_to(python_root)
        module_path = str(rel.with_suffix("")).replace("\\", "/").replace("/", ".")
    except ValueError:
        return "system"

    # Longest prefix match
    best_match = ""
    best_space = "system"
    for prefix, space in MODULE_TO_SPACE.items():
        if module_path.startswith(prefix) and len(prefix) > len(best_match):
            best_match = prefix
            best_space = space
    return best_space


def analyze_file(filepath: Path, python_root: Path) -> Dict[str, Any]:
    """Analyze a Python file for logging issues and opportunities."""
    issues = []
    suggestions = []

    try:
        source = filepath.read_text(encoding="utf-8", errors="replace")
        tree = ast.parse(source, filename=str(filepath))
    except (SyntaxError, UnicodeDecodeError):
        return None

    space = detect_space(filepath, python_root)
    has_logger = False
    has_logging_import = False
    bare_prints = []
    functions_without_logging = []
    tool_functions = []
    event_handlers = []

    # Check top-level for logger setup
    for node in ast.walk(tree):
        # Check for logging import
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "logging":
                    has_logging_import = True
        elif isinstance(node, ast.ImportFrom):
            if node.module == "logging":
                has_logging_import = True

        # Check for logger = logging.getLogger(__name__)
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in ("logger", "_logger"):
                    has_logger = True

        # Detect bare print() calls to stderr
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id == "print":
                # Check if it writes to stderr
                for kw in node.keywords:
                    if kw.arg == "file":
                        bare_prints.append(node.lineno)
                        break

    # Analyze functions and methods
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            name = node.name
            lineno = node.lineno
            body_lines = len(node.body) if node.body else 0

            # Skip trivial functions (< 3 lines), private helpers, and __init__
            if body_lines < 3 or name.startswith("__"):
                continue

            # Check if function has any logging call
            has_log_call = False
            for child in ast.walk(node):
                if isinstance(child, ast.Call):
                    func = child.func
                    if isinstance(func, ast.Attribute):
                        if func.attr in ("debug", "info", "warning", "error", "critical"):
                            if isinstance(func.value, ast.Name) and func.value.id in ("logger", "_logger", "logging"):
                                has_log_call = True
                                break

            if not has_log_call and body_lines >= 5:
                # Categorize the function
                is_tool = name.endswith("_tool") or name.startswith("create_") or name.startswith("get_") or name.startswith("list_")
                is_handler = name.startswith("_handle_") or name.startswith("handle_") or name.startswith("on_")
                is_public = not name.startswith("_")

                if is_tool:
                    tool_functions.append({"name": name, "line": lineno, "body_lines": body_lines})
                elif is_handler:
                    event_handlers.append({"name": name, "line": lineno, "body_lines": body_lines})
                elif is_public and body_lines >= 8:
                    functions_without_logging.append({"name": name, "line": lineno, "body_lines": body_lines})

    # Build issues list
    if not has_logging_import:
        issues.append({"type": "no_logging_import", "severity": "high",
                       "message": "Missing `import logging`"})

    if not has_logger and has_logging_import:
        issues.append({"type": "no_logger", "severity": "high",
                       "message": "Has logging import but no `logger = logging.getLogger(__name__)`"})

    if not has_logger and not has_logging_import:
        issues.append({"type": "no_logging_setup", "severity": "high",
                       "message": "No logging setup at all"})

    if bare_prints:
        issues.append({"type": "bare_print_stderr", "severity": "medium",
                       "message": f"Found {len(bare_prints)} print-to-stderr calls (lines: {bare_prints[:5]})",
                       "lines": bare_prints[:10]})

    # Build suggestions
    for fn in tool_functions:
        suggestions.append({
            "type": "tool_logging",
            "function": fn["name"],
            "line": fn["line"],
            "suggestion": f"Add `logger.debug('[{fn['name']}] called with ...')` at entry and `logger.debug('... result: ...')` before return"
        })

    for fn in event_handlers:
        suggestions.append({
            "type": "handler_logging",
            "function": fn["name"],
            "line": fn["line"],
            "suggestion": f"Add `logger.debug('[{fn['name']}] event_type=...')` at entry"
        })

    for fn in functions_without_logging:
        suggestions.append({
            "type": "function_logging",
            "function": fn["name"],
            "line": fn["line"],
            "suggestion": f"Add debug log at entry for {fn['body_lines']}-line function"
        })

    if not issues and not suggestions:
        return None

    return {
        "file": str(filepath.relative_to(python_root)),
        "space": space,
        "color": SPACE_COLORS.get(space, "Dim"),
        "issues": issues,
        "suggestions": suggestions,
        "has_logger": has_logger,
    }


def scan_codebase(python_root: Path) -> Dict[str, Any]:
    """Scan the entire Python codebase."""
    results = []
    skipped = []

    # Directories to skip (submodules and non-project code)
    skip_dirs = {"__pycache__", ".git", "node_modules", "Coding_engine",
                 "Automation_ui", "swe_desgine", ".venv312"}
    # Submodule paths to skip (specific nested dirs, not entire spaces)
    skip_submodules = {("spaces", "rowboat", "rowboat"),
                       ("spaces", "shuttles", "swe_desgine")}

    total_files = 0
    for py_file in sorted(python_root.rglob("*.py")):
        # Skip excluded directories
        if any(skip in py_file.parts for skip in skip_dirs):
            continue
        # Skip git submodules (nested same-name dirs)
        rel_parts = py_file.relative_to(python_root).parts
        if any(all(p in rel_parts for p in sub) for sub in skip_submodules):
            continue
        # Skip __init__.py (usually just imports)
        if py_file.name == "__init__.py":
            continue
        # Skip test files
        if py_file.name.startswith("test_"):
            continue

        total_files += 1
        result = analyze_file(py_file, python_root)
        if result:
            results.append(result)

    # Group by space
    by_space = {}
    for r in results:
        space = r["space"]
        if space not in by_space:
            by_space[space] = {"files": [], "color": r["color"]}
        by_space[space]["files"].append(r)

    # Summary
    total_issues = sum(len(r["issues"]) for r in results)
    total_suggestions = sum(len(r["suggestions"]) for r in results)
    files_no_logger = sum(1 for r in results if not r["has_logger"])

    return {
        "summary": {
            "files_scanned": total_files,
            "files_with_issues": len(results),
            "total_issues": total_issues,
            "total_suggestions": total_suggestions,
            "files_without_logger": files_no_logger,
        },
        "by_space": by_space,
    }


def main():
    """Run the scanner."""
    # Determine python root
    if len(sys.argv) > 1:
        python_root = Path(sys.argv[1])
    else:
        # Auto-detect from script location
        script_dir = Path(__file__).resolve().parent
        # Walk up to find python/ directory
        for p in [script_dir] + list(script_dir.parents):
            candidate = p / "python"
            if candidate.is_dir() and (candidate / "electron_backend.py").exists():
                python_root = candidate
                break
        else:
            print("ERROR: Could not find python/ directory", file=sys.stderr)
            sys.exit(1)

    report = scan_codebase(python_root)
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
