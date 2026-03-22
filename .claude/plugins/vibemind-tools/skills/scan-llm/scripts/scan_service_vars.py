#!/usr/bin/env python3
"""
Scan VibeMind codebase for non-model environment variables and write
per-space service config YAML files.

Categorizes vars into: api_keys, urls, feature_flags, settings.

Usage:
    python scan_service_vars.py --root /path/to/project --configs-dir configs
    python scan_service_vars.py --root /path/to/project --json
"""

import argparse
import json
import re
import sys
from pathlib import Path
from collections import defaultdict

# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

PY_GETENV = [
    re.compile(r'''os\.getenv\(\s*["']([A-Z_][A-Z0-9_]*)["'](?:\s*,\s*["']?([^"')]+)["']?)?\)'''),
    re.compile(r'''os\.environ\.get\(\s*["']([A-Z_][A-Z0-9_]*)["'](?:\s*,\s*["']?([^"')]+)["']?)?\)'''),
    re.compile(r'''os\.environ\[["']([A-Z_][A-Z0-9_]*)["']\]'''),
]

# Pydantic Field(env="VAR") or Field(default=..., env="VAR")
PYDANTIC_ENV = re.compile(r'''env\s*=\s*["']([A-Z_][A-Z0-9_]*)["']''')

JS_ENV = re.compile(r'''process\.env\.([A-Z_][A-Z0-9_]*)''')

# Model-related vars to EXCLUDE (handled by scan_llm_models.py)
MODEL_VAR_RE = re.compile(r'MODEL', re.IGNORECASE)

SKIP_DIRS = {
    "__pycache__", "node_modules", ".git", ".venv", "venv", ".venv312",
    "dist", "build", ".eggs", ".claude", "dashboard",
    "Coding_engine", "Automation_ui", "swe_desgine", "rowboat",
    "external", "brain", "minibook",
}

SCAN_EXTENSIONS = {".py", ".js"}

# ---------------------------------------------------------------------------
# Domain Classification
# ---------------------------------------------------------------------------

PATH_TO_DOMAIN = [
    ("spaces/ideas",        "ideas"),
    ("spaces/coding",       "coding"),
    ("spaces/desktop",      "desktop"),
    ("spaces/rowboat",      "rowboat"),
    ("spaces/roarboot",     "rowboat"),
    ("spaces/research",     "research"),
    ("spaces/minibook",     "minibook"),
    ("spaces/schedule",     "schedule"),
    ("spaces/shuttles",     "shuttles"),
    ("spaces/n8n",          "n8n"),
    ("spaces/brain",        "brain"),
    ("voice/",              "voice"),
    ("swarm/orchestrator",  "orchestrator"),
    ("swarm/broadcast",     "broadcast"),
    ("swarm/stream_listener", "stream_listener"),
    ("swarm/space_agents",  "space_agents"),
    ("swarm/",              "swarm"),
    ("workers/",            "workers"),
    ("publishing/",         "publishing"),
    ("memory/",             "memory"),
    ("tools/",              "shared_tools"),
    ("config.py",           "core"),
    ("data/",               "core"),
    ("electron_backend.py", "core"),
    ("electron-app/",       "electron"),
    ("tests/",              "tests"),
]


def classify_domain(filepath: str) -> str:
    normalized = filepath.replace("\\", "/")
    for fragment, domain in PATH_TO_DOMAIN:
        if fragment in normalized:
            return domain
    return "other"


# ---------------------------------------------------------------------------
# Categorization
# ---------------------------------------------------------------------------

def categorize_var(var_name: str) -> str:
    """Categorize an env var by its naming pattern."""
    if var_name.endswith(("_KEY", "_SECRET", "_TOKEN", "_PASSWORD")):
        return "api_keys"
    if var_name.endswith(("_URL", "_HOST", "_PORT", "_URI")) or "_URL" in var_name:
        return "urls"
    if var_name.startswith("USE_") or var_name.endswith("_ENABLED"):
        return "feature_flags"
    if var_name.endswith(("_PATH", "_DIR", "_BINARY")):
        return "paths"
    return "settings"


def is_model_var(var_name: str) -> bool:
    """Check if this is a model-related var (handled by LLM scanner)."""
    return bool(MODEL_VAR_RE.search(var_name))


# ---------------------------------------------------------------------------
# Scanning
# ---------------------------------------------------------------------------

def scan_file(filepath: Path, root: Path) -> list:
    """Scan a file for env var references. Returns list of dicts."""
    results = []
    rel = str(filepath.relative_to(root))
    suffix = filepath.suffix

    try:
        content = filepath.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return results

    for i, line in enumerate(content.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("#") and suffix == ".py":
            continue

        if suffix == ".py":
            for pattern in PY_GETENV:
                for m in pattern.finditer(line):
                    var_name = m.group(1)
                    default = m.group(2) if m.lastindex >= 2 else None
                    if not is_model_var(var_name):
                        results.append({
                            "var": var_name,
                            "default": default,
                            "file": rel,
                            "line": i,
                        })

            for m in PYDANTIC_ENV.finditer(line):
                var_name = m.group(1)
                if not is_model_var(var_name):
                    results.append({
                        "var": var_name,
                        "default": None,
                        "file": rel,
                        "line": i,
                    })

        if suffix == ".js":
            for m in JS_ENV.finditer(line):
                var_name = m.group(1)
                if not is_model_var(var_name):
                    results.append({
                        "var": var_name,
                        "default": None,
                        "file": rel,
                        "line": i,
                    })

    return results


def scan_codebase(root: Path) -> list:
    all_results = []
    for ext in SCAN_EXTENSIONS:
        for filepath in root.rglob(f"*{ext}"):
            if any(skip in filepath.parts for skip in SKIP_DIRS):
                continue
            all_results.extend(scan_file(filepath, root))
    return all_results


# ---------------------------------------------------------------------------
# Grouping & Output
# ---------------------------------------------------------------------------

def deduplicate(results: list) -> dict:
    """Deduplicate and group by var name, keeping domain + default info."""
    vars_info = {}
    for r in results:
        var = r["var"]
        if var not in vars_info:
            vars_info[var] = {
                "var": var,
                "default": r["default"],
                "category": categorize_var(var),
                "locations": [],
                "domains": set(),
            }
        vars_info[var]["locations"].append(f"{r['file']}:{r['line']}")
        vars_info[var]["domains"].add(classify_domain(r["file"]))
        if r["default"] and not vars_info[var]["default"]:
            vars_info[var]["default"] = r["default"]
    return vars_info


def group_by_domain(vars_info: dict) -> dict:
    """Group vars by their primary domain."""
    grouped = defaultdict(list)
    for var_data in vars_info.values():
        # Pick primary domain (first non-test, non-other)
        domains = var_data["domains"]
        primary = "core"
        for d in sorted(domains):
            if d not in ("tests", "other"):
                primary = d
                break
        grouped[primary].append(var_data)
    return dict(sorted(grouped.items()))


def write_per_space_service_configs(grouped: dict, configs_dir: Path):
    """Write per-domain service config YAML files to configs/services/."""
    svc_dir = configs_dir / "services"
    svc_dir.mkdir(parents=True, exist_ok=True)

    for domain, var_list in sorted(grouped.items()):
        # Sort vars into categories
        categories = defaultdict(list)
        for v in sorted(var_list, key=lambda x: x["var"]):
            categories[v["category"]].append(v)

        lines = [
            f"# {domain} — Service Configuration",
            "# Auto-generated by scan-service-vars. Re-run to update.",
            "",
        ]

        cat_order = ["api_keys", "urls", "feature_flags", "paths", "settings"]
        for cat in cat_order:
            if cat not in categories:
                continue
            lines.append(f"{cat}:")
            for v in categories[cat]:
                lines.append(f'  - var: "{v["var"]}"')
                if v["default"]:
                    lines.append(f'    default: "{v["default"]}"')
                locs = v["locations"][:3]
                if len(locs) == 1:
                    lines.append(f'    location: "{locs[0]}"')
                else:
                    lines.append("    locations:")
                    for loc in locs:
                        lines.append(f'      - "{loc}"')
                    if len(v["locations"]) > 3:
                        lines.append(f'      # +{len(v["locations"])-3} more')
                lines.append("")
            lines.append("")

        filename = domain.lower().replace(" ", "_") + ".yml"
        (svc_dir / filename).write_text("\n".join(lines), encoding="utf-8")

    return svc_dir


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Scan for service env vars (non-model)")
    parser.add_argument("--root", default=".", help="Project root directory")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--configs-dir", type=str, default=None,
                        help="Write per-space service configs to dir")
    args = parser.parse_args()

    root = Path(args.root).resolve()

    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    results = scan_codebase(root)
    vars_info = deduplicate(results)
    grouped = group_by_domain(vars_info)

    if args.configs_dir:
        configs_path = root / args.configs_dir
        svc_dir = write_per_space_service_configs(grouped, configs_path)
        files = list(svc_dir.glob("*.yml"))
        print(f"Written {len(files)} service config files to {svc_dir}")
        for f in sorted(files):
            print(f"  {f.name}")
    elif args.json:
        # Serialize sets to lists
        serializable = {}
        for domain, var_list in grouped.items():
            serializable[domain] = []
            for v in var_list:
                entry = dict(v)
                entry["domains"] = sorted(entry["domains"])
                serializable[domain].append(entry)
        print(json.dumps({"total_vars": len(vars_info), "by_domain": serializable},
                          indent=2, default=str))
    else:
        sep = "=" * 60
        print(f"\n{sep}")
        print(f"  SERVICE ENV VAR SCAN")
        print(f"{sep}")
        print(f"  Total vars: {len(vars_info)}")
        print(f"  Domains: {len(grouped)}")
        for domain, var_list in sorted(grouped.items()):
            print(f"\n  [{domain.upper()}] ({len(var_list)} vars)")
            print(f"  {'-'*40}")
            for v in sorted(var_list, key=lambda x: x["var"]):
                default = f" = {v['default']}" if v["default"] else ""
                print(f"    [{v['category']}] {v['var']}{default}")
        print(f"\n{sep}\n")


if __name__ == "__main__":
    main()
