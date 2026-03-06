# SWE Design Submodule

## Overview

The swe_desgine submodule provides a software engineering design pipeline for structured requirements evaluation and bubble promotion. It powers the shuttle pipeline in VibeMind, which moves bubbles through progressive refinement stages.

> **Note on naming:** The directory and repository are named `swe_desgine` (not `swe_design`). This naming is intentional and maintained for consistency with the upstream repository.

## Location

- **Path in VibeMind:** `python/spaces/shuttles/swe_desgine/`
- **Upstream repository:** https://github.com/Flissel/swe_desgine.git
- **Configured in:** `.gitmodules`

## How VibeMind Uses It

### Agent

There is no dedicated Shuttles agent. Shuttle events are handled by the **BubblesAgent** (`python/spaces/ideas/agents/bubbles_agent.py`) in the Ideas space:

- `bubble.evaluate` -- Evaluates a bubble's readiness for promotion
- `bubble.promote` -- Moves a bubble to the next pipeline stage

### Shuttle Pipeline

The shuttle pipeline is a structured requirements workflow:

1. A bubble is submitted for evaluation
2. The SWE Design pipeline assesses the bubble's completeness and quality
3. If ready, the bubble is promoted to the next stage
4. Results are stored in the `shuttles` database table

### Database

Shuttle data is persisted in the `shuttles` table:

| Column | Purpose |
|--------|---------|
| `shuttle_id` | Unique identifier |
| `bubble_id` | Associated bubble |
| `current_stage` | Current pipeline stage |

### Electron Integration

- **`electron-app/renderer/shuttle_manager.js`** -- Manages the shuttle pipeline UI in the renderer, showing stage progression and evaluation results.
- **`electron-app/swe-design-manager.js`** -- Manages the Factory Space BrowserView embedding for the SWE Design interface.

## Initialize / Update

```bash
# Initialize
git submodule update --init python/spaces/shuttles/swe_desgine

# Update to latest
cd python/spaces/shuttles/swe_desgine
git pull origin main
cd ../../../..
git add python/spaces/shuttles/swe_desgine
git commit -m "Update swe_desgine submodule"
```
