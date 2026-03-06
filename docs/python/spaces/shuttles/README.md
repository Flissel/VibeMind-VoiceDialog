# Shuttles Space

The Shuttles space is a special-purpose directory that contains only the SWE Design submodule. Unlike other spaces, it has no dedicated backend agent, tools, or workers. Shuttle events (`bubble.evaluate`, `bubble.promote`) are handled by the BubblesAgent in the Ideas space.

## Directory Structure

```
python/spaces/shuttles/
└── swe_desgine/                # Git submodule (SWE Design pipeline)
```

> **Note:** There is no `__init__.py`, no `agents/`, no `tools/`, and no `workers/` directory. This space exists solely to house the SWE Design submodule.

## Shuttle Pipeline

The shuttle pipeline is a requirements evaluation and promotion workflow. It moves bubbles through structured stages:

1. **Evaluate** -- Assess a bubble's readiness (`bubble.evaluate`)
2. **Promote** -- Move a bubble to the next stage (`bubble.promote`)

These events are handled by the **BubblesAgent** in the Ideas space (`python/spaces/ideas/agents/bubbles_agent.py`), not by a dedicated Shuttles agent.

## SWE Design Submodule

The `swe_desgine` submodule provides the software engineering design pipeline:

- **Path:** `python/spaces/shuttles/swe_desgine/`
- **Upstream:** https://github.com/Flissel/swe_desgine.git
- **Initialize:** `git submodule update --init python/spaces/shuttles/swe_desgine`

> **Note on naming:** The directory is named `swe_desgine` (not `swe_design`). This naming is maintained for consistency with the upstream repository and git submodule configuration.

See [docs/submodules/swe-design.md](../../submodules/swe-design.md) for details.

## Electron UI Integration

The shuttle pipeline has a dedicated UI component in the Electron app:

- **`electron-app/renderer/shuttle_manager.js`** -- Manages the shuttle pipeline UI, showing stage progression and evaluation results.
- **`electron-app/swe-design-manager.js`** -- Manages the Factory Space BrowserView embedding for the SWE Design interface.

## Database

Shuttle data is stored in the `shuttles` table:

| Column | Purpose |
|--------|---------|
| `shuttle_id` | Unique shuttle identifier |
| `bubble_id` | Associated bubble |
| `current_stage` | Current pipeline stage |
