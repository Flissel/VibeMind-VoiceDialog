# Spaces

VibeMind organizes functionality into 8 domain spaces. Each space has its own backend agent, tools, and event types.

## Space Summary

| Space | Stream | Agent | Event Prefix | Status |
|-------|--------|-------|-------------|--------|
| Bubbles | `events:tasks:bubbles` | BubblesAgent | `bubble.*` | Stable |
| Ideas | `events:tasks:ideas` | IdeasAgent | `idea.*` | Stable |
| Coding | `events:tasks:coding` | CodingAgent | `code.*` | Stable |
| Desktop | `events:tasks:desktop` | DesktopAgent | `desktop.*`, `messaging.*`, `web.*` | Stable |
| Rowboat | `events:tasks:roarboot` | RoarbootBackendAgent | `roarboot.*` | Beta |
| Research | `events:tasks:zeroclaw` | ZeroClawResearchAgent | `research.*` | Beta |
| Minibook | `events:tasks:minibook` | MinibookBackendAgent | `minibook.*` | Beta |
| Shuttles | N/A | None (SWE Design submodule only) | N/A | Submodule only |
| Schedule | `events:tasks:schedule` | ScheduleBackendAgent | `schedule.*` | Beta |

## Ideas Space

The core space. Manages bubbles (containers) and ideas (content nodes) in a navigable hierarchy.

**Key Tools:**
- `create_bubble`, `enter_bubble`, `list_bubbles`, `exit_bubble`
- `create_idea`, `find_idea`, `update_idea`, `delete_idea`
- `auto_link_ideas` — LLM-based semantic linking
- `convert_format` — Transform ideas to action lists, kanban, mindmaps, SWOT, etc.
- `summarize_idea`, `expand_ideas`, `explain_idea`
- `start_exploration` — AI-Scientist explores connections

**Format Types:** note, action_list, pros_cons, hierarchy, specs, kanban, mindmap, swot, user_story, flowchart

**Files:** `python/spaces/ideas/`

## Coding Space

Generates code projects from idea descriptions using an external Coding Engine.

**Key Tools:**
- `generate_code` — Start code generation from a description
- `get_generation_status` — Poll progress
- `start_preview` / `stop_preview` — VNC-based live preview
- `idea_to_project` — Convert an idea directly to a code project
- `modify_code` — Apply changes to generated code

**Files:** `python/spaces/coding/`

## Desktop Space

Automates desktop interactions — opening apps, clicking, typing, screenshots.

**Key Tools:**
- `open_app`, `click_element`, `type_text`, `press_key`
- `take_screenshot`, `scroll_screen`
- `execute_desktop_task` — General task execution
- `moire_scan` / `moire_find_element` — Vision-based OCR element finding
- `send_whatsapp` / `send_telegram` — Messaging bridge

**Files:** `python/spaces/desktop/`

## Rowboat Space

Knowledge graph exploration and retrieval-augmented generation (RAG).

**Enable:** Requires Rowboat submodule and Docker.

**Files:** `python/spaces/rowboat/`

## Research Space

Web research powered by the ZeroClaw engine.

**Enable:** `USE_ZEROCLAW=true`

**Files:** `python/spaces/research/`, `external/zeroclaw/`

## Minibook Space

Inter-space collaboration — coordinates tasks across multiple spaces.

**Enable:** `USE_MINIBOOK_HUB=true`

**Files:** `python/spaces/minibook/`, `external/minibook/`

## Shuttles Space

Requirements evaluation pipeline. Takes a bubble through stages: mining → requirements → validation → knowledge graph → techstack.

**Files:** `python/spaces/shuttles/`

## Schedule Space

APScheduler-based task scheduling — reminders, alarms, recurring tasks.

**Enable:** `SCHEDULE_ENABLED=true`

**Files:** `python/spaces/schedule/`

## Adding a New Space

See [docs/development/adding-a-space.md](../development/adding-a-space.md).
