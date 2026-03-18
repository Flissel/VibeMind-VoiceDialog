#!/usr/bin/env python3
"""
Scan the VibeMind codebase for os.getenv() / os.environ.get() calls
and compare against .env.example to find missing or undocumented variables.

Output is grouped by domain/space so you know where each var belongs.

Usage:
    python scan_env_vars.py [--root /path/to/project]
    python scan_env_vars.py [--root /path/to/project] --json
"""

import argparse
import json
import re
import sys
from pathlib import Path
from collections import defaultdict


# Patterns that match os.getenv("VAR"), os.getenv('VAR'), os.environ.get("VAR"),
# os.environ["VAR"], os.environ.get("VAR", default)
# Line-level patterns (fast, catches most cases)
GETENV_PATTERNS = [
    re.compile(r'''os\.getenv\(\s*["']([A-Z_][A-Z0-9_]*)["']'''),
    re.compile(r'''os\.environ\.get\(\s*["']([A-Z_][A-Z0-9_]*)["']'''),
    re.compile(r'''os\.environ\[["']([A-Z_][A-Z0-9_]*)["']\]'''),
]

# Multiline patterns: catch os.getenv(\n    "VAR" across line breaks
GETENV_MULTILINE = [
    re.compile(r'''os\.getenv\(\s*\n\s*["']([A-Z_][A-Z0-9_]*)["']'''),
    re.compile(r'''os\.environ\.get\(\s*\n\s*["']([A-Z_][A-Z0-9_]*)["']'''),
]

# Skip directories — always skip (generic build/cache dirs)
SKIP_DIRS_ALWAYS = {
    "__pycache__", "node_modules", ".git", ".venv", "venv", ".venv312",
    "dist", "build", ".eggs", ".claude",
}

# Skip specific subpaths (use forward slashes, matched against relative path)
# These are external submodules or vendored code, NOT VibeMind spaces
SKIP_SUBPATHS = [
    "external/",             # all external submodules
    "python/spaces/coding/Coding_engine/",
    "python/spaces/desktop/Automation_ui/",
    "python/spaces/shuttles/swe_desgine/",
    "python/spaces/rowboat/rowboat/",  # rowboat submodule inside space
    "electron-app/dashboard/",          # React dashboard (built separately)
]

# Skip file patterns
SKIP_FILES = {".pyc", ".pyo", ".so", ".dll"}


def _should_skip(file_path: Path, root: Path) -> bool:
    """Check if a file should be skipped based on dir and subpath rules."""
    # Check always-skip directories
    if any(skip in file_path.parts for skip in SKIP_DIRS_ALWAYS):
        return True
    # Check subpath exclusions
    try:
        rel = str(file_path.relative_to(root)).replace("\\", "/")
        for subpath in SKIP_SUBPATHS:
            if rel.startswith(subpath):
                return True
    except ValueError:
        pass
    return False

# =============================================================================
# Domain Classification
# =============================================================================

# Path fragment -> domain name (checked longest-first)
PATH_TO_DOMAIN = [
    ("spaces/ideas",        "Ideas"),
    ("spaces/coding",       "Coding"),
    ("spaces/desktop",      "Desktop"),
    ("spaces/rowboat",      "Rowboat"),
    ("spaces/research",     "Research"),
    ("spaces/minibook",     "Minibook"),
    ("spaces/schedule",     "Schedule"),
    ("voice/",              "Voice"),
    ("swarm/orchestrator",  "Orchestrator"),
    ("swarm/logging",       "Logging"),
    ("swarm/broadcast",     "Broadcast"),
    ("swarm/conversion",    "Conversion"),
    ("swarm/zeroclaw",      "ZeroClaw"),
    ("swarm/",              "Swarm"),
    ("workers/",            "Workers"),
    ("publishing/",         "Publishing"),
    ("memory/",             "Memory"),
    ("tools/",              "Shared Tools"),
    ("config.py",           "Core"),
    ("data/",               "Core"),
    ("electron_backend.py", "Core"),
    ("electron-app/",       "Electron"),
    ("tests/",              "Tests"),
]


def classify_domain(locations: list) -> str:
    """Classify a variable's domain based on its file locations.

    Uses the first non-test location for classification.
    Falls back to 'Other' if no pattern matches.
    """
    # Prefer non-test locations
    sorted_locs = sorted(locations, key=lambda l: ("tests/" in l, l))

    for loc in sorted_locs:
        # Normalize path separators
        normalized = loc.replace("\\", "/")
        for fragment, domain in PATH_TO_DOMAIN:
            if fragment in normalized:
                return domain

    return "Other"


def group_by_domain(vars_dict: dict) -> dict:
    """Group variables by their domain.

    Returns: {domain: {var_name: [locations]}}
    """
    grouped = defaultdict(dict)
    for var, locs in sorted(vars_dict.items()):
        domain = classify_domain(locs)
        grouped[domain][var] = locs
    return dict(sorted(grouped.items()))


# =============================================================================
# Scanning
# =============================================================================

def scan_python_files(root: Path) -> dict:
    """Scan all .py files for env var references."""
    code_vars = defaultdict(list)

    for py_file in root.rglob("*.py"):
        if _should_skip(py_file, root):
            continue
        if py_file.suffix in SKIP_FILES:
            continue

        try:
            content = py_file.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        rel_path = py_file.relative_to(root)
        lines = content.splitlines()

        # Line-level matching (fast)
        for i, line in enumerate(lines, 1):
            for pattern in GETENV_PATTERNS:
                for match in pattern.finditer(line):
                    var_name = match.group(1)
                    code_vars[var_name].append(f"{rel_path}:{i}")

        # Multiline matching: os.getenv(\n    "VAR"
        for pattern in GETENV_MULTILINE:
            for match in pattern.finditer(content):
                var_name = match.group(1)
                # Calculate line number from match position
                line_no = content[:match.start()].count("\n") + 1
                loc = f"{rel_path}:{line_no}"
                if loc not in code_vars.get(var_name, []):
                    code_vars[var_name].append(loc)

    return dict(code_vars)


def scan_js_files(root: Path) -> dict:
    """Scan .js files for process.env.VAR references."""
    code_vars = defaultdict(list)
    pattern = re.compile(r'process\.env\.([A-Z_][A-Z0-9_]*)')

    for js_file in root.rglob("*.js"):
        if _should_skip(js_file, root):
            continue

        try:
            content = js_file.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        for i, line in enumerate(content.splitlines(), 1):
            for match in pattern.finditer(line):
                var_name = match.group(1)
                rel_path = js_file.relative_to(root)
                code_vars[var_name].append(f"{rel_path}:{i}")

    return dict(code_vars)


def parse_env_example(env_file: Path) -> dict:
    """Parse .env.example and return documented var names with their comments."""
    documented = {}
    prev_comment = ""

    if not env_file.exists():
        return documented

    for line in env_file.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            prev_comment = stripped.lstrip("# ").strip()
            continue
        if "=" in stripped:
            var_name = stripped.split("=", 1)[0].strip()
            if var_name.startswith("#"):
                var_name = var_name.lstrip("# ").strip()
                if "=" in var_name:
                    var_name = var_name.split("=", 1)[0].strip()
            documented[var_name] = prev_comment
            prev_comment = ""
        else:
            if not stripped:
                prev_comment = ""

    return documented


# =============================================================================
# Main
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Scan for undocumented env vars (grouped by domain)")
    parser.add_argument("--root", default=".", help="Project root directory")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    env_file = root / ".env.example"

    # Ensure UTF-8 output on Windows
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    # Scan code
    py_vars = scan_python_files(root)
    js_vars = scan_js_files(root)

    # Merge
    all_code_vars = defaultdict(list)
    for var, locs in {**py_vars, **js_vars}.items():
        all_code_vars[var].extend(locs)

    # Parse .env.example
    documented = parse_env_example(env_file)

    # Find missing & unused
    missing = {
        var: locs for var, locs in sorted(all_code_vars.items())
        if var not in documented
    }
    unused = {
        var: comment for var, comment in sorted(documented.items())
        if var not in all_code_vars
    }

    # Group by domain
    missing_by_domain = group_by_domain(missing)
    all_by_domain = group_by_domain(dict(all_code_vars))

    result = {
        "total_code_vars": len(all_code_vars),
        "total_documented": len(documented),
        "missing_count": len(missing),
        "unused_count": len(unused),
        "missing_by_domain": missing_by_domain,
        "unused": unused,
        "all_by_domain": all_by_domain,
    }

    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        sep = "=" * 60
        thin = "-" * 40
        print(f"\n{sep}")
        print(f"  ENV VAR SYNC REPORT (by Domain)")
        print(f"{sep}")
        print(f"  Code vars found:    {result['total_code_vars']}")
        print(f"  Documented in .env: {result['total_documented']}")
        print(f"  Missing from .env:  {result['missing_count']}")
        print(f"  Unused in .env:     {result['unused_count']}")

        if missing_by_domain:
            print(f"\n{sep}")
            print(f"  MISSING BY DOMAIN")
            print(f"{sep}")

            for domain, vars_dict in sorted(missing_by_domain.items()):
                print(f"\n  [{domain.upper()}] ({len(vars_dict)} missing)")
                print(f"  {thin}")
                for var, locs in sorted(vars_dict.items()):
                    print(f"  {var}")
                    for loc in locs[:2]:
                        print(f"    -> {loc}")
                    if len(locs) > 2:
                        print(f"    -> ... +{len(locs)-2} more")

        if unused:
            print(f"\n{sep}")
            print(f"  UNUSED (in .env.example but not in code)")
            print(f"{sep}")
            for var, comment in sorted(unused.items()):
                desc = f" ({comment})" if comment else ""
                print(f"  {var}{desc}")

        # Summary: all domains with counts
        print(f"\n{sep}")
        print(f"  DOMAIN OVERVIEW (all vars)")
        print(f"{sep}")
        for domain, vars_dict in sorted(all_by_domain.items()):
            documented_count = sum(1 for v in vars_dict if v in documented)
            missing_count = sum(1 for v in vars_dict if v not in documented)
            status = "OK" if missing_count == 0 else f"{missing_count} missing"
            print(f"  {domain:<20} {len(vars_dict):>3} vars  ({documented_count} doc, {status})")

        print(f"\n{sep}\n")


if __name__ == "__main__":
    main()
