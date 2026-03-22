---
name: scan-llm
description: This skill should be used when the user asks to "scan LLM models", "find all models", "LLM inventory", "generate configs", "update config files", "which models are used", "list all LLMs", "model overview", "service config", or mentions auditing or tracking LLM and service configuration across the codebase.
---

# Scan LLM Models & Generate Configs

Scan the VibeMind codebase for all LLM model references and service env vars, then produce per-space YAML config files.

## Safety Rules

**Read-only scan.** The scanners make no code changes. They only write to the output directory (`configs/`) or inventory files.

## Workflow

### 1. Generate Per-Space Configs (Primary)

Run the config generator to produce `configs/llm/*.yml` and `configs/services/*.yml`:

```bash
python .claude/plugins/vibemind-tools/skills/scan-llm/scripts/generate_configs.py --root . --output configs
```

This runs both scanners and writes:
- `configs/llm/{domain}.yml` — LLM models per space (model, env_var, provider, location)
- `configs/services/{domain}.yml` — Service vars per space (api_keys, urls, feature_flags, settings)
- `configs/README.md` — Documentation

### 2. Individual Scanners

For standalone use:

```bash
# LLM models only — human-readable report
python .claude/plugins/vibemind-tools/skills/scan-llm/scripts/scan_llm_models.py --root .

# LLM models — JSON output
python .claude/plugins/vibemind-tools/skills/scan-llm/scripts/scan_llm_models.py --root . --json

# LLM models — per-space YAML configs
python .claude/plugins/vibemind-tools/skills/scan-llm/scripts/scan_llm_models.py --root . --configs-dir configs

# Service vars — per-space YAML configs
python .claude/plugins/vibemind-tools/skills/scan-llm/scripts/scan_service_vars.py --root . --configs-dir configs

# Service vars — JSON output
python .claude/plugins/vibemind-tools/skills/scan-llm/scripts/scan_service_vars.py --root . --json
```

### 3. Cross-Reference

Compare scanner output against:
- `LLM_INVENTORY.md` — manually curated LLM overview
- `LLM_SCAN.md` — auto-generated model scan
- `.env.example` — documented environment variables

## What Gets Scanned

### LLM Scanner (`scan_llm_models.py`)

| Pattern | Language | Example |
|---------|----------|---------|
| Model name literals | Python/JS/TS | `"anthropic/claude-sonnet-4"` |
| `os.getenv("*MODEL*")` | Python | `os.getenv("CLASSIFIER_MODEL", "claude-3.5-haiku")` |
| Standalone `"*MODEL*"` strings | Python | `Field(env="VISION_MODEL")` |
| `process.env.*MODEL*` | JavaScript | `process.env.ROWBOAT_MODEL` |
| YAML `*model*:` keys | YAML | `model: claude-sonnet-4-6` |

### Service Scanner (`scan_service_vars.py`)

| Pattern | Language | Example |
|---------|----------|---------|
| `os.getenv("VAR")` | Python | `os.getenv("REDIS_URL", "localhost")` |
| `os.environ.get("VAR")` | Python | `os.environ.get("SUPABASE_KEY")` |
| `Field(env="VAR")` | Python | Pydantic config fields |
| `process.env.VAR` | JavaScript | `process.env.NODE_ENV` |

Service vars are categorized as: `api_keys`, `urls`, `feature_flags`, `paths`, `settings`.

## Scripts

- **`scripts/generate_configs.py`** — Wrapper that runs both scanners and writes `configs/` output
- **`scripts/scan_llm_models.py`** — LLM model scanner (`--json`, `--yaml`, `--configs-dir`)
- **`scripts/scan_service_vars.py`** — Service env var scanner (`--json`, `--configs-dir`)