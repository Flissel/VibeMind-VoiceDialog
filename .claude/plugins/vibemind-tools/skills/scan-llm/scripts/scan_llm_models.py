#!/usr/bin/env python3
"""
Scan VibeMind codebase for LLM model references and write a YAML inventory.

Finds model= assignments, os.getenv() model vars, OpenRouter/OpenAI/Anthropic
model strings, YAML model configs, and hardcoded model names.

Usage:
    python scan_llm_models.py [--root /path/to/project]
    python scan_llm_models.py [--root /path/to/project] --json
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

# Known model name pattern (provider/model or plain model id)
MODEL_NAME_RE = re.compile(
    r"""(?:['"])"""
    r"""((?:anthropic|openai|google|meta-llama|mistralai|deepseek|nvidia|"""
    r"""qwen|xiaomi|allenai|SakanaAI|openrouter)"""
    r"""/[\w.:_-]+"""          # provider/model
    r"""|gpt-[\w.:_-]+"""      # gpt-4o, gpt-4o-mini, gpt-4.1, gpt-5.2-codex
    r"""|claude-[\w.:_-]+"""   # claude-sonnet-4, claude-haiku-4.5
    r"""|gemini-[\w.:_-]+"""   # gemini-1.5-flash, gemini-2.0-flash
    r"""|o1-[\w.:_-]+"""       # o1-2024-12-17
    r"""|llama[\w.:_-]+"""     # llama3.1:8b
    r"""|qwen[\w.:_-]+"""      # qwen2.5-coder:7b
    r"""|grok-[\w.:_-]+"""     # grok-2-latest
    r"""|text-embedding-[\w.:_-]+"""  # text-embedding-3-small
    r"""|all-(?:MiniLM|mpnet)[\w.:_-]+""" # sentence-transformers
    r""")"""
    r"""(?:['"])""",
    re.VERBOSE,
)

# Env var patterns for model overrides (single-line os.getenv/os.environ)
ENV_MODEL_RE = re.compile(
    r"""os\.(?:getenv|environ\.get)\s*\(\s*['"]"""
    r"""([A-Z_]*MODEL[A-Z_]*)['"]"""
    r"""(?:\s*,\s*['"]([^'"]+)['"])?"""  # optional default
)

# os.environ["VAR"] (bracket access, no parenthesis)
ENV_BRACKET_RE = re.compile(
    r"""os\.environ\[['"]([A-Z_]*MODEL[A-Z_]*)['"]"""
)

# Standalone quoted MODEL env var name (catches multiline getenv, Pydantic Field(env=), etc.)
STANDALONE_MODEL_VAR_RE = re.compile(
    r"""['"]([A-Z][A-Z0-9_]*MODEL[A-Z0-9_]*)['"]"""
)

# JS env model pattern
JS_ENV_MODEL_RE = re.compile(
    r"""process\.env\.([A-Z_]*MODEL[A-Z_]*)"""
)

# YAML model keys
YAML_MODEL_RE = re.compile(
    r"""^\s*([\w_-]*model[\w_-]*)\s*:\s*['"]?([^\s'"#]+)""",
    re.IGNORECASE | re.MULTILINE,
)

# Skip directories
SKIP_DIRS = {
    "__pycache__", "node_modules", ".git", ".venv", "venv", ".venv312",
    "dist", "build", ".eggs", ".claude", "dashboard",
}

# File extensions to scan
SCAN_EXTENSIONS = {".py", ".js", ".ts", ".json", ".yml", ".yaml"}

# ---------------------------------------------------------------------------
# Domain classification (reuse from sync-env)
# ---------------------------------------------------------------------------

PATH_TO_DOMAIN = [
    ("spaces/ideas",        "Ideas"),
    ("spaces/coding",       "Coding"),
    ("spaces/desktop",      "Desktop"),
    ("spaces/rowboat",      "Rowboat"),
    ("spaces/research",     "Research"),
    ("spaces/minibook",     "Minibook"),
    ("spaces/schedule",     "Schedule"),
    ("spaces/shuttles",     "Shuttles"),
    ("spaces/roarboot",     "Rowboat"),
    ("spaces/brain",        "Brain"),
    ("voice/",              "Voice"),
    ("swarm/orchestrator",  "Orchestrator"),
    ("swarm/broadcast",     "Broadcast"),
    ("swarm/conversion",    "Conversion"),
    ("swarm/stream_listener", "StreamListener"),
    ("swarm/space_agents",  "SpaceAgents"),
    ("swarm/agents",        "SwarmAgents"),
    ("swarm/logging",       "Logging"),
    ("swarm/",              "Swarm"),
    ("workers/",            "Workers"),
    ("publishing/",         "Publishing"),
    ("tools/",              "SharedTools"),
    ("config.py",           "Core"),
    ("data/",               "Data"),
    ("electron_backend.py", "Core"),
    ("electron-app/",       "Electron"),
    ("external/",           "External"),
    ("tests/",              "Tests"),
]


def classify_domain(filepath: str) -> str:
    normalized = filepath.replace("\\", "/")
    for fragment, domain in PATH_TO_DOMAIN:
        if fragment in normalized:
            return domain
    return "Other"


# ---------------------------------------------------------------------------
# Scanning
# ---------------------------------------------------------------------------

def scan_file(filepath: Path, root: Path) -> list:
    """Scan a single file for LLM model references. Returns list of dicts."""
    results = []
    rel = str(filepath.relative_to(root))

    try:
        content = filepath.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return results

    suffix = filepath.suffix

    for i, line in enumerate(content.splitlines(), 1):
        # Skip comments
        stripped = line.strip()
        if stripped.startswith("#") and suffix in (".py", ".yml", ".yaml"):
            # Still scan YAML comments for model refs
            if suffix not in (".yml", ".yaml"):
                continue

        # Model name literals
        for m in MODEL_NAME_RE.finditer(line):
            results.append({
                "model": m.group(1),
                "file": rel,
                "line": i,
                "env_var": None,
                "context": stripped[:120],
            })

        # Python env var model references
        if suffix == ".py":
            for m in ENV_MODEL_RE.finditer(line):
                results.append({
                    "model": m.group(2) or "?",
                    "file": rel,
                    "line": i,
                    "env_var": m.group(1),
                    "context": stripped[:120],
                })
            for m in ENV_BRACKET_RE.finditer(line):
                results.append({
                    "model": "?",
                    "file": rel,
                    "line": i,
                    "env_var": m.group(1),
                    "context": stripped[:120],
                })
            # Catch standalone MODEL var names (multiline getenv, Pydantic Field(env=), etc.)
            for m in STANDALONE_MODEL_VAR_RE.finditer(line):
                var_name = m.group(1)
                # Skip if already captured by ENV_MODEL_RE
                if not ENV_MODEL_RE.search(line) or var_name not in [
                    em.group(1) for em in ENV_MODEL_RE.finditer(line)
                ]:
                    results.append({
                        "model": "?",
                        "file": rel,
                        "line": i,
                        "env_var": var_name,
                        "context": stripped[:120],
                    })

        # JS env var model references
        if suffix in (".js", ".ts"):
            for m in JS_ENV_MODEL_RE.finditer(line):
                results.append({
                    "model": "?",
                    "file": rel,
                    "line": i,
                    "env_var": m.group(1),
                    "context": stripped[:120],
                })

    # YAML model keys
    if suffix in (".yml", ".yaml"):
        for m in YAML_MODEL_RE.finditer(content):
            line_num = content[:m.start()].count("\n") + 1
            results.append({
                "model": m.group(2),
                "file": rel,
                "line": line_num,
                "env_var": None,
                "context": f"{m.group(1)}: {m.group(2)}",
            })

    return results


def scan_codebase(root: Path) -> list:
    """Scan all relevant files in the codebase."""
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

def group_by_domain(results: list) -> dict:
    """Group results by domain."""
    grouped = defaultdict(list)
    for r in results:
        domain = classify_domain(r["file"])
        grouped[domain].append(r)
    return dict(sorted(grouped.items()))


def deduplicate(results: list) -> list:
    """Remove duplicate model refs at same file:line, merging env_var info."""
    # First pass: merge env_var into entries at the same file:line
    env_by_loc = {}
    for r in results:
        if r.get("env_var"):
            loc_key = (r["file"], r["line"])
            env_by_loc[loc_key] = r["env_var"]

    # Apply env_var to all entries at same location
    for r in results:
        if not r.get("env_var"):
            loc_key = (r["file"], r["line"])
            if loc_key in env_by_loc:
                r["env_var"] = env_by_loc[loc_key]

    # Deduplicate, preferring entries with actual model names over "?"
    best = {}
    for r in results:
        key = (r["file"], r["line"], r.get("env_var", ""))
        if key not in best:
            best[key] = r
        elif best[key]["model"] == "?" and r["model"] != "?":
            best[key] = r

    # Also deduplicate by (model, file, line) to avoid double entries
    seen = set()
    deduped = []
    for r in best.values():
        dedup_key = (r["model"], r["file"], r["line"])
        if dedup_key not in seen:
            seen.add(dedup_key)
            deduped.append(r)
    return deduped


def build_yaml_output(grouped: dict) -> str:
    """Build YAML string from grouped results."""
    lines = ["# VibeMind LLM Model Inventory (auto-generated)", "# Run scan again to update", ""]

    for domain, refs in sorted(grouped.items()):
        lines.append(f"{domain}:")
        # Group by model within domain
        by_model = defaultdict(list)
        for r in refs:
            by_model[r["model"]].append(r)

        for model, entries in sorted(by_model.items()):
            lines.append(f"  - model: \"{model}\"")
            if entries[0].get("env_var"):
                lines.append(f"    env_var: \"{entries[0]['env_var']}\"")
            locations = [f"{e['file']}:{e['line']}" for e in entries]
            if len(locations) == 1:
                lines.append(f"    location: \"{locations[0]}\"")
            else:
                lines.append(f"    locations:")
                for loc in locations[:5]:
                    lines.append(f"      - \"{loc}\"")
                if len(locations) > 5:
                    lines.append(f"      # ... +{len(locations)-5} more")
        lines.append("")

    return "\n".join(lines)


SKIP_MODELS = {
    "claude-runner", "claude-runner-status", "claude-runner:latest", "claude-code",
    "gpt-researcher", "gpt-researcher-mcp", "llama_index.core",
    "llama_index.vector_stores.qdrant", "gemini-image", "primary:", "type:",
}

SKIP_ENV = {"MODEL_TEMPERATURE", "ARCH_MODEL_CONTEXT_MAX", "DEFAULT_MODEL"}


def detect_provider(model: str) -> str:
    """Detect LLM provider from model string."""
    prefixes = {
        "anthropic/": "OpenRouter", "openai/": "OpenRouter", "google/": "OpenRouter",
        "meta-llama/": "OpenRouter", "mistralai/": "OpenRouter", "nvidia/": "OpenRouter",
        "qwen/": "OpenRouter", "xiaomi/": "OpenRouter", "deepseek/": "OpenRouter",
        "allenai/": "OpenRouter", "openrouter/": "OpenRouter",
        "SakanaAI/": "HuggingFace", "Qwen/": "HuggingFace",
    }
    for prefix, provider in prefixes.items():
        if model.startswith(prefix):
            return provider
    starts = {
        "claude-": "Anthropic", "gpt-": "OpenAI", "o1-": "OpenAI", "o3-": "OpenAI",
        "gemini-": "Google", "llama": "Ollama", "qwen": "Ollama", "grok-": "Grok",
        "text-embedding-": "OpenAI", "all-MiniLM": "sentence-transformers",
        "all-mpnet": "sentence-transformers",
    }
    for prefix, provider in starts.items():
        if model.startswith(prefix):
            return provider
    return "Unknown"


def is_valid_model(model: str) -> bool:
    """Check if a model string is a real model (not a false positive)."""
    if model == "?" or model in SKIP_MODELS:
        return False
    if model.startswith("^") or (len(model) > 0 and model[0].isdigit() and ":" not in model[:5]):
        return False
    return True


def write_per_space_llm_configs(grouped: dict, configs_dir: Path):
    """Write per-domain LLM config YAML files to configs/llm/."""
    llm_dir = configs_dir / "llm"
    llm_dir.mkdir(parents=True, exist_ok=True)

    for domain, refs in sorted(grouped.items()):
        by_model = defaultdict(list)
        env_overrides = []
        for r in refs:
            if is_valid_model(r["model"]):
                by_model[r["model"]].append(r)
            elif r["model"] == "?" and r.get("env_var") and r["env_var"] not in SKIP_ENV:
                env_overrides.append(r)

        if not by_model and not env_overrides:
            continue

        lines = [
            f"# {domain} — LLM Models",
            "# Auto-generated by scan-llm. Re-run to update.",
            "",
            "models:",
        ]

        for model in sorted(by_model.keys()):
            entries = by_model[model]
            provider = detect_provider(model)
            env_var = next((e["env_var"] for e in entries if e.get("env_var") and e["env_var"] not in SKIP_ENV), None)
            locations = sorted(set(f"{e['file']}:{e['line']}" for e in entries))

            lines.append(f'  - model: "{model}"')
            if env_var:
                lines.append(f'    env_var: "{env_var}"')
            lines.append(f'    provider: "{provider}"')
            if len(locations) == 1:
                lines.append(f'    location: "{locations[0]}"')
            else:
                lines.append("    locations:")
                for loc in locations[:8]:
                    lines.append(f'      - "{loc}"')
                if len(locations) > 8:
                    lines.append(f"      # +{len(locations)-8} more")
            lines.append("")

        seen_env = set()
        for r in env_overrides:
            ev = r["env_var"]
            if ev not in seen_env:
                seen_env.add(ev)
                lines.append(f'  - env_var: "{ev}"')
                lines.append('    model: null  # set via environment')
                lines.append(f'    location: "{r["file"]}:{r["line"]}"')
                lines.append("")

        filename = domain.lower().replace(" ", "_") + ".yml"
        (llm_dir / filename).write_text("\n".join(lines), encoding="utf-8")

    return llm_dir


def print_report(grouped: dict, total: int):
    """Print human-readable report."""
    sep = "=" * 60
    print(f"\n{sep}")
    print(f"  LLM MODEL SCAN REPORT")
    print(f"{sep}")
    print(f"  Total model references: {total}")
    print(f"  Domains: {len(grouped)}")

    unique_models = set()
    unique_env_vars = set()
    for refs in grouped.values():
        for r in refs:
            if r["model"] != "?":
                unique_models.add(r["model"])
            if r.get("env_var"):
                unique_env_vars.add(r["env_var"])

    print(f"  Unique models: {len(unique_models)}")
    print(f"  Model env vars: {len(unique_env_vars)}")

    for domain, refs in sorted(grouped.items()):
        models_in_domain = set(r["model"] for r in refs if r["model"] != "?")
        print(f"\n  [{domain.upper()}] ({len(models_in_domain)} unique models, {len(refs)} refs)")
        print(f"  {'-'*40}")
        by_model = defaultdict(list)
        for r in refs:
            by_model[r["model"]].append(r)
        for model, entries in sorted(by_model.items()):
            env = f" (${entries[0]['env_var']})" if entries[0].get("env_var") else ""
            print(f"    {model}{env}")
            for e in entries[:2]:
                print(f"      -> {e['file']}:{e['line']}")
            if len(entries) > 2:
                print(f"      -> ... +{len(entries)-2} more")

    print(f"\n{sep}\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Scan for LLM model references")
    parser.add_argument("--root", default=".", help="Project root directory")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--yaml", type=str, default=None,
                        help="Write YAML inventory to file (e.g. --yaml llm_inventory.yml)")
    parser.add_argument("--configs-dir", type=str, default=None,
                        help="Write per-space LLM configs to dir (e.g. --configs-dir configs)")
    args = parser.parse_args()

    root = Path(args.root).resolve()

    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    results = scan_codebase(root)
    results = deduplicate(results)
    grouped = group_by_domain(results)

    if args.configs_dir:
        configs_path = root / args.configs_dir
        llm_dir = write_per_space_llm_configs(grouped, configs_path)
        files = list(llm_dir.glob("*.yml"))
        print(f"Written {len(files)} LLM config files to {llm_dir}")
        for f in sorted(files):
            print(f"  {f.name}")
    elif args.json:
        print(json.dumps({"total": len(results), "by_domain": grouped}, indent=2, default=str))
    elif args.yaml:
        yaml_path = root / args.yaml
        yaml_content = build_yaml_output(grouped)
        yaml_path.write_text(yaml_content, encoding="utf-8")
        print(f"Written {len(results)} model refs to {yaml_path}")
    else:
        print_report(grouped, len(results))


if __name__ == "__main__":
    main()
