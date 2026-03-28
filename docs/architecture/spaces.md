# Spaces

VibeMind organizes functionality into 15 domain spaces. Each space has its own backend agent, tools, and event types.

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
| Schedule | `events:tasks:schedule` | ScheduleBackendAgent | `schedule.*` | Beta |
| N8n | `events:tasks:n8n` | N8nBackendAgent | `n8n.*` | Stable |
| AgentFarm | `events:tasks:agentfarm` | AgentFarmBackendAgent | `agentfarm.*` | Stable |
| Video | `events:tasks:video` | VideoBackendAgent | `video.*` | Beta |
| MiroFish | `events:tasks:mirofish_pred` | MiroFishBackendAgent | `mirofish.*` | Beta |
| Flowzen | via submodule | FlowzenAgent | `flowzen.*` | Beta |
| Brain | — (standalone) | — | — | Stable |
| Shuttles | N/A | None (SWE Design submodule only) | N/A | Submodule only |

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

## AgentFarm Space

Multi-agent team orchestration using AutoGen 0.4.

**Key Tools:**
- `create_team` — Create agent team from template or config
- `run_team` — Start async team task execution
- `list_teams`, `stop_run`, `get_run_results` — Team lifecycle
- `start_collaboration` — Multi-space collaboration via Minibook

**Subsystems:** TeamRunner (async execution), MCP Server (Claude integration), HybridPipeline (multi-space), OpenClaw Bridge

**Files:** `python/spaces/autogen/`

## Video Space

Video production pipeline with team videos, product demos, vision (Sora AI), lip sync, and voice cloning.

**Key Tools:**
- `team_run_step` — Execute team video pipeline (analyze → backgrounds → composite → build → split → final)
- `vision_generate` — Her-style vision video via Sora AI
- `demo_analyze` / `demo_build` — Product demo production
- `lipsync_run` / `lipsync_analyze` — MuseTalk lip sync
- `voice_clone` / `voice_tts` — Chatterbox voice cloning + TTS
- `publish_videos_to_rowboat` — Publish to knowledge graph

**Submodules:** `vibevideo` (team + demo + vision), `vibevideo_deepfake` (lipsync + voice)

**Files:** `python/spaces/video/`

## MiroFish Space

Offline AI prediction engine with multi-agent simulations and knowledge graphs.

**Key Tools:**
- `simulate` — End-to-end prediction (upload → graph → simulation → report)
- `build_graph` / `search_graph` — Knowledge graph operations
- `chat_report` — Interactive chat with report agent
- `interview_agent` — Query simulated agents
- Docker management (start, stop, restart, status)

**Backend:** Flask + Vue app in Docker (localhost:5001), Neo4j graph database, Ollama for local LLM

**Files:** `python/spaces/mirofish/`

## Flowzen Space (Blaue Rose)

Circadian-aware activity tracking, daily journaling, and Brain integration.

**Key Tools:**
- `recommend_task` — Circadian-aware activity recommendation
- `accept_recommendation` — Log recommended activity
- `get_flowzen_status` — Current activity state

**Integration:** Brain space via `FlowzenBrainBridge`, circadian matrix for time-of-day awareness

**Files:** `python/spaces/flowzen/` (proxy to submodule)

## N8n Space

Workflow automation via N8n with AI-generated workflows.

**Key Tools:**
- `n8n_generate` — AI-generated workflow from description (6-agent AutoGen Society)
- `n8n_list`, `n8n_status`, `n8n_activate`, `n8n_deactivate`, `n8n_delete`
- `n8n_execute`, `n8n_describe`

**Files:** `python/spaces/n8n/`

## Adding a New Space

See [docs/development/adding-a-space.md](../development/adding-a-space.md).
