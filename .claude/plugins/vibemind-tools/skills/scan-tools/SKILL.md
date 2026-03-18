---
name: scan-tools
description: >
  Scan codebase for vibe coding tool integrations — CLI tools (Claude CLI, Kilo CLI, Codex, Aider),
  SDKs (Anthropic, OpenAI, Google AI), agent frameworks (AutoGen, LangChain, CrewAI),
  MCP servers, and services (OpenRouter, Supermemory, n8n).
  Use when asked to "scan coding tools", "find all tools", "which CLIs are used",
  "tool inventory", "MCP servers", "vibe coding tools", "scan integrations",
  "welche tools", "tool overview".
---

# scan-tools — Vibe Coding Tools Scanner

Scans the VibeMind repo for all AI coding tool integrations and generates structured output.

## What it detects

| Category | Tools |
|----------|-------|
| **CLI Tools** | Claude CLI, Kilo Code CLI, Codex CLI, Aider |
| **SDKs** | Anthropic SDK, OpenAI SDK, Google AI SDK |
| **Agent Frameworks** | AutoGen 0.4+, LangChain/LangGraph, CrewAI |
| **Protocols** | MCP (Model Context Protocol) — servers, configs |
| **Services** | OpenRouter, Supermemory, n8n |

## How to run

```bash
# Console report
cd /path/to/VibeMind-VoiceDialog
python .claude/plugins/vibemind-tools/skills/scan-tools/scripts/scan_coding_tools.py

# JSON output
python .claude/plugins/vibemind-tools/skills/scan-tools/scripts/scan_coding_tools.py --json

# Full YAML inventory
python .claude/plugins/vibemind-tools/skills/scan-tools/scripts/scan_coding_tools.py --yaml TOOLS_SCAN.md

# Per-space config files (→ configs/tools/*.yml)
python .claude/plugins/vibemind-tools/skills/scan-tools/scripts/scan_coding_tools.py --configs-dir configs
```

## Instructions for Claude

When the user triggers this skill:

1. Run the scanner from the project root:
   ```bash
   cd <project_root>
   python .claude/plugins/vibemind-tools/skills/scan-tools/scripts/scan_coding_tools.py --root .
   ```

2. If the user wants a file output, use `--yaml TOOLS_SCAN.md` or `--configs-dir configs`.

3. If the user wants per-space configs alongside LLM/service configs, run:
   ```bash
   python .claude/plugins/vibemind-tools/skills/scan-tools/scripts/scan_coding_tools.py --root . --configs-dir configs
   ```

4. Report the results: which tools are found, which are not, and in which domains they appear.

## Detection methods

- **subprocess**: CLI tool invocations via `subprocess.run/Popen`
- **import**: Python/JS SDK imports
- **config**: Environment variables, config patterns
- **dependency**: Entries in `requirements.txt`, `package.json`
- **file_marker**: Config files like `.mcp.json`, `CLAUDE.md`, `.kilocode/`
- **mcp_server**: Individual MCP server directories in `mcp_plugins/servers/`
