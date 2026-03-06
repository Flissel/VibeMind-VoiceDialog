# Tool Functions Reference

All tool functions return `{"success": bool, "message": str, ...}`.

Tools exist in two locations following a dual-location pattern:
- **`python/tools/`** -- Shared/legacy stubs and cross-domain utilities
- **`python/spaces/<domain>/tools/`** -- Authoritative domain-specific implementations

## Bubble Tools

**Files:** `python/spaces/ideas/tools/bubble_tools.py` (authoritative), `python/tools/bubble_tools.py` (shared)

| Function | Parameters | Description |
|----------|-----------|-------------|
| `create_bubble(title)` | title: str | Create a new bubble |
| `enter_bubble(bubble_name)` | bubble_name: str | Navigate into bubble |
| `exit_bubble()` | -- | Exit to parent |
| `list_bubbles()` | -- | List all top-level bubbles |
| `delete_bubble(title)` | title: str | Delete bubble by name |
| `delete_all_except(titles)` | titles: list | Delete all except named bubbles |
| `update_bubble(title, new_title?, new_description?)` | title: str | Update bubble properties |
| `find_bubble(query)` | query: str | Fuzzy search bubbles |
| `get_bubble_stats()` | -- | Get bubble statistics |
| `score_bubbles()` | -- | Score all bubbles |
| `evaluate_bubble(title?)` | title: str | Evaluate bubble quality |
| `promote_bubble(title)` | title: str | Promote bubble to project |
| `get_current_bubble()` | -- | Get current bubble context |

## Idea Tools

**Files:** `python/spaces/ideas/tools/idea_tools.py` (authoritative), `python/tools/idea_tools.py` (stubs)

| Function | Parameters | Description |
|----------|-----------|-------------|
| `create_idea(title, content?)` | title: str, content: str | Create idea in current bubble |
| `list_ideas()` | -- | List ideas in current context |
| `find_idea(query)` | query: str | Fuzzy search ideas |
| `update_idea(idea_name, new_content)` | idea_name: str, new_content: str | Update idea |
| `delete_idea(idea_name)` | idea_name: str | Delete idea |
| `connect_ideas(idea1, idea2)` | idea1: str, idea2: str | Create link |
| `auto_link_ideas()` | -- | LLM-based auto-linking |
| `add_image(idea_name, image_url)` | idea_name: str, image_url: str | Attach image to idea |
| `get_current_space()` | -- | Get current space context |
| `summarize_idea(idea_name?)` | idea_name: str | Generate summary |
| `generate_whitepaper(start_node?)` | start_node: str | Generate white paper |
| `expand_ideas(idea_name, count?)` | idea_name: str, count: int | Generate sub-ideas |
| `explain_idea(idea_name)` | idea_name: str | Explain in detail |
| `analyze_links(idea_name?)` | idea_name: str | Analyze link structure |

## Exploration Tools

**File:** `python/spaces/ideas/tools/exploration_tools.py`

| Function | Parameters | Description |
|----------|-----------|-------------|
| `start_exploration(query?)` | query: str | Start AI exploration from current bubble |
| `stop_exploration()` | -- | Stop active exploration |
| `get_exploration_status()` | -- | Get exploration state |
| `accept_node(node_id)` | node_id: str | Accept discovered connection |
| `reject_node(node_id)` | node_id: str | Reject discovered connection |
| `set_exploration_depth(level)` | level: int | Set exploration depth |
| `visualize_exploration()` | -- | Generate exploration visualization |
| `continue_exploration()` | -- | Continue paused exploration |
| `set_exploration_direction(direction)` | direction: str | Set exploration direction |
| `respond_to_exploration(response)` | response: str | Respond to exploration prompt |

## Summary Tools

**Files:** `python/spaces/ideas/tools/summary_tools.py`, `python/tools/summary_tools.py`

| Function | Parameters | Description |
|----------|-----------|-------------|
| `summarize_bubble(bubble_id?)` | bubble_id: str | Summarize bubble contents |

## Formatting Tools

**Files:** `python/spaces/ideas/tools/structured_formatting_tools.py`, `python/tools/structured_formatting_tools.py`

| Function | Parameters | Description |
|----------|-----------|-------------|
| `format_idea_content(idea_id, format_type)` | idea_id: str, format_type: str | Format to structured type |
| `list_available_formats()` | -- | Return available formats |
| `convert_format(idea_name, target_format)` | idea_name: str, target_format: str | Convert idea format |

## Format Dispatcher

**Files:** `python/spaces/ideas/tools/format_dispatcher.py`, `python/tools/format_dispatcher.py`

Routes `idea.format_*` event types to the correct formatting function with injected `target_format`.

## Autogen Research Tools

**File:** `python/spaces/ideas/tools/autogen_research.py`

| Function | Parameters | Description |
|----------|-----------|-------------|
| `autogen_research(query)` | query: str | Run autogen-based research for idea enrichment |

## Coding Tools

**File:** `python/spaces/coding/tools/coding_tools.py`

| Function | Parameters | Description |
|----------|-----------|-------------|
| `generate_code(title, description?)` | title: str | Start code generation |
| `get_generation_status()` | -- | Poll progress |
| `cancel_generation(job_id)` | job_id: str | Cancel generation |
| `list_generated_projects()` | -- | List all projects |
| `start_preview(project_id?)` | project_id: str | Start VNC preview |
| `stop_preview(project_id?)` | project_id: str | Stop preview |
| `idea_to_project(idea_name)` | idea_name: str | Convert idea to project |
| `modify_code(instruction)` | instruction: str | Apply code changes |
| `show_project(project_id?)` | project_id: str | Show project details |

## Adapted Coding Tools

**File:** `python/spaces/coding/tools/adapted_coding_tools.py`

Adapter layer that wraps coding_tools for compatibility with the backend agent interface.

## Voice Coding Tools

**File:** `python/spaces/coding/tools/voice_coding_tools.py`

Voice-optimized wrappers for coding operations with simplified parameter handling.

## Desktop Tools

**File:** `python/spaces/desktop/tools/desktop_tools.py`

| Function | Parameters | Description |
|----------|-----------|-------------|
| `open_app(app_name)` | app_name: str | Open application |
| `click_element(element_description)` | element_description: str | Click UI element |
| `type_text(text)` | text: str | Type text |
| `press_key(key)` | key: str | Press keyboard key |
| `take_screenshot()` | -- | Capture screen |
| `scroll_screen(direction)` | direction: str | Scroll up/down |
| `execute_desktop_task(description)` | description: str | General task |

## Adapted Desktop Tools

**File:** `python/spaces/desktop/tools/adapted_desktop_tools.py`

Adapter layer that wraps desktop_tools for compatibility with the backend agent interface.

## Moire Tools (Vision)

**Files:** `python/spaces/desktop/tools/moire_tools.py`, `python/tools/moire_tools.py`

| Function | Parameters | Description |
|----------|-----------|-------------|
| `moire_scan()` | -- | Vision-based screen scan |
| `moire_find(element)` | element: str | Find UI element via OCR/vision |

## Quick Action Tools

**File:** `python/spaces/desktop/tools/quickaction_tools.py`

| Function | Parameters | Description |
|----------|-----------|-------------|
| `quick_action(action)` | action: str | Execute a quick desktop action |

## Task Tools (Desktop)

**File:** `python/spaces/desktop/tools/task_tools.py`

| Function | Parameters | Description |
|----------|-----------|-------------|
| `create_task(title, description)` | title: str, description: str | Create a desktop task node |
| `update_task(task_id, status)` | task_id: str, status: str | Update task status |
| `list_tasks()` | -- | List all desktop tasks |

## Roarboot Tools

**Files:** `python/spaces/rowboat/tools/roarboot_tools.py`, `python/spaces/rowboat/tools/roarboot_client.py`

| Function | Parameters | Description |
|----------|-----------|-------------|
| `roarboot_search(query)` | query: str | Search Roarboot data |
| `roarboot_query(query)` | query: str | Query Roarboot knowledge base |
| `roarboot_email_draft(subject, body, recipient?)` | subject: str, body: str | Draft an email |
| `roarboot_meeting_brief(meeting_id?)` | meeting_id: str | Generate meeting brief |
| `roarboot_deck(topic, slides?)` | topic: str, slides: int | Generate slide deck |
| `roarboot_voice_note(content)` | content: str | Create voice note |
| `roarboot_status()` | -- | Get Roarboot service status |
| `roarboot_open()` | -- | Open Roarboot interface |
| `roarboot_reset()` | -- | Reset Roarboot state |

## Roarboot Docker Tools

**File:** `python/spaces/rowboat/tools/docker_tools.py`

| Function | Parameters | Description |
|----------|-----------|-------------|
| `docker_start()` | -- | Start Roarboot Docker container |
| `docker_stop()` | -- | Stop Roarboot Docker container |
| `docker_restart()` | -- | Restart Roarboot Docker container |
| `docker_status()` | -- | Get Docker container status |

## Research Tools

**File:** `python/spaces/research/tools/research_tools.py`

| Function | Parameters | Description |
|----------|-----------|-------------|
| `web_research(query)` | query: str | Deep web research |
| `scrape_url(url)` | url: str | Scrape webpage content |
| `summarize_url(url)` | url: str | Summarize webpage |
| `research_to_idea(research_id)` | research_id: str | Convert research result to idea |
| `research_to_rowboat(research_id)` | research_id: str | Send research to Roarboot |

## Minibook Tools

**Files:** `python/spaces/minibook/tools/minibook_tools.py`, `python/spaces/minibook/tools/minibook_client.py`, `python/spaces/minibook/tools/collaboration_tools.py`

| Function | Parameters | Description |
|----------|-----------|-------------|
| `minibook_discuss(topic, context?)` | topic: str, context: str | Start multi-agent discussion |
| `minibook_collaborate(task, agents?)` | task: str, agents: list | Collaborative task execution |
| `minibook_status()` | -- | Get discussion status |
| `minibook_results(session_id?)` | session_id: str | Get discussion results |
| `minibook_list_projects()` | -- | List Minibook projects |
| `minibook_poll(question, options?)` | question: str, options: list | Poll agents for opinions |

## Schedule Tools

**File:** `python/spaces/schedule/tools/schedule_tools.py`

| Function | Parameters | Description |
|----------|-----------|-------------|
| `create_schedule(title, time, action)` | title: str, time: str, action: str | Create scheduled task |
| `list_schedules()` | -- | List scheduled tasks |
| `cancel_schedule(task_id)` | task_id: str | Cancel scheduled task |
| `modify_schedule(task_id, changes)` | task_id: str, changes: dict | Modify scheduled task |
| `schedule_status(task_id?)` | task_id: str | Get schedule status |
| `snooze_schedule(task_id, duration)` | task_id: str, duration: str | Snooze a scheduled task |

## Shared Utility Tools (python/tools/)

### Workspace Tools

**File:** `python/tools/workspace_tools.py`

General workspace state and context utilities.

### Navigation Tools

**File:** `python/tools/navigation_tools.py`

Bubble/space navigation helpers.

### Conversation Tools

**File:** `python/tools/conversation_tools.py`

Conversation history read/write utilities.

### Session Tools

**File:** `python/tools/session_tools.py`

Voice/conversation session management.

### Memory Tools

**File:** `python/tools/memory_tools.py`

Semantic memory store/retrieve operations.

### Task Memory Tools

**File:** `python/tools/task_memory_tools.py`

Task-specific memory operations (via Supermemory).

### Supermemory Tools

**File:** `python/tools/supermemory_tools.py`

Direct Supermemory API wrappers.

### System Status Tools

**File:** `python/tools/system_status_tools.py`

System health and diagnostics.

### Task Status Tools

**File:** `python/tools/task_status_tools.py`

Task execution status tracking.

### Handoff Tools

**File:** `python/tools/handoff_tools.py`

Agent-to-agent handoff utilities.

### Transfer Handler

**File:** `python/tools/transfer_handler.py`

Manages voice agent transfer sequences.

### Client Tools Manager

**File:** `python/tools/client_tools_manager.py`

Registers and manages client-side tool definitions.

### Worker Queue

**File:** `python/tools/worker_queue.py`

Background task queue for async tool execution.

### Browser Worker

**File:** `python/tools/browser_worker.py`

Headless browser automation worker.

### Index Mapping

**File:** `python/tools/index_mapping.py`

Maps event types to tool functions and parameter schemas.

### Bubble Requirements Tool

**File:** `python/tools/bubble_requirements_tool.py`

Shuttle pipeline: extract and evaluate bubble requirements.
