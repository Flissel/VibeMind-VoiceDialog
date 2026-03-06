# Git Submodules

VibeMind includes 6 external repositories as git submodules. Each powers a specific space or feature.

## Submodule Map

| Submodule | Path | Space | Purpose |
|-----------|------|-------|---------|
| **Coding_engine** | `python/spaces/coding/Coding_engine/` | Coding | AI code generation engine |
| **Automation_ui** | `python/spaces/desktop/Automation_ui/` | Desktop | Desktop automation GUI |
| **Rowboat** | `python/spaces/rowboat/rowboat/` | Rowboat | Knowledge graph + RAG engine |
| **SWE Design** | `python/spaces/shuttles/swe_desgine/` | Shuttles | Requirements validation pipeline |
| **ZeroClaw** | `external/zeroclaw/` | Research | Web scraping + research engine |
| **Minibook** | `external/minibook/` | Minibook | Inter-space collaboration platform |

## Cloning

```bash
# Clone everything
git clone --recursive https://github.com/Flissel/VibeMind-VoiceDialog.git

# Or init after cloning
git submodule update --init --recursive
```

## Updating Submodules

```bash
# Update all to latest
git submodule update --remote --merge

# Update specific submodule
cd python/spaces/coding/Coding_engine
git pull origin main
cd ../../../..
git add python/spaces/coding/Coding_engine
git commit -m "Update Coding_engine submodule"
```

## What Happens Without Submodules

VibeMind degrades gracefully when submodules are missing:

| Missing Submodule | Impact |
|-------------------|--------|
| Coding_engine | `code.generate` returns error; other spaces work |
| Automation_ui | Desktop tools still work via pyautogui; no GUI |
| Rowboat | Rowboat space unavailable; other spaces work |
| SWE Design | Shuttle pipeline unavailable |
| ZeroClaw | Research space unavailable |
| Minibook | Inter-space collaboration unavailable |

**Core functionality (Ideas, voice, 3D UI) always works without any submodules.**

## Submodule-Specific Configuration

### Coding_engine
```bash
CODING_ENGINE_PATH=python/spaces/coding/Coding_engine  # Auto-detected
VNC_BASE_URL=https://preview.vibemind.io/vnc
```

### Rowboat
Requires Docker for the knowledge graph backend:
```bash
cd python/spaces/rowboat/rowboat
docker compose up
```

### Minibook
```bash
USE_MINIBOOK_HUB=true
# Docker Compose available at docker-compose.minibook.yml
```

### ZeroClaw

> **Note:** The ZeroClaw submodule is empty by default. Initialize with:
> ```bash
> git submodule update --init external/zeroclaw
> ```

```bash
USE_ZEROCLAW=true
```
