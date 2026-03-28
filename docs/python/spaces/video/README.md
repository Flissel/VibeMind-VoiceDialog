# Video Space

> Video production pipeline with team videos, product demos, vision (Sora AI), lip sync (MuseTalk), and voice cloning (Chatterbox).

## Overview

The Video Space provides end-to-end video production capabilities through two Git submodules (`vibevideo` and `vibevideo_deepfake`) wrapped by a backend agent and Electron UI. Videos are tracked in SQLite and can be published to Rowboat as knowledge sources.

## Architecture

```
Voice / ClawPort Chat
        ↓
VideoBackendAgent (events:tasks:video)
        ↓
video_tools.py (_run_cli → submodule scripts)
   ├── vibevideo/        (team, demo, vision, sora)
   └── vibevideo_deepfake/ (lipsync, voice clone)
        ↓
VideoRepository + VideoProjectRepository (SQLite)
        ↓
Electron Video UI (wizard-based React app)
        ↓
media_server.py (localhost:9877, Range requests)
```

## Backend Agent

**File:** `python/spaces/video/agents/video_agent.py`
**Class:** `VideoBackendAgent`
**Stream:** `events:tasks:video`

### Event Types (11)

| Event | Tool | Description |
|-------|------|-------------|
| `video.status` | `video_status` | Check installed tools and submodules |
| `video.team_status` | `team_pipeline_status` | Available pipeline steps |
| `video.team_run` | `team_run_step` | Execute team video pipeline step |
| `video.vision` | `vision_generate` | Generate Her-style vision video (Sora AI) |
| `video.demo_analyze` | `demo_analyze` | Analyze screenrecording for demo |
| `video.demo_build` | `demo_build` | Build demo video from scene config |
| `video.lipsync` | `lipsync_run` | Run MuseTalk lip sync |
| `video.lipsync_analyze` | `lipsync_analyze` | Quality analysis on lip sync |
| `video.voice_clone` | `voice_clone` | Extract reference audio (Chatterbox) |
| `video.voice_tts` | `voice_tts` | Generate TTS voiceover per person |
| `video.publish` | `publish_videos_to_rowboat` | Publish videos to Rowboat knowledge graph |

### Parameter Mapping (German → English)

| Event | Mapping |
|-------|---------|
| `video.team_run` | schritt/stufe → step |
| `video.lipsync` | name/person → person |
| `video.voice_tts` | name/person → person |
| `video.demo_analyze` | datei/file/video → input_file, dauer → target_duration |
| `video.demo_build` | config/datei → config_path |

## Tools

**File:** `python/spaces/video/tools/video_tools.py` (506 lines)

All tools delegate to CLI scripts via `_run_cli()` with 600s timeout. Return format:

```python
{"success": bool, "message": str, "stdout": str, "stderr": str, "exit_code": int}
```

### Tool Categories

**Team Video Pipeline** (6 steps: analyze → backgrounds → composite → build → split → final)

- `team_pipeline_status()` — List available steps
- `team_run_step(step='all')` — Execute one or all steps

**Vision / Sora AI**

- `vision_generate(**kwargs)` — Generate Her-style vision videos; modes: `--generate-sora`, `--generate-tts`, `--build-only`

**Product Demo**

- `demo_analyze(input_file, target_duration=60)` — Analyze screenrecording
- `demo_build(config_path)` — Build demo from scene config

**Lip Sync (MuseTalk)**

- `lipsync_run(person=None)` — Run lip sync, optionally filter by person
- `lipsync_analyze()` — Quality analysis

**Voice**

- `voice_clone()` — Extract reference audio for Chatterbox cloning (local)
- `voice_tts(person=None)` — Generate TTS voiceover

**Gallery & Projects**

- `scan_video_outputs()` — List videos from DB (fallback: filesystem scan)
- `import_videos(source_dir)` — Import videos with auto-detection (person, stage, category)
- `create_video_project(name, description)` — Create production project
- `add_project_person(project_id, name, role, raw_video_path)` — Add person with pipeline init
- `list_video_projects()` — List all projects
- `get_project_pipeline(project_id)` — Full pipeline matrix
- `get_reference_pipeline()` — Reference pipeline (Surya's template)
- `run_pipeline_step(project_id, person_name, step_name)` — Execute step, track status

**Publishing**

- `publish_videos_to_rowboat()` — Publish all DB videos to Rowboat (MongoDB → filesystem fallback)

## Data Layer

### VideoRepository (`python/data/video_repository.py`)

CRUD for video assets. Auto-detects person, stage, category from file paths.

**Known Persons:** Felix, Lisa, Moritz, Steffen, Stefan, Stephane, Surya

### VideoProjectRepository (`python/data/video_project_repository.py`)

Project + pipeline tracking. 10-step pipeline per person:

```
raw → analyze → voice_clone → transcript → tts → lipsync → background → composite → build → final
```

Steps are per-person (raw through composite) or group (build, final).

**Tables:** `video_projects`, `video_project_persons`, `video_pipeline_steps`

## Electron UI

| Component | File |
|-----------|------|
| BrowserView Manager | `electron-app/video-manager.js` |
| Preload (IPC API) | `electron-app/video-preload.js` |
| React App | `electron-app/video-ui/src/features/VideoProduction.tsx` |
| Types | `electron-app/video-ui/src/types.ts` |

### UI Features

- **Quick Action Grid** — 5 wizard cards: Team, Vision, Demo, Lipsync, Voice
- **Wizard System** — Step-by-step modals (choice → input → progress → done)
- **Project Pipeline Matrix** — Persons x Steps grid with status badges
- **Video Gallery** — Browse, filter, play, delete videos (auto-refresh 30s)
- **Media Server** — `localhost:9877` for video streaming with Range requests

### IPC API (`window.vibemindVideo`)

Video tools, gallery, project management, and publish methods. See `video-preload.js` for full list.

## Submodules

| Submodule | Path | Purpose |
|-----------|------|---------|
| vibevideo | `python/spaces/video/vibevideo/` | Team video pipeline, product demos, Sora vision |
| vibevideo_deepfake | `python/spaces/video/vibevideo_deepfake/` | MuseTalk lip sync, Chatterbox voice cloning |

## Directory Structure

```
python/spaces/video/
├── agents/
│   └── video_agent.py          # VideoBackendAgent
├── tools/
│   └── video_tools.py          # All tool functions (506 lines)
├── media_server.py              # HTTP server for video streaming (port 9877)
├── vibevideo/                   # Submodule: team + demo + vision
│   ├── pipeline/                # analyze, build, final_cut, raw_cut, split_screen
│   ├── product/                 # demo_video, extract_frames, whisper_engine
│   ├── sora/                    # composite_persons, sora_backgrounds, sora_vision
│   └── vibevideo.py             # CLI entry point
└── vibevideo_deepfake/          # Submodule: lipsync + voice
    └── deepfake.py              # CLI entry point
```
