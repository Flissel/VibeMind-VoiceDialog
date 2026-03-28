# Installation Guide

Choose your platform:

- [Windows](windows.md) — Primary development platform, fully tested
- [macOS](macos.md) — Community-tested
- [Linux](linux.md) — Ubuntu/Debian and Fedora/RHEL
- [Docker](docker.md) — Containerized setup

## Quick Path (All Platforms)

```bash
git clone --recursive https://github.com/Flissel/VibeMind-VoiceDialog.git
cd VibeMind-VoiceDialog
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cd electron-app && npm install && cd ..
cp .env.example .env        # Edit with your OPENAI_API_KEY
cd electron-app && npm start
```

## Minimal vs Full Setup

| Mode | What You Need | Features |
|------|--------------|----------|
| **Minimal** | Python 3.11+, Node 18+, OpenAI key | Voice, Ideas space, basic intent routing |
| **Full** | + Redis, Supermemory key, submodules | All 15 spaces, memory, async mode, coding engine |

Set `FORCE_SYNC_MODE=true` in `.env` for minimal mode (no Redis required).

## Next Steps

- [Prerequisites](prerequisites.md) — All external dependencies explained
- [Troubleshooting](troubleshooting.md) — Common setup issues
- [Configuration](../configuration.md) — Environment variable reference
