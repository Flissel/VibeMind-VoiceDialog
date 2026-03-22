# Tool Functions Reference

All tool functions return `{"success": bool, "message": str, ...}`.

Tools exist in two locations following a dual-location pattern:
- **`python/tools/`** -- Shared/legacy stubs and cross-domain utilities
- **`python/spaces/<domain>/tools/`** -- Authoritative domain-specific implementations

## Shared Utility Tools (python/tools/)

### Browser Worker

**File:** `python/tools/browser_worker.py`

| Function | Parameters | Description |
|----------|-----------|-------------|
| `search_images_tool()` | params | Search for images on the web. |
| `download_image_tool()` | params | Download an image from URL. |
| `register_browser_tools()` | tools_manager | Register browser tools with the ClientToolsManager (with observer logging). |

### Bubble Requirements Tool

**File:** `python/tools/bubble_requirements_tool.py`

| Function | Parameters | Description |
|----------|-----------|-------------|
| `process_bubble_requirements()` | bubble_id: str | Verarbeite die Inhalte einer Bubble und generiere Requirements für die Vorver... |
| `get_bubble_requirements()` | bubble_id: str | Hole die Requirements für eine Bubble. |
| `list_bubbles_with_requirements()` | -- | Liste alle Bubbles und generiere Requirements für jede. |

### Conversation Tools

**File:** `python/tools/conversation_tools.py`

| Function | Parameters | Description |
|----------|-----------|-------------|
| `start_session()` | agent_id? | Start a new conversation session. |
| `end_session()` | summary? | End the current conversation session. |
| `record_message()` | speaker: str, text: str, metadata? | Record a message to the conversation buffer AND persist to database. |
| `clear_conversation()` | -- | Clear the in-memory conversation buffer and end current session. |
| `get_current_session_id()` | -- | Get the current session ID. |
| `get_session_history()` | session_id?, limit: int | Get conversation history from the database. |
| `search_conversation_history()` | query: str, limit: int | Search across all conversation history (supermemory). |
| `get_conversation_transcript()` | -- | Get the full conversation as formatted text. |
| `get_conversation_summary()` | -- | Get a brief summary of the conversation (last few exchanges). |
| `save_conversation()` | params | Save the current conversation to a bubble's canvas. |
| `save_summary()` | params | Save a conversation summary to canvas. |
| `extract_key_points()` | params | Extract and save key points from the conversation. |
| `create_idea_from_discussion()` | params | Create a new idea from the current discussion. |
| `add_to_current_bubble()` | params | Add content to the currently active bubble. |
| `register_conversation_tools()` | tools_manager | Register conversation tools with the ClientToolsManager (with observer logging). |

### Handoff Tools

**File:** `python/tools/handoff_tools.py`

| Function | Parameters | Description |
|----------|-----------|-------------|
| `register_handoff_tools()` | tools_manager | Register Handoff MCP tools with the ClientToolsManager. |
| `create_wrapper()` | async_func | -- |
| `wrapper()` | params | -- |

### Index Mapping

**File:** `python/tools/index_mapping.py`

| Function | Parameters | Description |
|----------|-----------|-------------|
| `get_index_mapping()` | -- | Get or create the IndexMapping singleton. |
| `clear_index_mapping()` | -- | Clear all mappings (useful for testing). |
| `set_idea_mapping()` | nodes, bubble_id? | Update idea mapping from list_ideas() result. |
| `set_bubble_mapping()` | bubbles | Update bubble mapping from list_bubbles() result. |
| `resolve_idea_index()` | ref: str | Resolve a numeric reference to an idea ID. |
| `resolve_bubble_index()` | ref: str | Resolve a numeric reference to a bubble ID. |
| `get_idea_title()` | index: int | Get the title of an idea by its index. |
| `get_bubble_title()` | index: int | Get the title of a bubble by its index. |
| `get_available_idea_indices()` | -- | Get list of available idea indices (1, 2, 3, ...). |
| `get_available_bubble_indices()` | -- | Get list of available bubble indices (1, 2, 3, ...). |
| `format_available_ideas()` | -- | Format available ideas for voice output. |
| `format_available_bubbles()` | -- | Format available bubbles for voice output. |

### Memory Tools

**File:** `python/tools/memory_tools.py`

| Function | Parameters | Description |
|----------|-----------|-------------|
| `register_memory_tools()` | tools_manager | Registriert Memory Tools im ClientToolsManager. |
| `to_dict()` | -- | -- |
| `store_history_wrapper()` | params | -- |
| `get_frequent_wrapper()` | params | -- |
| `get_suggestions_wrapper()` | params | -- |

### Navigation Tools

**File:** `python/tools/navigation_tools.py`

| Function | Parameters | Description |
|----------|-----------|-------------|
| `set_electron_sender()` | sender | Set the Electron IPC message sender callback. |
| `navigate_to_space()` | params | Navigate to a specific space in the multiverse. |
| `select_item()` | params | Select the next or previous item in the current space. |
| `select_by_name()` | params | Select an item by name or index. |
| `enter_selection()` | params | Enter the currently selected bubble or project. |
| `exit_view()` | params | Exit the current view and return to overview. |
| `get_current_view()` | params | Get information about the current view state. |
| `select_shuttle()` | params | Select a requirement shuttle by name or direction. |
| `enter_shuttle()` | params | Enter the selected shuttle to view its requirements. |
| `exit_shuttle()` | params | Exit the shuttle view and return to the multiverse overview. |
| `continue_to_project()` | params | Continue from shuttle to create a project in the Projects Space. |
| `register_navigation_tools()` | tools_manager | Register all navigation tools with the ClientToolsManager. |

### Session Tools

**File:** `python/tools/session_tools.py`

| Function | Parameters | Description |
|----------|-----------|-------------|
| `mark_session_start()` | -- | Called when a voice session starts. |
| `mark_interaction()` | -- | Called when user or agent speaks - resets inactivity timer. |
| `mark_session_end()` | -- | Called when voice session ends. |
| `get_session_elapsed_seconds()` | -- | Get seconds elapsed since session start. |
| `get_inactivity_seconds()` | -- | Get seconds since last interaction. |
| `mark_tool_start()` | -- | Called when a tool starts executing. |
| `mark_tool_end()` | -- | Called when a tool finishes executing. |
| `mark_user_speech()` | -- | Called when user speaks - tracks time for keepalive blocking. |
| `is_tool_running()` | -- | Check if a tool is currently running. |
| `should_send_keepalive()` | -- | Check if it's appropriate to send a keepalive prompt like "Bist du noch da?". |
| `check_session_status()` | params | Check the current voice session status. |
| `extend_session()` | params | Acknowledge session continuation - prevents inactivity timeout. |
| `request_session_restart()` | params | Request to restart the voice session (to reset the 10-minute timer). |
| `end_session_gracefully()` | params | End the voice session gracefully with a summary. |
| `check_timeout_warning()` | params | Check if session is approaching timeout and warn user. |
| `should_auto_restart()` | -- | Check if session should auto-restart (for internal use). |
| `register_session_tools()` | tools_manager | Register all session tools with the tools manager. |

### Supermemory Tools

**File:** `python/tools/supermemory_tools.py`

| Function | Parameters | Description |
|----------|-----------|-------------|
| `get_session_id()` | -- | Get current session ID, creating one if needed. |
| `set_session_id()` | session_id: str | Set the current session ID (called by voice_dialog_main). |
| `search_memory()` | params | Search SuperMemory for relevant context based on a query. |
| `store_to_supermemory()` | params | Store important information in SuperMemory for later recall. |
| `recall_conversation()` | params | Recall the conversation history from the current session. |
| `clear_session_memory()` | params | Start a fresh session (creates new session ID). |
| `register_supermemory_tools()` | tools_manager | Register all SuperMemory tools with the tools manager. |

### System Status Tools

**File:** `python/tools/system_status_tools.py`

| Function | Parameters | Description |
|----------|-----------|-------------|
| `get_system_status()` | params? | Get current system status including active operations. |
| `check_stuck_operations()` | params? | Check for operations that are taking too long. |
| `print_status_summary()` | params? | Print detailed status summary to terminal (for debugging). |

### Task Memory Tools

**File:** `python/tools/task_memory_tools.py`

| Function | Parameters | Description |
|----------|-----------|-------------|
| `get_tasks_today()` | params | Was habe ich heute gemacht? |
| `get_recent_tasks()` | params | Was war der letzte Task? / Zeig mir die letzten Tasks. |
| `search_task_history()` | params | Suche in der Task-Historie. |
| `get_task_stats()` | params | Zeig mir meine Task-Statistiken. |

### Task Status Tools

**File:** `python/tools/task_status_tools.py`

| Function | Parameters | Description |
|----------|-----------|-------------|
| `check_task_status()` | params | Prüft den Status eines bestimmten Tasks. |
| `list_active_tasks()` | params | Zeigt alle aktuell laufenden Tasks. |
| `get_queue_status()` | params | Zeigt den Status aller Task-Queues. |
| `get_recent_completions()` | params | Zeigt kürzlich abgeschlossene Tasks. |

### Worker Queue

**File:** `python/tools/worker_queue.py`

| Function | Parameters | Description |
|----------|-----------|-------------|
| `get_report_queue()` | -- | Get singleton ReportQueue instance. |
| `get_task_queue()` | -- | Get singleton TaskQueue instance. |
| `seed_task()` | description: str, priority: str | Seed a task for the Claude worker. Returns IMMEDIATELY. |
| `get_task_status()` | task_id: str | Check the status of a task. |
| `get_last_result()` | -- | Get the result of the most recently completed task. |
| `cancel_task()` | task_id: str | Cancel a running or queued task. |
| `get_queue_status()` | -- | Get overall queue status. |
| `get_worker_report()` | -- | Get the latest progress report from the Claude worker. |
| `get_all_reports()` | task_id: str | Get all reports for a specific task. |
| `register_worker_queue_tools()` | tools_manager | Register worker queue tools with the ClientToolsManager. |
| `push_report()` | report: StepReport | Worker pushes report every 3 steps. |
| `get_latest_report()` | -- | Voice agent calls this to get latest report. |
| `get_reports_for_task()` | task_id: str | Get all reports for a specific task. |
| `clear_task_reports()` | task_id: str | Clear reports for a completed task. |
| `seed_task()` | description: str, priority: str | Add a task to the queue. Returns immediately. |
| `has_pending_tasks()` | -- | Check if there are tasks waiting. |
| `has_higher_priority_task()` | current_priority: TaskPriority | Check if there's a higher priority task waiting. |
| `get_task()` | task_id: str | Get task by ID. |
| `get_last_completed()` | -- | Get the most recently completed task. |
| `update_task()` | task_id: str, status?, current_step?, total_steps?, progress_message?, result?, error? | Update task progress. |
| `cancel_task()` | task_id: str | Cancel a task. |
| `get_status()` | -- | Get queue status. |

### Workspace Tools

**File:** `python/tools/workspace_tools.py`

| Function | Parameters | Description |
|----------|-----------|-------------|
| `set_electron_sender()` | sender | Set the Electron IPC message sender callback. |
| `set_bubble_position_getter()` | getter | Set the bubble position getter callback. |
| `get_bubble_position()` | bubble_db_id: str | Get bubble position by database ID. |
| `capture_idea()` | params | Capture a new idea from voice or text input. |
| `list_ideas()` | params | List all ideas or filter by criteria. |
| `get_idea()` | params | Get details about a specific idea. |
| `score_idea()` | params | Score an idea across multiple dimensions. |
| `create_project()` | params | Create a new project directly (not from an idea). |
| `list_projects()` | params | List all projects or filter by status. |
| `promote_idea()` | params | Promote an idea to a project. |
| `update_project()` | params | Update a project's status or progress. |
| `add_to_canvas()` | params | Add an idea or project to the visual canvas. |
| `connect_nodes()` | params | Connect two nodes on the canvas. |
| `list_canvas()` | params | List items on the canvas. |
| `add_to_bubble()` | params | Add a node to a specific bubble in the Electron multiverse canvas. |
| `add_image_to_bubble()` | params | Add an image to a bubble in the Electron multiverse canvas. |
| `list_bubble_nodes()` | params | List nodes in a specific bubble. |
| `edit_canvas_node()` | params | Edit an existing node on the canvas. |
| `delete_bubble_node()` | params | Delete a node from a bubble's canvas. |
| `register_workspace_tools()` | tools_manager | Register all workspace tools with the ClientToolsManager (with observer loggi... |


## Space-Specific Tools

### Adapted Coding Tools (Coding)

**File:** `python/spaces/coding/tools/adapted_coding_tools.py`

| Function | Parameters | Description |
|----------|-----------|-------------|
| `generate_code()` | title: str?, description: str, tech_stack: str, requirements?, autonomous: bool | Start code generation for a new project using Hybrid Run. |
| `get_generation_status()` | job_id: str, project_name: str | Get the current status of a code generation job. |
| `start_preview()` | job_id: str, project_name: str, resolution: str | Start a VNC preview for a completed project. |
| `stop_preview()` | job_id: str, project_name: str | Stop a running VNC preview. |
| `list_generated_projects()` | status_filter: str, limit: int | List all generated projects. |
| `cancel_generation()` | job_id: str? | Cancel a running code generation job. |

### Coding Tools (Coding)

**File:** `python/spaces/coding/tools/coding_tools.py`

| Function | Parameters | Description |
|----------|-----------|-------------|
| `set_electron_sender()` | sender | Set the Electron IPC message sender callback. |
| `set_coding_engine_runner()` | runner | Set the CodingEngineRunner instance. |
| `generate_code()` | params | Start code generation for a new project using Hybrid Run. |
| `get_generation_status()` | params | Get the current status of a code generation job. |
| `start_preview()` | params | Start a VNC preview for a completed project. |
| `stop_preview()` | params | Stop a running VNC preview. |
| `list_generated_projects()` | params | List all generated projects. |
| `cancel_generation()` | params | Cancel a running code generation job. |
| `exit_project()` | params | Exit the Projects/Coding Space and return to Ideas Space. |
| `register_coding_tools()` | tools_manager | Register all coding tools with the ClientToolsManager. |

### Voice Coding Tools (Coding)

**File:** `python/spaces/coding/tools/voice_coding_tools.py`

| Function | Parameters | Description |
|----------|-----------|-------------|
| `idea_to_project_sync()` | idea_name: str?, tech_stack: str | Synchronous wrapper for idea_to_project. |
| `modify_code_sync()` | instruction: str?, job_id: str | Synchronous wrapper for modify_code. |

### Desktop Tools (Desktop)

**File:** `python/spaces/desktop/tools/desktop_tools.py`

| Function | Parameters | Description |
|----------|-----------|-------------|
| `register_desktop_tools()` | tools_manager | Registriert Desktop Tools im ClientToolsManager. |
| `execute_desktop_task_wrapper()` | params | -- |
| `click_element_wrapper()` | params | -- |
| `type_text_wrapper()` | params | -- |
| `press_key_wrapper()` | params | -- |
| `take_screenshot_wrapper()` | params | -- |
| `scroll_screen_wrapper()` | params | -- |

### Moire Tools (Desktop)

**File:** `python/spaces/desktop/tools/moire_tools.py`

| Function | Parameters | Description |
|----------|-----------|-------------|
| `get_moire_client()` | -- | Get singleton MoireServer client (for test scripts only). |
| `register_moire_tools()` | tools_manager | Register Moire Server tools with the ClientToolsManager. |
| `find_element_by_text()` | text: str, exact: bool | Find element by matching text. |
| `get_all_texts()` | -- | Get all recognized texts. |
| `create_wrapper()` | async_func | -- |
| `wrapper()` | params | -- |
| `run_in_new_loop()` | -- | -- |

### Quickaction Tools (Desktop)

**File:** `python/spaces/desktop/tools/quickaction_tools.py`

| Function | Parameters | Description |
|----------|-----------|-------------|
| `register_quickaction_tools()` | tools_manager | Registriert Quick Action Tools im ClientToolsManager. |
| `open_app_wrapper()` | params | -- |
| `use_app_wrapper()` | params | -- |

### Task Tools (Desktop)

**File:** `python/spaces/desktop/tools/task_tools.py`

| Function | Parameters | Description |
|----------|-----------|-------------|
| `set_electron_sender()` | sender | Setzt die Funktion zum Senden von Nachrichten an Electron. |
| `register_task_tools()` | tools_manager | Registriert Task Tools im ClientToolsManager. |
| `to_dict()` | -- | -- |
| `create_task_wrapper()` | params | -- |
| `update_status_wrapper()` | params | -- |
| `get_list_wrapper()` | params | -- |
| `mark_complete_wrapper()` | params | -- |
| `watch_progress_wrapper()` | params | -- |

### Autogen Research (Ideas)

**File:** `python/spaces/ideas/tools/autogen_research.py`

| Function | Parameters | Description |
|----------|-----------|-------------|
| `get_research_system()` | language: str | Hole oder erstelle die globale Research-System Instanz. |

### Bubble Tools (Ideas)

**File:** `python/spaces/ideas/tools/bubble_tools.py`

| Function | Parameters | Description |
|----------|-----------|-------------|
| `get_current_bubble_db_id()` | -- | Get the current bubble's database UUID. |
| `get_current_bubble()` | -- | Get the current bubble's data as a dictionary. |
| `get_pending_agent_switch()` | -- | Check if an agent switch is pending. |
| `list_bubbles()` | params | List all BUBBLES in the Ideas Space (top-level containers). |
| `find_bubble()` | params | Search for a bubble by name (fuzzy) and automatically enter it. |
| `create_bubble()` | params | Create a new bubble/idea space. |
| `update_bubble()` | params | Update a bubble's title or description. |
| `get_bubble_stats()` | params | Get statistics about a bubble based on its content. |
| `score_bubble()` | params | Calculate and update bubble score based on content richness. |
| `promote_bubble()` | params | Promote a bubble/idea to a project. |
| `delete_bubble()` | params | Delete a bubble/idea space with CASCADE deletion of all content. |
| `delete_all_bubbles_except()` | params? | Delete all bubbles/spaces EXCEPT the specified ones. |
| `enter_bubble()` | params | Enter a bubble and switch to its dedicated agent. |
| `exit_bubble()` | params | Exit current bubble and return to the multiverse agent. |
| `generate_bubble_embeddings()` | params | Generate embeddings for all bubbles in the database. |
| `evaluate_bubble_evolution()` | params | Evaluate how evolved/complete a bubble's ideas are using AI analysis. |
| `register_bubble_tools()` | tools_manager | Register all bubble tools with the tools manager (with observer logging). |
| `load_bubble_nodes()` | bubble_db_id: str | Load nodes and edges for a bubble from the database. |

### Exploration Tools (Ideas)

**File:** `python/spaces/ideas/tools/exploration_tools.py`

| Function | Parameters | Description |
|----------|-----------|-------------|
| `get_exploration_tools()` | -- | Get list of exploration tools for registration. |

### Format Dispatcher (Ideas)

**File:** `python/spaces/ideas/tools/format_dispatcher.py`

| Function | Parameters | Description |
|----------|-----------|-------------|
| `format_as_note()` | source_content, title: str | Convert any format to a well-written plain note using LLM. |
| `format_as_table()` | source_content, title: str, columns: str | Convert any format to table. |
| `format_as_action_list()` | source_content, title: str | Convert any format to action list. |
| `format_as_pros_cons()` | source_content, title: str | Convert any format to pros/cons table. |
| `format_as_hierarchy()` | source_content, title: str | Convert any format to hierarchy/outline. |
| `format_as_specs()` | source_content, title: str | Convert any format to technical specifications. |
| `format_as_kanban()` | source_content, title: str | Convert any format to a Kanban board with columns and cards. |
| `format_as_mindmap()` | source_content, title: str | Convert any format to a mind map with central concept and branches. |
| `format_as_swot()` | source_content, title: str | Convert any format to a SWOT analysis. |
| `format_as_user_story()` | source_content, title: str | Convert any format to user stories. |
| `format_as_flowchart()` | source_content, title: str | Convert any format to a flowchart with steps and decisions. |
| `convert_format()` | params | Convert an idea from one format to another. |
| `get_idea_format()` | params | Get the current format of an idea. |
| `list_available_formats()` | params? | List all available format types. |
| `format_idea_table()` | params | Format idea as table. Wrapper for convert_format with target_format=table. |
| `format_idea_note()` | params | Format idea as simple note. Wrapper for convert_format with target_format=note. |
| `format_idea_action_list()` | params | Format idea as action/task list. Wrapper for convert_format with target_forma... |
| `format_idea_pros_cons()` | params | Format idea as pros and cons list. Wrapper for convert_format with target_for... |
| `format_idea_hierarchy()` | params | Format idea as hierarchy/outline. Wrapper for convert_format with target_form... |
| `format_idea_specs()` | params | Format idea as technical specification. Wrapper for convert_format with targe... |
| `format_idea_kanban()` | params | Format idea as Kanban board. Wrapper for convert_format with target_format=ka... |
| `format_idea_mindmap()` | params | Format idea as mind map. Wrapper for convert_format with target_format=mindmap. |
| `format_idea_swot()` | params | Format idea as SWOT analysis. Wrapper for convert_format with target_format=s... |
| `format_idea_user_story()` | params | Format idea as user stories. Wrapper for convert_format with target_format=us... |
| `format_idea_flowchart()` | params | Format idea as flowchart/process diagram. Wrapper for convert_format with tar... |
| `revert_format()` | params | Revert an idea node to its previous format (undo last format change). |

### Idea Tools (Ideas)

**File:** `python/spaces/ideas/tools/idea_tools.py`

| Function | Parameters | Description |
|----------|-----------|-------------|
| `calculate_spiral_position()` | count: int, existing_positions, center_x: float, center_y: float, min_distance: float | Calculate non-overlapping spiral position for a new node. |
| `list_ideas()` | params | List all NOTES (canvas items) inside the current space/bubble. |
| `count_ideas()` | params? | Count the number of ideas/notes in the current space. |
| `create_idea()` | params | Create a new note in the current bubble/space. |
| `create_idea_batch()` | params | Create multiple ideas/notes at once via LLM generation. |
| `add_image()` | params | Add an image to the current bubble/space. |
| `find_idea()` | params | Search for notes matching a query. |
| `update_idea()` | params | Update an existing idea. |
| `classify_idea()` | params | Classify an idea using AI backend analysis. |
| `connect_ideas()` | params | Connect two ideas with an edge. |
| `disconnect_ideas()` | params | Disconnect/unlink two ideas by removing their edge. |
| `connect_ideas_multi()` | params | Connect one idea to multiple others by index or name. |
| `link_idea_to_root()` | params | Link an idea to the root node of the current bubble. |
| `delete_idea()` | params | Delete an idea. |
| `get_current_space()` | params | Get information about current location. |
| `expand_ideas()` | params | Expand existing ideas using AI to generate related concepts. |
| `move_idea()` | params | Move an idea/note from current space to another space. |
| `auto_link_ideas()` | params | Automatically analyze all ideas in current bubble and create links |
| `analyze_and_suggest_links()` | params | Analyze all ideas in current bubble and suggest meaningful links |
| `explain_idea()` | params | Explain what an idea is about using AI analysis. |
| `format_idea_as_table()` | params | Format an idea's content as a table structure. |
| `register_idea_tools()` | tools_manager | Register all idea tools with the tools manager (with observer logging). |
| `resolve_idea()` | ref: str | -- |
| `resolve_idea()` | ref: str | -- |
| `resolve()` | ref: str | -- |
| `run_in_thread()` | -- | -- |

### Structured Formatting Tools (Ideas)

**File:** `python/spaces/ideas/tools/structured_formatting_tools.py`

| Function | Parameters | Description |
|----------|-----------|-------------|
| `validate_format_schema()` | content_json, format_type: str | Validate structured content against its format schema. |
| `merge_structured_content()` | existing_content, new_content, merge_strategy: str | Merge new structured content with existing content. |
| `update_canvas_node_structured()` | node_id: str, content_json, format_type: str | Update a canvas node with structured content. |
| `update_idea_structured_content()` | idea_id: str, new_content_json, format_type: str, merge: bool | SQL Tool: Update idea with structured content. |
| `query_structured_content()` | idea_id: str | SQL Tool: Query structured content of an idea. |
| `format_idea_as_table()` | idea_name: str?, custom_columns?, format_instruction: str | Format an existing idea's content into a structured table. |
| `register_structured_formatting_tools()` | tools_manager | Register structured formatting tools with the tools manager. |
| `get_supported_formats()` | -- | Get list of supported format types. |
| `format_content_preview()` | content_json, format_type: str, max_length: int | Generate a human-readable preview of structured content. |
| `deep_update()` | target, source | -- |

### Summary Tools (Ideas)

**File:** `python/spaces/ideas/tools/summary_tools.py`

| Function | Parameters | Description |
|----------|-----------|-------------|
| `summarize_idea()` | params | Summarize a specific idea/bubble or a single note using AI via OpenRouter. |
| `list_summaries()` | params | List all ideas that have summaries. |
| `get_summary()` | params | Get the existing summary for an idea. |
| `generate_white_paper()` | params | Generate a structured White Paper document from linked ideas using graph trav... |
| `generate_project_structure()` | params | Convert bubble whitepaper/notes into a structured project with requirements. |
| `generate_feature_docs()` | params | Generate detailed markdown documents for each feature in a bubble. |
| `submit_to_req_orchestrator()` | params | Submit bubble requirements to req-orchestrator for validation. |
| `get_requirement_clarifications()` | params | Get pending clarification questions for requirements. |
| `sync_shuttle_from_orchestrator()` | params | Sync shuttle checkpoint state from req-orchestrator API. |
| `create_stage_shuttles()` | params | Create 4 stage-specific shuttles for a bubble (one per checkpoint). |
| `generate_project_doc()` | params | Generate a cohesive project documentation from all bubble content via LLM. |
| `register_summary_tools()` | tools_manager | Register all summary tools with the tools manager. |
| `get_bubble_position()` | bubble_db_id | -- |

### Collaboration Tools (Minibook)

**File:** `python/spaces/minibook/tools/collaboration_tools.py`

| Function | Parameters | Description |
|----------|-----------|-------------|
| `register_all_space_agents()` | client, project_id: str? | Register all VibeMind spaces as Minibook agents and join the collaboration pr... |
| `detect_needed_spaces()` | task: str | Analyze a task description to determine which spaces are needed. |
| `start_collaboration()` | task: str, goal: str | Start a multi-space collaboration task. |
| `poll_responses()` | -- | Manually poll for collaboration responses. |

### Minibook Client (Minibook)

**File:** `python/spaces/minibook/tools/minibook_client.py`

| Function | Parameters | Description |
|----------|-----------|-------------|
| `get_minibook_client()` | -- | Get or create the global MinibookClient instance. |
| `reset_minibook_client()` | -- | Reset the client (for testing). |
| `register_agent()` | name: str | Register a new agent in Minibook. |
| `list_agents()` | -- | List all registered agents. |
| `create_project()` | name: str, description: str, agent_name: str | Create a new project. |
| `list_projects()` | agent_name: str | List all projects. |
| `join_project()` | project_id: str, agent_name: str, role: str | Join a project with a specific role. |
| `create_post()` | project_id: str, content: str, agent_name: str, post_type: str, title: str | Create a post in a project. |
| `get_posts()` | project_id: str, agent_name: str | Get all posts in a project. |
| `create_comment()` | post_id: str, content: str, agent_name: str | Create a comment on a post. |
| `get_comments()` | post_id: str, agent_name: str | Get all comments on a post. |
| `get_notifications()` | agent_name: str | Get notifications for an agent (mentions, replies). |
| `mark_notification_read()` | notification_id: str, agent_name: str | Mark a notification as read. |
| `get_status()` | -- | Check if Minibook is reachable. |
| `project_id()` | -- | Current collaboration project ID. |
| `project_id()` | value: str | -- |
| `has_agent()` | name: str | Check if an agent is registered locally. |

### Minibook Tools (Minibook)

**File:** `python/spaces/minibook/tools/minibook_tools.py`

| Function | Parameters | Description |
|----------|-----------|-------------|
| `get_minibook_status()` | -- | Check Minibook connection status. |
| `start_discussion()` | message: str, topic: str | Start a discussion in Minibook. |
| `get_discussion_results()` | discussion_id: str | Get results of a Minibook discussion. |
| `list_projects()` | -- | List all Minibook projects. |

### N8N Api Client (N8N)

**File:** `python/spaces/n8n/tools/n8n_api_client.py`

| Function | Parameters | Description |
|----------|-----------|-------------|
| `get_n8n_client()` | -- | Get or create the N8nApiClient singleton. |
| `health_check()` | -- | Check if n8n instance is reachable. |
| `list_workflows()` | -- | List all workflows. |
| `get_workflow()` | workflow_id: str | Get a single workflow by ID. |
| `create_workflow()` | workflow_json | Create a new workflow from JSON definition. |
| `update_workflow()` | workflow_id: str, workflow_json | Update an existing workflow. |
| `delete_workflow()` | workflow_id: str | Delete a workflow. |
| `activate_workflow()` | workflow_id: str | Activate a workflow. |
| `deactivate_workflow()` | workflow_id: str | Deactivate a workflow. |
| `execute_workflow()` | workflow_id: str, data: Dict? | Execute a workflow manually with optional input data. |
| `get_executions()` | workflow_id?, limit: int | Get recent workflow executions. |

### N8N Workflow Tools (N8N)

**File:** `python/spaces/n8n/tools/n8n_workflow_tools.py`

| Function | Parameters | Description |
|----------|-----------|-------------|
| `generate_workflow()` | description: str | Generate an n8n workflow from a natural language description and push it to n8n. |
| `list_workflows()` | -- | List all workflows in the n8n instance. |
| `get_n8n_status()` | -- | Check if the n8n instance is online and reachable. |
| `activate_workflow()` | workflow_id: str?, name: str? | Activate a workflow by ID or name. |
| `deactivate_workflow()` | workflow_id: str?, name: str? | Deactivate a workflow by ID or name. |
| `delete_workflow()` | workflow_id: str?, name: str? | Delete a workflow by ID or name. |
| `execute_workflow()` | workflow_id: str?, name: str?, data: Dict? | Execute a workflow manually. |
| `describe_workflow()` | workflow_id: str?, name: str? | Get detailed information about a workflow. |

### Workflow Generator (N8N)

**File:** `python/spaces/n8n/tools/workflow_generator.py`

| Function | Parameters | Description |
|----------|-----------|-------------|
| `plan_workflow()` | description: str | Phase 1: Use LLM to create a structured workflow plan from NL description. |
| `assemble_workflow()` | plan | Phase 2: Assemble valid n8n workflow JSON from a structured plan. |
| `generate_workflow_json()` | description: str | Generate complete n8n workflow JSON from natural language description. |
| `generate_workflow_json_society()` | description: str | Generate n8n workflow using the Society of Mind multi-agent system. |

### Research Tools (Research)

**File:** `python/spaces/research/tools/research_tools.py`

| Function | Parameters | Description |
|----------|-----------|-------------|
| `web_research()` | query: str | Research a topic on the web via ZeroClaw. |
| `scrape_url()` | url: str | Scrape a URL and extract content via ZeroClaw. |
| `summarize_url()` | url: str | Summarize the content of a URL via ZeroClaw. |
| `research_to_idea()` | query: str, title: str? | Research a topic and save results as a new Idea in the current space. |
| `research_to_rowboat()` | query: str | Research a topic and push results into Rowboat Knowledge Graph. |

### Docker Tools (Rowboat)

**File:** `python/spaces/rowboat/tools/docker_tools.py`

| Function | Parameters | Description |
|----------|-----------|-------------|
| `start_docker()` | -- | Start the Rowboat Docker stack. |
| `stop_docker()` | -- | Stop the Rowboat Docker stack. |
| `restart_docker()` | -- | Restart the Rowboat Docker stack. |
| `docker_status()` | -- | Check the status of the Rowboat Docker containers. |

### Roarboot Client (Rowboat)

**File:** `python/spaces/rowboat/tools/roarboot_client.py`

| Function | Parameters | Description |
|----------|-----------|-------------|
| `get_roarboot_client()` | -- | Get or create RoarbootClient singleton. |
| `project_id()` | -- | Expose project ID for URL construction. |
| `chat()` | message: str, context: str | Send a chat message to Rowboat and get a response. |
| `search_knowledge()` | query: str | Search the Rowboat knowledge graph. |
| `query_knowledge()` | subject: str, question: str? | Query knowledge about a subject (person, project, etc.). |
| `draft_email()` | recipient: str, topic: str, context: str | Draft an email using Rowboat's knowledge context. |
| `generate_meeting_brief()` | meeting: str, participants: str | Generate a meeting brief with relevant context. |
| `generate_deck()` | topic: str, context: str | Generate a presentation deck outline. |
| `process_voice_note()` | text: str | Process a voice note and update the knowledge graph. |
| `get_status()` | -- | Check Rowboat connection status. |
| `reset_conversation()` | context: str? | Reset conversation context. |
| `list_conversations()` | -- | List active conversation contexts and their IDs. |

### Roarboot Tools (Rowboat)

**File:** `python/spaces/rowboat/tools/roarboot_tools.py`

| Function | Parameters | Description |
|----------|-----------|-------------|
| `search_knowledge()` | query: str | Search the Rowboat knowledge graph. |
| `query_knowledge()` | subject: str, question: str? | Query knowledge about a person, project, or topic. |
| `draft_email()` | recipient: str, topic: str, context: str | Draft an email using Rowboat's knowledge context. |
| `generate_meeting_brief()` | meeting: str, participants: str | Generate a meeting brief with relevant context. |
| `generate_deck()` | topic: str, context: str | Generate a presentation deck outline. |
| `process_voice_note()` | text: str | Process a voice note and update the knowledge graph. |
| `get_status()` | -- | Check Rowboat connection status. |
| `open_webview()` | context: str | Signal Electron to show the Rowboat WebView. |
| `reset_conversation()` | context: str? | Reset Rowboat conversation context. |

### Schedule Tools (Schedule)

**File:** `python/spaces/schedule/tools/schedule_tools.py`

| Function | Parameters | Description |
|----------|-----------|-------------|
| `set_electron_sender()` | sender | Set the Electron IPC message sender callback. |
| `set_schedule_worker()` | worker | Set the ScheduleWorker reference so tools can add/remove jobs live. |
| `create_scheduled_task()` | user_text: str, title: str | Parse a German time expression from user_text, persist to DB, |
| `list_scheduled_tasks()` | status: str | List scheduled tasks, optionally filtered by status. |
| `cancel_scheduled_task()` | task_id: str, title: str | Cancel a scheduled task by ID or fuzzy title match. |
| `modify_scheduled_task()` | task_id: str, title: str, new_time: str, new_action: str | Modify a scheduled task's time and/or action. |
| `get_schedule_status()` | -- | Get a summary of all scheduled tasks. |
| `snooze_scheduled_task()` | task_id: str, title: str, minutes: int, user_text: str | Snooze a task — create a new one-shot DateTrigger for now + X minutes. |

