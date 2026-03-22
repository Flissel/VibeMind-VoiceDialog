# VibeMind Config Output

Auto-generated per-space configuration files.
Last generated: 2026-03-10 14:09

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
