# Video Space Design

**Date:** 2026-03-16
**Status:** Draft
**Author:** Claude Code

## Summary

New "Video" domain space for VibeMind integrating two external repositories (`vibevideo` and `vibevideo-deepfake`) as git submodules. The space provides video generation (Sora pipeline), editing, product videos, lipsync/deepfake, and voice cloning — primarily for producing team and individual videos.

Routing through Minibook (existing hub/router). Tools use Python-Import with Adapter-Layer pattern for tight integration.

## Architecture

```
Voice/Text → Minibook Router (SpaceRouter) → VideoBackendAgent
                                                   ↓
                                         adapted_video_tools.py
                                        ┌──────────┴──────────┐
                                  vibevideo/              vibevideo_deepfake/
                                  (Submodule, MIT)        (Submodule, Proprietary)
                                  - pipeline/             - lipsync/
                                  - sora/                 - voice/
                                  - product/
                                  - utils/
```

## Directory Structure

```
python/spaces/video/
├── __init__.py
├── agents/
│   ├── __init__.py
│   └── video_agent.py              # VideoBackendAgent (extends BaseBackendAgent)
├── tools/
│   ├── __init__.py
│   ├── adapted_video_tools.py      # Adapter layer: imports from submodules
│   ├── video_generation_tools.py   # Sora-Pipeline wrapper (vibevideo)
│   └── deepfake_tools.py           # Lipsync + Voice-Cloning wrapper (vibevideo-deepfake)
├── vibevideo/                      # Git Submodule → github.com/Flissel/vibevideo
└── vibevideo_deepfake/             # Git Submodule → github.com/Flissel/vibevideo-deepfake (underscore for Python import)
```

## Event Types

| Event Type | Tool Function | Source Repo | Description |
|------------|--------------|-------------|-------------|
| `video.generate` | `generate_video` | vibevideo | Text-to-video via Sora pipeline |
| `video.edit` | `edit_video` | vibevideo | Cut/edit existing video |
| `video.product` | `create_product_video` | vibevideo | Create product marketing video |
| `video.status` | `get_pipeline_status` | vibevideo | Query pipeline generation status |
| `video.lipsync` | `create_lipsync` | vibevideo-deepfake | Lipsync/deepfake for team/individual videos |
| `video.voice_clone` | `clone_voice_for_video` | vibevideo-deepfake | Voice cloning for video narration |

## Voice Commands (German)

```
"Erstelle ein Video ueber X"           → video.generate   {"description": "X"}
"Schneide das Video bei 2 Minuten"     → video.edit       {"action": "cut", "timestamp": "2:00"}
"Erstelle ein Produkt-Video fuer X"    → video.product    {"product": "X"}
"Video-Status?"                        → video.status
"Wie weit ist das Video?"              → video.status
"Mach einen Lipsync von dem Video"     → video.lipsync    {"source": "..."}
"Klone die Stimme fuer das Video"      → video.voice_clone {"voice_source": "..."}
"Erstelle ein Team-Video"              → video.generate   {"description": "Team-Video", "type": "team"}
```

## Backend Agent

```python
import os
from typing import Dict, Callable, Optional
from swarm.backend_agents.base_agent import BaseBackendAgent


class VideoBackendAgent(BaseBackendAgent):

    EVENT_TO_TOOL: Dict[str, str] = {
        "video.generate": "generate_video",
        "video.edit": "edit_video",
        "video.product": "create_product_video",
        "video.status": "get_pipeline_status",
        "video.lipsync": "create_lipsync",
        "video.voice_clone": "clone_voice_for_video",
    }

    PARAM_MAPPING: Dict[str, Dict[str, str]] = {
        "video.generate": {"text": "description", "prompt": "description", "beschreibung": "description"},
        "video.edit": {"zeit": "timestamp", "time": "timestamp", "aktion": "action"},
        "video.product": {"name": "product", "produkt": "product"},
        "video.lipsync": {"quelle": "source", "video": "source"},
        "video.voice_clone": {"stimme": "voice_source", "voice": "voice_source"},
    }

    @property
    def stream(self) -> str:
        return "events:tasks:video"

    @property
    def name(self) -> str:
        return "VideoAgent"

    def _load_tools(self) -> Dict[str, Callable]:
        from spaces.video.tools.video_generation_tools import (
            generate_video, edit_video, create_product_video, get_pipeline_status,
        )
        from spaces.video.tools.deepfake_tools import (
            create_lipsync, clone_voice_for_video,
        )
        return {
            "generate_video": generate_video,
            "edit_video": edit_video,
            "create_product_video": create_product_video,
            "get_pipeline_status": get_pipeline_status,
            "create_lipsync": create_lipsync,
            "clone_voice_for_video": clone_voice_for_video,
        }

    def _get_tool_name(self, event_type: str) -> Optional[str]:
        return self.EVENT_TO_TOOL.get(event_type)


# Singleton
_video_agent: Optional[VideoBackendAgent] = None


def get_video_agent() -> Optional[VideoBackendAgent]:
    """Get or create VideoBackendAgent singleton. Returns None if VIDEO_ENABLED=false."""
    global _video_agent
    if os.getenv("VIDEO_ENABLED", "false").lower() != "true":
        return None
    if _video_agent is None:
        _video_agent = VideoBackendAgent()
    return _video_agent
```

## Adapter Layer Pattern

`adapted_video_tools.py` imports directly from submodule packages:

```python
# Import from vibevideo submodule
from spaces.video.vibevideo.pipeline import VideoPipeline
from spaces.video.vibevideo.sora import SoraGenerator
from spaces.video.vibevideo.product import ProductVideoBuilder

# Import from vibevideo-deepfake submodule
from spaces.video.vibevideo_deepfake.lipsync import LipsyncEngine
from spaces.video.vibevideo_deepfake.voice import VoiceCloner
```

Each tool function follows the standard VibeMind pattern:
- Accept `**kwargs` for flexibility
- Return `{"success": bool, "message": str, "data": {...}}`
- Call `_broadcast_to_electron()` for UI updates
- Include `response_hint` for Rachel voice responses

## Minibook Registration

### SPACE_AGENT_REGISTRY (collaboration_tools.py)

```python
"video": {
    "name": "vibemind_video",
    "domain_prefix": "video.",
    "role": (
        "Video-Produktion: Videos generieren (Sora-Pipeline), schneiden, "
        "Produkt-Videos erstellen, Lipsync/Deepfake fuer Team- und Einzel-Videos, "
        "Voice-Cloning fuer Video-Narration."
    ),
}
```

### SPACE_KEYWORDS (collaboration_tools.py)

```python
"video": ["video", "film", "clip", "schneid", "lipsync", "deepfake",
           "voice clone", "produkt-video", "sora", "team-video"]
```

### SpaceRouter (space_router.py)

```python
EVENT_TYPE_TO_SPACE["video."] = "video"
```

### TaskEnricher (task_enricher.py)

```python
# Default event type for video space
"video": "video.generate"

# Space-to-prefix mapping
"video": "video."
```

## 3D Multiverse Visualization

```javascript
video: {
    objects: [],
    position: new THREE.Vector3(20, 0, 18),
    icon: '🎬',
    name: 'Video Studio',
    agent: { name: 'Director', slug: 'video', role: 'Video Producer' },
    color: 0xff4488  // Pink/Magenta
}
```

## Files to Modify

| File | Change |
|------|--------|
| `.gitmodules` | Add 2 submodule entries (vibevideo as `vibevideo`, vibevideo-deepfake as `vibevideo_deepfake` with underscore path) |
| `python/swarm/backend_agents/__init__.py` | Add `get_video_agent()` lazy import + `__getattr__` entry |
| `python/swarm/event_team/event_router.py` | Add `STREAM_TASKS_VIDEO` constant + 6 event mappings + `get_category()` branch + `all_streams()` entry |
| `python/swarm/orchestrator/intent_classifier.py` | Add Video Space section to `CLASSIFIER_PROMPT_TEMPLATE` |
| `python/spaces/minibook/tools/collaboration_tools.py` | Add to `SPACE_AGENT_REGISTRY` + `SPACE_KEYWORDS` |
| `python/spaces/minibook/enrichment/space_router.py` | Add `"video.": "video"` to `EVENT_TYPE_TO_SPACE` |
| `python/spaces/minibook/enrichment/task_enricher.py` | Add video defaults + prefix mapping |
| `electron-app/renderer/multiverse.js` | Add video space definition to `this.spaces` |
| `python/electron_backend.py` | Handle new IPC message types (video_generation_*, lipsync_complete) |

## Files to Create

| File | Purpose |
|------|---------|
| `python/spaces/video/__init__.py` | Package init |
| `python/spaces/video/agents/__init__.py` | Package init |
| `python/spaces/video/agents/video_agent.py` | VideoBackendAgent implementation |
| `python/spaces/video/tools/__init__.py` | Package init |
| `python/spaces/video/tools/adapted_video_tools.py` | Adapter layer importing from submodules |
| `python/spaces/video/tools/video_generation_tools.py` | Sora/edit/product tool functions |
| `python/spaces/video/tools/deepfake_tools.py` | Lipsync + voice clone tool functions |

## IPC Messages (Python → Electron)

| Message Type | Purpose | Payload |
|-------------|---------|---------|
| `video_generation_started` | Pipeline started | `{video_id, description, type}` |
| `video_generation_progress` | Progress update | `{video_id, progress_pct, stage}` |
| `video_generation_complete` | Video ready | `{video_id, output_path, duration}` |
| `video_edit_complete` | Edit done | `{video_id, output_path}` |
| `lipsync_complete` | Lipsync done | `{video_id, output_path}` |

## Dependencies

From vibevideo `requirements.txt` and vibevideo-deepfake `requirements.txt` — to be merged into main `requirements.txt` or kept isolated via the adapter layer with lazy imports and graceful degradation if deps missing.

## Configuration (.env)

```bash
# Video Space
VIDEO_ENABLED=true
VIBEVIDEO_PATH=python/spaces/video/vibevideo
VIBEVIDEO_DEEPFAKE_PATH=python/spaces/video/vibevideo-deepfake
```
