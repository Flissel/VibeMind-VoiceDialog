#!/usr/bin/env python3
"""
Generate per-space config files for VibeMind.

Runs both the LLM model scanner and the service var scanner,
writing YAML configs to a configs/ output directory.

Usage:
    python generate_configs.py --root /path/to/project --output configs
"""

import argparse
import subprocess
import sys
from pathlib import Path
from datetime import datetime

SCRIPTS_DIR = Path(__file__).parent


def run_scanner(script_name: str, root: str, configs_dir: str) -> bool:
    """Run a scanner script with --configs-dir."""
    script = SCRIPTS_DIR / script_name
    cmd = [sys.executable, str(script), "--root", root, "--configs-dir", configs_dir]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.stdout:
        print(result.stdout, end="")
    if result.returncode != 0:
        print(f"ERROR running {script_name}:", file=sys.stderr)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        return False
    return True


def write_readme(configs_dir: Path):
    """Generate configs/README.md."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    content = f"""# VibeMind Config Output

Auto-generated per-space configuration files.
Last generated: {now}

## Structure

```
configs/
├── llm/          # LLM model configs per space
│   ├── voice.yml
│   ├── orchestrator.yml
│   ├── ideas.yml
│   └── ...
├── services/     # Service env vars per space
│   ├── core.yml
│   ├── minibook.yml
│   ├── rowboat.yml
│   └── ...
└── README.md
```

## Regenerate

```bash
python .claude/plugins/vibemind-tools/skills/scan-llm/scripts/generate_configs.py --root . --output configs
```

## LLM Configs (`configs/llm/`)

Each file lists all LLM models used by that space/domain:
- `model` — The model identifier (e.g. `anthropic/claude-sonnet-4`)
- `env_var` — Environment variable to override the default
- `provider` — Detected provider (OpenRouter, Anthropic, OpenAI, etc.)
- `location` — Source file and line number

## Service Configs (`configs/services/`)

Each file lists non-model env vars grouped by category:
- `api_keys` — API keys, secrets, tokens
- `urls` — Service URLs, hosts, ports
- `feature_flags` — Boolean toggles (`USE_*`, `*_ENABLED`)
- `paths` — File system paths
- `settings` — Thresholds, timeouts, other config
"""
    (configs_dir / "README.md").write_text(content, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Generate per-space config files")
    parser.add_argument("--root", default=".", help="Project root directory")
    parser.add_argument("--output", default="configs", help="Output directory (default: configs)")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    configs_dir = root / args.output

    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    sep = "=" * 50
    print(f"\n{sep}")
    print(f"  VibeMind Config Generator")
    print(f"{sep}\n")

    print("Phase 1: Scanning LLM models...")
    ok1 = run_scanner("scan_llm_models.py", str(root), args.output)

    print("\nPhase 2: Scanning service vars...")
    ok2 = run_scanner("scan_service_vars.py", str(root), args.output)

    print("\nPhase 3: Writing README...")
    write_readme(configs_dir)
    print(f"  Written configs/README.md")

    # Summary
    llm_files = list((configs_dir / "llm").glob("*.yml")) if (configs_dir / "llm").exists() else []
    svc_files = list((configs_dir / "services").glob("*.yml")) if (configs_dir / "services").exists() else []

    print(f"\n{sep}")
    print(f"  DONE")
    print(f"{sep}")
    print(f"  LLM configs:     {len(llm_files)} files in {configs_dir / 'llm'}")
    print(f"  Service configs:  {len(svc_files)} files in {configs_dir / 'services'}")
    print(f"  README:           {configs_dir / 'README.md'}")

    if not ok1 or not ok2:
        print("\n  WARNING: Some scanners had errors")
        sys.exit(1)

    print(f"\n{sep}\n")


if __name__ == "__main__":
    main()