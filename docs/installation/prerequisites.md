# Prerequisites

## Required

| Dependency | Version | Purpose |
|-----------|---------|---------|
| **Python** | 3.11+ | Backend, intent classification, tool execution |
| **Node.js** | 18+ | Electron app, renderer |
| **npm** | 9+ | Package management (comes with Node.js) |
| **Git** | 2.x | Source control, submodule management |
| **OpenAI API Key** | — | Voice (Realtime API) + intent classification |

## Optional

| Dependency | Version | Purpose | When Needed |
|-----------|---------|---------|-------------|
| **Redis** | 6+ | Async event processing | `FORCE_SYNC_MODE=false` |
| **CMake** | 3.16+ | C++ visual module build | Audio-reactive visuals |
| **vcpkg** | Latest | C++ package manager (Windows) | Audio-reactive visuals |
| **FFmpeg** | 4+ | Audio format conversion | Some audio pipelines |
| **Tesseract** | 5+ | OCR for desktop automation | Desktop space screenshot reading |
| **Docker** | 24+ | Coding engine containers | Coding space code generation |

## API Keys

| Service | Variable | Required | Purpose |
|---------|----------|----------|---------|
| OpenAI | `OPENAI_API_KEY` | Yes | Voice + LLM classification |
| OpenRouter | `OPENROUTER_API_KEY` | No | Alternative LLM provider |
| Supermemory | `SUPERMEMORY_API_KEY` | No | Semantic memory services |

## Git Submodules

The repo includes 6 submodules. Clone with `--recursive` to pull them:

```bash
git clone --recursive https://github.com/Flissel/VibeMind-VoiceDialog.git
```

Or init after cloning:

```bash
git submodule update --init --recursive
```

| Submodule | Path | Purpose |
|-----------|------|---------|
| Coding_engine | `python/spaces/coding/Coding_engine/` | Code generation engine |
| Automation_ui | `python/spaces/desktop/Automation_ui/` | Desktop automation UI |
| Rowboat | `python/spaces/rowboat/rowboat/` | Knowledge graph engine |
| SWE Design | `python/spaces/shuttles/swe_design/` | Requirements pipeline |
| ZeroClaw | `external/zeroclaw/` | Web research engine |
| Minibook | `external/minibook/` | Inter-space collaboration |

> **Note:** VibeMind works without submodules — the corresponding spaces will be unavailable but the core (Ideas, voice, UI) still functions.
